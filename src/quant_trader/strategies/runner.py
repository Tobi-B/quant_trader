"""Signal-Runner: applies a registered strategy to cached bars.

The runner reads bars from the Parquet cache (Phase 1) and feeds them to a
strategy loaded via `StrategyLoader`. It supports both single-ticker
strategies (`StrategyBase.on_bar`) and universe strategies
(`MultiTickerStrategyBase.on_universe_bars`). Signals are collected into a
flat list and returned to the caller (typically the CLI) for formatting.

The runner does **not** execute trades or compute P&L - that is Phase 3.
It is a smoke-test tool: small, deterministic, cache-only.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies.base import MultiTickerStrategyBase, StrategyBase
from quant_trader.strategies.errors import (
    StrategyConfigError,
    StrategyError,
    UnknownStrategyError,
)
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.strategies.types import PortfolioState, Signal

log = get_logger(__name__)


class SignalFormatter:
    """Formats a list of `Signal`s as a fixed-width table.

    The output is deterministic (left-justified columns) so tests can
    assert against the rendered text. When `len(signals) > limit` a footer
    line `(... N more)` is appended; the full list is not truncated.
    """

    _HEADERS: tuple[str, str, str, str] = ("TIMESTAMP", "TICKER", "ACTION", "REASON")

    def format_signals(self, signals: Sequence[Signal], limit: int = 100) -> str:
        if not signals:
            return "no signals"
        ts_w = max(len(self._HEADERS[0]), len("2024-01-02T16:00:00"))
        tk_w = max(len(self._HEADERS[1]), max(len(s.ticker) for s in signals))
        ac_w = len(self._HEADERS[2])
        re_w = max(len(self._HEADERS[3]), max(len(s.reason) for s in signals))
        header = " | ".join(
            [
                self._HEADERS[0].ljust(ts_w),
                self._HEADERS[1].ljust(tk_w),
                self._HEADERS[2].ljust(ac_w),
                self._HEADERS[3].ljust(re_w),
            ]
        )
        sep = "-+-".join(["-" * ts_w, "-" * tk_w, "-" * ac_w, "-" * re_w])
        lines = [header, sep]
        for sig in signals[:limit]:
            lines.append(
                " | ".join(
                    [
                        sig.timestamp.isoformat(timespec="seconds").ljust(ts_w),
                        sig.ticker.ljust(tk_w),
                        str(sig.action.value).ljust(ac_w),
                        sig.reason.ljust(re_w),
                    ]
                )
            )
        if len(signals) > limit:
            lines.append(f"... {len(signals) - limit} more")
        return "\n".join(lines)


class SignalRunner:
    """Applies a strategy to cached bars and collects the emitted signals.

    Single-ticker strategies are fed chronologically via `on_bar`.
    Universe strategies receive one `(timestamp, bars_by_ticker)` tuple per
    distinct trading date, sorted chronologically.
    """

    def __init__(self, cache: ParquetCache, loader: StrategyLoader) -> None:
        self._cache = cache
        self._loader = loader

    def _resolve_multi_tickers(
        self,
        strategy: MultiTickerStrategyBase,
        universe_arg: str | None,
    ) -> list[str]:
        if universe_arg:
            from quant_trader.core.config import get_settings
            from quant_trader.universe.presets import PresetNotFoundError, PresetRepository

            repo = PresetRepository(get_settings().universe_presets_path)
            try:
                preset = repo.get(universe_arg)
            except PresetNotFoundError as exc:
                raise StrategyError(
                    f"Universe-Preset '{universe_arg}' nicht gefunden: {exc.name}"
                ) from exc
            return [t.upper() for t in preset.tickers]
        params_universe = strategy.params.get("universe")
        if not params_universe:
            raise StrategyConfigError(
                "Multi-Ticker-Strategie benoetigt 'universe' in den Parametern "
                "oder '--universe PRESET'"
            )
        return [str(t).upper() for t in params_universe]

    def _read_bars(
        self,
        ticker: str,
        granularity: Granularity,
        start: date,
        end: date,
    ) -> list[Bar]:
        if not self._cache.exists(ticker, granularity):
            path = self._cache.path_for(ticker, granularity)
            raise FileNotFoundError(
                f"Kein Cache fuer {ticker} ({granularity.value}) unter {path}. "
                f"Erst `python -m quant_trader.data {ticker}` aufrufen."
            )
        return self._cache.read(ticker, granularity, start, end)

    def _run_single(
        self,
        strategy: StrategyBase,
        ticker: str,
        granularity: Granularity,
        start: date,
        end: date,
    ) -> list[Signal]:
        bars = self._read_bars(ticker, granularity, start, end)
        portfolio = PortfolioState()
        signals: list[Signal] = []
        for bar in bars:
            signals.extend(strategy.on_bar(bar, portfolio))
        return signals

    def _run_multi(
        self,
        strategy: MultiTickerStrategyBase,
        tickers: list[str],
        granularity: Granularity,
        start: date,
        end: date,
    ) -> list[Signal]:
        per_ticker: dict[str, list[Bar]] = {}
        for t in tickers:
            per_ticker[t] = self._read_bars(t, granularity, start, end)
        grouped: dict[date, dict[str, Bar]] = defaultdict(dict)
        for ticker, bars in per_ticker.items():
            for bar in bars:
                grouped[bar.timestamp.date()][ticker] = bar
        portfolio = PortfolioState()
        signals: list[Signal] = []
        for ts_date in sorted(grouped.keys()):
            ts_dt = next(iter(grouped[ts_date].values())).timestamp
            signals.extend(strategy.on_universe_bars(ts_dt, dict(grouped[ts_date]), portfolio))
        return signals

    def run(
        self,
        strategy_name: str,
        *,
        ticker: str = "",
        universe: str | None = None,
        start: date,
        end: date,
        granularity: Granularity = Granularity.DAILY,
    ) -> list[Signal]:
        if not self._loader.is_registered(strategy_name):
            raise UnknownStrategyError(strategy_name, self._loader.registered_names())
        try:
            strategy = self._loader.load(strategy_name, ticker=ticker)
        except StrategyError:
            raise
        except FileNotFoundError as exc:
            raise StrategyConfigError(str(exc)) from exc

        if isinstance(strategy, StrategyBase):
            if not ticker:
                raise StrategyConfigError(
                    f"Strategy '{strategy_name}' ist Single-Ticker: --ticker ist erforderlich"
                )
            log.info(
                "signal_runner.start",
                strategy=strategy_name,
                mode="single",
                ticker=ticker,
                granularity=granularity.value,
                start=start.isoformat(),
                end=end.isoformat(),
            )
            signals = self._run_single(strategy, ticker, granularity, start, end)
        elif isinstance(strategy, MultiTickerStrategyBase):
            tickers = self._resolve_multi_tickers(strategy, universe)
            log.info(
                "signal_runner.start",
                strategy=strategy_name,
                mode="multi",
                tickers=tickers,
                granularity=granularity.value,
                start=start.isoformat(),
                end=end.isoformat(),
            )
            signals = self._run_multi(strategy, tickers, granularity, start, end)
        else:
            raise StrategyConfigError(f"Unbekannter Strategy-Typ: {type(strategy).__name__}")

        log.info(
            "signal_runner.summary",
            strategy=strategy_name,
            signals=len(signals),
        )
        return signals
