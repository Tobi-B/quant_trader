"""BacktestEngine: applies a strategy to historical bars and produces a BacktestResult."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import date as date_cls
from typing import cast

from quant_trader.backtest.errors import BacktestConfigError
from quant_trader.backtest.fill import FillSimulator
from quant_trader.backtest.portfolio import Portfolio
from quant_trader.backtest.sizer import PositionSizer
from quant_trader.backtest.types import (
    BacktestConfig,
    BacktestResult,
    EquitySnapshot,
    Fill,
    FillMode,
    PendingFill,
    Trade,
)
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar
from quant_trader.strategies.base import MultiTickerStrategyBase, StrategyBase
from quant_trader.strategies.types import Action, PortfolioState, Signal

log = get_logger(__name__)


class BacktestEngine:
    """Simulates a single strategy on cached bars and produces trades + equity curve.

    Supports both `StrategyBase` (single-ticker) and `MultiTickerStrategyBase`
    (universe-based) strategies. The engine owns a pending-fill queue and a
    per-ticker ledger of open positions used to compute closed Trade records
    when a SELL fills. `Portfolio` is immutable (frozen dataclass) and is
    replaced (not mutated) on every fill, which makes the engine a pure
    state machine over the portfolio.
    """

    def __init__(
        self,
        strategy: StrategyBase | MultiTickerStrategyBase,
        config: BacktestConfig,
    ) -> None:
        if config.initial_cash <= 0:
            raise BacktestConfigError(f"initial_cash muss > 0 sein (got {config.initial_cash})")
        sizer = config.sizer
        if not hasattr(sizer, "allocate"):
            raise BacktestConfigError(f"sizer hat keine allocate-Methode: {type(sizer).__name__}")
        self._strategy = strategy
        self._config = config
        self._sizer = cast(PositionSizer, sizer)
        self._commission_per_trade = config.commission_per_trade
        self._commission_per_share = config.commission_per_share
        self._stop_loss_pct = config.stop_loss_pct
        self._fill_simulator = FillSimulator(config.fill_mode, slippage_pct=config.slippage_pct)
        self._total_commission = 0.0
        self._stop_loss_count = 0

    def run(self, bars_by_ticker: dict[str, list[Bar]]) -> BacktestResult:
        if not bars_by_ticker:
            raise BacktestConfigError("bars_by_ticker ist leer")
        for ticker, bars in bars_by_ticker.items():
            if not bars:
                raise BacktestConfigError(f"bars fuer {ticker} sind leer")

        self._total_commission = 0.0
        self._stop_loss_count = 0
        start_time = time.perf_counter()
        if isinstance(self._strategy, MultiTickerStrategyBase):
            result = self._run_multi(bars_by_ticker)
        elif isinstance(self._strategy, StrategyBase):
            result = self._run_single(bars_by_ticker)
        else:
            raise BacktestConfigError(f"Unbekannter Strategy-Typ: {type(self._strategy).__name__}")
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        log.info(
            "backtest.complete",
            strategy=result.strategy_name,
            duration_ms=round(duration_ms, 2),
            bars=len(result.equity_curve),
            trades=len(result.trades),
            final_equity=round(result.final_equity, 2),
            total_commission=round(self._total_commission, 4),
            stop_loss_count=self._stop_loss_count,
        )
        return result

    def _run_single(self, bars_by_ticker: dict[str, list[Bar]]) -> BacktestResult:
        strategy = cast(StrategyBase, self._strategy)
        ticker = strategy.ticker
        if not ticker:
            raise BacktestConfigError("Single-Ticker-Strategie hat keinen ticker gesetzt")
        if ticker not in bars_by_ticker:
            raise BacktestConfigError(f"Keine Bars fuer Ticker {ticker}")
        bars = sorted(bars_by_ticker[ticker], key=lambda b: b.timestamp)
        log.info(
            "backtest.start",
            strategy=strategy.name,
            mode="single",
            ticker=ticker,
            bars=len(bars),
            fill_mode=self._config.fill_mode.value,
        )

        portfolio = Portfolio(cash=self._config.initial_cash)
        open_positions: dict[str, _OpenPosition] = {}
        pending: list[PendingFill] = []
        trades: list[Trade] = []
        equity_curve: list[EquitySnapshot] = []

        for i, bar in enumerate(bars):
            self._check_stop_losses(
                ticker=ticker,
                ticker_bars=bars,
                current_index=i,
                bar=bar,
                open_positions=open_positions,
                pending=pending,
            )
            signals = strategy.on_bar(bar, _portfolio_state(portfolio))
            for sig in signals:
                self._schedule(sig, ticker, bars, i, pending)
            portfolio, open_positions, trades = self._process_pending(
                pending=pending,
                current_bar=bar,
                portfolio=portfolio,
                open_positions=open_positions,
                trades=trades,
            )
            prices = {ticker: bar.adjusted_close}
            equity_curve.append(_snapshot(bar.timestamp.date(), portfolio, prices))

        return _build_result(
            strategy=strategy,
            config=self._config,
            bars=bars,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _run_multi(self, bars_by_ticker: dict[str, list[Bar]]) -> BacktestResult:
        strategy = cast(MultiTickerStrategyBase, self._strategy)
        sorted_by_ticker: dict[str, list[Bar]] = {
            t: sorted(bars, key=lambda b: b.timestamp) for t, bars in bars_by_ticker.items()
        }
        total_bars = sum(len(b) for b in sorted_by_ticker.values())
        log.info(
            "backtest.start",
            strategy=strategy.name,
            mode="multi",
            tickers=sorted(sorted_by_ticker.keys()),
            bars=total_bars,
            fill_mode=self._config.fill_mode.value,
        )

        bars_by_date: dict[date_cls, dict[str, Bar]] = defaultdict(dict)
        for ticker, bars in sorted_by_ticker.items():
            for bar in bars:
                bars_by_date[bar.timestamp.date()][ticker] = bar

        portfolio = Portfolio(cash=self._config.initial_cash)
        open_positions: dict[str, _OpenPosition] = {}
        pending: list[PendingFill] = []
        trades: list[Trade] = []
        equity_curve: list[EquitySnapshot] = []
        all_bars_flat: list[Bar] = [b for bars in sorted_by_ticker.values() for b in bars]

        for ts_date in sorted(bars_by_date.keys()):
            bars_at_date = bars_by_date[ts_date]
            ts_dt = next(iter(bars_at_date.values())).timestamp
            for tkr in sorted(bars_at_date.keys()):
                ticker_bars = sorted_by_ticker.get(tkr, [])
                bar_at_date = bars_at_date.get(tkr)
                if not ticker_bars or bar_at_date is None:
                    continue
                idx = _index_of_bar(ticker_bars, bar_at_date)
                if idx < 0:
                    continue
                self._check_stop_losses(
                    ticker=tkr,
                    ticker_bars=ticker_bars,
                    current_index=idx,
                    bar=bar_at_date,
                    open_positions=open_positions,
                    pending=pending,
                )
            signals = strategy.on_universe_bars(
                ts_dt, dict(bars_at_date), _portfolio_state(portfolio)
            )
            for sig in signals:
                ticker = sig.ticker
                ticker_bars = sorted_by_ticker.get(ticker, [])
                bar_at_date = bars_at_date.get(ticker)
                if not ticker_bars or bar_at_date is None:
                    continue
                idx = _index_of_bar(ticker_bars, bar_at_date)
                if idx < 0:
                    continue
                self._schedule(sig, ticker, ticker_bars, idx, pending)
            portfolio, open_positions, trades = self._process_pending(
                pending=pending,
                current_bar=next(iter(bars_at_date.values())),
                portfolio=portfolio,
                open_positions=open_positions,
                trades=trades,
            )
            prices = {t: b.adjusted_close for t, b in bars_at_date.items()}
            equity_curve.append(_snapshot(ts_date, portfolio, prices))

        first_date = min(b.timestamp.date() for b in all_bars_flat)
        last_date = max(b.timestamp.date() for b in all_bars_flat)
        return _build_result(
            strategy=self._strategy,
            config=self._config,
            bars=all_bars_flat,
            trades=trades,
            equity_curve=equity_curve,
            start=first_date,
            end=last_date,
        )

    def _schedule(
        self,
        signal: Signal,
        ticker: str,
        bars: list[Bar],
        current_index: int,
        pending: list[PendingFill],
    ) -> None:
        if signal.action is Action.HOLD:
            return
        try:
            pending.append(self._fill_simulator.schedule(signal, bars, current_index))
        except ValueError as exc:
            log.warning(
                "backtest.fill_skipped",
                ticker=ticker,
                reason=str(exc),
                signal_action=str(signal.action.value),
            )

    def _check_stop_losses(
        self,
        *,
        ticker: str,
        ticker_bars: list[Bar],
        current_index: int,
        bar: Bar,
        open_positions: dict[str, _OpenPosition],
        pending: list[PendingFill],
    ) -> None:
        if self._stop_loss_pct is None:
            return
        pos = open_positions.get(ticker)
        if pos is None or pos.qty <= 0:
            return
        threshold = pos.entry_price * (1.0 - self._stop_loss_pct / 100.0)
        if float(bar.open) >= threshold:
            return
        stop_loss_signal = Signal(
            timestamp=bar.timestamp,
            ticker=ticker,
            action=Action.SELL,
            reason="stop_loss",
        )
        self._schedule(stop_loss_signal, ticker, ticker_bars, current_index, pending)
        self._stop_loss_count += 1
        log.warning(
            "backtest.stop_loss",
            ticker=ticker,
            entry_price=pos.entry_price,
            trigger_price=float(bar.open),
            stop_loss_pct=self._stop_loss_pct,
        )

    def _commission_for(self, qty: int) -> float:
        if qty <= 0:
            return 0.0
        return max(self._commission_per_trade, qty * self._commission_per_share)

    def _process_pending(
        self,
        *,
        pending: list[PendingFill],
        current_bar: Bar,
        portfolio: Portfolio,
        open_positions: dict[str, _OpenPosition],
        trades: list[Trade],
    ) -> tuple[Portfolio, dict[str, _OpenPosition], list[Trade]]:
        still_pending: list[PendingFill] = []
        for pf in pending:
            if pf.execute_on.timestamp > current_bar.timestamp:
                still_pending.append(pf)
                continue
            fill = self._fill_simulator.resolve(pf)
            portfolio, open_positions, trades = self._apply_fill(
                fill=fill,
                portfolio=portfolio,
                open_positions=open_positions,
                trades=trades,
            )
        pending.clear()
        pending.extend(still_pending)
        return portfolio, open_positions, trades

    def _apply_fill(
        self,
        *,
        fill: Fill,
        portfolio: Portfolio,
        open_positions: dict[str, _OpenPosition],
        trades: list[Trade],
    ) -> tuple[Portfolio, dict[str, _OpenPosition], list[Trade]]:
        ticker = fill.ticker
        if fill.action == "BUY":
            if portfolio.position_qty(ticker) > 0:
                log.debug(
                    "backtest.rebuy_noop",
                    ticker=ticker,
                    current_qty=portfolio.position_qty(ticker),
                )
                return portfolio, open_positions, trades
            sizing = self._sizer.allocate(
                price=fill.price,
                available_cash=portfolio.cash,
                n_open_positions=portfolio.n_open_positions(),
            )
            if sizing.skipped or sizing.qty <= 0:
                log.warning(
                    "backtest.insufficient_cash",
                    ticker=ticker,
                    price=fill.price,
                    cash=round(portfolio.cash, 2),
                )
                return portfolio, open_positions, trades
            commission = self._commission_for(sizing.qty)
            self._total_commission += commission
            new_portfolio = portfolio.with_cash(-sizing.allocated_cash - commission).with_position(
                ticker, sizing.qty
            )
            new_open_positions = dict(open_positions)
            new_open_positions[ticker] = _OpenPosition(
                entry_date=fill.timestamp.date(),
                entry_price=fill.price,
                qty=sizing.qty,
                entry_commission=commission,
            )
            log.info(
                "backtest.buy_filled",
                ticker=ticker,
                qty=sizing.qty,
                price=fill.price,
                allocated=round(sizing.allocated_cash, 2),
                fee=round(commission, 4),
                cash_after=round(new_portfolio.cash, 2),
            )
            return new_portfolio, new_open_positions, trades
        if fill.action == "SELL":
            qty = portfolio.position_qty(ticker)
            if qty <= 0:
                log.warning("backtest.sell_no_position", ticker=ticker)
                return portfolio, open_positions, trades
            entry = open_positions.get(ticker)
            entry_date = entry.entry_date if entry is not None else fill.timestamp.date()
            entry_price = entry.entry_price if entry is not None else fill.price
            entry_commission = entry.entry_commission if entry is not None else 0.0
            proceeds = qty * fill.price
            exit_commission = self._commission_for(qty)
            self._total_commission += exit_commission
            new_portfolio = portfolio.with_cash(proceeds - exit_commission).with_position(
                ticker, -qty
            )
            new_open_positions = dict(open_positions)
            new_open_positions.pop(ticker, None)
            pnl = proceeds - entry_commission - exit_commission - qty * entry_price
            pnl_pct = (pnl / (qty * entry_price)) if entry_price > 0 else 0.0
            new_trade = Trade(
                ticker=ticker,
                entry_date=entry_date,
                entry_price=entry_price,
                exit_date=fill.timestamp.date(),
                exit_price=fill.price,
                pnl=round(pnl, 4),
                pnl_pct=round(pnl_pct, 6),
            )
            new_trades = [*trades, new_trade]
            log.info(
                "backtest.sell_filled",
                ticker=ticker,
                qty=qty,
                price=fill.price,
                proceeds=round(proceeds, 2),
                fee=round(exit_commission, 4),
                pnl=round(pnl, 2),
            )
            return new_portfolio, new_open_positions, new_trades
        log.warning("backtest.unknown_action", ticker=ticker, action=fill.action)
        return portfolio, open_positions, trades


class _OpenPosition:
    __slots__ = ("entry_commission", "entry_date", "entry_price", "qty")

    def __init__(
        self,
        entry_date: date_cls,
        entry_price: float,
        qty: int,
        entry_commission: float = 0.0,
    ) -> None:
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.qty = qty
        self.entry_commission = entry_commission


def _portfolio_state(portfolio: Portfolio) -> PortfolioState:
    return PortfolioState(cash=portfolio.cash, positions=dict(portfolio.positions))


def _snapshot(
    snapshot_date: date_cls, portfolio: Portfolio, prices: dict[str, float]
) -> EquitySnapshot:
    return EquitySnapshot(
        date=snapshot_date,
        equity=round(portfolio.equity(prices), 2),
        cash=round(portfolio.cash, 2),
        positions=dict(portfolio.positions),
    )


def _index_of_bar(bars: list[Bar], target: Bar) -> int:
    for i, b in enumerate(bars):
        if b.timestamp == target.timestamp:
            return i
    return -1


def _build_result(
    *,
    strategy: StrategyBase | MultiTickerStrategyBase,
    config: BacktestConfig,
    bars: list[Bar],
    trades: list[Trade],
    equity_curve: list[EquitySnapshot],
    start: date_cls | None = None,
    end: date_cls | None = None,
) -> BacktestResult:
    if not bars:
        raise BacktestConfigError("build_result ohne bars aufgerufen")
    first_date = start if start is not None else bars[0].timestamp.date()
    last_date = end if end is not None else bars[-1].timestamp.date()
    final_equity = equity_curve[-1].equity if equity_curve else config.initial_cash
    return BacktestResult(
        strategy_name=strategy.name,
        params=dict(getattr(strategy, "params", {})),
        start=first_date,
        end=last_date,
        fill_mode=FillMode(config.fill_mode),
        initial_cash=config.initial_cash,
        final_equity=round(final_equity, 2),
        trades=trades,
        equity_curve=equity_curve,
    )
