"""
Serviço de análise de utilização de disco do sistema.
"""

import os
import shutil
from typing import Dict, Any
from .utils import format_size


class DiskService:
    @staticmethod
    def get_mount_usage(path: str) -> Dict[str, Any]:
        """Obtém estatísticas de disco para um caminho especificado."""
        try:
            usage = shutil.disk_usage(path)
            total = usage.total
            used = usage.used
            free = usage.free
            percent = (used / total * 100.0) if total > 0 else 0.0
            
            return {
                "path": path,
                "total": total,
                "used": used,
                "free": free,
                "percent": percent,
                "total_formatted": format_size(total),
                "used_formatted": format_size(used),
                "free_formatted": format_size(free),
                "percent_formatted": f"{percent:.1f}%"
            }
        except Exception as e:
            return {
                "path": path,
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0.0,
                "total_formatted": "0 B",
                "used_formatted": "0 B",
                "free_formatted": "0 B",
                "percent_formatted": "0%",
                "error": str(e)
            }

    @classmethod
    def get_disk_summary(cls) -> Dict[str, Any]:
        """Retorna resumo detalhado do disco principal e partição home."""
        root_info = cls.get_mount_usage("/")
        home_path = os.path.expanduser("~")
        home_info = cls.get_mount_usage(home_path)

        # Verifica se /home está montado em partição separada
        try:
            root_stat = os.stat("/")
            home_stat = os.stat(home_path)
            separate_home = root_stat.st_dev != home_stat.st_dev
        except Exception:
            separate_home = False

        return {
            "root": root_info,
            "home": home_info,
            "separate_home": separate_home,
            "primary": root_info
        }
