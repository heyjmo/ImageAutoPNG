"""
Branded per-user installer for ImageAutoPNG (by heyjmo).

- Wizard UI with logo, install path, and options
- Copies THIS executable (sys.executable) — never a nested .exe from _MEIPASS
- Registers Start Menu, optional startup, and Add/Remove Programs (ARP)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import winreg
from pathlib import Path

from version_info import (
    APP_NAME,
    COPYRIGHT,
    DESCRIPTION,
    EXE_NAME,
    PRODUCT_NAME,
    PUBLISHER,
    VERSION,
)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Per-user Uninstall key (no admin required)
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
INSTALL_PATH_VALUE = "InstallLocation"


def default_install_dir() -> Path:
    """Microsoft-style per-user default: %LOCALAPPDATA%\\Programs\\<App>."""
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "Programs" / APP_NAME


def config_dir() -> Path:
    return Path.home() / f".{APP_NAME.lower()}"


def install_meta_path() -> Path:
    return config_dir() / "install.json"


def load_saved_install_dir() -> Path | None:
    try:
        data = json.loads(install_meta_path().read_text(encoding="utf-8"))
        p = Path(data.get("install_dir", ""))
        if p.is_dir():
            return p
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    # Fallback: read ARP
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            loc, _ = winreg.QueryValueEx(key, INSTALL_PATH_VALUE)
            p = Path(loc)
            if p.is_dir():
                return p
    except OSError:
        pass
    return None


def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / "assets" / name


def should_run_as_setup() -> bool:
    if "--install" in sys.argv or "/install" in sys.argv:
        return True
    if "--uninstall" in sys.argv or "/uninstall" in sys.argv:
        return True
    stem = Path(sys.executable if getattr(sys, "frozen", False) else __file__).stem.lower()
    return "setup" in stem or stem.endswith("-install")


def wants_uninstall() -> bool:
    return "--uninstall" in sys.argv or "/uninstall" in sys.argv


def _message(title: str, text: str, error: bool = False) -> None:
    try:
        import ctypes

        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        print(f"{title}: {text}")


def _create_shortcut(shortcut_path: Path, target: Path, workdir: Path, icon: Path | None = None) -> None:
    try:
        import win32com.client  # type: ignore

        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(str(shortcut_path))
        sc.Targetpath = str(target)
        sc.WorkingDirectory = str(workdir)
        sc.Description = DESCRIPTION
        if icon and icon.exists():
            sc.IconLocation = str(icon)
        else:
            sc.IconLocation = str(target)
        sc.save()
        return
    except Exception:
        pass

    def _esc(p: Path) -> str:
        return str(p).replace("\\", "\\\\")

    icon_line = ""
    if icon and icon.exists():
        icon_line = f'sc.IconLocation = "{_esc(icon)}"\n'
    else:
        icon_line = f'sc.IconLocation = "{_esc(target)}"\n'

    vbs = (
        'Set sh = CreateObject("WScript.Shell")\n'
        f'Set sc = sh.CreateShortcut("{_esc(shortcut_path)}")\n'
        f'sc.TargetPath = "{_esc(target)}"\n'
        f'sc.WorkingDirectory = "{_esc(workdir)}"\n'
        f'sc.Description = "{DESCRIPTION}"\n'
        f"{icon_line}"
        "sc.Save\n"
    )
    tmp = Path(os.environ.get("TEMP", ".")) / "iap_shortcut.vbs"
    tmp.write_text(vbs, encoding="utf-8", errors="replace")
    subprocess.run(["wscript", "//nologo", str(tmp)], check=False, creationflags=0x08000000)
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


def _copy_self(src: Path, dest: Path, retries: int = 8) -> None:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with open(src, "rb") as f:
                data = f.read()
            if not data:
                raise OSError("Source executable is empty")
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            return
        except OSError as e:
            last_err = e
            time.sleep(0.4 * (attempt + 1))
            try:
                t = dest.with_suffix(".tmp")
                if t.exists():
                    t.unlink(missing_ok=True)
            except OSError:
                pass
    raise OSError(
        f"Could not copy installer to:\n{dest}\n\n"
        f"Source:\n{src}\n\n"
        f"Error: {last_err}\n\n"
        "Try: right-click Setup → Properties → Unblock, then run again."
    )


def _write_uninstall_bat(dest_dir: Path, dest_exe: Path) -> Path:
    bat = dest_dir / "Uninstall.bat"
    # Quiet path for ARP; interactive when double-clicked
    bat.write_text(
        f"""@echo off
