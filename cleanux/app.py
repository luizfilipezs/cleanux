"""
Ponto de entrada da aplicação Cleanux (Adw.Application).
"""

import os
import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, Gdk

from .ui.main_window import MainWindow
from .ui.styles import CUSTOM_CSS


class CleanuxApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.cleanux",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()
        self._setup_icon_theme()

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(application=self)
        self.window.present()

    def _setup_icon_theme(self):
        try:
            display = Gdk.Display.get_default()
            if display:
                icon_theme = Gtk.IconTheme.get_for_display(display)
                extra_icon_dirs = [
                    "/var/lib/flatpak/exports/share/icons",
                    os.path.expanduser("~/.local/share/flatpak/exports/share/icons"),
                    "/usr/share/pixmaps",
                    "/var/lib/snapd/desktop/icons",
                ]
                for d in extra_icon_dirs:
                    if os.path.exists(d):
                        icon_theme.add_search_path(d)
        except Exception:
            pass

    def _load_css(self):
        try:
            display = Gdk.Display.get_default()
            if display:
                css_provider = Gtk.CssProvider()
                if hasattr(css_provider, "load_from_string"):
                    css_provider.load_from_string(CUSTOM_CSS)
                else:
                    css_provider.load_from_data(CUSTOM_CSS.encode("utf-8"))
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
        except Exception as e:
            print(f"Aviso: Não foi possível carregar o CSS customizado: {e}", file=sys.stderr)


def main():
    app = CleanuxApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
