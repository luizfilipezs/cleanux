"""
Internationalization (i18n) module for Cleanux.
Supports English ('en') and Portuguese ('pt').
Auto-detects system locale and falls back to English ('en') for unsupported languages.
"""

import os
import locale
from typing import Dict, Callable, List

SUPPORTED_LANGUAGES = ("en", "pt")

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Header & Navigation
        "refresh_tooltip": "Refresh system data",
        "lang_tooltip": "Change application language",
        "tab_clean": "Cleanup & Disk",
        "tab_apps": "Top 10 Apps",
        "tab_about": "About",

        # Tab 1: Disk & Cleanup
        "disk_title": "System Storage",
        "disk_subtitle": "Root partition (/)",
        "disk_in_use": "{percent} in use",
        "metric_used": "Used Space",
        "metric_free": "Free Space",
        "metric_total": "Total Capacity",
        "clean_group_title": "Safe Cleanup Options",
        "clean_group_desc": "All actions below are 100% safe for the system and never remove documents, photos, or personal data.",
        "badge_safe": "100% Safe",
        "btn_select_all": "Select All",
        "btn_deselect_all": "Deselect All",
        "reclaimable_label": "Space to free: {size}",
        "btn_clean_selected": "Clean Selected",

        # Cleanup Targets
        "target.apt_cache.name": "APT Package Cache",
        "target.apt_cache.desc": "Downloaded .deb packages from updates that are already installed on the system.",
        "target.apt_cache.safety": "100% Safe: Packages are already installed; .deb files are only installation copies.",

        "target.apt_autoremove.name": "Orphaned / Unused Packages",
        "target.apt_autoremove.desc": "Old automatic libraries and dependencies no longer required by any program.",
        "target.apt_autoremove.safety": "100% Safe: The package manager only removes unrequired dependencies.",

        "target.journal_logs.name": "Old Systemd Journal Logs",
        "target.journal_logs.desc": "Archived history of service logs and previous boot records.",
        "target.journal_logs.safety": "100% Safe: Preserves logs from the last 3 days (max 100 MB) for recent diagnostics.",

        "target.thumbnails.name": "Media Thumbnail Cache",
        "target.thumbnails.desc": "Cached thumbnails automatically generated when browsing images and videos.",
        "target.thumbnails.safety": "100% Safe: The system recreates thumbnails instantly when opening folders.",

        "target.crash_reports.name": "Crash Reports (Crash Dumps)",
        "target.crash_reports.desc": "Memory dump files from past program errors stored in /var/crash/.",
        "target.crash_reports.safety": "100% Safe: Diagnostic records from terminated processes.",

        "target.trash.name": "User Trash",
        "target.trash.desc": "Files already discarded by the user waiting to free up space.",
        "target.trash.safety": "Safe: Files you have already sent to the trash.",

        "target.flatpak_unused.name": "Orphaned Flatpak Runtimes",
        "target.flatpak_unused.desc": "Flatpak environments and extensions no longer needed by any app.",
        "target.flatpak_unused.safety": "100% Safe: Only removes dependencies of already uninstalled Flatpak apps.",

        "target.user_caches.name": "User Temporary Caches",
        "target.user_caches.desc": "Temporary files and unnecessary caches from compilers and tools (~/.cache).",
        "target.user_caches.safety": "100% Safe: Temporary caches reloadable on demand.",

        # Status & Toasts
        "status_analyzing": "Analyzing: {name}...",
        "status_analysis_done": "Analysis completed",
        "status_starting_clean": "Starting safe cleanup...",
        "status_cleaning_user": "Cleaning: {name}...",
        "status_cleaning_root": "Cleaning system: {name}...",
        "status_clean_done": "Cleanup completed!",
        "toast_clean_finished": "Cleanup completed! {size} freed successfully!",
        "toast_apps_reloaded": "Application list updated!",

        # Tab 2: Top 10 Apps
        "apps_title": "Top 10 Heaviest Applications",
        "apps_desc": "Installed applications on the system that consume the most storage space.",
        "apps_rescan_tooltip": "Reload application list",
        "app_row_subtitle": "Source: {source} • {size}",
        "source_system": "System",

        # Tab 3: About
        "about_desc": (
            "Version 1.0.0 • Native System Cleaner and Optimizer for Linux\n\n"
            "Specially designed to keep your system fast, freeing up space with complete safety."
        ),
        "about_group_title": "Cleanux Safety Commitment",
        "about_row1_title": "User Data Preservation",
        "about_row1_sub": "Cleanux never removes files in Documents, Pictures, Videos, Downloads, or Desktop.",
        "about_row2_title": "Essential Log Integrity",
        "about_row2_sub": "Vacuums Journal history while preserving the last 3 days for failure diagnostics.",
        "about_row3_title": "Safe Package Removal",
        "about_row3_sub": "Eliminates only orphaned packages and cached .deb files that can be re-downloaded anytime.",
        "about_row4_title": "Native Linux Technology",
        "about_row4_sub": "Built with GTK 4 and Libadwaita for maximum visual integration and speed on Zorin OS and GNOME.",
    },
    "pt": {
        # Header & Navigation
        "refresh_tooltip": "Atualizar dados do sistema",
        "lang_tooltip": "Alterar idioma do aplicativo",
        "tab_clean": "Limpeza & Disco",
        "tab_apps": "Top 10 Apps",
        "tab_about": "Sobre",

        # Tab 1: Disk & Cleanup
        "disk_title": "Armazenamento do Sistema",
        "disk_subtitle": "Partição raiz (/)",
        "disk_in_use": "{percent} em uso",
        "metric_used": "Espaço Usado",
        "metric_free": "Espaço Livre",
        "metric_total": "Capacidade Total",
        "clean_group_title": "Opções de Limpeza Segura",
        "clean_group_desc": "Todas as ações abaixo são 100% seguras para o sistema e nunca removem documentos, fotos ou dados pessoais.",
        "badge_safe": "100% Seguro",
        "btn_select_all": "Selecionar Todos",
        "btn_deselect_all": "Desmarcar Todos",
        "reclaimable_label": "Espaço a liberar: {size}",
        "btn_clean_selected": "Limpar Selecionados",

        # Cleanup Targets
        "target.apt_cache.name": "Cache de Pacotes APT",
        "target.apt_cache.desc": "Pacotes .deb baixados durante atualizações já instalados no sistema.",
        "target.apt_cache.safety": "100% Seguro: Os pacotes já estão instalados; arquivos .deb são apenas cópias de instalação.",

        "target.apt_autoremove.name": "Pacotes Órfãos / Não Utilizados",
        "target.apt_autoremove.desc": "Bibliotecas e dependências automáticas antigas que não são mais exigidas por nenhum programa.",
        "target.apt_autoremove.safety": "100% Seguro: O gerenciador de pacotes remove apenas dependências não requeridas.",

        "target.journal_logs.name": "Logs Antigos do Systemd Journal",
        "target.journal_logs.desc": "Histórico arquivado de registros de serviços e inicializações anteriores.",
        "target.journal_logs.safety": "100% Seguro: Preserva os logs dos últimos 3 dias (máx. 100 MB) para diagnóstico recente.",

        "target.thumbnails.name": "Cache de Miniaturas de Mídia",
        "target.thumbnails.desc": "Miniaturas em cache geradas automaticamente ao navegar por imagens e vídeos.",
        "target.thumbnails.safety": "100% Seguro: O sistema recria miniaturas instantaneamente ao abrir pastas.",

        "target.crash_reports.name": "Relatórios de Travamento (Crash Dumps)",
        "target.crash_reports.desc": "Arquivos de despejo de memória de erros passados armazenados em /var/crash/.",
        "target.crash_reports.safety": "100% Seguro: Registros de diagnóstico de processos finalizados.",

        "target.trash.name": "Lixeira do Usuário",
        "target.trash.desc": "Arquivos já descartados pelo usuário aguardando liberação de espaço.",
        "target.trash.safety": "Seguro: Arquivos que você já enviou para a lixeira.",

        "target.flatpak_unused.name": "Runtimes Flatpak Órfãos",
        "target.flatpak_unused.desc": "Ambientes e extensões Flatpak que não são mais necessários por nenhum app.",
        "target.flatpak_unused.safety": "100% Seguro: Remove somente dependências de aplicativos Flatpak já desinstalados.",

        "target.user_caches.name": "Caches Temporários do Usuário",
        "target.user_caches.desc": "Arquivos temporários e caches desnecessários de compiladores e ferramentas (~/.cache).",
        "target.user_caches.safety": "100% Seguro: Caches temporários recarregáveis sob demanda.",

        # Status & Toasts
        "status_analyzing": "Analisando: {name}...",
        "status_analysis_done": "Análise concluída",
        "status_starting_clean": "Iniciando limpeza segura...",
        "status_cleaning_user": "Limpando: {name}...",
        "status_cleaning_root": "Limpando sistema: {name}...",
        "status_clean_done": "Limpeza concluída!",
        "toast_clean_finished": "Limpeza concluída! {size} liberados com sucesso!",
        "toast_apps_reloaded": "Lista de aplicativos atualizada!",

        # Tab 2: Top 10 Apps
        "apps_title": "Os 10 Aplicativos Mais Pesados",
        "apps_desc": "Aplicativos instalados no sistema que mais consomem espaço de armazenamento.",
        "apps_rescan_tooltip": "Recarregar lista de aplicativos",
        "app_row_subtitle": "Origem: {source} • {size}",
        "source_system": "Sistema",

        # Tab 3: About
        "about_desc": (
            "Versão 1.0.0 • Limpador e Otimizador Nativo de Sistema para Linux\n\n"
            "Desenvolvido especialmente para manter seu sistema ágil, liberando espaço com total segurança."
        ),
        "about_group_title": "Compromisso de Segurança do Cleanux",
        "about_row1_title": "Preservação de Dados do Usuário",
        "about_row1_sub": "O Cleanux nunca remove arquivos em Documentos, Imagens, Vídeos, Downloads ou Área de Trabalho.",
        "about_row2_title": "Integridade de Logs Essenciais",
        "about_row2_sub": "Compacta o histórico do Journal preservando os últimos 3 dias para diagnóstico de falhas.",
        "about_row3_title": "Remoção Segura de Pacotes",
        "about_row3_sub": "Elimina apenas pacotes órfãos e arquivos .deb em cache já instalados que podem ser baixados a qualquer momento.",
        "about_row4_title": "Tecnologia Nativa Linux",
        "about_row4_sub": "Construído com GTK 4 e Libadwaita para máxima integração visual e velocidade no Zorin OS e distribuições GNOME.",
    }
}