setlocal
echo Uninstalling {APP_NAME}...
"{dest_exe}" --uninstall
if errorlevel 1 (
  echo Fallback cleanup...
  taskkill /F /IM {EXE_NAME} >nul 2>&1
  reg delete "HKCU\\{RUN_KEY}" /v {APP_NAME} /f >nul 2>&1
  reg delete "HKCU\\{UNINSTALL_KEY}" /f >nul 2>&1
  del "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{PUBLISHER}\\{APP_NAME}.lnk" >nul 2>&1
  rmdir "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{PUBLISHER}" >nul 2>&1
  cd /d "%TEMP%"
  rmdir /s /q "{dest_dir}" >nul 2>&1
)
echo Done.
if /I "%~1"=="/S" exit /b 0
pause
""",
        encoding="utf-8",
    )
    return bat


def register_arp(dest_dir: Path, dest_exe: Path, uninstall_bat: Path) -> None:
    """Add/Remove Programs entry for this user (no admin)."""
    display_icon = str(dest_exe)
    estimated_size_kb = max(1, dest_exe.stat().st_size // 1024)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, f"{PRODUCT_NAME} {VERSION}")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, display_icon)
        winreg.SetValueEx(key, INSTALL_PATH_VALUE, 0, winreg.REG_SZ, str(dest_dir))
        winreg.SetValueEx(key, "InstallDate", 0, winreg.REG_SZ, time.strftime("%Y%m%d"))
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, int(estimated_size_kb))
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "Comments", 0, winreg.REG_SZ, DESCRIPTION)
        # Quiet uninstall for Settings app
        winreg.SetValueEx(
            key,
            "UninstallString",
            0,
            winreg.REG_SZ,
            f'"{dest_exe}" --uninstall',
        )
        winreg.SetValueEx(
            key,
            "QuietUninstallString",
            0,
            winreg.REG_SZ,
            f'"{dest_exe}" --uninstall',
        )


def unregister_arp() -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def do_install(
    dest_dir: Path,
    *,
    start_with_windows: bool = True,
    launch_after: bool = True,
    desktop_shortcut: bool = False,
) -> Path:
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "The .exe installer only works when built with PyInstaller.\n"
            "For source installs, use install.ps1 instead."
        )

    src = Path(sys.executable).resolve()
    dest_dir = dest_dir.expanduser().resolve()
    dest_exe = dest_dir / EXE_NAME

    if src != dest_exe:
        if dest_exe.exists():
            subprocess.run(
                ["taskkill", "/F", "/IM", EXE_NAME],
                check=False,
                capture_output=True,
                creationflags=0x08000000,
            )
            time.sleep(0.5)
        _copy_self(src, dest_exe)

    # Start Menu under publisher folder (common Windows style)
    programs = (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / PUBLISHER
    )
    programs.mkdir(parents=True, exist_ok=True)
    _create_shortcut(programs / f"{APP_NAME}.lnk", dest_exe, dest_dir)

    if desktop_shortcut:
        desktop = Path.home() / "Desktop"
        if desktop.is_dir():
            _create_shortcut(desktop / f"{APP_NAME}.lnk", dest_exe, dest_dir)

    # Startup Run key
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if start_with_windows:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{dest_exe}"')
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError as e:
        raise OSError(f"Could not update startup entry: {e}") from e

    # Config defaults
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"
    if not cfg_path.exists():
        cfg = {
            "watch_folder": str(Path.home() / "Downloads"),
            "delete_originals": True,
            "convert_existing_on_start": True,
            "start_with_windows": start_with_windows,
            "recursive": False,
        }
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    else:
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["start_with_windows"] = start_with_windows
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    # Remember install location
    install_meta_path().write_text(
        json.dumps(
            {
                "install_dir": str(dest_dir),
                "version": VERSION,
                "publisher": PUBLISHER,
                "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    uninstall_bat = _write_uninstall_bat(dest_dir, dest_exe)
    register_arp(dest_dir, dest_exe, uninstall_bat)

    if launch_after:
        subprocess.Popen([str(dest_exe)], cwd=str(dest_dir), close_fds=True)

    return dest_exe


def do_uninstall() -> None:
    dest_dir = load_saved_install_dir() or default_install_dir()
    # Also try legacy path from earlier builds
    legacy = Path(os.environ.get("LOCALAPPDATA", "")) / APP_NAME

    subprocess.run(
        ["taskkill", "/F", "/IM", EXE_NAME],
        check=False,
        capture_output=True,
        creationflags=0x08000000,
    )
    time.sleep(0.4)

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    except OSError:
        pass

    unregister_arp()

    # Shortcuts
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    for link in [
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / PUBLISHER / f"{APP_NAME}.lnk",
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_NAME}.lnk",
        Path.home() / "Desktop" / f"{APP_NAME}.lnk",
    ]:
        try:
            link.unlink(missing_ok=True)
        except OSError:
            pass
    pub_dir = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / PUBLISHER
    try:
        if pub_dir.is_dir() and not any(pub_dir.iterdir()):
            pub_dir.rmdir()
    except OSError:
        pass

    # Remove install folders (best effort; may fail if we are running from there)
    for folder in {dest_dir, legacy}:
        if not folder or not folder.exists():
            continue
        for pattern in ("*.exe", "*.bat", "*.tmp", "*.ico", "*.png"):
            for f in folder.glob(pattern):
                try:
                    f.unlink()
                except OSError:
                    pass
        try:
            folder.rmdir()
        except OSError:
            pass

    try:
        install_meta_path().unlink(missing_ok=True)
    except OSError:
        pass

    _message(
        f"{APP_NAME} Uninstall",
        f"{APP_NAME} has been removed.\n\n"
        f"Optional: delete settings folder\n{config_dir()}\n"
        "if you want a complete wipe.",
    )


# ---------------------------------------------------------------------------
# Installer wizard UI
# ---------------------------------------------------------------------------


def show_install_wizard() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    from PIL import Image, ImageTk

    result: dict = {"ok": False}

    root = tk.Tk()
    root.title(f"{PRODUCT_NAME} Setup — {PUBLISHER}")
    root.resizable(False, False)
    root.configure(bg="#f4f6f8")

    # Window icon if available
    ico = resource_path("app_icon.ico")
    if not ico.exists():
        ico = Path(__file__).resolve().parent / "assets" / "app_icon.ico"
    try:
        if ico.exists():
            root.iconbitmap(default=str(ico))
    except tk.TclError:
        pass

    outer = tk.Frame(root, bg="#f4f6f8", padx=0, pady=0)
    outer.pack(fill="both", expand=True)

    # Banner
    logo_path = resource_path("jmo_logo.png")
    if not logo_path.exists():
        logo_path = Path(__file__).resolve().parent / "assets" / "jmo_logo.png"
    banner_holder = tk.Frame(outer, bg="#121c2a", height=120)
    banner_holder.pack(fill="x")
    banner_holder.pack_propagate(False)
    photo = None
    if logo_path.exists():
        try:
            im = Image.open(logo_path)
            # Fit width ~560
            w, h = im.size
            target_w = 560
            scale = target_w / max(w, 1)
            im = im.resize((target_w, max(1, int(h * scale))), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            lbl = tk.Label(banner_holder, image=photo, bg="#121c2a", bd=0)
            lbl.image = photo  # type: ignore[attr-defined]
            lbl.pack(anchor="w")
        except Exception:
            tk.Label(
                banner_holder,
                text=f"  {PUBLISHER}",
                font=("Segoe UI", 22, "bold"),
                fg="white",
                bg="#121c2a",
                anchor="w",
            ).pack(fill="both", expand=True, padx=20)
    else:
        tk.Label(
            banner_holder,
            text=f"  {PUBLISHER}",
            font=("Segoe UI", 22, "bold"),
            fg="white",
            bg="#121c2a",
            anchor="w",
        ).pack(fill="both", expand=True, padx=20)

    body = tk.Frame(outer, bg="#f4f6f8", padx=24, pady=16)
    body.pack(fill="both", expand=True)

    tk.Label(
        body,
        text=f"Install {PRODUCT_NAME}",
        font=("Segoe UI", 14, "bold"),
        bg="#f4f6f8",
        fg="#1a2332",
        anchor="w",
    ).pack(fill="x")
    tk.Label(
        body,
        text=f"Version {VERSION}  ·  {DESCRIPTION}",
        font=("Segoe UI", 9),
        bg="#f4f6f8",
        fg="#5a6a7a",
        anchor="w",
        wraplength=520,
        justify="left",
    ).pack(fill="x", pady=(4, 14))

    # Install location
    tk.Label(body, text="Install location", font=("Segoe UI", 10, "bold"), bg="#f4f6f8", anchor="w").pack(
        fill="x"
    )
    path_row = tk.Frame(body, bg="#f4f6f8")
    path_row.pack(fill="x", pady=(4, 10))
    path_var = tk.StringVar(value=str(default_install_dir()))
    path_entry = ttk.Entry(path_row, textvariable=path_var, width=58)
    path_entry.pack(side="left", fill="x", expand=True, ipady=3)

    def browse() -> None:
        chosen = filedialog.askdirectory(
            title="Choose install folder",
            initialdir=path_var.get() or str(default_install_dir()),
        )
        if chosen:
            # If user picked a parent, still use AppName subfolder when empty name
            p = Path(chosen)
            if p.name.lower() != APP_NAME.lower():
                p = p / APP_NAME
            path_var.set(str(p))

    ttk.Button(path_row, text="Browse…", command=browse).pack(side="left", padx=(8, 0))

    tk.Label(
        body,
        text="Default is a standard per-user folder (no administrator rights required).",
        font=("Segoe UI", 8),
        bg="#f4f6f8",
        fg="#7a8a9a",
        anchor="w",
    ).pack(fill="x", pady=(0, 12))

    # Options
    start_var = tk.BooleanVar(value=True)
    launch_var = tk.BooleanVar(value=True)
    desk_var = tk.BooleanVar(value=False)

    opts = tk.Frame(body, bg="#f4f6f8")
    opts.pack(fill="x")
    tk.Checkbutton(
        opts,
        text="Start with Windows",
        variable=start_var,
        bg="#f4f6f8",
        activebackground="#f4f6f8",
        font=("Segoe UI", 10),
        anchor="w",
    ).pack(fill="x")
    tk.Checkbutton(
        opts,
        text="Launch ImageAutoPNG when setup finishes",
        variable=launch_var,
        bg="#f4f6f8",
        activebackground="#f4f6f8",
        font=("Segoe UI", 10),
        anchor="w",
    ).pack(fill="x")
    tk.Checkbutton(
        opts,
        text="Create desktop shortcut",
        variable=desk_var,
        bg="#f4f6f8",
        activebackground="#f4f6f8",
        font=("Segoe UI", 10),
        anchor="w",
    ).pack(fill="x")

    status = tk.Label(body, text="", font=("Segoe UI", 9), bg="#f4f6f8", fg="#2a7a2a", anchor="w")
    status.pack(fill="x", pady=(12, 0))

    btns = tk.Frame(body, bg="#f4f6f8")
    btns.pack(fill="x", pady=(16, 4))

    def on_cancel() -> None:
        result["ok"] = False
        root.destroy()

    def on_install() -> None:
        target = Path(path_var.get().strip())
        if not target.parts:
            messagebox.showerror("Install", "Please choose an install location.")
            return
        try:
            # Ensure we can create the folder
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Install", f"Cannot create folder:\n{target}\n\n{e}")
            return

        status.config(text="Installing…", fg="#1a5a9a")
        root.update_idletasks()
        try:
            dest = do_install(
                target,
                start_with_windows=start_var.get(),
                launch_after=launch_var.get(),
                desktop_shortcut=desk_var.get(),
            )
        except Exception as e:
            status.config(text="")
            messagebox.showerror(f"{PRODUCT_NAME} Setup", f"Install failed:\n\n{e}")
            return

        result["ok"] = True
        from version_info import DONATE_URL, WEBSITE_URL

        messagebox.showinfo(
            f"{PRODUCT_NAME} Setup",
            f"{PRODUCT_NAME} was installed successfully.\n\n"
            f"by {PUBLISHER}  ·  free software\n"
            f"Location:\n{dest.parent}\n\n"
            "It appears in Settings → Apps.\n"
            "Right-click the tray icon for options.\n\n"
            f"Website: {WEBSITE_URL}\n"
            f"Donate (optional): {DONATE_URL}",
        )
        root.destroy()

    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right")
    install_btn = ttk.Button(btns, text="Install", command=on_install)
    install_btn.pack(side="right", padx=(0, 8))

    # Footer
    tk.Label(
        body,
        text=COPYRIGHT,
        font=("Segoe UI", 8),
        bg="#f4f6f8",
        fg="#9aa8b5",
        anchor="w",
    ).pack(fill="x", pady=(8, 0))

    # Center on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    if not result.get("ok"):
        raise SystemExit(0)


def run_setup_and_exit() -> None:
    if wants_uninstall():
        try:
            do_uninstall()
        except Exception as e:
            _message(f"{APP_NAME} Uninstall", f"Uninstall failed:\n\n{e}", error=True)
            raise SystemExit(1) from e
        raise SystemExit(0)

    # Silent install for automation: --install --silent
    if "--silent" in sys.argv or "/S" in sys.argv:
        try:
            dest_dir = default_install_dir()
            for i, arg in enumerate(sys.argv):
                if arg.lower() in ("--dir", "/dir") and i + 1 < len(sys.argv):
                    dest_dir = Path(sys.argv[i + 1])
            do_install(dest_dir, start_with_windows=True, launch_after=True, desktop_shortcut=False)
        except Exception as e:
            _message(f"{APP_NAME} Setup", f"Install failed:\n\n{e}", error=True)
            raise SystemExit(1) from e
        raise SystemExit(0)

    try:
        show_install_wizard()
    except SystemExit:
        raise
    except Exception as e:
        _message(f"{APP_NAME} Setup", f"Install failed:\n\n{e}", error=True)
        raise SystemExit(1) from e
    raise SystemExit(0)
