"""
Serviço de limpeza segura do sistema operacional.
Todas as ações são rigorosamente seguras e nunca afetam dados pessoais do usuário.
"""

import os
import glob
import re
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional, Tuple
from .utils import (
    format_size,
    get_dir_size,
    run_command_safe,
    run_elevated_command,
    check_command_available
)
from .i18n import t


@dataclass
class CleanupTarget:
    id: str
    icon_name: str
    requires_root: bool
    size_bytes: int = 0
    selected: bool = True
    available: bool = True
    details: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return t(f"target.{self.id}.name")

    @property
    def description(self) -> str:
        return t(f"target.{self.id}.desc")

    @property
    def safety_info(self) -> str:
        return t(f"target.{self.id}.safety")

    @property
    def size_formatted(self) -> str:
        return format_size(self.size_bytes)


class CleanerService:
    def __init__(self):
        self.home_dir = os.path.expanduser("~")
        self.targets: Dict[str, CleanupTarget] = {}
        self._init_targets()

    def _init_targets(self):
        """Inicializa os alvos de limpeza disponíveis no sistema."""
        self.targets = {
            "apt_cache": CleanupTarget(
                id="apt_cache",
                icon_name="package-x-generic",
                requires_root=True,
                available=check_command_available("apt-get")
            ),
            "apt_autoremove": CleanupTarget(
                id="apt_autoremove",
                icon_name="edit-delete-symbolic",
                requires_root=True,
                available=check_command_available("apt-get")
            ),
            "journal_logs": CleanupTarget(
                id="journal_logs",
                icon_name="text-x-generic",
                requires_root=True,
                available=check_command_available("journalctl")
            ),
            "thumbnails": CleanupTarget(
                id="thumbnails",
                icon_name="image-x-generic",
                requires_root=False,
                available=True
            ),
            "crash_reports": CleanupTarget(
                id="crash_reports",
                icon_name="dialog-warning-symbolic",
                requires_root=True,
                available=os.path.exists("/var/crash")
            ),
            "trash": CleanupTarget(
                id="trash",
                icon_name="user-trash-symbolic",
                requires_root=False,
                available=True
            ),
            "flatpak_unused": CleanupTarget(
                id="flatpak_unused",
                icon_name="application-x-addon-symbolic",
                requires_root=False,
                available=check_command_available("flatpak")
            ),
            "user_caches": CleanupTarget(
                id="user_caches",
                icon_name="system-run-symbolic",
                requires_root=False,
                available=True
            )
        }

    def scan_all(self, progress_callback: Optional[Callable[[str, float], None]] = None) -> List[CleanupTarget]:
        """Varre todos os alvos e calcula os tamanhos passíveis de liberação."""
        keys = list(self.targets.keys())
        total = len(keys)

        for idx, key in enumerate(keys):
            target = self.targets[key]
            if progress_callback:
                progress_callback(t("status_analyzing", name=target.name), (idx / total))

            if not target.available:
                target.size_bytes = 0
                continue

            try:
                method = getattr(self, f"_scan_{key}", None)
                if method:
                    size, details = method()
                    target.size_bytes = size
                    target.details = details
            except Exception as e:
                target.size_bytes = 0
                target.details = [str(e)]

        if progress_callback:
            progress_callback(t("status_analysis_done"), 1.0)

        return list(self.targets.values())

    # --- Métodos de Varredura Específicos ---

    def _scan_apt_cache(self) -> Tuple[int, List[str]]:
        size = 0
        details = []
        archives_dir = "/var/cache/apt/archives"
        if os.path.exists(archives_dir):
            for f in glob.glob(os.path.join(archives_dir, "*.deb")):
                try:
                    s = os.path.getsize(f)
                    size += s
                    details.append(os.path.basename(f))
                except OSError:
                    pass
        return size, details

    def _scan_apt_autoremove(self) -> Tuple[int, List[str]]:
        ok, stdout, _ = run_command_safe(["apt-get", "--dry-run", "autoremove"], timeout=10)
        if not ok:
            return 0, []

        size = 0
        details = []
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("Remv "):
                pkg = line.split()[1] if len(line.split()) > 1 else line
                details.append(pkg)
            m = re.search(r"(\d+[\.,]?\d*)\s*(k|m|g|kb|mb|gb)\s*(b|bytes)?.*(?:liberad|freed)", line, re.IGNORECASE)
            if m:
                val = float(m.group(1).replace(",", "."))
                unit = m.group(2).lower()
                if "g" in unit:
                    size = int(val * 1024 * 1024 * 1024)
                elif "m" in unit:
                    size = int(val * 1024 * 1024)
                elif "k" in unit:
                    size = int(val * 1024)

        if not size and details:
            size = len(details) * 5 * 1024 * 1024

        return size, details

    def _scan_journal_logs(self) -> Tuple[int, List[str]]:
        ok, stdout, _ = run_command_safe(["journalctl", "--disk-usage"], timeout=5)
        if not ok:
            return 0, []

        m = re.search(r"(\d+[\.,]?\d*)\s*([KMG])", stdout)
        if m:
            val = float(m.group(1).replace(",", "."))
            unit = m.group(2).upper()
            total_journal = 0
            if unit == "G":
                total_journal = int(val * 1024 * 1024 * 1024)
            elif unit == "M":
                total_journal = int(val * 1024 * 1024)
            elif unit == "K":
                total_journal = int(val * 1024)

            retain_limit = 50 * 1024 * 1024
            reclaimable = max(0, total_journal - retain_limit)
            return reclaimable, [format_size(total_journal)]
        return 0, []

    def _scan_thumbnails(self) -> Tuple[int, List[str]]:
        thumb_path = os.path.join(self.home_dir, ".cache", "thumbnails")
        size = get_dir_size(thumb_path)
        count = 0
        if os.path.exists(thumb_path):
            for _, _, files in os.walk(thumb_path):
                count += len(files)
        return size, [str(count)]

    def _scan_crash_reports(self) -> Tuple[int, List[str]]:
        crash_path = "/var/crash"
        size = 0
        details = []
        if os.path.exists(crash_path):
            for f in glob.glob(os.path.join(crash_path, "*")):
                try:
                    s = os.path.getsize(f)
                    size += s
                    details.append(os.path.basename(f))
                except OSError:
                    pass
        return size, details

    def _scan_trash(self) -> Tuple[int, List[str]]:
        trash_path = os.path.join(self.home_dir, ".local", "share", "Trash")
        size = get_dir_size(trash_path)
        files_count = 0
        files_dir = os.path.join(trash_path, "files")
        if os.path.exists(files_dir):
            files_count = len(os.listdir(files_dir))
        return size, [str(files_count)]

    def _scan_flatpak_unused(self) -> Tuple[int, List[str]]:
        ok, stdout, _ = run_command_safe(["flatpak", "list", "--runtime"], timeout=5)
        if ok and stdout.strip():
            return 0, []
        return 0, []

    def _scan_user_caches(self) -> Tuple[int, List[str]]:
        safe_dirs = [
            os.path.join(self.home_dir, ".cache", "pip"),
            os.path.join(self.home_dir, ".cache", "yarn"),
            os.path.join(self.home_dir, ".cache", "npm"),
            os.path.join(self.home_dir, ".cache", "mesa_shader_cache"),
            os.path.join(self.home_dir, ".cache", "fontconfig"),
        ]
        total_size = 0
        found = []
        for d in safe_dirs:
            if os.path.exists(d):
                s = get_dir_size(d)
                if s > 0:
                    total_size += s
                    found.append(f"{os.path.basename(d)}: {format_size(s)}")
        return total_size, found

    # --- Métodos de Execução da Limpeza ---

    def clean_selected(
        self,
        selected_ids: List[str],
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[int, List[str]]:
        """
        Executa a limpeza para os alvos selecionados.
        Retorna (total_bytes_liberados, mensagens_de_status).
        """
        total_freed = 0
        messages = []

        root_targets = []
        user_targets = []

        for tid in selected_ids:
            if tid in self.targets:
                target = self.targets[tid]
                if target.requires_root:
                    root_targets.append(target)
                else:
                    user_targets.append(target)

        for target in user_targets:
            if status_callback:
                status_callback(t("status_cleaning_user", name=target.name))
            
            freed = self._clean_user_target(target.id)
            total_freed += freed
            messages.append(f"✓ {target.name}: {format_size(freed)}")

        if root_targets:
            for target in root_targets:
                if status_callback:
                    status_callback(t("status_cleaning_root", name=target.name))
                freed, msg = self._clean_root_target(target.id, target.size_bytes)
                total_freed += freed
                messages.append(msg)

        if status_callback:
            status_callback(t("status_clean_done"))

        return total_freed, messages

    def _clean_user_target(self, target_id: str) -> int:
        initial_size = self.targets[target_id].size_bytes
        
        if target_id == "thumbnails":
            thumb_path = os.path.join(self.home_dir, ".cache", "thumbnails")
            if os.path.exists(thumb_path):
                for item in os.listdir(thumb_path):
                    ip = os.path.join(thumb_path, item)
                    try:
                        if os.path.isdir(ip):
                            shutil.rmtree(ip, ignore_errors=True)
                        else:
                            os.remove(ip)
                    except OSError:
                        pass
            return initial_size

        elif target_id == "trash":
            trash_path = os.path.join(self.home_dir, ".local", "share", "Trash")
            files_dir = os.path.join(trash_path, "files")
            info_dir = os.path.join(trash_path, "info")
            for d in [files_dir, info_dir]:
                if os.path.exists(d):
                    for item in os.listdir(d):
                        ip = os.path.join(d, item)
                        try:
                            if os.path.isdir(ip):
                                shutil.rmtree(ip, ignore_errors=True)
                            else:
                                os.remove(ip)
                        except OSError:
                            pass
            return initial_size

        elif target_id == "flatpak_unused":
            run_command_safe(["flatpak", "uninstall", "--unused", "-y"], timeout=60)
            return initial_size

        elif target_id == "user_caches":
            safe_dirs = [
                os.path.join(self.home_dir, ".cache", "pip"),
                os.path.join(self.home_dir, ".cache", "yarn"),
                os.path.join(self.home_dir, ".cache", "npm"),
                os.path.join(self.home_dir, ".cache", "mesa_shader_cache"),
                os.path.join(self.home_dir, ".cache", "fontconfig"),
            ]
            for d in safe_dirs:
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
            return initial_size

        return 0

    def _clean_root_target(self, target_id: str, estimated_size: int) -> Tuple[int, str]:
        target_name = self.targets[target_id].name if target_id in self.targets else target_id
        if target_id == "apt_cache":
            ok, out, err = run_elevated_command(["apt-get", "clean"])
            if ok:
                return estimated_size, f"✓ {target_name}: {format_size(estimated_size)}"
            return 0, f"⚠ {target_name}: {err or out}"

        elif target_id == "apt_autoremove":
            ok, out, err = run_elevated_command(["apt-get", "autoremove", "-y", "--purge"])
            if ok:
                return estimated_size, f"✓ {target_name}: {format_size(estimated_size)}"
            return 0, f"⚠ {target_name}: {err or out}"

        elif target_id == "journal_logs":
            ok, out, err = run_elevated_command(["journalctl", "--vacuum-time=3d", "--vacuum-size=100M"])
            if ok:
                return estimated_size, f"✓ {target_name}: {format_size(estimated_size)}"
            return 0, f"⚠ {target_name}: {err or out}"

        elif target_id == "crash_reports":
            ok, out, err = run_elevated_command(["rm", "-rf", "/var/crash/*"])
            if ok:
                return estimated_size, f"✓ {target_name}: {format_size(estimated_size)}"
            return 0, f"⚠ {target_name}: {err or out}"

        return 0, f"⚠ {target_id}"