def detect_system_language() -> str:
    """
    Detects the default system language.
    Returns 'pt' if Portuguese, otherwise 'en' (for English or any unsupported language).
    """
    candidates: List[str] = []

    for env_var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        val = os.environ.get(env_var)
        if val:
            candidates.append(val)

    try:
        loc = locale.getlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass

    for raw in candidates:
        # Handle colon-separated lists in LANGUAGE (e.g. "pt_BR:pt:en")
        first_part = raw.split(":")[0].split(".")[0].strip().lower()
        if first_part.startswith("pt"):
            return "pt"
        if first_part.startswith("en"):
            return "en"
        if first_part and first_part not in ("c", "posix"):
            # System is explicitly set to another language (e.g., es, fr, de) -> fallback to 'en'
            return "en"

    return "en"


class I18nManager:
    def __init__(self):
        self._current_lang: str = detect_system_language()
        self._listeners: List[Callable[[str], None]] = []

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang_code: str):
        if lang_code not in SUPPORTED_LANGUAGES:
            lang_code = "en"
        if lang_code != self._current_lang:
            self._current_lang = lang_code
            for callback in list(self._listeners):
                callback(self._current_lang)

    def add_listener(self, callback: Callable[[str], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def translate(self, key: str, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self._current_lang, TRANSLATIONS["en"])
        text = lang_dict.get(key) or TRANSLATIONS["en"].get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text


# Global singleton instance
i18n = I18nManager()


def t(key: str, **kwargs) -> str:
    """Translates a key into the active language."""
    return i18n.translate(key, **kwargs)
