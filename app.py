"""
ImageAutoPNG — system-tray app that watches a folder and converts
.webp / .heic / .heif files to .png silently and immediately.
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

# Ensure local imports work when frozen or run from any cwd
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import load_config, log_line, save_config, CONFIG_PATH, LOG_PATH, APP_NAME
from converter import SUPPORTED_EXTENSIONS, convert_to_png, is_convertible, scan_folder
from tray_icon import create_icon

try:
    import pystray
except ImportError:
    print("Missing dependency: pystray. Run: pip install -r requirements.txt")
    sys.exit(1)


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = APP_NAME


def _is_windows() -> bool:
    return sys.platform == "win32"


def set_start_with_windows(enabled: bool) -> None:
    if not _is_windows():
        return
    try:
        import winreg

        if getattr(sys, "frozen", False):
            cmd = f'"{sys.executable}"'
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            runner = pythonw if pythonw.exists() else Path(sys.executable)
            cmd = f'"{runner}" "{APP_DIR / "app.py"}"'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
    except OSError as e:
        log_line(f"Could not update startup registry: {e}")


def get_start_with_windows() -> bool:
    if not _is_windows():
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        return False


class ConvertHandler(FileSystemEventHandler):
    def __init__(self, app: "ImageAutoPNG") -> None:
        super().__init__()
        self.app = app
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._queue(event.src_path)

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._queue(event.src_path)

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._queue(event.dest_path)

    def _queue(self, path_str: str) -> None:
        path = Path(path_str)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        key = str(path.resolve()) if path.exists() else str(path)
        with self._lock:
            if key in self._pending:
                return
            self._pending.add(key)
        threading.Thread(target=self._process, args=(path, key), daemon=True).start()

    def _process(self, path: Path, key: str) -> None:
        try:
            if self.app.paused:
                return
            if not path.exists():
                return
            if not is_convertible(path):
                return
            convert_to_png(path, delete_original=self.app.config.get("delete_originals", True))
            self.app.refresh_tooltip()
        finally:
            with self._lock:
                self._pending.discard(key)


class ImageAutoPNG:
    def __init__(self) -> None:
        self.config = load_config()
        self.paused = False
        self.observer: Observer | None = None
        self.icon: pystray.Icon | None = None
        self._converted_session = 0
        self._tk_root: tk.Tk | None = None

        # Sync startup flag with registry preference
        if self.config.get("start_with_windows", True):
            set_start_with_windows(True)

    def watch_folder(self) -> Path:
        return Path(self.config.get("watch_folder") or (Path.home() / "Downloads"))

    def start_watcher(self) -> None:
        folder = self.watch_folder()
        folder.mkdir(parents=True, exist_ok=True)

        if self.observer is not None:
            self.observer.stop()
            self.observer.join(timeout=3)

        recursive = bool(self.config.get("recursive", False))
        handler = ConvertHandler(self)
        self.observer = Observer()
        self.observer.schedule(handler, str(folder), recursive=recursive)
        self.observer.start()
        log_line(f"Watching: {folder} (recursive={recursive})")

        if self.config.get("convert_existing_on_start", True):
            threading.Thread(target=self._initial_scan, daemon=True).start()

    def _initial_scan(self) -> None:
        n = scan_folder(
            self.watch_folder(),
            delete_original=bool(self.config.get("delete_originals", True)),
            recursive=bool(self.config.get("recursive", False)),
        )
        self._converted_session += n
        self.refresh_tooltip()
        if n:
            log_line(f"Initial scan converted {n} file(s)")

    def stop_watcher(self) -> None:
        if self.observer is not None:
            self.observer.stop()
            self.observer.join(timeout=3)
            self.observer = None

    def refresh_tooltip(self) -> None:
        if self.icon is None:
            return
        status = "Paused" if self.paused else "Watching"
        folder = self.watch_folder()
        self.icon.title = f"{APP_NAME} — {status}\n{folder}"

    # --- UI helpers (tkinter dialogs on demand) ---

    def _run_on_ui(self, fn: Callable[[], None]) -> None:
        """Run a callable that needs a Tk root on a short-lived main thread hop."""
        def runner() -> None:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                fn()
            finally:
                root.destroy()

        threading.Thread(target=runner, daemon=True).start()

    def choose_folder(self, icon=None, item=None) -> None:
        def do() -> None:
            initial = str(self.watch_folder())
            path = filedialog.askdirectory(title="Choose folder to watch", initialdir=initial)
            if path:
                self.config["watch_folder"] = path
                save_config(self.config)
                self.start_watcher()
                self.refresh_tooltip()
                log_line(f"Watch folder changed to: {path}")

        self._run_on_ui(do)

    def toggle_pause(self, icon=None, item=None) -> None:
        self.paused = not self.paused
        log_line("Paused" if self.paused else "Resumed")
        self.refresh_tooltip()
        if self.icon:
            self.icon.update_menu()

    def toggle_delete(self, icon=None, item=None) -> None:
        self.config["delete_originals"] = not self.config.get("delete_originals", True)
        save_config(self.config)
        log_line(f"Delete originals: {self.config['delete_originals']}")
        if self.icon:
            self.icon.update_menu()

    def toggle_startup(self, icon=None, item=None) -> None:
        enabled = not self.config.get("start_with_windows", True)
        self.config["start_with_windows"] = enabled
        save_config(self.config)
        set_start_with_windows(enabled)
        log_line(f"Start with Windows: {enabled}")
        if self.icon:
            self.icon.update_menu()

    def scan_now(self, icon=None, item=None) -> None:
        def work() -> None:
            n = scan_folder(
                self.watch_folder(),
                delete_original=bool(self.config.get("delete_originals", True)),
                recursive=bool(self.config.get("recursive", False)),
            )
            self._converted_session += n
            self.refresh_tooltip()
            log_line(f"Manual scan converted {n} file(s)")

        threading.Thread(target=work, daemon=True).start()

    def open_folder(self, icon=None, item=None) -> None:
        folder = self.watch_folder()
        folder.mkdir(parents=True, exist_ok=True)
        if _is_windows():
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(folder)])

    def open_log(self, icon=None, item=None) -> None:
        from config import ensure_config_dir

        ensure_config_dir()
        if not LOG_PATH.exists():
            LOG_PATH.write_text("", encoding="utf-8")
        if _is_windows():
            os.startfile(LOG_PATH)  # type: ignore[attr-defined]
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(LOG_PATH)])

    def about(self, icon=None, item=None) -> None:
        def do() -> None:
            try:
                from version_info import DONATE_URL, GITHUB_URL, PUBLISHER, VERSION, WEBSITE_URL
            except ImportError:
                PUBLISHER, VERSION = "heyjmo", ""
                GITHUB_URL = WEBSITE_URL = DONATE_URL = ""
            messagebox.showinfo(
                APP_NAME,
                f"{APP_NAME}  {VERSION}\n"
                f"by {PUBLISHER}\n\n"
                "Free utility — silently converts .webp and .heic/.heif\n"
                "images to .png in your watched folder.\n\n"
                f"Watching:\n{self.watch_folder()}\n\n"
                f"Website: {WEBSITE_URL}\n"
                f"Source:  {GITHUB_URL}\n"
                f"Donate:  {DONATE_URL}\n\n"
                f"Config: {CONFIG_PATH}\n"
                f"Log: {LOG_PATH}",
            )

        self._run_on_ui(do)

    def _open_url(self, url: str) -> None:
        if not url:
            return
        import webbrowser

        webbrowser.open(url)

    def open_website(self, icon=None, item=None) -> None:
        try:
            from version_info import WEBSITE_URL
        except ImportError:
            WEBSITE_URL = "https://moseleyhost.com/AutoPNG"
        self._open_url(WEBSITE_URL)

    def open_github(self, icon=None, item=None) -> None:
        try:
            from version_info import GITHUB_URL
        except ImportError:
            GITHUB_URL = "https://github.com/heyjmo/ImageAutoPNG"
        self._open_url(GITHUB_URL)

    def open_donate(self, icon=None, item=None) -> None:
        try:
            from version_info import DONATE_URL
        except ImportError:
            DONATE_URL = "https://github.com/sponsors/heyjmo"
        if not DONATE_URL:
            def do() -> None:
                messagebox.showinfo(
                    APP_NAME,
                    "Donations are not configured yet.\n"
                    "Visit the project website or GitHub page for updates.",
                )

            self._run_on_ui(do)
            return
        self._open_url(DONATE_URL)

    def quit_app(self, icon=None, item=None) -> None:
        log_line("Exiting")
        self.stop_watcher()
        if self.icon:
            self.icon.stop()

    def build_menu(self) -> pystray.Menu:
        def pause_text(item):
            return "Resume" if self.paused else "Pause"

        def delete_checked(item):
            return bool(self.config.get("delete_originals", True))

        def startup_checked(item):
            return bool(self.config.get("start_with_windows", True))

        return pystray.Menu(
            pystray.MenuItem(lambda item: f"Folder: {self.watch_folder()}", None, enabled=False),
            pystray.MenuItem("Choose folder…", self.choose_folder),
            pystray.MenuItem("Open watched folder", self.open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_text, self.toggle_pause),
            pystray.MenuItem("Scan now", self.scan_now),
            pystray.MenuItem("Delete originals after convert", self.toggle_delete, checked=delete_checked),
            pystray.MenuItem("Start with Windows", self.toggle_startup, checked=startup_checked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open log", self.open_log),
            pystray.MenuItem("Website", self.open_website),
            pystray.MenuItem("GitHub", self.open_github),
            pystray.MenuItem("Donate…", self.open_donate),
            pystray.MenuItem("About", self.about),
            pystray.MenuItem("Quit", self.quit_app),
        )

    def run(self) -> None:
        log_line("Started")
        self.start_watcher()
        image = create_icon(64)
        self.icon = pystray.Icon(APP_NAME, image, APP_NAME, menu=self.build_menu())
        self.refresh_tooltip()
        self.icon.run()
        self.stop_watcher()


def main() -> None:
    # Frozen Setup / --install: copy THIS exe into LocalAppData (no nested extract)
    if getattr(sys, "frozen", False):
        from installer import run_setup_and_exit, should_run_as_setup

        if should_run_as_setup():
            run_setup_and_exit()
            return

    # Hide console window if launched with python.exe (not pythonw)
    if _is_windows() and not getattr(sys, "frozen", False):
        try:
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                # Only hide if we're not attached to an interactive parent for debugging
                if os.environ.get("IMAGEAUTOPNG_DEBUG") != "1":
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

    app = ImageAutoPNG()
    app.run()


if __name__ == "__main__":
    main()
