# Cleanux

**Cleanux** is a native Linux application built with **GTK 4** and **Libadwaita**, designed to monitor disk usage, identify the heaviest installed applications, and perform safe system cleanups without risking personal user data.

---

## ✨ Features

- **Storage Overview:**
  - Detailed inspection of the primary partition (`/`), displaying used space, free space, total capacity, and a visual progress bar.
- **100% Safe System Cleanup:**
  - **APT Package Cache:** Removes cached `.deb` files stored in `/var/cache/apt/archives` that are already installed.
  - **Orphaned / Unused Packages:** Removes obsolete dependencies that are no longer required by any program (`apt autoremove --purge`).
  - **Archived Systemd Journal Logs:** Vacuums older log history while preserving logs from the last 3 days (capped at 100 MB) for recent troubleshooting.
  - **Thumbnail Cache:** Cleans cached thumbnails in `~/.cache/thumbnails` (regenerated automatically on demand).
  - **Crash Reports (Crash Dumps):** Deletes legacy crash dumps in `/var/crash`.
  - **User Trash:** Empties discarded files in `~/.local/share/Trash`.
  - **Orphaned Flatpak Runtimes:** Removes unused Flatpak runtimes and extensions that have no associated applications.
  - **User Temporary Caches:** Cleans disposable caches from tools such as `pip`, `npm`, `yarn`, `fontconfig`, and `mesa_shader_cache`.
- **Top 10 Heaviest Applications:**
  - Ranked list of the 10 largest installed applications on the system (supporting **APT/DEB**, **Flatpak**, and **Snap** packages), featuring native icons, names, source packages, disk space occupied, and relative usage bars.
- **Internationalization (i18n):**
  - Supports **English** and **Portuguese**.
  - Automatically detects the system locale on startup (using English as fallback when the system is configured in an unsupported language) and allows real-time language switching directly from the header bar inside the app.

---

## 🛠️ Requirements

On Debian, Ubuntu, or Zorin OS based distributions:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

---

## 🚀 How to Run

### 1. Run directly from source

In the root directory of the project, run:

```bash
./run.py
```

Or via the executable script in `bin/`:

```bash
./bin/cleanux
```

### 2. Install via `.deb` package

The repository includes a ready-to-test installer package: `cleanux_1.0.0_all.deb`. To install it on your system:

```bash
sudo dpkg -i cleanux_1.0.0_all.deb
```

Once installed, **Cleanux** will be available in your application launcher menu or can be started from the terminal with:

```bash
cleanux
```

To uninstall:

```bash
sudo apt remove cleanux
```

---

## 📦 How to Build the `.deb` Package

If you make modifications to the source code and want to rebuild the `.deb` installer:

```bash
./build_deb.sh
```

This will recompile and generate `cleanux_1.0.0_all.deb` in the project root directory.

---

## 📂 Project Structure

```text
cleanux/
├── bin/
│   └── cleanux                   # Command-line launcher executable
├── cleanux/
│   ├── __init__.py               # Package metadata
│   ├── app.py                    # Application entry point (Adw.Application)
│   ├── apps_service.py           # Heaviest applications scanner (APT, Flatpak, Snap)
│   ├── cleaner_service.py        # Safe cleanup detection and execution engine
│   ├── disk_service.py           # Disk storage metric service
│   ├── i18n.py                   # Internationalization (EN/PT) & system locale detection
│   ├── utils.py                  # Formatting helpers and privilege elevation (pkexec)
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py        # Main window and tabs (GTK 4 / Libadwaita)
│       └── styles.py             # Custom CSS stylesheet
├── data/
│   ├── icons/                    # Application icons in SVG and PNG (hicolor)
│   └── io.github.cleanux.desktop # Linux desktop entry file
├── build_deb.sh                  # Debian packaging build script
├── run.py                        # Quick local runner script
├── .gitignore                    # Git ignore file
└── README.md                     # Project documentation
```

---

## 🔒 Safety Guarantee

**Cleanux** was engineered around strict safety principles:
- **Never** modifies or deletes personal files in user directories (`Documents`, `Downloads`, `Pictures`, `Videos`, `Music`, or `Desktop`).
- Actions requiring superuser privileges invoke the official Linux **PolicyKit (`pkexec`)** authentication dialog.
