"""
Upload website/AutoPNG/ to the host via FTP.

Usage:
  set FTP_PASS=your_password
  python upload_website.py

Or you will be prompted. Password is never written to disk by this script.
"""

from __future__ import annotations

import ftplib
import getpass
import os
import sys
from pathlib import Path

HOST = "ftp.moseleyhost.com"
USER = "moseleyh"
# Document root for moseleyhost.com
REMOTE_DIR = "/public_html/AutoPNG"

ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "website" / "AutoPNG"


def ensure_remote_dir(ftp: ftplib.FTP, path: str) -> None:
    parts = [p for p in path.strip("/").split("/") if p]
    ftp.cwd("/")
    for part in parts:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def upload_tree(ftp: ftplib.FTP, local: Path, remote: str) -> None:
    ensure_remote_dir(ftp, remote)
    for path in sorted(local.rglob("*")):
        rel = path.relative_to(local).as_posix()
        if path.is_dir():
            ensure_remote_dir(ftp, f"{remote}/{rel}")
            continue
        remote_path = f"{remote}/{rel}"
        remote_parent = remote_path.rsplit("/", 1)[0]
        ensure_remote_dir(ftp, remote_parent)
        print(f"  put {rel}")
        with open(path, "rb") as f:
            ftp.storbinary(f"STOR {remote_path}", f)


def main() -> int:
    if not LOCAL_DIR.is_dir():
        print(f"Missing local site: {LOCAL_DIR}", file=sys.stderr)
        return 1

    password = os.environ.get("FTP_PASS") or getpass.getpass(f"FTP password for {USER}@{HOST}: ")
    print(f"Connecting to {HOST}…")
    ftp = ftplib.FTP(HOST, timeout=60)
    ftp.login(USER, password)
    ftp.set_pasv(True)
    print(f"Uploading {LOCAL_DIR} → {REMOTE_DIR}")
    upload_tree(ftp, LOCAL_DIR, REMOTE_DIR)
    ftp.quit()
    print("Done. Visit https://heyjmo.com/AutoPNG/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
