"""Asynchronous live loop for realtime strategy execution."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

from quant_trader.core.logging import get_logger
from quant_trader.live.bars import RealtimeBarSource
from quant_trader.live.journal import TradeJournal
from quant_trader.live.protocol import BrokerClient
from quant_trader.live.types import OrderStatus
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.types import Action, PortfolioState

_logger = get_logger("live_loop")


@runtime_checkable
class _ConnectableBroker(Protocol):
    def connect(self) -> None: ...

    def disconnect(self) -> None: ...


@dataclass(frozen=True)
class LiveLoopSummary:
    run_id: str
    total_signals: int
    total_trades: int
    total_pnl: float


class LiveLoop:
    """Routes realtime bars through one strategy into broker orders."""

    def __init__(
        self,
        strategy: StrategyBase,
        broker: BrokerClient,
        source: RealtimeBarSource,
        journal: TradeJournal,
        run_id: str,
        duration: timedelta | None,
    ) -> None:
        self._strategy = strategy
        self._broker = broker
        self._source = source
        self._journal = journal
        self._run_id = run_id
        self._duration = duration

    async def run(self) -> LiveLoopSummary:
        if not self._strategy.ticker:
            raise ValueError("Live strategies require a ticker")
        started = time.monotonic()
        total_signals = 0
        total_trades = 0
        open_order_ids: dict[str, str] = {}
        summary: LiveLoopSummary | None = None
        _logger.info(
            "live_loop.start",
            run_id=self._run_id,
            strategy=self._strategy.name,
            ticker=self._strategy.ticker,
        )
        try:
            self._connect()
            self._source.subscribe(self._strategy.ticker)
            while True:
                remaining = self._remaining_seconds(started)
                if remaining is not None and remaining <= 0:
                    break
                try:
                    if remaining is None:
                        bar = await self._source.next_bar()
                    else:
                        bar = await asyncio.wait_for(self._source.next_bar(), timeout=remaining)
                except (StopAsyncIteration, TimeoutError):
                    break
                _logger.info(
                    "live_loop.bar_received",
                    run_id=self._run_id,
                    ticker=self._strategy.ticker,
                    timestamp=bar.timestamp.isoformat(),
                )
                portfolio = PortfolioState(cash=0.0, positions=self._broker.get_positions())
                signals = self._strategy.on_bar(bar, portfolio)
                total_signals += len(signals)
                for signal in signals:
                    _logger.info(
                        "live_loop.signal",
                        run_id=self._run_id,
                        ticker=signal.ticker,
                        action=signal.action.value,
                    )
                    if signal.action is Action.HOLD:
                        continue
                    positions = self._broker.get_positions()
                    qty = 1 if signal.action is Action.BUY else positions.get(signal.ticker, 0)
                    if qty <= 0:
                        _logger.warning(
                            "live_loop.order_skipped",
                            run_id=self._run_id,
                            ticker=signal.ticker,
                            action=signal.action.value,
                            reason="no_position_to_sell",
                        )
                        continue
                    order = self._broker.place_order(signal.ticker, signal.action, qty)
                    _logger.info(
                        "live_loop.order_placed",
                        run_id=self._run_id,
                        ticker=signal.ticker,
                        action=signal.action.value,
                        qty=qty,
                        client_order_id=order.client_order_id,
                        status=order.status.value,
                    )
                    if order.status is not OrderStatus.FILLED or order.avg_fill_price is None:
                        continue
                    if signal.action is Action.BUY:
                        try:
                            self._journal.append_open(
                                run_id=self._run_id,
                                strategy_name=self._strategy.name,
                                ticker=signal.ticker,
                                action=signal.action,
                                qty=order.filled_qty,
                                price=order.avg_fill_price,
                                client_order_id=order.client_order_id,
                                opened_at=order.updated_at,
                            )
                        except sqlite3.IntegrityError:
                            _logger.warning(
                                "live_loop.duplicate_order_skipped",
                                run_id=self._run_id,
                                client_order_id=order.client_order_id,
                            )
                            continue
                        open_order_ids[signal.ticker] = order.client_order_id
                        total_trades += 1
                    else:
                        open_order_id = open_order_ids.pop(signal.ticker, None)
                        if open_order_id is not None:
                            self._journal.close_trade(
                                client_order_id=open_order_id,
                                exit_price=order.avg_fill_price,
                                closed_at=order.updated_at,
                            )
                            _logger.info(
                                "live_loop.trade_closed",
                                run_id=self._run_id,
                                ticker=signal.ticker,
                                client_order_id=open_order_id,
                            )
            rows = self._journal.list_trades(self._run_id)
            summary = LiveLoopSummary(
                run_id=self._run_id,
                total_signals=total_signals,
                total_trades=total_trades,
                total_pnl=sum(row.pnl or 0.0 for row in rows),
            )
        finally:
            try:
                self._source.stop()
            finally:
                try:
                    self._disconnect()
                finally:
                    self._journal.close()
        if summary is None:
            raise RuntimeError("Live loop ended without a summary")
        _logger.info(
            "live_loop.complete",
            run_id=summary.run_id,
            total_signals=summary.total_signals,
            total_trades=summary.total_trades,
            total_pnl=summary.total_pnl,
        )
        return summary

    def _remaining_seconds(self, started: float) -> float | None:
        if self._duration is None:
            return None
        return self._duration.total_seconds() - (time.monotonic() - started)

    def _connect(self) -> None:
        if self._broker.is_connected():
            return
        if not isinstance(self._broker, _ConnectableBroker):
            raise RuntimeError("Broker is disconnected and cannot connect")
        self._broker.connect()
        if not self._broker.is_connected():
            raise RuntimeError("Broker connection failed")

    def _disconnect(self) -> None:
        if isinstance(self._broker, _ConnectableBroker) and self._broker.is_connected():
            self._broker.disconnect()


__all__ = ["LiveLoop", "LiveLoopSummary"]
