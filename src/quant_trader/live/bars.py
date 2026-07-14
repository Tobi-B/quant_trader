"""Realtime bar sources for mock and IBKR live trading."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol, cast, runtime_checkable

from quant_trader.core.types import Bar

try:
    import ib_insync as _loaded_ib_insync
except (ImportError, SystemExit):
    _ib_insync: object | None = None
else:
    _ib_insync = _loaded_ib_insync


class _RealtimeBar(Protocol):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class _IBAdapter:
    def __init__(self, client: object) -> None:
        self._client = client

    def request_realtime_bars(
        self,
        contract: object,
        bar_size: int,
        what_to_show: str,
        use_rth: bool,
    ) -> object:
        method_name = "reqRealTimeBars"
        request = cast(
            Callable[[object, int, str, bool], object],
            getattr(self._client, method_name),
        )
        return request(contract, bar_size, what_to_show, use_rth)

    def cancel_realtime_bars(self, bars: object) -> None:
        method_name = "cancelRealTimeBars"
        cancel = cast(Callable[[object], None], getattr(self._client, method_name))
        cancel(bars)


@runtime_checkable
class RealtimeBarSource(Protocol):
    def subscribe(self, ticker: str) -> None: ...

    async def next_bar(self) -> Bar: ...

    def stop(self) -> None: ...


class MockBarSource:
    """Queue-backed source whose bars are injected deterministically."""

    def __init__(self) -> None:
        self._subscribed: set[str] = set()
        self._bars: asyncio.Queue[Bar | None] = asyncio.Queue()
        self._stopped = False

    def subscribe(self, ticker: str) -> None:
        self._subscribed.add(ticker)

    async def next_bar(self) -> Bar:
        bar = await self._bars.get()
        if bar is None:
            raise StopAsyncIteration
        return bar

    def stop(self) -> None:
        if not self._stopped:
            self._stopped = True
            self._bars.put_nowait(None)

    def _inject(self, bar: Bar) -> None:
        self._bars.put_nowait(bar)


class IBKRBarSource:
    """Converts IBKR realtime bar events into application bars."""

    def __init__(self, ib: object | None = None) -> None:
        self._ib = _IBAdapter(ib) if ib is not None else self._new_ib_client()
        self._subscriptions: list[object] = []
        self._bars: asyncio.Queue[Bar | None] = asyncio.Queue()
        self._stopped = False

    def subscribe(self, ticker: str) -> None:
        module = self._require_ib_insync()
        stock_name = "Stock"
        stock_factory = cast(
            Callable[[str, str, str], object],
            getattr(module, stock_name),
        )
        contract = stock_factory(ticker, "SMART", "USD")
        subscription = self._ib.request_realtime_bars(contract, 5, "TRADES", False)
        self._connect_update_event(subscription)
        self._subscriptions.append(subscription)

    async def next_bar(self) -> Bar:
        bar = await self._bars.get()
        if bar is None:
            raise StopAsyncIteration
        return bar

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        for subscription in self._subscriptions:
            self._disconnect_update_event(subscription)
            self._ib.cancel_realtime_bars(subscription)
        self._subscriptions.clear()
        self._bars.put_nowait(None)

    def _on_update(self, bars: object, has_new_bar: bool) -> None:
        if not has_new_bar or self._stopped:
            return
        realtime_bars = cast(Sequence[_RealtimeBar], bars)
        if not realtime_bars:
            return
        latest = realtime_bars[-1]
        self._bars.put_nowait(
            Bar(
                timestamp=latest.time,
                open=float(latest.open),
                high=float(latest.high),
                low=float(latest.low),
                close=float(latest.close),
                adjusted_close=float(latest.close),
                volume=int(latest.volume),
            )
        )

    def _connect_update_event(self, subscription: object) -> None:
        event_name = "updateEvent"
        event = getattr(subscription, event_name)
        connect_name = "connect"
        connect = cast(
            Callable[[Callable[[object, bool], None]], object],
            getattr(event, connect_name),
        )
        connect(self._on_update)

    def _disconnect_update_event(self, subscription: object) -> None:
        event_name = "updateEvent"
        event = getattr(subscription, event_name)
        disconnect_name = "disconnect"
        disconnect = cast(
            Callable[[Callable[[object, bool], None]], object],
            getattr(event, disconnect_name),
        )
        disconnect(self._on_update)

    @staticmethod
    def _require_ib_insync() -> object:
        if _ib_insync is None:
            raise SystemExit(
                "ib_insync ist nicht installiert. Bitte `uv sync --extra live` ausfuehren."
            )
        return _ib_insync

    @classmethod
    def _new_ib_client(cls) -> _IBAdapter:
        module = cls._require_ib_insync()
        ib_name = "IB"
        ib_factory = cast(Callable[[], object], getattr(module, ib_name))
        return _IBAdapter(ib_factory())


__all__ = ["IBKRBarSource", "MockBarSource", "RealtimeBarSource"]
