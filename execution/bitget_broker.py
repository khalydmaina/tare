"""Bitget paper broker: live demo API when keyed, else local simulation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import httpx

from core.config import load_settings
from core.schemas import AccountState, Side

logger = logging.getLogger(__name__)

SideLike = Union[Side, str]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_side(side: SideLike) -> Side:
    if isinstance(side, Side):
        return side
    return Side(str(side).lower())


def _round_lot(size: float, lot_step: float) -> float:
    if lot_step <= 0:
        return size
    steps = round(size / lot_step)
    if steps <= 0 and size > 0:
        steps = 1
    return round(steps * lot_step, 10)


def apply_slippage(price: float, side: Side, slippage_bps: float, *, is_entry: bool = True) -> float:
    """Adverse slippage in bps. Entry long pays up; entry short sells down."""
    slip = slippage_bps / 10_000.0
    if side == Side.LONG:
        return price * (1.0 + slip) if is_entry else price * (1.0 - slip)
    return price * (1.0 - slip) if is_entry else price * (1.0 + slip)


def fee_notional(notional: float, fee_bps: float) -> float:
    return abs(notional) * (fee_bps / 10_000.0)


def exchange_size(size: float, spec: dict[str, float]) -> float:
    """Round a size DOWN to the contract's size step, so rounding never adds risk."""
    step = 10.0 ** -int(spec.get("volume_place", 3))
    step = max(step, float(spec.get("size_multiplier") or 0.0))
    return round(math.floor(size / step + 1e-9) * step, 10)


def exchange_price(price: float, spec: dict[str, float]) -> str:
    places = int(spec.get("price_place", 2))
    return f"{price:.{places}f}"


@dataclass
class Position:
    order_id: str
    symbol: str
    side: Side
    size: float
    entry: float
    sl: float
    tp: float
    fill_price: float
    fees: float
    opened_at: datetime
    status: str = "open"
    exit_price: Optional[float] = None
    closed_at: Optional[datetime] = None
    exchange_order_id: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


def _position_to_dict(p: Position) -> dict[str, Any]:
    return {
        "order_id": p.order_id,
        "symbol": p.symbol,
        "side": p.side.value,
        "size": p.size,
        "entry": p.entry,
        "sl": p.sl,
        "tp": p.tp,
        "fill_price": p.fill_price,
        "fees": p.fees,
        "opened_at": p.opened_at.isoformat(),
        "exchange_order_id": p.exchange_order_id,
        "meta": p.meta,
    }


def _position_from_dict(d: dict[str, Any]) -> Position:
    return Position(
        order_id=str(d["order_id"]),
        symbol=str(d["symbol"]),
        side=_as_side(d["side"]),
        size=float(d["size"]),
        entry=float(d["entry"]),
        sl=float(d["sl"]),
        tp=float(d["tp"]),
        fill_price=float(d["fill_price"]),
        fees=float(d["fees"]),
        opened_at=datetime.fromisoformat(d["opened_at"]),
        exchange_order_id=d.get("exchange_order_id"),
        meta=dict(d.get("meta") or {}),
    )


