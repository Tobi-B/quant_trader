"""Parquet-based cache for OHLCV bars."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from quant_trader.core.errors import ProviderError
from quant_trader.core.types import Bar, Granularity


_REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "adjusted_close", "volume"]


class ParquetCache:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def path_for(self, ticker: str, granularity: Granularity) -> Path:
        return self._base / "raw" / granularity.path_segment / f"{ticker}.parquet"

    def exists(self, ticker: str, granularity: Granularity) -> bool:
        return self.path_for(ticker, granularity).exists()

    def covers(
        self,
        ticker: str,
        granularity: Granularity,
        start: date,
        end: date,
    ) -> bool:
        path = self.path_for(ticker, granularity)
        if not path.exists():
            return False
        df = _safe_read_parquet(path)
        if df.empty:
            return False
        ts_min = pd.Timestamp(df["timestamp"].min()).date()
        ts_max = pd.Timestamp(df["timestamp"].max()).date()
        return ts_min <= start and ts_max >= end

    def read(
        self,
        ticker: str,
        granularity: Granularity,
        start: date,
        end: date,
    ) -> list[Bar]:
        path = self.path_for(ticker, granularity)
        df = _safe_read_parquet(path)
        ts = pd.to_datetime(df["timestamp"])
        mask = (ts.dt.date >= start) & (ts.dt.date <= end)
        sub = df.loc[mask]
        return _bars_from_dataframe(sub)

    def write(
        self,
        ticker: str,
        granularity: Granularity,
        bars: list[Bar],
    ) -> Path:
        if not bars:
            raise ProviderError("cache", f"refusing to write empty bars for {ticker}")
        path = self.path_for(ticker, granularity)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = _dataframe_from_bars(bars)
        df.to_parquet(path, index=False)
        return path


def _safe_read_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        raise ProviderError("cache", f"failed to read {path}: {exc}") from exc


def _dataframe_from_bars(bars: list[Bar]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": b.timestamp,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "adjusted_close": b.adjusted_close,
                "volume": b.volume,
            }
            for b in bars
        ],
        columns=_REQUIRED_COLUMNS,
    )


def _bars_from_dataframe(df: pd.DataFrame) -> list[Bar]:
    out: list[Bar] = []
    for _, row in df.iterrows():
        ts_value = row["timestamp"]
        if isinstance(ts_value, pd.Timestamp):
            ts_value = ts_value.to_pydatetime()
        elif isinstance(ts_value, datetime):
            pass
        else:
            ts_value = datetime.fromisoformat(str(ts_value)[:19])
        out.append(
            Bar(
                timestamp=ts_value,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                adjusted_close=float(row["adjusted_close"]),
                volume=int(row["volume"]),
            )
        )
    return out