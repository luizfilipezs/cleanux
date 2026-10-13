"""
Serviço abrangente de detecção e classificação de todos os aplicativos instalados no sistema.
Descobre aplicativos de múltiplas fontes:
- Pacotes APT / DEB (com agregação de pacotes-fonte / dados / core)
- Aplicativos em /opt e /usr/local (tarballs, instaladores manuais, IDEs como Android Studio, Antigravity, etc.)
- Aplicativos Flatpak (sistema e usuário)
- Aplicativos Snap (todas as revisões instaladas)
- AppImages (em ~/Applications, ~/.local/bin, ~/Downloads, ~/Desktop, /opt)
- JetBrains Toolbox e instalações locais em ~/.local/share
- Jogos da Steam (steamapps)
- Ferramentas e aplicações manuais de linha de comando / servidor (Docker, Mongosh, QEMU, Git, etc.)
"""

import os
import re
import glob
import shlex
import shutil
import configparser
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
from .utils import format_size, get_dir_size
from .i18n import i18n


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


# Pacotes base do sistema operacional que não devem ser listados como apps avulsos de CLI
SYSTEM_PLUMBING_PACKAGES = {
    "systemd", " systemd-sysv", "udev", "libc6", "locales", "iso-codes", "poppler-data",
    "bash", "coreutils", "util-linux", "mount", "login", "passwd", "sudo", "apt", "dpkg",
    "initramfs-tools", "initramfs-tools-core", "e2fsprogs", "parted", "fdisk", "gdisk",
    "kmod", "iproute2", "iptables", "nftables", "ufw", "cron", "logrotate", "rsyslog",
    "dbus", "polkitd", "flatpak", "snapd", "network-manager", "wpasupplicant",
    "xserver-xorg-core", "xwayland", "wayland-protocols", "gnome-shell", "gnome-session",
    "gdm3", "plymouth", "pulseaudio", "pipewire", "alsa-utils", "bluez", "cups",
    "cups-daemon", "avahi-daemon", "openssh-client", "openssh-server", "ca-certificates",
    "openssl", "curl", "wget", "tar", "gzip", "bzip2", "xz-utils", "unzip", "zip",
    "grep", "sed", "gawk", "mawk", "findutils", "procps", "psmisc", "less", "nano",
    "tzdata", "keyboard-configuration", "console-setup", "apparmor", "fwupd",
    "packagekit", "unattended-upgrades", "software-properties-common", "mokutil",
    "shim-signed", "grub-common", "grub-pc", "grub-efi-amd64", "grub-efi-amd64-bin",
    "grub-efi-amd64-signed", "efibootmgr", "os-prober", "wireless-regdb", "bolt",
    "switcheroo-control", "power-profiles-daemon", "thermald", "irqbalance",
    "xdg-desktop-portal", "xdg-desktop-portal-gtk", "xdg-desktop-portal-gnome",
    "xdg-utils", "shared-mime-info", "desktop-file-utils", "hicolor-icon-theme",
    "adwaita-icon-theme", "humanity-icon-theme", "ubuntu-mono", "zorin-os-desktop",
    "zorin-os-minimal", "zorin-os-standard", "zorin-appearance", "zorin-connect",
}

SNAP_EXCLUDED_BASES = {
    "core", "core18", "core20", "core22", "core24", "bare", "snapd",
    "gtk-common-themes", "gtk2-common-themes",
}

USER_DATA_FOLDERS = {
    "desktop", "área de trabalho", "documents", "documentos", "downloads",
    "music", "músicas", "pictures", "imagens", "videos", "vídeos",
    "public", "público", "templates", "modelos", "dev", "projects",
    "workspace", "repos", "src", "snap",
}


