"""
Serviço de detecção e classificação dos aplicativos mais pesados do sistema.
Analisa pacotes APT/deb, Flatpaks, Snaps e atalhos de aplicativos locais.
"""

import os
import glob
import configparser
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .utils import format_size, get_dir_size, run_command_safe


@dataclass
class AppInfo:
    rank: int
    name: str
    size_bytes: int
    icon: str
    source: str
    pkg_id: str
    percent_of_max: float = 1.0

    @property
    def size_formatted(self) -> str:
        return format_size(self.size_bytes)


class AppsService:
    @classmethod
    def get_top_heaviest_apps(cls, limit: int = 10) -> List[AppInfo]:
        """
        Retorna a lista dos 'limit' (padrão 10) aplicativos instalados
        mais pesados do sistema, com ícone, nome e tamanho ocupado.
        """
        apps_map: Dict[str, Dict[str, Any]] = {}

        # 1. Varre pacotes DPKG e mapeia para .desktop
        cls._scan_dpkg_apps(apps_map)

        # 2. Varre aplicativos Flatpak
        cls._scan_flatpak_apps(apps_map)

        # 3. Varre aplicativos Snap (se presentes)
        cls._scan_snap_apps(apps_map)

        # 4. Converte para lista e ordena
        app_list = list(apps_map.values())
        app_list.sort(key=lambda x: x["size_bytes"], reverse=True)

        # Pega os top 'limit'
        top_apps_data = app_list[:limit]
        
        max_size = top_apps_data[0]["size_bytes"] if top_apps_data else 1
        if max_size <= 0:
            max_size = 1

        result = []
        for rank, item in enumerate(top_apps_data, 1):
            percent = (item["size_bytes"] / max_size) if max_size > 0 else 0.0
            result.append(
                AppInfo(
                    rank=rank,
                    name=item["name"],
                    size_bytes=item["size_bytes"],
                    icon=item.get("icon") or "application-x-executable",
                    source=item.get("source", "Sistema"),
                    pkg_id=item.get("pkg_id", ""),
                    percent_of_max=min(1.0, max(0.02, percent))
                )
            )

        return result

    @classmethod
    def _scan_dpkg_apps(cls, apps_map: Dict[str, Dict[str, Any]]):
        """Mapeia pacotes DPKG com interface gráfica instalados no sistema."""
        dpkg_sizes: Dict[str, int] = {}
        try:
            out = subprocess.check_output(
                ["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\n"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            for line in out.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) == 2 and parts[1].isdigit():
                    # dpkg reporta tamanho em KB
                    dpkg_sizes[parts[0]] = int(parts[1]) * 1024
        except Exception:
            return

        # Mapeia /usr/share/applications/*.desktop para seus pacotes
        desktop_to_pkg: Dict[str, str] = {}
        info_dir = "/var/lib/dpkg/info"
        if os.path.exists(info_dir):
            for f in glob.glob(f"{info_dir}/*.list"):
                pkg_base = os.path.basename(f)[:-5].split(":")[0]
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                        for line in fp:
                            line = line.strip()
                            if line.endswith(".desktop") and line.startswith("/usr/share/applications/"):
                                desktop_to_pkg[line] = pkg_base
                except Exception:
                    pass

        # Lê os arquivos .desktop
        for df in glob.glob("/usr/share/applications/*.desktop"):
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read(df, encoding="utf-8")
                if "Desktop Entry" in cp:
                    sec = cp["Desktop Entry"]
                    if sec.get("NoDisplay", "false").lower() == "true":
                        continue
                    if sec.get("Type", "Application") != "Application":
                        continue
                    
                    name = sec.get("Name", "").strip()
                    icon = sec.get("Icon", "").strip()
                    pkg = desktop_to_pkg.get(df, "")
                    size = dpkg_sizes.get(pkg, 0) if pkg else 0

                    if name and size > 0:
                        # Se já existir uma entrada com o mesmo nome, mantém a de maior tamanho
                        key = f"deb:{name.lower()}"
                        if key not in apps_map or apps_map[key]["size_bytes"] < size:
                            apps_map[key] = {
                                "name": name,
                                "icon": icon or "application-x-executable",
                                "size_bytes": size,
                                "source": "APT / DEB",
                                "pkg_id": pkg
                            }
            except Exception:
                pass

    @classmethod
    def _scan_flatpak_apps(cls, apps_map: Dict[str, Dict[str, Any]]):
        """Mapeia aplicativos Flatpak instalados e seus tamanhos reais."""
        bases = [
            "/var/lib/flatpak/app",
            os.path.expanduser("~/.local/share/flatpak/app")
        ]

        for base in bases:
            if not os.path.exists(base):
                continue

            for app_id in os.listdir(base):
                app_path = os.path.join(base, app_id)
                if not os.path.isdir(app_path):
                    continue

                size = get_dir_size(app_path)
                if size <= 0:
                    continue

                name = app_id
                icon = app_id

                # Tenta ler o desktop file exportado pelo flatpak
                desktop_candidates = [
                    f"/var/lib/flatpak/exports/share/applications/{app_id}.desktop",
                    os.path.expanduser(f"~/.local/share/flatpak/exports/share/applications/{app_id}.desktop")
                ]

                for df in desktop_candidates:
                    if os.path.exists(df):
                        cp = configparser.ConfigParser(interpolation=None)
                        try:
                            cp.read(df, encoding="utf-8")
                            if "Desktop Entry" in cp:
                                sec = cp["Desktop Entry"]
                                name = sec.get("Name", name)
                                icon = sec.get("Icon", icon)
                                break
                        except Exception:
                            pass

                key = f"flatpak:{name.lower()}"
                apps_map[key] = {
                    "name": name,
                    "icon": icon,
                    "size_bytes": size,
                    "source": "Flatpak",
                    "pkg_id": app_id
                }

    @classmethod
    def _scan_snap_apps(cls, apps_map: Dict[str, Dict[str, Any]]):
        """Mapeia aplicativos Snap instalados (com timeout para evitar bloqueios)."""
        snap_mount_dir = "/var/lib/snapd/snaps"
        if not os.path.exists(snap_mount_dir):
            return

        try:
            # Lista arquivos .snap instalados
            for sf in glob.glob(os.path.join(snap_mount_dir, "*.snap")):
                try:
                    sname = os.path.basename(sf)
                    # ex: code_123.snap
                    base_name = sname.split("_")[0]
                    # Ignora snaps de sistema padrão como core, bare, gtk-common-themes
                    if base_name in ["core", "core18", "core20", "core22", "core24", "bare", "gtk-common-themes", "gnome-3-38-2004", "snapd"]:
                        continue

                    size = os.path.getsize(sf)
                    name = base_name.capitalize()
                    icon = base_name

                    # Procura desktop file do snap
                    df = f"/var/lib/snapd/desktop/applications/{base_name}_{base_name}.desktop"
                    if os.path.exists(df):
                        cp = configparser.ConfigParser(interpolation=None)
                        try:
                            cp.read(df, encoding="utf-8")
                            if "Desktop Entry" in cp:
                                sec = cp["Desktop Entry"]
                                name = sec.get("Name", name)
                                icon = sec.get("Icon", icon)
                        except Exception:
                            pass

                    key = f"snap:{name.lower()}"
                    if key not in apps_map or apps_map[key]["size_bytes"] < size:
                        apps_map[key] = {
                            "name": name,
                            "icon": icon,
                            "size_bytes": size,
                            "source": "Snap",
                            "pkg_id": base_name
                        }
                except Exception:
                    pass
        except Exception:
            pass
