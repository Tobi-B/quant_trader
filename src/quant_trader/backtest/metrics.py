"""MetricsCalculator: derives key performance metrics from a BacktestResult."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from quant_trader.backtest.types import BacktestResult, EquitySnapshot, Trade

TRADING_DAYS_PER_YEAR: int = 252


@dataclass(frozen=True)
class Metrics:
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float | None
    max_drawdown_pct: float
    win_rate_pct: float | None
    n_trades: int
    exposure_pct: float


class EquityCurveStats:
    """Pure helpers for stats derived from an equity curve.

    All inputs are lists/snapshots from a `BacktestResult`; helpers do not
    mutate inputs and are safe to call with degenerate inputs (0/1 elements).
    """

    def compute_returns(self, equity_curve: Sequence[EquitySnapshot]) -> list[float]:
        if not equity_curve:
            return []
        out: list[float] = [0.0]
        prev = float(equity_curve[0].equity)
        for snap in equity_curve[1:]:
            current = float(snap.equity)
            if prev <= 0:
                out.append(0.0)
            else:
                out.append(current / prev - 1.0)
            prev = current
        return out

    def cagr_pct(
        self,
        equity_curve: Sequence[EquitySnapshot],
        initial_cash: float,
    ) -> float:
        if not equity_curve or initial_cash <= 0:
            return 0.0
        final_equity = float(equity_curve[-1].equity)
        n_periods = len(equity_curve) - 1
        if n_periods < 1:
            return 0.0
        years: float = float(n_periods) / float(TRADING_DAYS_PER_YEAR)
        if years <= 0:
            return 0.0
        if final_equity <= 0:
            return -100.0
        ratio: float = final_equity / initial_cash
        if ratio <= 0:
            return -100.0
        return (math.pow(ratio, 1.0 / years) - 1.0) * 100.0

    def sharpe(
        self,
        returns: Sequence[float],
    ) -> float | None:
        if len(returns) < 2:
            return None
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(variance)
        if std == 0:
            return None
        return (mean / std) * math.sqrt(TRADING_DAYS_PER_YEAR)

    def max_drawdown_pct(self, equity_curve: Sequence[EquitySnapshot]) -> float:
        if not equity_curve:
            return 0.0
        peak = float(equity_curve[0].equity)
        max_dd = 0.0
        for snap in equity_curve:
            equity = float(snap.equity)
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd * 100.0

    def exposure_pct(self, snapshots: Sequence[EquitySnapshot]) -> float:
        if not snapshots:
            return 0.0
        invested = sum(1 for s in snapshots if s.positions)
        return (invested / len(snapshots)) * 100.0


class TradeStats:
    def win_rate_pct(self, trades: Sequence[Trade]) -> float | None:
        if len(trades) < 2:
            return None
        wins = sum(1 for t in trades if t.pnl > 0)
        return (wins / len(trades)) * 100.0


class MetricsCalculator:
    def __init__(self) -> None:
        self._equity_stats = EquityCurveStats()
        self._trade_stats = TradeStats()

    def calculate(self, result: BacktestResult) -> Metrics:
        equity_curve = result.equity_curve
        trades = result.trades
        n_trades = len(trades)

        total_return_pct = 0.0
        if equity_curve and result.initial_cash > 0:
            final_equity = float(equity_curve[-1].equity)
            total_return_pct = (final_equity / result.initial_cash - 1.0) * 100.0

        cagr_pct = self._equity_stats.cagr_pct(equity_curve, result.initial_cash)
        max_dd_pct = self._equity_stats.max_drawdown_pct(equity_curve)
        exposure_pct = self._equity_stats.exposure_pct(equity_curve)

        sharpe_ratio: float | None
        if n_trades < 2:
            sharpe_ratio = None
        else:
            returns = self._equity_stats.compute_returns(equity_curve)
            sharpe_ratio = self._equity_stats.sharpe(returns)

        win_rate_pct = self._trade_stats.win_rate_pct(trades)

        return Metrics(
            total_return_pct=round(total_return_pct, 4),
            cagr_pct=round(cagr_pct, 4),
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=round(max_dd_pct, 4),
            win_rate_pct=win_rate_pct,
            n_trades=n_trades,
            exposure_pct=round(exposure_pct, 4),
        )
