"""Candle-close scheduling helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def tf_to_minutes(tf: str) -> int:
    if tf not in TF_MINUTES:
        raise ValueError(f"unsupported timeframe: {tf}")
    return TF_MINUTES[tf]


def floor_candle_time(ts: datetime, tf: str) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    minutes = tf_to_minutes(tf)
    epoch = int(ts.timestamp())
    bucket = epoch - (epoch % (minutes * 60))
    return datetime.fromtimestamp(bucket, tz=timezone.utc)


def next_candle_close(ts: datetime, tf: str) -> datetime:
    start = floor_candle_time(ts, tf)
    return start + timedelta(minutes=tf_to_minutes(tf))


def is_stale(candle_close: datetime, now: datetime, tf: str, max_intervals: int = 2) -> bool:
    """True if the candle is older than max_intervals completed bars."""
    if candle_close.tzinfo is None:
        candle_close = candle_close.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = now - candle_close
    return age > timedelta(minutes=tf_to_minutes(tf) * max_intervals)


class CandleCloseScheduler:
    """Thin APScheduler wrapper; optional so unit tests need no running loop."""

    def __init__(self, timeframe: str = "15m") -> None:
        self.timeframe = timeframe
        self._scheduler = None

    def start(self, callback: Callable[[], None], misfire_grace_seconds: int = 30) -> None:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        minutes = tf_to_minutes(self.timeframe)
        if minutes < 60:
            # Fire a few seconds after each candle close
            trigger = CronTrigger(minute=f"*/{minutes}", second=5)
        elif minutes == 60:
            trigger = CronTrigger(minute=0, second=5)
        else:
            hours = minutes // 60
            trigger = CronTrigger(hour=f"*/{hours}", minute=0, second=5)

        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            callback,
            trigger=trigger,
            id="candle_close",
            replace_existing=True,
            misfire_grace_time=misfire_grace_seconds,
        )
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
