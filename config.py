"""Persistent settings for ImageAutoPNG."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

APP_NAME = "ImageAutoPNG"


def _config_dir() -> Path:
    """
    Prefer %USERPROFILE%\\.imageautopng so config/logs are not swallowed by
    Windows Store Python's LocalAppData virtualization (LocalCache\\Local\\...).
    """
    return Path.home() / f".{APP_NAME.lower()}"


CONFIG_DIR = _config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "convert.log"

# Legacy locations (pre-fix / Store Python virtualized)
_LEGACY_DIRS = [
    Path.home() / "AppData" / "Local" / APP_NAME,
]

DEFAULTS: dict[str, Any] = {
    "watch_folder": str(Path.home() / "Downloads"),
    "delete_originals": True,
    "convert_existing_on_start": True,
    "start_with_windows": True,
    "recursive": False,
}


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_if_needed()


def _migrate_legacy_if_needed() -> None:
    """Copy config/log from older install paths once."""
    if CONFIG_PATH.exists():
        return
    for legacy in _LEGACY_DIRS:
        legacy_cfg = legacy / "config.json"
        if legacy_cfg.exists():
            try:
                shutil.copy2(legacy_cfg, CONFIG_PATH)
                legacy_log = legacy / "convert.log"
                if legacy_log.exists() and not LOG_PATH.exists():
                    shutil.copy2(legacy_log, LOG_PATH)
            except OSError:
                pass
            return


def load_config() -> dict[str, Any]:
    ensure_config_dir()
    if not CONFIG_PATH.exists():
        cfg = dict(DEFAULTS)
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def save_config(cfg: dict[str, Any]) -> None:
    ensure_config_dir()
    cleaned = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)


def log_line(message: str) -> None:
    ensure_config_dir()
    try:
        from datetime import datetime

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except OSError:
        pass
