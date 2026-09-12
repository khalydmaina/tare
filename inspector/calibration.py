"""Calibration matrix: Wilson lower bound lookup with conservative fallback."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, Sequence

Regime = Literal["low", "mid", "high"]

DEFAULT_BUCKETS: list[tuple[int, int]] = [
    (50, 59),
    (60, 69),
    (70, 79),
    (80, 89),
    (90, 100),
]
DEFAULT_REGIMES: tuple[Regime, ...] = ("low", "mid", "high")


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    margin = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)
    return (centre - margin) / denom


def bucket_label(lo: int, hi: int) -> str:
    return f"{lo}-{hi}"


def confidence_bucket(confidence: int, buckets: Sequence[tuple[int, int]]) -> Optional[str]:
    for lo, hi in buckets:
        if lo <= confidence <= hi:
            return bucket_label(lo, hi)
    return None


@dataclass
class Cell:
    n: int = 0
    wins: int = 0

    @property
    def hit_rate(self) -> float:
        return self.wins / self.n if self.n else 0.0

    def wilson(self, z: float = 1.96) -> float:
        return wilson_lower(self.wins, self.n, z=z)

    def to_dict(self) -> dict[str, int]:
        return {"n": self.n, "wins": self.wins}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Cell":
        return cls(n=int(data.get("n", 0)), wins=int(data.get("wins", 0)))


def _cell_key(bucket: str, regime: str) -> str:
    return f"{bucket}|{regime}"


@dataclass
class CalibrationMatrix:
    buckets: list[tuple[int, int]] = field(
        default_factory=lambda: list(DEFAULT_BUCKETS)
    )
    regimes: list[str] = field(default_factory=lambda: list(DEFAULT_REGIMES))
    min_n: int = 20
    prior_p: float = 0.35
    z: float = 1.96
    frozen: bool = False
    cells: dict[str, Cell] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.buckets = [(int(a), int(b)) for a, b in self.buckets]
        if not self.cells:
            self._ensure_cells()

    def _ensure_cells(self) -> None:
        for lo, hi in self.buckets:
            label = bucket_label(lo, hi)
            for regime in self.regimes:
                key = _cell_key(label, regime)
                if key not in self.cells:
                    self.cells[key] = Cell()

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "CalibrationMatrix":
        cal = settings.get("calibration", {}) if settings else {}
        raw_buckets = cal.get("buckets", DEFAULT_BUCKETS)
        buckets = [(int(b[0]), int(b[1])) for b in raw_buckets]
        n_regimes = int(cal.get("regimes", 3))
        regimes = list(DEFAULT_REGIMES[:n_regimes])
        return cls(
            buckets=buckets,
            regimes=regimes,
            min_n=int(cal.get("min_n", 20)),
            prior_p=float(cal.get("prior_p", 0.35)),
        )

    def get_cell(self, bucket: str, regime: str) -> Cell:
        key = _cell_key(bucket, regime)
        if key not in self.cells:
            self.cells[key] = Cell()
        return self.cells[key]

    def lookup(self, confidence: int, regime: str) -> float:
        """Conservative p_cal: cell Wilson → bucket Wilson → prior_p."""
        return self.lookup_with_evidence(confidence, regime)[0]

    def lookup_with_evidence(self, confidence: int, regime: str) -> tuple[float, str, int]:
        """p_cal plus where it came from: ``cell``, ``bucket`` or ``prior``, and its n.

        The gate has to tell "measured, and the answer is no" apart from "nothing measured
        yet": the first is a veto, the second is only an absence of evidence.
        """
        bucket = confidence_bucket(confidence, self.buckets)
        if bucket is None:
            return self.prior_p, "prior", 0

        cell = self.get_cell(bucket, regime)
        if cell.n >= self.min_n:
            return cell.wilson(self.z), "cell", cell.n

        bucket_n = 0
        bucket_wins = 0
        for r in self.regimes:
            c = self.get_cell(bucket, r)
            bucket_n += c.n
            bucket_wins += c.wins
        if bucket_n >= self.min_n:
            return wilson_lower(bucket_wins, bucket_n, z=self.z), "bucket", bucket_n

        return self.prior_p, "prior", bucket_n

    def update(self, confidence: int, regime: str, won: bool) -> None:
        if self.frozen:
            return
        bucket = confidence_bucket(confidence, self.buckets)
        if bucket is None:
            return
        if regime not in self.regimes:
            return
        cell = self.get_cell(bucket, regime)
        cell.n += 1
        if won:
            cell.wins += 1

    def update_from_outcome(
        self,
        confidence: int,
        regime: str,
        result: str,
    ) -> None:
        """Map labeler result to win/loss. timeout counts as loss for calibration."""
        won = result == "win"
        self.update(confidence, regime, won)

    def freeze(self) -> None:
        self.frozen = True

    def unfreeze(self) -> None:
        self.frozen = False

    def snapshot(self) -> dict[str, Any]:
        return self.to_dict()

    def restore(self, data: dict[str, Any]) -> None:
        loaded = CalibrationMatrix.from_dict(data)
        self.buckets = loaded.buckets
        self.regimes = loaded.regimes
        self.min_n = loaded.min_n
        self.prior_p = loaded.prior_p
        self.z = loaded.z
        self.frozen = loaded.frozen
        self.cells = loaded.cells

    def to_dict(self) -> dict[str, Any]:
        return {
            "buckets": [list(b) for b in self.buckets],
            "regimes": list(self.regimes),
            "min_n": self.min_n,
            "prior_p": self.prior_p,
            "z": self.z,
            "frozen": self.frozen,
            "cells": {k: v.to_dict() for k, v in self.cells.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationMatrix":
        buckets = [(int(a), int(b)) for a, b in data.get("buckets", DEFAULT_BUCKETS)]
        regimes = list(data.get("regimes", DEFAULT_REGIMES))
        cells_raw = data.get("cells", {})
        cells = {k: Cell.from_dict(v) for k, v in cells_raw.items()}
        matrix = cls(
            buckets=buckets,
            regimes=regimes,
            min_n=int(data.get("min_n", 20)),
            prior_p=float(data.get("prior_p", 0.35)),
            z=float(data.get("z", 1.96)),
            frozen=bool(data.get("frozen", False)),
            cells=cells,
        )
        matrix._ensure_cells()
        return matrix

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "CalibrationMatrix":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def overconfidence_gap(self, bucket: str) -> Optional[float]:
        """Bucket midpoint minus pooled empirical hit rate across regimes."""
        parts = bucket.split("-")
        if len(parts) != 2:
            return None
        lo, hi = int(parts[0]), int(parts[1])
        mid = (lo + hi) / 2.0 / 100.0
        n = 0
        wins = 0
        for r in self.regimes:
            c = self.get_cell(bucket, r)
            n += c.n
            wins += c.wins
        if n == 0:
            return None
        return mid - (wins / n)

    def clone(self) -> "CalibrationMatrix":
        return CalibrationMatrix.from_dict(deepcopy(self.to_dict()))