class AppsService:
    @classmethod
    def get_installed_apps(cls, limit: Optional[int] = None) -> List[AppInfo]:
        """
        Retorna a lista de todos os aplicativos instalados no sistema (ou até 'limit'),
        ordenados do mais pesado para o mais leve.
        """
        apps_map: Dict[str, Dict[str, Any]] = {}
        claimed_opt_dirs: Set[str] = set()
        claimed_files: Set[str] = set()

        # 1. Varre pacotes DPKG e todos os atalhos .desktop do sistema e do usuário
        cls._scan_dpkg_and_desktop_apps(apps_map, claimed_opt_dirs, claimed_files)

        # 2. Varre diretórios diretamente em /opt que não tenham sido reclamados
        cls._scan_opt_directories(apps_map, claimed_opt_dirs)

        # 3. Varre aplicativos Flatpak
        cls._scan_flatpak_apps(apps_map)

        # 4. Varre aplicativos Snap
        cls._scan_snap_apps(apps_map)

        # 5. Varre arquivos AppImage avulsos
        cls._scan_appimages(apps_map, claimed_files)

        # 6. Varre jogos instalados na Steam
        cls._scan_steam_apps(apps_map)

        # 7. Converte para lista e ordena por tamanho decrescente
        app_list = [a for a in apps_map.values() if a.get("size_bytes", 0) > 0]
        app_list.sort(key=lambda x: x["size_bytes"], reverse=True)

        if limit is not None and limit > 0:
            app_list = app_list[:limit]

        max_size = app_list[0]["size_bytes"] if app_list else 1
        if max_size <= 0:
            max_size = 1

        result = []
        for rank, item in enumerate(app_list, 1):
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
    def get_top_heaviest_apps(cls, limit: Optional[int] = None) -> List[AppInfo]:
        """Alias de compatibilidade que retorna todos os apps quando limit=None."""
        return cls.get_installed_apps(limit=limit)

    # =========================================================================
    # 1. DPKG + DESKTOP FILES + STANDALONE (/opt, /usr/local, ~/.local)
    # =========================================================================
    @classmethod
    def _scan_dpkg_and_desktop_apps(
        cls,
        apps_map: Dict[str, Dict[str, Any]],
        claimed_opt_dirs: Set[str],
        claimed_files: Set[str]
    ):
        pkg_size: Dict[str, int] = {}
        pkg_source: Dict[str, str] = {}
        pkg_section: Dict[str, str] = {}
        pkg_priority: Dict[str, str] = {}
        pkg_summary: Dict[str, str] = {}
        source_to_pkgs: Dict[str, Set[str]] = {}

        try:
            out = subprocess.check_output(
                [
                    "dpkg-query", "-W",
                    "-f=${db:Status-Abbrev}\t${Package}\t${Source}\t${Installed-Size}\t${Section}\t${Priority}\t${binary:Summary}\n"
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=8
            )
            for line in out.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 4 and parts[0].startswith("ii") and parts[3].isdigit():
                    pkg = parts[1].split(":")[0]
                    src_raw = parts[2].strip()
                    src = src_raw.split()[0] if src_raw else pkg
                    sz = int(parts[3]) * 1024

                    pkg_size[pkg] = pkg_size.get(pkg, 0) + sz
                    pkg_source[pkg] = src
                    pkg_section[pkg] = parts[4] if len(parts) > 4 else ""
                    pkg_priority[pkg] = parts[5] if len(parts) > 5 else ""
                    pkg_summary[pkg] = parts[6] if len(parts) > 6 else ""
                    source_to_pkgs.setdefault(src, set()).add(pkg)
        except Exception:
            pass

        # Mapeia arquivos .desktop, binários e pastas /opt a partir de /var/lib/dpkg/info/*.list
        desktop_to_pkg: Dict[str, str] = {}
        exec_to_pkg: Dict[str, str] = {}
        pkg_to_bins: Dict[str, List[str]] = {}
        pkg_to_opt_dirs: Dict[str, Set[str]] = {}

        info_dir = "/var/lib/dpkg/info"
        if os.path.exists(info_dir):
            for f in glob.glob(f"{info_dir}/*.list"):
                pkg_base = os.path.basename(f)[:-5].split(":")[0]
                if pkg_base not in pkg_size:
                    continue
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                        for line in fp:
                            line = line.strip()
                            if not line:
                                continue
                            if line.endswith(".desktop"):
                                desktop_to_pkg[line] = pkg_base
                            elif line.startswith("/usr/bin/") or line.startswith("/usr/games/") or line.startswith("/bin/"):
                                exec_to_pkg[line] = pkg_base
                                pkg_to_bins.setdefault(pkg_base, []).append(os.path.basename(line))
                            elif line.startswith("/opt/"):
                                segs = line.split("/")
                                if len(segs) >= 3 and segs[2]:
                                    opt_sub = f"/opt/{segs[2]}"
                                    claimed_opt_dirs.add(opt_sub)
                                    pkg_to_opt_dirs.setdefault(pkg_base, set()).add(opt_sub)
                                if len(segs) >= 4:
                                    exec_to_pkg[line] = pkg_base
                except Exception:
                    pass

        # Coleta todos os arquivos .desktop em diretórios do sistema e do usuário
        desktop_files = cls._collect_all_desktop_files()

        # Primeira passagem: identifica quais pacotes dpkg possuem .desktop visível
        parsed_desktops: List[Dict[str, Any]] = []
        visible_desktop_pkgs: Set[str] = set()

        for df in desktop_files:
            entry = cls._parse_desktop_file(df)
            if not entry:
                continue

            # Ignora se for atalho exportado por Flatpak ou Snap (tratados por seus scanners próprios)
            if entry["is_flatpak"] or entry["is_snap"]:
                continue

            pkg = desktop_to_pkg.get(df) or desktop_to_pkg.get(os.path.realpath(df))
            if not pkg and entry["exec_bin"]:
                exec_bin = entry["exec_bin"]
                pkg = exec_to_pkg.get(exec_bin) or exec_to_pkg.get(os.path.realpath(exec_bin))
                if not pkg and not os.path.isabs(exec_bin):
                    which_bin = shutil.which(exec_bin)
                    if which_bin:
                        pkg = exec_to_pkg.get(which_bin) or exec_to_pkg.get(os.path.realpath(which_bin))

            entry["pkg"] = pkg or ""
            if pkg:
                visible_desktop_pkgs.add(pkg)
            parsed_desktops.append(entry)

        # Calcula tamanho agregado por pacote visível (incluindo pacotes -core, -common, -data do mesmo Source)
        agg_pkg_size: Dict[str, int] = {}
        consumed_sources: Set[str] = set()

        for src, pkgs in source_to_pkgs.items():
            vis = [p for p in pkgs if p in visible_desktop_pkgs]
            if not vis:
                continue
            consumed_sources.add(src)
            if len(vis) == 1:
                agg_pkg_size[vis[0]] = sum(pkg_size.get(p, 0) for p in pkgs)
            else:
                primary = vis[0]
                for p in vis:
                    if p == src or p == f"{src}-common" or p == f"{src}-core":
                        primary = p
                        break
                for p in vis:
                    agg_pkg_size[p] = pkg_size.get(p, 0)
                for p in pkgs:
                    if p in vis:
                        continue
                    matched = False
                    for vp in vis:
                        suffix = vp.replace(src, "").strip("-")
                        if vp != primary and suffix and (vp in p or p.endswith(suffix)):
                            agg_pkg_size[vp] += pkg_size.get(p, 0)
                            matched = True
                            break
                    if not matched:
                        agg_pkg_size[primary] += pkg_size.get(p, 0)

        # Segunda passagem: constrói entradas de aplicativos a partir dos .desktop
        for entry in parsed_desktops:
            name = entry["name"]
            icon = entry["icon"]
            pkg = entry["pkg"]
            exec_bin = entry["exec_bin"]
            work_path = entry["path"]
            df_path = entry["desktop_file"]

            if pkg and pkg in pkg_size:
                size = agg_pkg_size.get(pkg, pkg_size.get(pkg, 0))
                # Se o pacote instala em /opt/<dir>, garante que o tamanho real em disco seja considerado
                if pkg in pkg_to_opt_dirs:
                    opt_total = sum(get_dir_size(d) for d in pkg_to_opt_dirs[pkg] if os.path.exists(d))
                    if opt_total > size:
                        size = opt_total

                key = f"deb:{pkg}:{name.lower()}"
                # Evita duplicar o mesmo pacote caso tenha dois .desktop quase idênticos (ex: System Monitor e GNOME System Monitor)
                pkg_key = f"deb_pkg:{pkg}"
                if pkg_key in apps_map:
                    if size > apps_map[pkg_key]["size_bytes"]:
                        apps_map[pkg_key]["size_bytes"] = size
                    continue

                apps_map[pkg_key] = {
                    "name": name,
                    "icon": icon or "application-x-executable",
                    "size_bytes": size,
                    "source": "APT / DEB",
                    "pkg_id": pkg
                }
            else:
                # Aplicativo Standalone / Manual / Tarball / /opt / /usr/local / AppImage / Local
                resolved = cls._resolve_standalone_app(
                    name=name,
                    exec_bin=exec_bin,
                    icon=icon,
                    work_path=work_path,
                    df_path=df_path,
                    claimed_opt_dirs=claimed_opt_dirs,
                    claimed_files=claimed_files
                )
                if resolved and resolved["size_bytes"] > 0:
                    key = f"standalone:{resolved['pkg_id'].lower()}"
                    if key not in apps_map or apps_map[key]["size_bytes"] < resolved["size_bytes"]:
                        apps_map[key] = resolved

        # 3. Descobre ferramentas/aplicativos importantes instalados manualmente via APT sem arquivo .desktop
        cls._scan_manual_apt_apps(
            apps_map=apps_map,
            pkg_size=pkg_size,
            pkg_source=pkg_source,
            pkg_section=pkg_section,
            pkg_priority=pkg_priority,
            pkg_summary=pkg_summary,
            source_to_pkgs=source_to_pkgs,
            pkg_to_bins=pkg_to_bins,
            consumed_sources=consumed_sources
        )

        # 4. Descobre binários/ferramentas standalone instaladas em /usr/local/bin
        cls._scan_usr_local_bin_apps(apps_map, claimed_files)

    @classmethod
    def _collect_all_desktop_files(cls) -> List[str]:
        """Coleta arquivos .desktop de todos os diretórios padrão, XDG e locais do usuário."""
        home = os.path.expanduser("~")
        search_dirs: List[str] = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.join(home, ".local", "share", "applications"),
        ]

        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            search_dirs.append(os.path.join(xdg_data_home, "applications"))

        xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "")
        for d in xdg_data_dirs.split(":"):
            if d.strip():
                search_dirs.append(os.path.join(d.strip(), "applications"))

        for desktop_folder in ("Desktop", "Área de Trabalho"):
            p = os.path.join(home, desktop_folder)
            if os.path.exists(p):
                search_dirs.append(p)

        seen_paths: Set[str] = set()
        result: List[str] = []

        for d in search_dirs:
            if not os.path.exists(d):
                continue
            try:
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.endswith(".desktop"):
                            full_p = os.path.join(root, f)
                            if full_p not in seen_paths:
                                seen_paths.add(full_p)
                                result.append(full_p)
            except OSError:
                pass

        return sorted(result)

    @classmethod
    def _parse_desktop_file(cls, df_path: str) -> Optional[Dict[str, Any]]:
        """Analisa um arquivo .desktop com suporte a localização e tolerância a erros."""
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read(df_path, encoding="utf-8")
        except Exception:
            return None

        if "Desktop Entry" not in cp:
            return None

        sec = cp["Desktop Entry"]
        if sec.get("Type", "Application").strip() != "Application":
            return None
        if sec.get("NoDisplay", "false").strip().lower() == "true":
            return None
        if sec.get("Hidden", "false").strip().lower() == "true":
            return None

        lang = i18n.current_language
        name = ""
        if lang == "pt":
            name = sec.get("Name[pt_BR]", "") or sec.get("Name[pt]", "")
        if not name:
            name = sec.get("Name", "")
        name = name.strip()
        if not name:
            return None

        icon = sec.get("Icon", "").strip()
        exec_raw = sec.get("Exec", "").strip()
        work_path = sec.get("Path", "").strip()

        is_flatpak = (
            bool(sec.get("X-Flatpak", ""))
            or "/flatpak/exports/" in df_path
            or "flatpak run" in exec_raw
        )
        is_snap = (
            bool(sec.get("X-SnapInstanceName", ""))
            or "/var/lib/snapd/desktop/" in df_path
            or exec_raw.startswith("/snap/")
        )

        exec_bin = cls._extract_exec_binary(exec_raw)

        return {
            "desktop_file": df_path,
            "name": name,
            "icon": icon,
            "exec_raw": exec_raw,
            "exec_bin": exec_bin,
            "path": work_path,
            "is_flatpak": is_flatpak,
            "is_snap": is_snap,
        }

    @staticmethod
    def _extract_exec_binary(exec_str: str) -> str:
        """Extrai o caminho ou nome do executável principal a partir da linha Exec=."""
        if not exec_str:
            return ""
        try:
            tokens = shlex.split(exec_str)
        except Exception:
            tokens = exec_str.split()

        skip_wrappers = {"env", "/usr/bin/env", "sh", "bash", "/bin/sh", "/bin/bash", "-c", "exec"}
        for tok in tokens:
            if tok in skip_wrappers:
                continue
            if "=" in tok and not tok.startswith("/"):
                continue
            if tok.startswith("%") or tok.startswith("-"):
                continue
            return tok
        return tokens[0] if tokens else ""

    @classmethod
    def _resolve_standalone_app(
        cls,
        name: str,
        exec_bin: str,
        icon: str,
        work_path: str,
        df_path: str,
        claimed_opt_dirs: Set[str],
        claimed_files: Set[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve o diretório ou arquivo de instalação para aplicativos que não vieram via dpkg,
        como tarballs em /opt (Android Studio, Antigravity IDE), JetBrains Toolbox, AppImages, etc.
        """
        candidate_paths: List[str] = []

        if exec_bin:
            if os.path.isabs(exec_bin):
                candidate_paths.append(exec_bin)
                if os.path.exists(exec_bin) or os.path.islink(exec_bin):
                    try:
                        candidate_paths.append(os.path.realpath(exec_bin))
                    except Exception:
                        pass
            else:
                which_p = shutil.which(exec_bin)
                if which_p:
                    candidate_paths.append(which_p)
                    try:
                        candidate_paths.append(os.path.realpath(which_p))
                    except Exception:
                        pass
                for bin_dir in ("/usr/local/bin", os.path.expanduser("~/.local/bin"), os.path.expanduser("~/bin")):
                    cand = os.path.join(bin_dir, exec_bin)
                    if os.path.exists(cand) or os.path.islink(cand):
                        candidate_paths.append(cand)
                        if os.path.islink(cand):
                            try:
                                link_target = os.readlink(cand)
                                if os.path.isabs(link_target):
                                    candidate_paths.append(link_target)
                            except Exception:
                                pass

        if work_path and os.path.isabs(work_path):
            candidate_paths.append(work_path)
        if icon and os.path.isabs(icon):
            candidate_paths.append(icon)

        resolved_icon = icon

        for cand in candidate_paths:
            # 1. AppImage
            if cand.lower().endswith(".appimage") and os.path.isfile(cand):
                sz = get_dir_size(cand)
                if sz > 0:
                    claimed_files.add(os.path.realpath(cand))
                    return {
                        "name": name,
                        "icon": resolved_icon or "application-x-executable",
                        "size_bytes": sz,
                        "source": "AppImage",
                        "pkg_id": os.path.basename(cand)
                    }

            # 2. Instalado em /opt/<app_folder>
            if cand.startswith("/opt/"):
                segs = cand.split("/")
                if len(segs) >= 3 and segs[2]:
                    opt_folder = f"/opt/{segs[2]}"
                    actual_opt_folder = cls._match_existing_opt_folder(opt_folder)
                    if actual_opt_folder:
                        claimed_opt_dirs.add(actual_opt_folder)
                        if resolved_icon.startswith(opt_folder + "/") and actual_opt_folder != opt_folder:
                            alt_icon = resolved_icon.replace(opt_folder, actual_opt_folder, 1)
                            if os.path.exists(alt_icon):
                                resolved_icon = alt_icon
                        if os.path.isabs(resolved_icon) and not os.path.exists(resolved_icon):
                            resolved_icon = cls._find_icon_in_dir(actual_opt_folder, os.path.basename(resolved_icon))
                        sz = get_dir_size(actual_opt_folder)
                        if sz > 0:
                            return {
                                "name": name,
                                "icon": resolved_icon or "application-x-executable",
                                "size_bytes": sz,
                                "source": "/opt (Standalone)",
                                "pkg_id": os.path.basename(actual_opt_folder)
                            }

            # 3. JetBrains Toolbox (~/.local/share/JetBrains/Toolbox/apps/<App>)
            if "/JetBrains/Toolbox/apps/" in cand:
                m = re.search(r"(.*/JetBrains/Toolbox/apps/[^/]+)", cand)
                if m and os.path.exists(m.group(1)):
                    jb_dir = m.group(1)
                    sz = get_dir_size(jb_dir)
                    if sz > 0:
                        return {
                            "name": name,
                            "icon": resolved_icon or "application-x-executable",
                            "size_bytes": sz,
                            "source": "JetBrains Toolbox",
                            "pkg_id": os.path.basename(jb_dir)
                        }

            # 4. Instalado em /usr/local/<app_folder>
            if cand.startswith("/usr/local/"):
                segs = cand.split("/")
                if len(segs) >= 4:
                    sub = segs[3]
                    if sub not in ("bin", "sbin", "etc", "games", "include", "man", "src", "share", "lib", "lib64"):
                        target_dir = f"/usr/local/{sub}"
                        if os.path.exists(target_dir):
                            sz = get_dir_size(target_dir)
                            if sz > 0:
                                return {
                                    "name": name,
                                    "icon": resolved_icon or "application-x-executable",
                                    "size_bytes": sz,
                                    "source": "/usr/local",
                                    "pkg_id": sub
                                }
                    elif sub in ("lib", "lib64", "share") and len(segs) >= 5:
                        sub2 = segs[4]
                        if sub2 not in ("applications", "icons", "pixmaps", "man", "doc", "locale", "mime"):
                            target_dir = f"/usr/local/{sub}/{sub2}"
                            if os.path.exists(target_dir):
                                sz = get_dir_size(target_dir)
                                if sz > 0:
                                    return {
                                        "name": name,
                                        "icon": resolved_icon or "application-x-executable",
                                        "size_bytes": sz,
                                        "source": "/usr/local",
                                        "pkg_id": sub2
                                    }
                    elif sub == "bin" and os.path.isfile(cand):
                        sz = get_dir_size(cand)
                        if sz > 0:
                            claimed_files.add(os.path.realpath(cand))
                            return {
                                "name": name,
                                "icon": resolved_icon or "application-x-executable",
                                "size_bytes": sz,
                                "source": "/usr/local/bin",
                                "pkg_id": os.path.basename(cand)
                            }

            # 5. Instalado no diretório do usuário (~/.local/share/<app>, ~/Applications/<app>, etc.)
            home = os.path.expanduser("~")
            if cand.startswith(home + "/"):
                rel = cand[len(home) + 1:]
                segs = rel.split("/")
                target_path = None
                if rel.startswith(".local/share/") and len(segs) >= 3:
                    app_sub = segs[2]
                    if app_sub not in ("applications", "icons", "mime", "flatpak", "Trash", "gvfs-metadata", "keyrings"):
                        target_path = os.path.join(home, ".local", "share", app_sub)
                elif rel.startswith(".local/lib/") and len(segs) >= 3:
                    target_path = os.path.join(home, ".local", "lib", segs[2])
                elif segs[0].lower() in ("applications", "apps", "programs") and len(segs) >= 2:
                    target_path = os.path.join(home, segs[0], segs[1])
                elif segs[0].lower() not in USER_DATA_FOLDERS and not segs[0].startswith(".cache") and not segs[0].startswith(".config"):
                    target_path = os.path.join(home, segs[0])

                if target_path and os.path.exists(target_path):
                    sz = get_dir_size(target_path)
                    if sz > 0:
                        if os.path.isfile(target_path):
                            claimed_files.add(os.path.realpath(target_path))
                        return {
                            "name": name,
                            "icon": resolved_icon or "application-x-executable",
                            "size_bytes": sz,
                            "source": "Local (~)",
                            "pkg_id": os.path.basename(target_path)
                        }

        return None

    @staticmethod
    def _match_existing_opt_folder(opt_folder: str) -> Optional[str]:
        """
        Verifica se opt_folder existe em /opt.
        Caso tenha sido renomeado (ex: /opt/antigravity-ide -> /opt/antigravity),
        encontra a pasta correspondente em /opt.
        """
        if os.path.exists(opt_folder):
            return opt_folder
        if not os.path.exists("/opt"):
            return None

        target_name = os.path.basename(opt_folder).lower()
        target_stem = target_name.split("-")[0]

        try:
            for entry in os.listdir("/opt"):
                full_p = os.path.join("/opt", entry)
                if not os.path.isdir(full_p):
                    continue
                elower = entry.lower()
                if elower == target_name or elower == target_stem or target_name.startswith(elower) or elower.startswith(target_name):
                    return full_p
        except OSError:
            pass
        return None

    @staticmethod
    def _find_icon_in_dir(app_dir: str, preferred_filename: str = "") -> str:
        """Procura por um arquivo de ícone dentro do diretório do aplicativo."""
        if not os.path.exists(app_dir):
            return "application-x-executable"
        fallback_icon = ""
        try:
            for root, dirs, files in os.walk(app_dir):
                depth = root[len(app_dir):].count(os.sep)
                if depth > 4:
                    dirs[:] = []
                    continue
                for f in files:
                    if preferred_filename and f == preferred_filename:
                        return os.path.join(root, f)
                    if not fallback_icon and f.lower().endswith((".png", ".svg")):
                        fallback_icon = os.path.join(root, f)
        except OSError:
            pass
        return fallback_icon or "application-x-executable"

    # =========================================================================
    # 2. VARREDURA DIRETA DE /opt/*
    # =========================================================================
    @classmethod
    def _scan_opt_directories(cls, apps_map: Dict[str, Dict[str, Any]], claimed_opt_dirs: Set[str]):
        """Descobre aplicativos instalados em /opt que não possuam atalho em /usr/share/applications."""
        if not os.path.exists("/opt"):
            return

        try:
            entries = os.listdir("/opt")
        except OSError:
            return

        for entry in entries:
            opt_path = os.path.join("/opt", entry)
            if not os.path.isdir(opt_path) or opt_path in claimed_opt_dirs:
                continue

            # Ignora pastas vazias ou pastas de containerd/sistema sem app
            if entry in ("containerd", "cni"):
                continue

            size = get_dir_size(opt_path)
            if size <= 0:
                continue

            # Procura por um .desktop ou ícone dentro de /opt/<entry>
            name = entry.replace("-", " ").replace("_", " ").title()
            icon = "application-x-executable"

            for root, dirs, files in os.walk(opt_path):
                depth = root[len(opt_path):].count(os.sep)
                if depth > 3:
                    dirs[:] = []
                    continue
                for f in files:
                    if f.endswith(".desktop"):
                        parsed = cls._parse_desktop_file(os.path.join(root, f))
                        if parsed:
                            name = parsed["name"]
                            if parsed["icon"]:
                                icon = parsed["icon"]
                            break
                    elif icon == "application-x-executable" and f.lower() in (
                        f"{entry.lower()}.png", f"{entry.lower()}.svg", "icon.png", "icon.svg", "product_logo_128.png", "studio.png", "code.png"
                    ):
                        icon = os.path.join(root, f)

            key = f"opt:{entry.lower()}"
            if key not in apps_map:
                apps_map[key] = {
                    "name": name,
                    "icon": icon,
                    "size_bytes": size,
                    "source": "/opt (Standalone)",
                    "pkg_id": entry
                }

    # =========================================================================
    # 3. APLICATIVOS APT MANUAIS SEM .DESKTOP (CLI / DEV / SERVER)
    # =========================================================================
    @classmethod
    def _scan_manual_apt_apps(
        cls,
        apps_map: Dict[str, Dict[str, Any]],
        pkg_size: Dict[str, int],
        pkg_source: Dict[str, str],
        pkg_section: Dict[str, str],
        pkg_priority: Dict[str, str],
        pkg_summary: Dict[str, str],
        source_to_pkgs: Dict[str, Set[str]],
        pkg_to_bins: Dict[str, List[str]],
        consumed_sources: Set[str]
    ):
        """
        Descobre aplicações e suítes instaladas manualmente via APT que não possuem atalho GUI
        (ex: Docker, MongoDB Shell, QEMU, Git, etc.), excluindo bibliotecas, fontes e drivers.
        """
        try:
            manual_out = subprocess.check_output(
                ["apt-mark", "showmanual"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            manual_pkgs = set(manual_out.strip().split("\n"))
        except Exception:
            return

        # Agrupa suítes conhecidas (ex: docker-ce + docker-ce-cli + docker-buildx-plugin + docker-compose-plugin + containerd.io)
        docker_pkgs = {"docker-ce", "docker-ce-cli", "docker-buildx-plugin", "docker-compose-plugin", "containerd.io", "docker.io"}
        installed_docker = [p for p in docker_pkgs if p in pkg_size]
        if installed_docker and any(p in manual_pkgs for p in installed_docker):
            docker_size = sum(pkg_size[p] for p in installed_docker)
            for p in installed_docker:
                consumed_sources.add(pkg_source.get(p, p))
            apps_map["apt_cli:docker"] = {
                "name": "Docker Engine & CLI",
                "icon": "system-run-symbolic",
                "size_bytes": docker_size,
                "source": "APT / CLI",
                "pkg_id": "docker-ce"
            }

        excluded_sections = (
            "libs", "kernel", "fonts", "metapackages", "localization",
            "doc", "perl", "python", "gnu-r", "translations", "introspection"
        )

        for pkg in sorted(manual_pkgs):
            if pkg not in pkg_size or pkg in SYSTEM_PLUMBING_PACKAGES:
                continue
            src = pkg_source.get(pkg, pkg)
            if src in consumed_sources or src in SYSTEM_PLUMBING_PACKAGES:
                continue
            if pkg.startswith(("lib", "linux-", "fonts-", "nvidia-", "xserver-", "gir1.2-", "python3-", "zorin-", "gnome-shell-", "grub-", "language-pack-")):
                continue

            sec = pkg_section.get(pkg, "").lower()
            if any(ex in sec for ex in excluded_sections):
                continue

            pri = pkg_priority.get(pkg, "").lower()
            if pri in ("required", "important", "standard"):
                continue

            # Precisa fornecer pelo menos um executável em /usr/bin para ser considerado um aplicativo
            if pkg not in pkg_to_bins:
                continue

            # Calcula tamanho de todo o grupo Source (ex: qemu, git, mongodb-mongosh)
            total_sz = sum(pkg_size.get(p, 0) for p in source_to_pkgs.get(src, {pkg}))
            # Filtra pacotes muito pequenos (< 2 MB) de CLI para manter a lista limpa e relevante
            if total_sz < 2 * 1024 * 1024:
                continue

            consumed_sources.add(src)
            summary = pkg_summary.get(pkg, "")
            pretty_name = cls._format_cli_pkg_name(pkg, summary)
            icon_name = pkg if pkg in ("git", "qemu", "vim", "htop", "tmux") else "utilities-terminal-symbolic"

            apps_map[f"apt_cli:{src}"] = {
                "name": pretty_name,
                "icon": icon_name,
                "size_bytes": total_sz,
                "source": "APT / CLI",
                "pkg_id": pkg
            }

    @staticmethod
    def _format_cli_pkg_name(pkg: str, summary: str) -> str:
        known_names = {
            "mongodb-mongosh": "MongoDB Shell (mongosh)",
            "qemu-system-x86": "QEMU System Emulator (x86)",
            "git": "Git",
            "nodejs": "Node.js",
            "golang-go": "Go Programming Language",
            "rustc": "Rust Compiler",
            "cargo": "Rust Cargo",
            "ffmpeg": "FFmpeg",
            "imagemagick": "ImageMagick",
        }
        if pkg in known_names:
            return known_names[pkg]
        return pkg.replace("-", " ").title()

    # =========================================================================
    # 4. BINÁRIOS STANDALONE EM /usr/local/bin
    # =========================================================================
    @classmethod
    def _scan_usr_local_bin_apps(cls, apps_map: Dict[str, Dict[str, Any]], claimed_files: Set[str]):
        """Descobre binários e ferramentas instaladas diretamente em /usr/local/bin."""
        local_bin = "/usr/local/bin"
        if not os.path.exists(local_bin):
            return

        mongo_tools = {
            "mongodump", "mongorestore", "mongoexport", "mongoimport",
            "mongofiles", "mongostat", "mongotop", "bsondump"
        }
        mongo_tools_size = 0
        other_bins: List[Tuple[str, int]] = []

        try:
            for fname in os.listdir(local_bin):
                fpath = os.path.join(local_bin, fname)
                if os.path.islink(fpath) or not os.path.isfile(fpath):
                    continue
                real_f = os.path.realpath(fpath)
                if real_f in claimed_files:
                    continue
                try:
                    sz = os.path.getsize(fpath)
                except OSError:
                    continue

                if fname in mongo_tools:
                    mongo_tools_size += sz
                    claimed_files.add(real_f)
                elif sz >= 1024 * 1024:  # >= 1 MB
                    other_bins.append((fname, sz))
                    claimed_files.add(real_f)
        except OSError:
            pass

        if mongo_tools_size > 0:
            apps_map["usr_local:mongodb_tools"] = {
                "name": "MongoDB Database Tools",
                "icon": "mongodb-compass",
                "size_bytes": mongo_tools_size,
                "source": "/usr/local/bin",
                "pkg_id": "mongodb-database-tools"
            }

        for fname, sz in other_bins:
            apps_map[f"usr_local:{fname.lower()}"] = {
                "name": fname.replace("-", " ").replace("_", " ").title(),
                "icon": "utilities-terminal-symbolic",
                "size_bytes": sz,
                "source": "/usr/local/bin",
                "pkg_id": fname
            }

    # =========================================================================
    # 5. APLICATIVOS FLATPAK
    # =========================================================================
    @classmethod
    def _scan_flatpak_apps(cls, apps_map: Dict[str, Dict[str, Any]]):
        """Mapeia aplicativos Flatpak instalados (sistema e usuário) e seus tamanhos."""
        bases = [
            "/var/lib/flatpak/app",
            os.path.expanduser("~/.local/share/flatpak/app")
        ]

        for base in bases:
            if not os.path.exists(base):
                continue
            try:
                app_ids = os.listdir(base)
            except OSError:
                continue

            for app_id in app_ids:
                app_path = os.path.join(base, app_id)
                if not os.path.isdir(app_path):
                    continue

                size = get_dir_size(app_path)
                # Soma também os dados dedicados do app em ~/.var/app/<app_id>, se existirem
                var_app_path = os.path.expanduser(f"~/.var/app/{app_id}")
                if os.path.exists(var_app_path):
                    size += get_dir_size(var_app_path)

                if size <= 0:
                    continue

                name = app_id
                icon = app_id

                desktop_candidates = [
                    f"/var/lib/flatpak/exports/share/applications/{app_id}.desktop",
                    os.path.expanduser(f"~/.local/share/flatpak/exports/share/applications/{app_id}.desktop")
                ]

                for df in desktop_candidates:
                    if os.path.exists(df):
                        parsed = cls._parse_desktop_file(df)
                        if parsed:
                            name = parsed["name"]
                            icon = parsed["icon"] or icon
                            break

                key = f"flatpak:{app_id.lower()}"
                apps_map[key] = {
                    "name": name,
                    "icon": icon,
                    "size_bytes": size,
                    "source": "Flatpak",
                    "pkg_id": app_id
                }

    # =========================================================================
    # 6. APLICATIVOS SNAP
    # =========================================================================
    @classmethod
    def _scan_snap_apps(cls, apps_map: Dict[str, Dict[str, Any]]):
        """Mapeia aplicativos Snap somando todas as revisões instaladas."""
        snap_sizes: Dict[str, int] = {}

        snap_mount_dir = "/var/lib/snapd/snaps"
        if os.path.exists(snap_mount_dir):
            for sf in glob.glob(os.path.join(snap_mount_dir, "*.snap")):
                try:
                    sname = os.path.basename(sf)
                    base_name = sname.rsplit("_", 1)[0]
                    if cls._is_excluded_snap(base_name):
                        continue
                    snap_sizes[base_name] = snap_sizes.get(base_name, 0) + os.path.getsize(sf)
                except OSError:
                    pass

        # Caso /snap/<app>/current exista e não tenhamos lido /var/lib/snapd/snaps
        if os.path.exists("/snap"):
            try:
                for entry in os.listdir("/snap"):
                    if entry == "bin" or cls._is_excluded_snap(entry) or entry in snap_sizes:
                        continue
                    cur_dir = os.path.join("/snap", entry, "current")
                    if os.path.isdir(cur_dir):
                        sz = get_dir_size(cur_dir)
                        if sz > 0:
                            snap_sizes[entry] = sz
            except OSError:
                pass

        for base_name, size in snap_sizes.items():
            if size <= 0:
                continue
            name = base_name.replace("-", " ").title()
            icon = base_name

            # Procura qualquer arquivo .desktop do snap (<snap_name>_*.desktop)
            desktop_matches = glob.glob(f"/var/lib/snapd/desktop/applications/{base_name}_*.desktop")
            for df in desktop_matches:
                parsed = cls._parse_desktop_file(df)
                if parsed:
                    name = parsed["name"]
                    icon = parsed["icon"] or icon
                    break

            key = f"snap:{base_name.lower()}"
            apps_map[key] = {
                "name": name,
                "icon": icon,
                "size_bytes": size,
                "source": "Snap",
                "pkg_id": base_name
            }

    @staticmethod
    def _is_excluded_snap(snap_name: str) -> bool:
        if snap_name in SNAP_EXCLUDED_BASES:
            return True
        if snap_name.startswith(("gnome-", "kf5-", "kf6-", "mesa-", "core")):
            return True
        return False

    # =========================================================================
    # 7. APPIMAGES AVULSOS
    # =========================================================================
    @classmethod
    def _scan_appimages(cls, apps_map: Dict[str, Dict[str, Any]], claimed_files: Set[str]):
        """Procura arquivos .AppImage em pastas comuns do usuário e do sistema."""
        home = os.path.expanduser("~")
        search_dirs = [
            os.path.join(home, "Applications"),
            os.path.join(home, "Apps"),
            os.path.join(home, ".local", "bin"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Área de Trabalho"),
            os.path.join(home, "Downloads"),
            "/opt",
        ]

        for d in search_dirs:
            if not os.path.exists(d):
                continue
            try:
                for entry in os.listdir(d):
                    if entry.lower().endswith(".appimage"):
                        fpath = os.path.join(d, entry)
                        real_f = os.path.realpath(fpath)
                        if real_f in claimed_files or not os.path.isfile(fpath):
                            continue
                        try:
                            sz = os.path.getsize(fpath)
                        except OSError:
                            continue
                        if sz > 0:
                            claimed_files.add(real_f)
                            clean_name = re.sub(r"[-_]?v?\d+(\.\d+)*.*$", "", entry[:-9], flags=re.IGNORECASE)
                            clean_name = (clean_name or entry[:-9]).replace("-", " ").replace("_", " ").strip()
                            apps_map[f"appimage:{entry.lower()}"] = {
                                "name": clean_name,
                                "icon": "application-x-executable",
                                "size_bytes": sz,
                                "source": "AppImage",
                                "pkg_id": entry
                            }
            except OSError:
                pass

    # =========================================================================
    # 8. JOGOS DA STEAM
    # =========================================================================
    @classmethod
    def _scan_steam_apps(cls, apps_map: Dict[str, Dict[str, Any]]):
        """Descobre jogos instalados via Steam através dos manifestos appmanifest_*.acf."""
        home = os.path.expanduser("~")
        steamapps_dirs = [
            os.path.join(home, ".steam", "steam", "steamapps"),
            os.path.join(home, ".local", "share", "Steam", "steamapps"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam", "steamapps"),
        ]

        seen_appids: Set[str] = set()
        for sdir in steamapps_dirs:
            if not os.path.exists(sdir):
                continue
            for acf in glob.glob(os.path.join(sdir, "appmanifest_*.acf")):
                try:
                    with open(acf, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                    m_id = re.search(r'"appid"\s+"(\d+)"', content)
                    m_name = re.search(r'"name"\s+"([^"]+)"', content)
                    m_size = re.search(r'"SizeOnDisk"\s+"(\d+)"', content)
                    if m_id and m_name and m_size:
                        appid = m_id.group(1)
                        name = m_name.group(1)
                        sz = int(m_size.group(1))
                        if appid in seen_appids or sz <= 0:
                            continue
                        if "Steamworks Common Redistributables" in name or name.startswith("Proton ") or name.startswith("Steam Linux Runtime"):
                            continue
                        seen_appids.add(appid)
                        apps_map[f"steam:{appid}"] = {
                            "name": name,
                            "icon": f"steam_icon_{appid}",
                            "size_bytes": sz,
                            "source": "Steam",
                            "pkg_id": appid
                        }
                except Exception:
                    pass
