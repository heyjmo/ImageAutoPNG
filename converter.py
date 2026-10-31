"""Convert .webp / .heic / .heif / .avif images to PNG."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PIL import Image

# Pillow wheels include an AVIF decoder. Importing the plugin registers .avif
# with Image.open, including inside the frozen installer.
try:
    from PIL import AvifImagePlugin  # noqa: F401

    AVIF_AVAILABLE = True
except ImportError:
    AVIF_AVAILABLE = False

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

from config import log_line

SUPPORTED_EXTENSIONS = {".webp", ".heic", ".heif", ".avif"}

# One conversion at a time per file path (scan + watcher can race)
_locks_guard = threading.Lock()
_path_locks: dict[str, threading.Lock] = {}


def _lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve()) if path.exists() else str(path).lower()
    with _locks_guard:
        if key not in _path_locks:
            _path_locks[key] = threading.Lock()
        return _path_locks[key]


def is_convertible(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file()


def wait_until_stable(path: Path, checks: int = 4, interval: float = 0.35) -> bool:
    """Wait until file size stops changing (download finished)."""
    last_size = -1
    stable = 0
    for _ in range(40):
        try:
            if not path.exists():
                return False
            size = path.stat().st_size
            if size == 0:
                time.sleep(interval)
                continue
            if size == last_size:
                stable += 1
                if stable >= checks:
                    return True
            else:
                stable = 0
                last_size = size
        except OSError:
            pass
        time.sleep(interval)
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def convert_to_png(src: Path, delete_original: bool = True) -> Path | None:
    """
    Convert a supported image to PNG next to the source.
    Returns the PNG path on success, None on failure/skip.
    """
    if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None
    if not src.is_file():
        return None

    lock = _lock_for(src)
    if not lock.acquire(blocking=False):
        # Another thread is already converting this file
        return None

    try:
        if not src.is_file():
            return None

        dest = src.with_suffix(".png")
        try:
            if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
                if delete_original:
                    try:
                        src.unlink(missing_ok=True)
                        log_line(f"Skipped (PNG exists), removed original: {src.name}")
                    except OSError as e:
                        log_line(f"PNG exists but could not remove original {src.name}: {e}")
                else:
                    log_line(f"Skipped (PNG exists): {src.name}")
                return dest
        except OSError:
            pass

        if not wait_until_stable(src):
            log_line(f"Unstable or empty, skipped: {src.name}")
            return None

        try:
            with Image.open(src) as im:
                # Preserve transparency when present
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    converted = im.convert("RGBA")
                else:
                    converted = im.convert("RGB")
                converted.save(dest, format="PNG", optimize=True)

            if delete_original:
                try:
                    src.unlink(missing_ok=True)
                except OSError as e:
                    log_line(f"Converted but could not delete original {src.name}: {e}")

            log_line(f"Converted: {src.name} -> {dest.name}")
            return dest
        except Exception as e:
            log_line(f"Failed {src.name}: {e}")
            return None
    finally:
        lock.release()


def scan_folder(folder: Path, delete_original: bool = True, recursive: bool = False) -> int:
    """Convert all supported images currently in folder. Returns count converted."""
    if not folder.is_dir():
        return 0
    count = 0
    pattern = "**/*" if recursive else "*"
    for path in folder.glob(pattern):
        if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file():
            if convert_to_png(path, delete_original=delete_original):
                count += 1
    return count
