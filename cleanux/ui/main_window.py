"""
Janela Principal da Aplicação Cleanux com interface Libadwaita / GTK 4.
"""

import os
import threading
from typing import List, Dict, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

from ..disk_service import DiskService
from ..cleaner_service import CleanerService, CleanupTarget
from ..apps_service import AppsService, AppInfo
from ..utils import format_size


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Cleanux")
        self.set_default_size(880, 680)
        self.set_size_request(620, 500)

        self.cleaner_service = CleanerService()
        self.current_targets: List[CleanupTarget] = []
        self.clean_rows: List[Adw.ActionRow] = []
        self.app_rows: List[Adw.ActionRow] = []
        self.target_switches: Dict[str, Gtk.Switch] = {}
        self.target_size_labels: Dict[str, Gtk.Label] = {}
        self.is_busy = False

        self._build_ui()
        self.refresh_all_data()

    def _build_ui(self):
        # 1. Toast Overlay para notificações
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # 2. Main Box vertical
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)

        # 3. Header Bar com ViewSwitcherTitle
        header_bar = Adw.HeaderBar()
        self.view_title = Adw.ViewSwitcherTitle()
        header_bar.set_title_widget(self.view_title)

        # Botão de atualização geral no header
        self.btn_refresh = Gtk.Button()
        self.btn_refresh.set_icon_name("view-refresh-symbolic")
        self.btn_refresh.set_tooltip_text("Atualizar dados do sistema")
        self.btn_refresh.connect("clicked", lambda _: self.refresh_all_data())
        header_bar.pack_start(self.btn_refresh)

        # Spinner de atividade no header
        self.header_spinner = Gtk.Spinner()
        header_bar.pack_start(self.header_spinner)

        main_box.append(header_bar)

        # 4. View Stack com 3 abas
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)
        self.view_title.set_stack(self.view_stack)

        # Aba 1: Limpeza & Armazenamento
        self.tab_clean = self._create_clean_tab()
        self.view_stack.add_titled_with_icon(
            self.tab_clean, "clean", "Limpeza & Disco", "drive-harddisk-symbolic"
        )

        # Aba 2: Top 10 Aplicativos
        self.tab_apps = self._create_apps_tab()
        self.view_stack.add_titled_with_icon(
            self.tab_apps, "apps", "Top 10 Apps", "starred-symbolic"
        )

        # Aba 3: Sobre & Segurança
        self.tab_about = self._create_about_tab()
        self.view_stack.add_titled_with_icon(
            self.tab_about, "about", "Sobre", "help-about-symbolic"
        )

        main_box.append(self.view_stack)

        # Barra inferior de visualização em telas pequenas
        switcher_bar = Adw.ViewSwitcherBar()
        switcher_bar.set_stack(self.view_stack)
        self.view_title.bind_property(
            "title-visible",
            switcher_bar,
            "reveal",
            0
        )
        main_box.append(switcher_bar)

    # =========================================================================
    # ABA 1: LIMPEZA & ARMAZENAMENTO
    # =========================================================================
    def _create_clean_tab(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_tightening_threshold(640)
        scrolled.set_child(clamp)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        clamp.set_child(content_box)

        # --- Cartão de Uso de Disco ---
        disk_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        disk_card.add_css_class("disk-card")
        disk_card.add_css_class("card")

        disk_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        disk_icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        disk_icon.set_pixel_size(24)
        disk_icon.set_margin_end(10)
        disk_header.append(disk_icon)

        disk_title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        lbl_disk_title = Gtk.Label(label="Armazenamento do Sistema", xalign=0)
        lbl_disk_title.add_css_class("card-title")
        lbl_disk_path = Gtk.Label(label="Partição raiz (/)", xalign=0)
        lbl_disk_path.add_css_class("dim-label")
        disk_title_box.append(lbl_disk_title)
        disk_title_box.append(lbl_disk_path)
        disk_header.append(disk_title_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        disk_header.append(spacer)

        self.lbl_disk_percent_badge = Gtk.Label(label="--%")
        self.lbl_disk_percent_badge.add_css_class("disk-percent-badge")
        disk_header.append(self.lbl_disk_percent_badge)
        disk_card.append(disk_header)

        # Barra de Progresso do Disco
        self.disk_progress = Gtk.ProgressBar()
        self.disk_progress.set_fraction(0.0)
        disk_card.append(self.disk_progress)

        # Linha de Métricas
        metrics_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        metrics_box.set_homogeneous(True)

        self.lbl_metric_used = self._create_metric_widget(metrics_box, "Espaço Usado", "-- GB")
        self.lbl_metric_free = self._create_metric_widget(metrics_box, "Espaço Livre", "-- GB")
        self.lbl_metric_total = self._create_metric_widget(metrics_box, "Capacidade Total", "-- GB")

        disk_card.append(metrics_box)
        content_box.append(disk_card)

        # --- Grupo de Opções de Limpeza ---
        self.clean_group = Adw.PreferencesGroup()
        self.clean_group.set_title("Opções de Limpeza Segura")
        self.clean_group.set_description(
            "Todas as ações abaixo são 100% seguras para o sistema e nunca removem documentos, fotos ou dados pessoais."
        )

        content_box.append(self.clean_group)

        # Barra de Ações Inferior
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_bar.set_margin_top(6)

        btn_select_all = Gtk.Button(label="Selecionar Todos")
        btn_select_all.connect("clicked", lambda _: self._set_all_targets(True))
        action_bar.append(btn_select_all)

        btn_deselect_all = Gtk.Button(label="Desmarcar Todos")
        btn_deselect_all.connect("clicked", lambda _: self._set_all_targets(False))
        action_bar.append(btn_deselect_all)

        spacer2 = Gtk.Box()
        spacer2.set_hexpand(True)
        action_bar.append(spacer2)

        self.lbl_reclaimable_total = Gtk.Label(label="Espaço a liberar: 0 B")
        self.lbl_reclaimable_total.add_css_class("badge-size")
        action_bar.append(self.lbl_reclaimable_total)

        self.btn_clean_now = Gtk.Button(label="Limpar Selecionados")
        self.btn_clean_now.set_icon_name("user-trash-symbolic")
        self.btn_clean_now.add_css_class("suggested-action")
        self.btn_clean_now.add_css_class("clean-button-prominent")
        self.btn_clean_now.connect("clicked", lambda _: self._on_clean_clicked())
        action_bar.append(self.btn_clean_now)

        content_box.append(action_bar)

        # Barra de status da operação
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status_box.set_visible(False)
        self.status_spinner = Gtk.Spinner()
        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_box.append(self.status_spinner)
        self.status_box.append(self.status_label)
        content_box.append(self.status_box)

        return scrolled

    def _create_metric_widget(self, parent: Gtk.Box, title: str, value: str) -> Gtk.Label:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_title = Gtk.Label(label=title, xalign=0)
        lbl_title.add_css_class("disk-metric-title")
        lbl_val = Gtk.Label(label=value, xalign=0)
        lbl_val.add_css_class("disk-metric-value")
        box.append(lbl_title)
        box.append(lbl_val)
        parent.append(box)
        return lbl_val

    # =========================================================================
    # ABA 2: TOP 10 APLICATIVOS
    # =========================================================================
    def _create_apps_tab(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_tightening_threshold(640)
        scrolled.set_child(clamp)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        clamp.set_child(content_box)

        # Cabeçalho da aba de apps
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        lbl_title = Gtk.Label(label="Os 10 Aplicativos Mais Pesados", xalign=0)
        lbl_title.add_css_class("title-2")
        lbl_desc = Gtk.Label(
            label="Aplicativos instalados no sistema que mais consomem espaço de armazenamento.",
            xalign=0
        )
        lbl_desc.add_css_class("dim-label")

        title_vbox.append(lbl_title)
        title_vbox.append(lbl_desc)
        header_box.append(title_vbox)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        btn_rescan_apps = Gtk.Button()
        btn_rescan_apps.set_icon_name("view-refresh-symbolic")
        btn_rescan_apps.set_tooltip_text("Recarregar lista de aplicativos")
        btn_rescan_apps.connect("clicked", lambda _: self._load_apps_data())
        header_box.append(btn_rescan_apps)

        content_box.append(header_box)

        # Grupo com a lista de apps
        self.apps_group = Adw.PreferencesGroup()
        content_box.append(self.apps_group)

        return scrolled

    # =========================================================================
    # ABA 3: SOBRE & SEGURANÇA
    # =========================================================================
    def _create_about_tab(self) -> Gtk.Widget:
        status_page = Adw.StatusPage()
        status_page.set_icon_name("security-high-symbolic")
        status_page.set_title("Cleanux")
        status_page.set_description(
            "Versão 1.0.0 • Limpador e Otimizador Nativo de Sistema para Linux\n\n"
            "Desenvolvido especialmente para manter seu sistema ágil, liberando espaço com total segurança."
        )

        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Compromisso de Segurança do Cleanux")

        row1 = Adw.ActionRow(
            title="Preservação de Dados do Usuário",
            subtitle="O Cleanux nunca remove arquivos em Documentos, Imagens, Vídeos, Downloads ou Área de Trabalho."
        )
        row1.add_prefix(Gtk.Image.new_from_icon_name("folder-documents-symbolic"))
        info_group.add(row1)

        row2 = Adw.ActionRow(
            title="Integridade de Logs Essenciais",
            subtitle="Compacta o histórico do Journal preservando os últimos 3 dias para diagnóstico de falhas."
        )
        row2.add_prefix(Gtk.Image.new_from_icon_name("text-x-generic-symbolic"))
        info_group.add(row2)

        row3 = Adw.ActionRow(
            title="Remoção Segura de Pacotes",
            subtitle="Elimina apenas pacotes órfãos e arquivos .deb em cache já instalados que podem ser baixados a qualquer momento."
        )
        row3.add_prefix(Gtk.Image.new_from_icon_name("software-properties-symbolic"))
        info_group.add(row3)

        row4 = Adw.ActionRow(
            title="Tecnologia Nativa Linux",
            subtitle="Construído com GTK 4 e Libadwaita para máxima integração visual e velocidade no Zorin OS e distribuições GNOME."
        )
        row4.add_prefix(Gtk.Image.new_from_icon_name("desktop-symbolic"))
        info_group.add(row4)

        clamp.set_child(info_group)
        status_page.set_child(clamp)

        return status_page

    # =========================================================================
    # CARREGAMENTO E ATUALIZAÇÃO DE DADOS
    # =========================================================================
    def refresh_all_data(self):
        """Dispara atualização em segundo plano de disco, alvos e apps."""
        if self.is_busy:
            return

        self.is_busy = True
        self.header_spinner.start()
        self.btn_refresh.set_sensitive(False)

        def worker():
            # 1. Disco
            disk_summary = DiskService.get_disk_summary()
            
            # 2. Varredura de limpeza
            targets = self.cleaner_service.scan_all()

            # 3. Varredura dos top apps
            apps = AppsService.get_top_heaviest_apps(10)

            GLib.idle_add(self._on_data_loaded, disk_summary, targets, apps)

        threading.Thread(target=worker, daemon=True).start()

    def _on_data_loaded(self, disk_summary: Dict, targets: List[CleanupTarget], apps: List[AppInfo]):
        self.is_busy = False
        self.header_spinner.stop()
        self.btn_refresh.set_sensitive(True)

        # Atualiza Disco
        self._update_disk_ui(disk_summary)

        # Atualiza Alvos de Limpeza
        self.current_targets = targets
        self._populate_clean_targets(targets)

        # Atualiza Top Apps
        self._populate_apps_list(apps)

    def _update_disk_ui(self, disk_summary: Dict):
        root = disk_summary["root"]
        percent = root["percent"]
        self.disk_progress.set_fraction(percent / 100.0)

        # Ajusta cor do percentual conforme saturação
        self.lbl_disk_percent_badge.set_text(root["percent_formatted"] + " em uso")
        if percent > 85.0:
            self.lbl_disk_percent_badge.set_css_classes(["disk-percent-badge", "destructive-action"])
        else:
            self.lbl_disk_percent_badge.set_css_classes(["disk-percent-badge"])

        self.lbl_metric_used.set_text(root["used_formatted"])
        self.lbl_metric_free.set_text(root["free_formatted"])
        self.lbl_metric_total.set_text(root["total_formatted"])

    def _populate_clean_targets(self, targets: List[CleanupTarget]):
        # Remove linhas existentes do grupo antes de recriar
        for row in self.clean_rows:
            self.clean_group.remove(row)
        self.clean_rows.clear()
        self.target_switches.clear()
        self.target_size_labels.clear()

        for target in targets:
            row = Adw.ActionRow()
            row.set_title(target.name)
            row.set_subtitle(target.description)

            # Ícone
            img = Gtk.Image.new_from_icon_name(target.icon_name)
            img.set_pixel_size(24)
            row.add_prefix(img)

            # Selo de tamanho
            lbl_size = Gtk.Label(label=target.size_formatted)
            lbl_size.add_css_class("badge-size")
            row.add_suffix(lbl_size)
            self.target_size_labels[target.id] = lbl_size

            # Switch de seleção
            switch = Gtk.Switch()
            switch.set_active(target.selected and target.size_bytes > 0)
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect("notify::active", lambda s, _, tid=target.id: self._on_switch_toggled(tid, s.get_active()))
            row.add_suffix(switch)
            self.target_switches[target.id] = switch

            # Badge de segurança
            badge = Gtk.Label(label="100% Seguro")
            badge.add_css_class("badge-safe")
            row.add_suffix(badge)

            self.clean_group.add(row)
            self.clean_rows.append(row)

        self._update_reclaimable_sum()

    def _on_switch_toggled(self, target_id: str, is_active: bool):
        for t in self.current_targets:
            if t.id == target_id:
                t.selected = is_active
                break
        self._update_reclaimable_sum()

    def _set_all_targets(self, select: bool):
        for target in self.current_targets:
            target.selected = select
            if target.id in self.target_switches:
                self.target_switches[target.id].set_active(select)
        self._update_reclaimable_sum()

    def _update_reclaimable_sum(self):
        total_selected = sum(t.size_bytes for t in self.current_targets if t.selected)
        self.lbl_reclaimable_total.set_text(f"Espaço a liberar: {format_size(total_selected)}")
        self.btn_clean_now.set_sensitive(total_selected > 0 and not self.is_busy)

    def _populate_apps_list(self, apps: List[AppInfo]):
        # Remove linhas existentes antes de repopular a lista
        for row in self.app_rows:
            self.apps_group.remove(row)
        self.app_rows.clear()

        # Adiciona os 10 aplicativos mais pesados
        for app in apps:
            row = Adw.ActionRow()
            row.set_title(app.name)
            row.set_subtitle(f"Origem: {app.source} • {app.size_formatted}")

            # Badge de Ranking (#1, #2, #3, ...)
            lbl_rank = Gtk.Label(label=f"#{app.rank}")
            rank_class = f"badge-rank-{app.rank}" if app.rank <= 3 else "badge-rank"
            lbl_rank.add_css_class("badge-rank")
            lbl_rank.add_css_class(rank_class)
            row.add_prefix(lbl_rank)

            # Ícone do Aplicativo
            icon_widget = self._resolve_app_icon(app.icon)
            row.add_prefix(icon_widget)

            # Barra de proporção e tamanho à direita
            right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            right_box.set_valign(Gtk.Align.CENTER)
            right_box.set_size_request(140, -1)

            lbl_size = Gtk.Label(label=app.size_formatted, xalign=1)
            lbl_size.add_css_class("app-size")
            right_box.append(lbl_size)

            pbar = Gtk.ProgressBar()
            pbar.set_fraction(app.percent_of_max)
            right_box.append(pbar)

            row.add_suffix(right_box)
            self.apps_group.add(row)
            self.app_rows.append(row)

    def _resolve_app_icon(self, icon_str: str) -> Gtk.Widget:
        """Resolve ícone a partir de caminho de arquivo ou nome no tema de ícones."""
        img = Gtk.Image()
        img.set_pixel_size(36)

        if not icon_str:
            img.set_from_icon_name("application-x-executable")
            return img

        if os.path.isabs(icon_str) and os.path.exists(icon_str):
            try:
                img.set_from_file(icon_str)
                return img
            except Exception:
                pass

        # Tenta carregar pelo nome do tema
        img.set_from_icon_name(icon_str)
        return img

    def _load_apps_data(self):
        """Recarrega apenas a lista de aplicativos."""
        if self.is_busy:
            return

        self.is_busy = True
        self.header_spinner.start()
        self.btn_refresh.set_sensitive(False)

        def worker():
            apps = AppsService.get_top_heaviest_apps(10)
            GLib.idle_add(self._on_apps_reloaded, apps)

        threading.Thread(target=worker, daemon=True).start()

    def _on_apps_reloaded(self, apps: List[AppInfo]):
        self.is_busy = False
        self.header_spinner.stop()
        self.btn_refresh.set_sensitive(True)
        self._populate_apps_list(apps)
        toast = Adw.Toast.new("Lista de aplicativos atualizada!")
        self.toast_overlay.add_toast(toast)

    # =========================================================================
    # EXECUÇÃO DA LIMPEZA
    # =========================================================================
    def _on_clean_clicked(self):
        selected_ids = [t.id for t in self.current_targets if t.selected and t.size_bytes > 0]
        if not selected_ids:
            return

        self.is_busy = True
        self.btn_clean_now.set_sensitive(False)
        self.status_box.set_visible(True)
        self.status_spinner.start()
        self.status_label.set_text("Iniciando limpeza segura...")

        def update_status(text: str):
            GLib.idle_add(self.status_label.set_text, text)

        def worker():
            freed, msgs = self.cleaner_service.clean_selected(selected_ids, status_callback=update_status)
            GLib.idle_add(self._on_clean_finished, freed, msgs)

        threading.Thread(target=worker, daemon=True).start()

    def _on_clean_finished(self, freed_bytes: int, messages: List[str]):
        self.is_busy = False
        self.status_spinner.stop()
        self.status_box.set_visible(False)
        self.btn_clean_now.set_sensitive(True)

        msg_text = f"Limpeza concluída! {format_size(freed_bytes)} liberados com sucesso!"
        toast = Adw.Toast.new(msg_text)
        toast.set_timeout(5)
        self.toast_overlay.add_toast(toast)

        # Atualiza os dados de disco e re-varre os alvos
        self.refresh_all_data()
