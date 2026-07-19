"""
Build a single self-contained executable for distribution.

  release/ImageAutoPNG.exe         — tray app (also supports --install / --uninstall)
  release/ImageAutoPNG-Setup.exe   — same binary, renamed (shows branded wizard)

Usage:
  python build_exe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"
APP_EXE = "ImageAutoPNG.exe"
SETUP_EXE = "ImageAutoPNG-Setup.exe"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Ensure logo + ico exist
    print("\n=== Generating branded assets ===\n")
    run([sys.executable, str(ROOT / "generate_assets.py")])

    ico = ASSETS / "app_icon.ico"
    logo = ASSETS / "jmo_logo.png"
    ver = ROOT / "file_version_info.txt"
    if not ico.exists():
        print(f"ERROR: missing {ico}", file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)

    sep = ";" if sys.platform == "win32" else ":"
    add_data = [
        f"{logo}{sep}{logo.name}",
        f"{ico}{sep}{ico.name}",
    ]

    print("\n=== Building ImageAutoPNG.exe ===\n")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "ImageAutoPNG",
        "--icon",
        str(ico),
        "--version-file",
        str(ver),
        "--hidden-import",
        "pillow_heif",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--hidden-import",
        "installer",
        "--hidden-import",
        "version_info",
        "--collect-all",
        "pillow_heif",
        "--collect-all",
        "pystray",
    ]
    for item in add_data:
        cmd.extend(["--add-data", item])
    cmd.append(str(ROOT / "app.py"))
    run(cmd)

    app_path = DIST / APP_EXE
    if not app_path.exists():
        print(f"ERROR: expected {app_path}", file=sys.stderr)
        return 1
    print(f"Built: {app_path} ({app_path.stat().st_size // 1024} KB)")

    release = ROOT / "release"
    if release.exists():
        shutil.rmtree(release)
    release.mkdir()

    shutil.copy2(app_path, release / APP_EXE)
    shutil.copy2(app_path, release / SETUP_EXE)
    # Also ship a loose logo for docs / store listings
    shutil.copy2(logo, release / "jmo_logo.png")

    print("\n=== Done ===")
    print(f"  App / portable : {release / APP_EXE}")
    print(f"  Installer      : {release / SETUP_EXE}")
    print()
    print("Distribute ImageAutoPNG-Setup.exe — branded wizard, path picker, ARP entry.")
    print("Optional next step for SmartScreen: Authenticode code signing (see README).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
