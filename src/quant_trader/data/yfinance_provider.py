"""yfinance implementation of DataProvider."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import yfinance as yf

from quant_trader.core.errors import ProviderError, TickerNotFoundError
from quant_trader.core.types import Bar, Granularity


_INTERVAL_MAP: dict[Granularity, str] = {
    Granularity.DAILY: "1d",
    Granularity.INTRADAY_60M: "60m",
    Granularity.INTRADAY_15M: "15m",
}


class YFinanceProvider:
    name = "yfinance"

    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]:
        interval = _INTERVAL_MAP[granularity]
        try:
            df = yf.download(
                ticker,
                start=start.isoformat(),
                end=end.isoformat(),
                interval=interval,
                auto_adjust=False,
                progress=False,
            )
        except Exception as exc:
            raise ProviderError(self.name, str(exc)) from exc

        if df.empty:
            raise TickerNotFoundError(ticker)

        return _dataframe_to_bars(df)


def _dataframe_to_bars(df: pd.DataFrame) -> list[Bar]:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    cols = {str(c).lower().strip(): c for c in df.columns}
    open_col = cols.get("open")
    high_col = cols.get("high")
    low_col = cols.get("low")
    close_col = cols.get("close")
    adj_col = cols.get("adj close")
    vol_col = cols.get("volume")

    if not all([open_col, high_col, low_col, close_col, vol_col]):
        raise ProviderError("yfinance", f"unexpected columns: {list(df.columns)}")

    bars: list[Bar] = []
    for ts, row in df.iterrows():
        ts_value = _coerce_timestamp(ts)
        bars.append(
            Bar(
                timestamp=ts_value,
                open=float(row[open_col]),
                high=float(row[high_col]),
                low=float(row[low_col]),
                close=float(row[close_col]),
                adjusted_close=float(row[adj_col]) if adj_col is not None else float(row[close_col]),
                volume=int(row[vol_col]),
            )
        )
    return bars


def _coerce_timestamp(ts: object) -> datetime:
    if isinstance(ts, pd.Timestamp):
        return ts.to_pydatetime()
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(str(ts)[:19])