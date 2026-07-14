"""Tests for the DailySummaryFormatter."""

from __future__ import annotations

from datetime import datetime

from quant_trader.live import DailySummary, DailySummaryFormatter, TradeJournal
from quant_trader.live.journal import TradeRow


def _summary(total_trades: int = 3, total_pnl: float = 12.34) -> DailySummary:
    return DailySummary(
        run_id="run-1",
        strategy_name="sma_cross",
        total_trades=total_trades,
        open_positions_count=1,
        total_pnl=total_pnl,
        duration_seconds=3600.0,
        closed_at="2026-07-14T17:00:00",
    )


def _trade(
    ticker: str = "SPY",
    entry: float = 100.0,
    exit: float = 110.0,
    pnl: float = 10.0,
) -> TradeRow:
    return TradeRow(
        id=1,
        run_id="run-1",
        strategy_name="sma_cross",
        ticker=ticker,
        action="SELL",
        qty=1,
        entry_price=entry,
        exit_price=exit,
        pnl=pnl,
        pnl_pct=(exit - entry) / entry if entry else None,
        opened_at="2026-07-14T10:00:00",
        closed_at="2026-07-14T11:00:00",
        client_order_id="order-1",
        created_at=datetime(2026, 7, 14, 10, 0, 0).isoformat(),
    )


def test_summary_formatter_with_no_trades() -> None:
    formatter = DailySummaryFormatter()
    output = formatter.format(_summary(), [])
    assert "Tageszusammenfassung" in output
    assert "keine Trades" in output
    assert "Run-ID:              run-1" in output
    assert "Strategie:           sma_cross" in output
    assert "Trades (gesamt):     3" in output
    assert "Offene Positionen:   1" in output
    assert "P&L (gesamt):        +12.34" in output
    assert "Laufzeit (Sekunden): 3600.00" in output
    assert "Beendet um:          2026-07-14T17:00:00" in output


def test_summary_formatter_with_trades() -> None:
    formatter = DailySummaryFormatter()
    trades = [_trade()]
    output = formatter.format(_summary(), trades)
    assert "TICKER" in output
    assert "ENTRY" in output
    assert "EXIT" in output
    assert "PNL" in output
    assert "PNL_%" in output
    assert "SPY" in output
    assert "100.00" in output
    assert "110.00" in output
    assert "+10.00" in output
    assert "+10.00%" in output
    assert "keine Trades" not in output
    assert "... " not in output


def test_summary_formatter_top_caps_at_10() -> None:
    formatter = DailySummaryFormatter()
    trades = [_trade(ticker=f"T{i}") for i in range(15)]
    output = formatter.format(_summary(total_trades=15), trades)
    assert "T0" in output
    assert "T9" in output
    assert "T10" not in output
    assert "... 5 weitere" in output


def test_summary_formatter_handles_trade_with_none_pnl() -> None:
    formatter = DailySummaryFormatter()
    open_trade = TradeRow(
        id=2,
        run_id="run-1",
        strategy_name="sma_cross",
        ticker="QQQ",
        action="BUY",
        qty=1,
        entry_price=50.0,
        exit_price=None,
        pnl=None,
        pnl_pct=None,
        opened_at="2026-07-14T10:00:00",
        closed_at=None,
        client_order_id="order-2",
        created_at=datetime(2026, 7, 14, 10, 0, 0).isoformat(),
    )
    output = formatter.format(_summary(), [open_trade])
    assert "QQQ" in output
    assert "n/a" in output


def test_summary_formatter_round_trips_via_journal(tmp_path) -> None:
    formatter = DailySummaryFormatter()
    summary = _summary()
    journal = TradeJournal(tmp_path / "trades.sqlite")
    journal.append_summary(summary)
    persisted = journal.list_summaries()[0]
    rendered = formatter.format(persisted, [])
    journal.close()
    assert "Tageszusammenfassung" in rendered
    assert "Run-ID:              run-1" in rendered