class PaperModeAccount:
    """Equity, positions and hard-limit state for paper trading; restart-safe via to_dict()."""

    def __init__(self, equity: float = 10_000.0) -> None:
        self.starting_equity = float(equity)
        self.cash = float(equity)
        self.equity = float(equity)
        self.peak_equity = float(equity)
        self.day_start_equity = float(equity)
        self.day = _utcnow().date().isoformat()
        self.positions: dict[str, Position] = {}
        self.closed: list[Position] = []
        self.order_log: list[dict[str, Any]] = []
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        # (losses in a row, cooldown hours); the live loop refreshes this from limits.yaml
        self.loss_cooldown: tuple[int, float] = (3, 4.0)

    def roll_day(self, now: Optional[datetime] = None) -> None:
        """The daily-loss baseline resets at 00:00 UTC."""
        today = (now or _utcnow()).astimezone(timezone.utc).date().isoformat()
        if today != self.day:
            self.day = today
            self.day_start_equity = self.equity

    def open_notional(self) -> float:
        return sum(abs(p.fill_price * p.size) for p in self.positions.values())

    def to_account_state(self) -> AccountState:
        by_sym: dict[str, int] = {}
        for p in self.positions.values():
            by_sym[p.symbol] = by_sym.get(p.symbol, 0) + 1
        notional = self.open_notional()
        return AccountState(
            equity=self.equity,
            available=max(0.0, self.cash),
            peak_equity=self.peak_equity,
            day_start_equity=self.day_start_equity,
            open_positions=len(self.positions),
            positions_by_symbol=by_sym,
            consecutive_losses=self.consecutive_losses,
            cooldown_until=self.cooldown_until,
            leverage=notional / self.equity if self.equity > 0 else 0.0,
            open_notional=notional,
        )

    def register_open(self, pos: Position) -> None:
        self.positions[pos.order_id] = pos
        self.cash -= pos.fees
        self.equity = self.cash + self._unrealized(mark=None)
        self.peak_equity = max(self.peak_equity, self.equity)

    def register_close(
        self, pos: Position, pnl: float, exit_fees: float, now: Optional[datetime] = None
    ) -> None:
        self.positions.pop(pos.order_id, None)
        self.cash += pnl - exit_fees
        self.equity = self.cash
        self.peak_equity = max(self.peak_equity, self.equity)
        self.closed.append(pos)
        if pnl - exit_fees < 0:
            self.consecutive_losses += 1
            losses, hours = self.loss_cooldown
            if losses > 0 and self.consecutive_losses >= losses:
                self.cooldown_until = (now or _utcnow()) + timedelta(hours=float(hours))
                self.consecutive_losses = 0
        else:
            self.consecutive_losses = 0

    def _unrealized(self, mark: Optional[float]) -> float:
        # Mark-to-entry until an external mark is supplied; PnL realized on close.
        _ = mark
        return 0.0

    def mark_equity(self, marks: Optional[dict[str, float]] = None) -> float:
        unrealized = 0.0
        if marks:
            for p in self.positions.values():
                m = marks.get(p.symbol)
                if m is None:
                    continue
                if p.side == Side.LONG:
                    unrealized += (m - p.fill_price) * p.size
                else:
                    unrealized += (p.fill_price - m) * p.size
        self.equity = self.cash + unrealized
        self.peak_equity = max(self.peak_equity, self.equity)
        return self.equity

    def to_dict(self) -> dict[str, Any]:
        return {
            "starting_equity": self.starting_equity,
            "cash": self.cash,
            "equity": self.equity,
            "peak_equity": self.peak_equity,
            "day_start_equity": self.day_start_equity,
            "day": self.day,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "positions": [_position_to_dict(p) for p in self.positions.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaperModeAccount":
        acct = cls(float(data.get("starting_equity", 10_000.0)))
        for key in ("cash", "equity", "peak_equity", "day_start_equity"):
            if key in data:
                setattr(acct, key, float(data[key]))
        acct.day = str(data.get("day", acct.day))
        acct.consecutive_losses = int(data.get("consecutive_losses", 0))
        cooldown = data.get("cooldown_until")
        acct.cooldown_until = datetime.fromisoformat(cooldown) if cooldown else None
        for raw in data.get("positions", []):
            pos = _position_from_dict(raw)
            acct.positions[pos.order_id] = pos
        return acct


class PaperBroker:
    """Market orders with attached SL/TP on Bitget demo, or local sim fills."""

    BASE = "https://api.bitget.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        *,
        paper: bool = True,
        starting_equity: float = 10_000.0,
        slippage_bps: Optional[float] = None,
        fee_bps: Optional[float] = None,
        lot_step: Optional[float] = None,
        timeout: float = 20.0,
        account: Optional[PaperModeAccount] = None,
    ) -> None:
        settings = load_settings()
        ex = settings.get("execution", {})
        self.api_key = api_key if api_key is not None else os.getenv("BITGET_API_KEY", "")
        self.api_secret = api_secret if api_secret is not None else os.getenv("BITGET_API_SECRET", "")
        self.passphrase = passphrase if passphrase is not None else os.getenv("BITGET_PASSPHRASE", "")
        self.paper = paper
        self.timeout = timeout
        self.slippage_bps = float(slippage_bps if slippage_bps is not None else ex.get("slippage_bps", 5))
        self.fee_bps = float(fee_bps if fee_bps is not None else ex.get("fee_bps", 4))
        self.lot_step = float(lot_step if lot_step is not None else ex.get("lot_step", 0.001))
        self.account = account or PaperModeAccount(starting_equity)
        self._use_api = bool(self.api_key and self.api_secret and self.passphrase)
        self._specs: dict[str, dict[str, float]] = {}

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        prehash = f"{ts}{method.upper()}{path}{body}"
        sign = base64.b64encode(
            hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
        ).decode()
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US",
        }
        if self.paper:
            headers["paptrading"] = "1"
        return headers

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        body_str = json.dumps(payload)
        headers = self._headers("POST", path, body_str)
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.BASE}{path}", content=body_str, headers=headers)
            r.raise_for_status()
            data = r.json()
        if isinstance(data, dict) and data.get("code") not in (None, "00000"):
            raise RuntimeError(f"Bitget error: {data}")
        return data.get("data", data) if isinstance(data, dict) else data

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        q = ""
        if params:
            q = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._headers("GET", path + q)
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.BASE}{path}", params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        if isinstance(data, dict) and data.get("code") not in (None, "00000"):
            raise RuntimeError(f"Bitget error: {data}")
        return data.get("data", data) if isinstance(data, dict) else data

    def _sim_fill_price(
        self,
        side: Side,
        *,
        next_open: Optional[float] = None,
        last_price: Optional[float] = None,
        entry: Optional[float] = None,
    ) -> float:
        base = next_open if next_open is not None else last_price
        if base is None:
            base = entry
        if base is None or base <= 0:
            raise ValueError("need next_open, last_price, or entry for simulated fill")
        return apply_slippage(float(base), side, self.slippage_bps, is_entry=True)

    def place_order(
        self,
        symbol: str,
        side: SideLike,
        size: float,
        entry: float,
        sl: float,
        tp: float,
        *,
        next_open: Optional[float] = None,
        last_price: Optional[float] = None,
    ) -> dict[str, Any]:
        """Place a market order with attached SL/TP. Returns order/fill dict."""
        side_e = _as_side(side)
        bg_symbol = symbol if str(symbol).endswith("USDT") else f"{symbol}USDT"
        qty = _round_lot(float(size), self.lot_step)
        if qty <= 0:
            raise ValueError("size rounds to zero")

        exchange_order_id: Optional[str] = None
        mode = "sim"
        fill_price: Optional[float] = None

        if self._use_api:
            try:
                fill_price, exchange_order_id, qty = self._place_api_order(
                    bg_symbol, side_e, qty, sl, tp
                )
                mode = "api"
            except Exception as exc:
                logger.warning("Bitget paper API place failed (%s); simulating fill", exc)

        if fill_price is None:
            fill_price = self._sim_fill_price(
                side_e, next_open=next_open, last_price=last_price, entry=entry
            )

        notional = fill_price * qty
        fees = fee_notional(notional, self.fee_bps)
        order_id = exchange_order_id or f"sim-{uuid.uuid4().hex[:12]}"
        pos = Position(
            order_id=order_id,
            symbol=bg_symbol,
            side=side_e,
            size=qty,
            entry=float(entry),
            sl=float(sl),
            tp=float(tp),
            fill_price=fill_price,
            fees=fees,
            opened_at=_utcnow(),
            exchange_order_id=exchange_order_id,
            meta={"mode": mode, "proposed_entry": float(entry)},
        )
        self.account.register_open(pos)
        record = {
            "order_id": order_id,
            "exchange_order_id": exchange_order_id,
            "symbol": bg_symbol,
            "side": side_e.value,
            "size": qty,
            "entry": float(entry),
            "fill_price": fill_price,
            "sl": float(sl),
            "tp": float(tp),
            "fees": fees,
            "mode": mode,
            "status": "open",
            "ts": pos.opened_at.isoformat(),
        }
        self.account.order_log.append(record)
        logger.info(
            "order placed id=%s fill=%.6f fees=%.6f mode=%s side=%s size=%s",
            order_id,
            fill_price,
            fees,
            mode,
            side_e.value,
            qty,
        )
        return record

    def _contract_spec(self, symbol: str) -> dict[str, float]:
        """Size and price precision for a USDT-M contract, fetched once per symbol."""
        if symbol not in self._specs:
            data = self._get(
                "/api/v2/mix/market/contracts",
                params={"productType": "USDT-FUTURES", "symbol": symbol},
            )
            row = data[0] if isinstance(data, list) and data else data
            row = row if isinstance(row, dict) else {}
            self._specs[symbol] = {
                "volume_place": float(row.get("volumePlace") or 3),
                "price_place": float(row.get("pricePlace") or 2),
                "size_multiplier": float(row.get("sizeMultiplier") or 0),
                "min_trade_num": float(row.get("minTradeNum") or 0),
            }
        return self._specs[symbol]

    def _place_api_order(
        self,
        symbol: str,
        side: Side,
        size: float,
        sl: float,
        tp: float,
    ) -> tuple[float, str, float]:
        spec = self._contract_spec(symbol)
        qty = exchange_size(size, spec)
        if qty <= 0 or qty < spec["min_trade_num"]:
            raise ValueError(f"size {size} is below the {symbol} contract minimum")
        # Hedge-mode open: long → buy/open, short → sell/open
        bg_side = "buy" if side == Side.LONG else "sell"
        payload = {
            "symbol": symbol,
            "productType": "USDT-FUTURES",
            "marginMode": "crossed",
            "marginCoin": "USDT",
            "size": f"{qty:.{int(spec['volume_place'])}f}",
            "side": bg_side,
            "tradeSide": "open",
            "orderType": "market",
            "clientOid": uuid.uuid4().hex[:32],
            "presetStopSurplusPrice": exchange_price(tp, spec),
            "presetStopLossPrice": exchange_price(sl, spec),
        }
        data = self._post("/api/v2/mix/order/place-order", payload)
        oid = str(data.get("orderId") or data.get("clientOid") or "")
        if not oid:
            raise RuntimeError(f"no orderId in response: {data}")
        fill = self._fetch_fill_price(symbol, oid)
        return fill, oid, qty

    def _fetch_fill_price(self, symbol: str, order_id: str) -> float:
        try:
            data = self._get(
                "/api/v2/mix/order/detail",
                params={
                    "symbol": symbol,
                    "productType": "USDT-FUTURES",
                    "orderId": order_id,
                },
            )
            if isinstance(data, dict):
                for key in ("priceAvg", "fillPrice", "price"):
                    if data.get(key) not in (None, "", "0"):
                        return float(data[key])
        except Exception as exc:
            logger.warning("fill detail fetch failed: %s", exc)
        # Fallback: ticker last
        raw = self._get(
            "/api/v2/mix/market/ticker",
            params={"symbol": symbol, "productType": "USDT-FUTURES"},
        )
        if isinstance(raw, list) and raw:
            return float(raw[0].get("lastPr") or raw[0].get("last"))
        if isinstance(raw, dict):
            return float(raw.get("lastPr") or raw.get("last"))
        raise RuntimeError("unable to determine fill price")

    def close_order(
        self,
        order_id: str,
        *,
        price: Optional[float] = None,
        next_open: Optional[float] = None,
        last_price: Optional[float] = None,
    ) -> dict[str, Any]:
        """Close an open position. `price` is the level the labeler says it exited at."""
        pos = self.account.positions.get(order_id)
        if pos is None:
            raise KeyError(f"no open position {order_id}")

        exit_px = price
        mode = pos.meta.get("mode", "sim")
        if mode == "api" and self._use_api:
            try:
                exit_px = self._close_api_position(pos)
            except Exception as exc:
                # Usually the exchange already closed it at the attached SL/TP.
                logger.warning("Bitget paper API close failed (%s); booking exit at %s", exc, price)
                exit_px = price

        if exit_px is None:
            base = next_open if next_open is not None else last_price
            if base is None:
                base = pos.fill_price
            exit_px = apply_slippage(float(base), pos.side, self.slippage_bps, is_entry=False)

        if pos.side == Side.LONG:
            pnl = (exit_px - pos.fill_price) * pos.size
        else:
            pnl = (pos.fill_price - exit_px) * pos.size
        exit_fees = fee_notional(exit_px * pos.size, self.fee_bps)
        pos.status = "closed"
        pos.exit_price = exit_px
        pos.closed_at = _utcnow()
        self.account.register_close(pos, pnl, exit_fees)
        record = {
            "order_id": order_id,
            "symbol": pos.symbol,
            "side": pos.side.value,
            "size": pos.size,
            "fill_price": pos.fill_price,
            "exit_price": exit_px,
            "fees": pos.fees + exit_fees,
            "pnl": pnl - exit_fees,
            "status": "closed",
            "ts": pos.closed_at.isoformat(),
        }
        self.account.order_log.append(record)
        logger.info(
            "order closed id=%s exit=%.6f pnl=%.6f fees=%.6f",
            order_id,
            exit_px,
            pnl - exit_fees,
            pos.fees + exit_fees,
        )
        return record

    def _close_api_position(self, pos: Position) -> float:
        bg_side = "sell" if pos.side == Side.LONG else "buy"
        # Bitget rejects a size with more decimals than the contract allows ("44.0" for a 0-place coin)
        spec = self._contract_spec(pos.symbol)
        payload = {
            "symbol": pos.symbol,
            "productType": "USDT-FUTURES",
            "marginMode": "crossed",
            "marginCoin": "USDT",
            "size": f"{pos.size:.{int(spec['volume_place'])}f}",
            "side": bg_side,
            "tradeSide": "close",
            "orderType": "market",
            "clientOid": uuid.uuid4().hex[:32],
        }
        data = self._post("/api/v2/mix/order/place-order", payload)
        oid = str(data.get("orderId") or "")
        return self._fetch_fill_price(pos.symbol, oid) if oid else pos.fill_price

    def get_open_positions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in self.account.positions.values():
            out.append(
                {
                    "order_id": p.order_id,
                    "exchange_order_id": p.exchange_order_id,
                    "symbol": p.symbol,
                    "side": p.side.value,
                    "size": p.size,
                    "entry": p.entry,
                    "fill_price": p.fill_price,
                    "sl": p.sl,
                    "tp": p.tp,
                    "fees": p.fees,
                    "status": p.status,
                    "opened_at": p.opened_at.isoformat(),
                }
            )
        return out
