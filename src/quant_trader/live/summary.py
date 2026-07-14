"""DailySummaryFormatter: fixed-width German table for end-of-run summary."""

from __future__ import annotations

from collections.abc import Sequence

from quant_trader.live.journal import TradeRow
from quant_trader.live.types import DailySummary


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}"


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.2f}%"


class DailySummaryFormatter:
    """Renders the daily summary as fixed-width deterministic German table."""

    def __init__(self, top: int = 10) -> None:
        self._top = top

    def format(self, summary: DailySummary, trades: Sequence[TradeRow]) -> str:
        lines: list[str] = []
        lines.append("Tageszusammenfassung")
        lines.append("====================")
        lines.append(f"  Run-ID:              {summary.run_id}")
        lines.append(f"  Strategie:           {summary.strategy_name}")
        lines.append(f"  Trades (gesamt):     {summary.total_trades}")
        lines.append(f"  Offene Positionen:   {summary.open_positions_count}")
        lines.append(f"  P&L (gesamt):        {_fmt_money(summary.total_pnl)}")
        lines.append(f"  Laufzeit (Sekunden): {summary.duration_seconds:.2f}")
        lines.append(f"  Beendet um:          {summary.closed_at}")
        lines.append("")
        lines.append(f"Top-Trades (max {self._top})")
        lines.append("-" * len(f"Top-Trades (max {self._top})"))
        lines.append(self._format_trades(trades))
        return "\n".join(lines)

    def _format_trades(self, trades: Sequence[TradeRow]) -> str:
        if not trades:
            return "keine Trades"
        top = self._top
        shown = list(trades[:top])
        headers = ("TICKER", "ENTRY", "EXIT", "PNL", "PNL_%")
        rows: list[tuple[str, ...]] = []
        for trade in shown:
            rows.append(
                (
                    trade.ticker,
                    _fmt_price(trade.entry_price),
                    _fmt_price(trade.exit_price),
                    _fmt_money(trade.pnl),
                    _fmt_pct(trade.pnl_pct),
                )
            )
        widths = [len(h) for h in headers]
        for row in rows:
            widths = [max(w, len(c)) for w, c in zip(widths, row, strict=False)]
        sep = "-+-".join("-" * w for w in widths)
        lines: list[str] = []
        lines.append(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
        lines.append(sep)
        for row in rows:
            lines.append(" | ".join(c.ljust(widths[i]) for i, c in enumerate(row)))
        if len(trades) > top:
            lines.append(f"... {len(trades) - top} weitere")
        return "\n".join(lines)


__all__ = ["DailySummaryFormatter"]
