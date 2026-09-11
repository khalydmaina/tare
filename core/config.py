"""Load read-only settings and limits; hash limits each cycle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = ROOT / "config" / "settings.yaml"
DEFAULT_LIMITS = ROOT / "config" / "limits.yaml"


def load_yaml(path: Path | str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping in {path}")
    return data


def load_settings(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_SETTINGS)


def load_limits(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_LIMITS)


def hash_limits(limits: dict[str, Any]) -> str:
    payload = json.dumps(limits, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class ConfigBundle:
    def __init__(
        self,
        settings_path: Path | str | None = None,
        limits_path: Path | str | None = None,
    ) -> None:
        self.settings_path = Path(settings_path or DEFAULT_SETTINGS)
        self.limits_path = Path(limits_path or DEFAULT_LIMITS)
        self.reload()

    def reload(self) -> None:
        self.settings = load_settings(self.settings_path)
        self.limits = load_limits(self.limits_path)
        self.limits_hash = hash_limits(self.limits)
