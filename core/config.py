"""Load read-only settings and limits; hash limits each cycle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = ROOT / "config" / "settings.yaml"
DEFAULT_LIMITS = ROOT / "config" / "limits.yaml"


def resolve_path(value: Path | str) -> Path:
    """Anchor relative paths at the repo root so scripts agree wherever they run from."""
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def db_path(settings: dict[str, Any] | None = None) -> Path:
    """Flight Recorder database shared by the live loop, exporter, harness and dashboard.

    TARE_DB wins when set; otherwise recorder.db_path from settings.yaml.
    """
    configured = os.getenv("TARE_DB") or (
        (settings if settings is not None else load_settings()).get("recorder") or {}
    ).get("db_path", "data/tare.db")
    return resolve_path(configured)


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
