"""Tests for ConsoleFormatter: fixed-width, deterministic German tables."""

from __future__ import annotations

from datetime import date

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.report.console import ConsoleFormatter
from quant_trader.backtest.types import BacktestResult, EquitySnapshot, FillMode, Trade


def _metrics() -> Metrics:
    return Metrics(
        total_return_pct=12.34,
        cagr_pct=5.67,
        sharpe_ratio=1.42,
        max_drawdown_pct=-15.50,
        win_rate_pct=60.0,
        n_trades=5,
        exposure_pct=80.0,
    )


def _empty_metrics() -> Metrics:
    return Metrics(
        total_return_pct=0.0,
        cagr_pct=0.0,
        sharpe_ratio=None,
        max_drawdown_pct=0.0,
        win_rate_pct=None,
        n_trades=0,
        exposure_pct=0.0,
    )


def _trade(pnl: float) -> Trade:
    return Trade(
        ticker="SPY",
        entry_date=date(2024, 1, 5),
        entry_price=100.0,
        exit_date=date(2024, 1, 10),
        exit_price=100.0 + pnl,
        pnl=pnl,
        pnl_pct=pnl / 100.0,
    )


def _result(trades: list[Trade]) -> BacktestResult:
    return BacktestResult(
        strategy_name="sma_cross",
        params={"fast": 5, "slow": 10},
        start=date(2024, 1, 2),
        end=date(2024, 6, 30),
        fill_mode=FillMode.NEXT_OPEN,
        initial_cash=100_000.0,
        final_equity=112_000.0,
        trades=trades,
        equity_curve=[
            EquitySnapshot(date=date(2024, 1, 2), equity=100_000.0, cash=100_000.0),
            EquitySnapshot(date=date(2024, 6, 30), equity=112_000.0, cash=0.0),
        ],
    )


class TestConsoleFormatterMetrics:
    def test_format_metrics_contains_all_keys(self) -> None:
        out = ConsoleFormatter().format_metrics(_metrics())
        assert "Total Return" in out
        assert "CAGR" in out
        assert "Sharpe" in out
        assert "Max Drawdown" in out
        assert "Win-Rate" in out
        assert "Trades" in out
        assert "Exposure" in out
        assert "12.34%" in out
        assert "1.4200" in out

    def test_format_metrics_sharpe_none(self) -> None:
        out = ConsoleFormatter().format_metrics(_empty_metrics())
        assert "n/a" in out

    def test_format_metrics_deterministic(self) -> None:
        f = ConsoleFormatter()
        a = f.format_metrics(_metrics())
        b = f.format_metrics(_metrics())
        assert a == b


class TestConsoleFormatterTrades:
    def test_empty_trades_returns_message(self) -> None:
        out = ConsoleFormatter().format_trades([])
        assert out == "keine Trades"

    def test_trades_renders_table(self) -> None:
        out = ConsoleFormatter().format_trades([_trade(50.0), _trade(-20.0)])
        assert "TICKER" in out
        assert "ENTRY" in out
        assert "EXIT" in out
        assert "SPY" in out
        assert "+50.00" in out
        assert "-20.00" in out

    def test_trades_top_caps(self) -> None:
        trades = [_trade(10.0 * i) for i in range(1, 6)]
        out = ConsoleFormatter().format_trades(trades, top=2)
        assert "... 3 weitere" in out

    def test_trades_no_footer_when_under_top(self) -> None:
        out = ConsoleFormatter().format_trades([_trade(5.0)], top=10)
        assert "..." not in out

    def test_trades_table_deterministic(self) -> None:
        f = ConsoleFormatter()
        a = f.format_trades([_trade(10.0), _trade(-5.0)])
        b = f.format_trades([_trade(10.0), _trade(-5.0)])
        assert a == b


class TestConsoleFormatterReport:
    def test_format_report_contains_header_metrics_trades(self) -> None:
        result = _result([_trade(50.0), _trade(-20.0)])
        out = ConsoleFormatter().format_report(result, _metrics(), top=5)
        assert "Backtest: sma_cross" in out
        assert "2024-01-02 - 2024-06-30" in out
        assert "Total Return" in out
        assert "SPY" in out

    def test_format_report_empty_trades(self) -> None:
        result = _result([])
        out = ConsoleFormatter().format_report(result, _empty_metrics(), top=5)
        assert "keine Trades" in out
        assert "n/a" in out
