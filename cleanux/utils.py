"""
Utilitários de sistema, formatação e execução segura de comandos.
"""

import os
import shutil
import subprocess
from typing import Tuple, List, Optional


def format_size(size_bytes: int) -> str:
    """Formata bytes em formato legível (B, KB, MB, GB, TB)."""
    if size_bytes <= 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
        
    if unit_index == 0:
        return f"{int(size)} B"
    elif unit_index == 1:
        return f"{size:.1f} KB"
    elif unit_index == 2:
        return f"{size:.1f} MB"
    else:
        return f"{size:.2f} {units[unit_index]}"


def get_dir_size(path: str) -> int:
    """Calcula o tamanho total de um diretório em bytes, ignorando symlinks."""
    total = 0
    if not os.path.exists(path):
        return 0
    
    if os.path.isfile(path) and not os.path.islink(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    try:
        for root, _, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def is_root() -> bool:
    """Verifica se o processo está sendo executado como root."""
    return os.geteuid() == 0


def check_command_available(cmd: str) -> bool:
    """Verifica se um executável está presente no PATH."""
    return shutil.which(cmd) is not None


def run_command_safe(cmd: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
    """Executa um comando local de forma segura com timeout."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False
        )
        return (proc.returncode == 0, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired:
        return (False, "", f"Comando expirou após {timeout}s")
    except Exception as e:
        return (False, "", str(e))


def run_elevated_command(cmd: List[str], timeout: int = 120) -> Tuple[bool, str, str]:
    """
    Executa um comando que requer privilégios de superusuário.
    Usa 'pkexec' para exibir o diálogo nativo do PolicyKit quando não for root.
    """
    if is_root():
        return run_command_safe(cmd, timeout=timeout)
    
    if check_command_available("pkexec"):
        elevated = ["pkexec"] + cmd
        return run_command_safe(elevated, timeout=timeout)
    elif check_command_available("sudo"):
        elevated = ["sudo", "-n"] + cmd
        return run_command_safe(elevated, timeout=timeout)
    else:
        return (False, "", "Nenhum utilitário de elevação (pkexec/sudo) encontrado.")
