"""Project paths, settings, and one resolution function."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "settings.json"

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "paths": {
        "downloads": "downloads",
        "library": "library",
        "cache": "cache",
        "logs": "logs",
    },
    "download": {
        "format": "cbz",
        "keep_images": False,
        "chapters_workers": 4,
        "images_workers": 6,
    },
    "network": {
        "timeout": 40,
        "retries": 3,
        "cache_ttl": 21600,
    },
    "ui": {
        "theme": "ink",
        "reduce_motion": False,
        "font_scale": 100,
        "scan_on_open": True,
    },
}


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_settings(path: Path | None = None) -> dict:
    """Read settings, quarantine a corrupt file, and merge over defaults."""
    path = path or SETTINGS_PATH
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        try:
            path.replace(path.with_suffix(".json.bad"))
        except OSError:
            pass
        return copy.deepcopy(DEFAULTS)
    return deep_merge(DEFAULTS, data)


def save_settings(settings: dict, path: Path | None = None) -> None:
    """Atomic save; a slider drag never truncates the live file."""
    path = path or SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".json.part")
    part.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(part, path)


def resolve_path(value: str | Path, root: Path = ROOT) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (root / path)


def paths(settings: dict) -> dict[str, Path]:
    return {name: resolve_path(value) for name, value in settings["paths"].items()}


def workers(settings: dict) -> tuple[int, int]:
    return (
        max(1, min(8, int(settings["download"]["chapters_workers"]))),
        max(1, min(10, int(settings["download"]["images_workers"]))),
    )


def env(name: str) -> str | None:
    return os.environ.get(f"YAOI_{name}")


def resolve(settings: dict, section: str, key: str, cli_value: Any = None) -> Any:
    """CLI flag -> YAOI_* env -> settings.json -> defaults."""
    if cli_value is not None:
        return cli_value
    env_value = env(f"{section}_{key}".upper())
    if env_value is not None:
        value = settings[section][key]
        if isinstance(value, bool):
            return env_value.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(value, int):
            try:
                return int(env_value)
            except ValueError:
                pass
        return env_value
    return settings[section][key]


def ensure_dirs(settings: dict) -> dict[str, Path]:
    out = paths(settings)
    for path in out.values():
        path.mkdir(parents=True, exist_ok=True)
    return out


def frozen_root() -> Path:
    """The folder beside a frozen executable, or the checkout."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return ROOT
