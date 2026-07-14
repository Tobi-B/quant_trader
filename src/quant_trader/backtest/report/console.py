"""ConsoleFormatter: fixed-width, deterministic German tables for terminal output."""

from __future__ import annotations

from collections.abc import Sequence

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.types import BacktestResult, Trade


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def _fmt_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


class ConsoleFormatter:
    """Renders metrics + trades as fixed-width, deterministic German tables.

    Output is deterministic (left-justified columns) so tests can assert
    against the rendered text. Empty inputs render a friendly "keine
    Trades" line without crashing.
    """

    def format_metrics(self, metrics: Metrics) -> str:
        lines: list[str] = []
        lines.append("Backtest-Metriken")
        lines.append("=================")
        lines.append(f"  Total Return:  {metrics.total_return_pct:.2f}%")
        lines.append(f"  CAGR:          {metrics.cagr_pct:.2f}%")
        sharpe_str = _fmt_float(metrics.sharpe_ratio)
        lines.append(f"  Sharpe Ratio:  {sharpe_str}")
        lines.append(f"  Max Drawdown:  {metrics.max_drawdown_pct:.2f}%")
        wr_str = _fmt_pct(metrics.win_rate_pct)
        lines.append(f"  Win-Rate:      {wr_str}")
        lines.append(f"  Trades:        {metrics.n_trades}")
        lines.append(f"  Exposure:      {metrics.exposure_pct:.2f}%")
        return "\n".join(lines)

    def format_trades(self, trades: Sequence[Trade], top: int = 10) -> str:
        if not trades:
            return "keine Trades"
        headers = ("TICKER", "ENTRY", "EXIT", "PRICE_IN", "PRICE_OUT", "PNL", "PNL_%")
        rows: list[tuple[str, ...]] = []
        for t in trades[:top]:
            rows.append(
                (
                    t.ticker,
                    t.entry_date.isoformat(),
                    t.exit_date.isoformat(),
                    f"{t.entry_price:.2f}",
                    f"{t.exit_price:.2f}",
                    f"{t.pnl:+.2f}",
                    f"{t.pnl_pct * 100:+.2f}%",
                )
            )
        widths = [len(h) for h in headers]
        for row in rows:
            widths = [max(w, len(c)) for w, c in zip(widths, row, strict=False)]
        sep = "-+-".join("-" * w for w in widths)
        out: list[str] = []
        out.append(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
        out.append(sep)
        for row in rows:
            out.append(" | ".join(c.ljust(widths[i]) for i, c in enumerate(row)))
        if len(trades) > top:
            out.append(f"... {len(trades) - top} weitere")
        return "\n".join(out)

    def format_report(
        self,
        result: BacktestResult,
        metrics: Metrics,
        top: int = 10,
    ) -> str:
        header = self._format_header(result)
        metrics_block = self.format_metrics(metrics)
        trades_block = self.format_trades(result.trades, top=top)
        return f"{header}\n\n{metrics_block}\n\nTop-Trades (max {top})\n------------------\n{trades_block}"

    @staticmethod
    def _format_header(result: BacktestResult) -> str:
        return (
            f"Backtest: {result.strategy_name}\n"
            f"Periode: {result.start.isoformat()} - {result.end.isoformat()}\n"
            f"Initial Cash: {_fmt_money(result.initial_cash)}  "
            f"Final Equity: {_fmt_money(result.final_equity)}  "
            f"Fill-Mode: {result.fill_mode.value}"
        )
