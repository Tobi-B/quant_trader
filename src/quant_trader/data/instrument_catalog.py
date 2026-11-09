"""Central instrument catalog: FMP-backed snapshot store + search/filter service."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import pandas as pd

from quant_trader.core.errors import (
    CatalogRefreshError,
    CatalogUnavailableError,
    DataError,
    EmptyUniverseSelectionError,
    ProviderError,
)
from quant_trader.core.logging import get_logger
from quant_trader.core.types import ExchangeDescriptor, Instrument
from quant_trader.universe.dynamic_store import DynamicUniverse, DynamicUniverseStore

log = get_logger(__name__)

_SNAPSHOT_COLUMNS = [
    "snapshot_id",
    "ticker",
    "name",
    "exchange",
    "exchange_full_name",
    "currency",
    "instrument_type",
    "country",
    "sector",
    "is_active",
]

# Standard universes that can be rebuilt from the catalog. `sp500` is not
# among them: S&P 500 membership is a licensed index product and none of the
# key-free sources carry it, so it stays a static preset (ADR-0019).
# `capital`/`labor` are the sector baskets behind long_capital_short_labor,
# resolved from FMP-enriched sectors (ADR-0020); they stay empty until
# `catalog enrich-sectors` has run.
_STANDARD_UNIVERSE_NAMES = ("dax40", "etfs", "capital", "labor")
_ETF_TYPES = ("etf", "etn", "etc")
_CAPITAL_SECTORS = ("Financial Services", "Real Estate", "Technology")
_LABOR_SECTORS = ("Consumer Cyclical", "Industrials")


class CatalogProvider(Protocol):
    def fetch_stock_list(self) -> list[Instrument]: ...
    def fetch_etf_list(self) -> list[Instrument]: ...
    def fetch_fund_list(self) -> list[Instrument]: ...
    def fetch_index_list(self) -> list[Instrument]: ...
    def fetch_crypto_list(self) -> list[Instrument]: ...
    def fetch_exchanges(self) -> list[ExchangeDescriptor]: ...
    def fetch_sectors(self) -> list[str]: ...
    def fetch_countries(self) -> list[str]: ...
    def fetch_index_membership(self, index_id: str) -> list[str]: ...


@dataclass(frozen=True)
class CatalogRefreshResult:
    snapshot_id: str
    total: int
    added: int
    removed: int
    unchanged: int
    used_fallback: bool


@dataclass(frozen=True)
class FilterOptions:
    instrument_types: tuple[str, ...]
    exchanges: tuple[str, ...]
    countries: tuple[str, ...]
    sectors: tuple[str, ...]
    indices: tuple[str, ...]


@dataclass(frozen=True)
class CatalogStatus:
    snapshot_id: str | None
    total: int
    age: timedelta | None
    needs_refresh: bool


class InstrumentCatalogSnapshotStore:
    """Persists the instrument catalog as a single Parquet file.

    Writes are atomic (temp file + `os.replace`) so a crash mid-refresh
    never leaves a half-written snapshot behind - `read()` always sees
    either the previous snapshot or the fully new one.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def path_for(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> pd.DataFrame | None:
        if not self._path.exists():
            return None
        return pd.read_parquet(self._path)

    def write(self, df: pd.DataFrame, snapshot_id: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        out = df.copy()
        out["snapshot_id"] = snapshot_id
        out.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, self._path)

    def latest_snapshot_id(self) -> str | None:
        df = self.read()
        if df is None or df.empty:
            return None
        return str(df["snapshot_id"].iloc[0])

    def snapshot_age(self) -> timedelta | None:
        if not self._path.exists():
            return None
        mtime = datetime.fromtimestamp(self._path.stat().st_mtime, tz=UTC)
        return datetime.now(UTC) - mtime

    def needs_refresh(self, max_age: timedelta) -> bool:
        age = self.snapshot_age()
        if age is None:
            return True
        return age > max_age


class SectorSource(Protocol):
    """Anything that can map ticker -> sector (see SectorEnrichmentStore)."""

    def sector_map(self) -> dict[str, str]: ...


class InstrumentCatalogService:
    """Refreshes, searches, and builds universes from the instrument catalog."""

    def __init__(
        self,
        provider: CatalogProvider,
        store: InstrumentCatalogSnapshotStore,
        dynamic_store: DynamicUniverseStore,
        refresh_interval: timedelta = timedelta(hours=24),
        sector_source: SectorSource | None = None,
    ) -> None:
        self._provider = provider
        self._store = store
        self._dynamic_store = dynamic_store
        self._refresh_interval = refresh_interval
        self._sector_source = sector_source

    def refresh(self, *, force: bool = False) -> CatalogRefreshResult:
        if not force and self._store.exists() and not self._store.needs_refresh(
            self._refresh_interval
        ):
            df = self._store.read()
            total = 0 if df is None else len(df)
            snapshot_id = self._store.latest_snapshot_id() or ""
            return CatalogRefreshResult(
                snapshot_id=snapshot_id,
                total=total,
                added=0,
                removed=0,
                unchanged=total,
                used_fallback=False,
            )

        log.info("catalog.refresh.start", force=force)
        try:
            merged = self._fetch_and_merge()
        except (DataError, ProviderError) as exc:
            if self._store.exists():
                log.warning(
                    "catalog.refresh.fallback",
                    error_type=type(exc).__name__,
                    reason=str(exc),
                )
                df = self._store.read()
                total = 0 if df is None else len(df)
                return CatalogRefreshResult(
                    snapshot_id=self._store.latest_snapshot_id() or "",
                    total=total,
                    added=0,
                    removed=0,
                    unchanged=total,
                    used_fallback=True,
                )
            log.error("catalog.snapshot.unavailable", error_type=type(exc).__name__)
            raise CatalogUnavailableError(None, str(exc)) from exc

        if merged.empty:
            raise CatalogRefreshError("fmp", "provider returned an empty instrument set")

        previous_tickers: set[str] = set()
        previous_df = self._store.read()
        if previous_df is not None and not previous_df.empty:
            previous_tickers = set(previous_df["ticker"])
        new_tickers = set(merged["ticker"])

        snapshot_id = f"{datetime.now(UTC).isoformat()}-{uuid.uuid4().hex[:8]}"
        self._store.write(merged, snapshot_id)

        added = len(new_tickers - previous_tickers)
        removed = len(previous_tickers - new_tickers)
        unchanged = len(new_tickers & previous_tickers)
        log.info(
            "catalog.refresh.complete",
            snapshot_id=snapshot_id,
            total=len(merged),
            added=added,
            removed=removed,
            unchanged=unchanged,
        )
        return CatalogRefreshResult(
            snapshot_id=snapshot_id,
            total=len(merged),
            added=added,
            removed=removed,
            unchanged=unchanged,
            used_fallback=False,
        )

    def _fetch_and_merge(self) -> pd.DataFrame:
        provider_name = getattr(self._provider, "name", type(self._provider).__name__)
        log.info("catalog.refresh.provider", provider=provider_name)
        # A composite provider may memoise its downloads across the several
        # fetch_*_list calls one refresh makes; drop that cache first so a
        # refresh really re-reads the sources instead of replaying the last run.
        invalidate = getattr(self._provider, "invalidate", None)
        if callable(invalidate):
            invalidate()
        instruments: list[Instrument] = [
            *self._provider.fetch_stock_list(),
            *self._provider.fetch_etf_list(),
            *self._provider.fetch_fund_list(),
            *self._provider.fetch_index_list(),
            *self._provider.fetch_crypto_list(),
        ]
        seen: set[tuple[str, str, str]] = set()
        rows: list[dict[str, object]] = []
        for instrument in instruments:
            key = (instrument.ticker, instrument.exchange, instrument.currency)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "ticker": instrument.ticker,
                    "name": instrument.name,
                    "exchange": instrument.exchange,
                    "exchange_full_name": instrument.exchange_full_name,
                    "currency": instrument.currency,
                    "instrument_type": instrument.instrument_type,
                    "country": instrument.country,
                    "sector": instrument.sector,
                    "is_active": instrument.is_active,
                }
            )
        return pd.DataFrame(rows, columns=_SNAPSHOT_COLUMNS[1:])

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
        instrument_type: str | None = None,
        exchange: str | None = None,
        country: str | None = None,
        sector: str | None = None,
    ) -> list[Instrument]:
        df = self._require_snapshot()
        cleaned = query.strip().upper()
        mask = pd.Series(True, index=df.index)
        if cleaned:
            # Class shares are written `BRK.B` on some venues and `BRK-B` on
            # others; a trader typing either form means the same instrument,
            # so both are matched against a separator-normalised ticker.
            tickers = df["ticker"].str.upper()
            normalised = tickers.str.replace("-", ".", regex=False)
            needle = _normalise_ticker(cleaned)
            mask &= (
                tickers.eq(cleaned)
                | normalised.eq(needle)
                | tickers.str.contains(cleaned, regex=False)
                | df["name"].str.upper().str.contains(cleaned, regex=False)
            )
        mask &= _optional_eq(df, "instrument_type", instrument_type)
        mask &= _optional_eq(df, "exchange", exchange)
        mask &= _optional_eq(df, "country", country)
        mask &= _optional_eq(df, "sector", sector)
        matched = df.loc[mask].head(max(1, min(limit, 500)))
        return [_row_to_instrument(row) for _, row in matched.iterrows()]

    def list_filter_options(self) -> FilterOptions:
        df = self._require_snapshot()
        return FilterOptions(
            instrument_types=_unique_sorted(df["instrument_type"]),
            exchanges=_unique_sorted(df["exchange"]),
            countries=_unique_sorted(df["country"]),
            sectors=_unique_sorted(df["sector"]),
            indices=tuple(sorted((*_STANDARD_UNIVERSE_NAMES, "mdax", "sdax"))),
        )

    def snapshot_status(self) -> CatalogStatus:
        df = self._store.read()
        total = 0 if df is None else len(df)
        return CatalogStatus(
            snapshot_id=self._store.latest_snapshot_id(),
            total=total,
            age=self._store.snapshot_age(),
            needs_refresh=self._store.needs_refresh(self._refresh_interval),
        )

    def build_dynamic_universe(
        self,
        name: str,
        *,
        filters: Mapping[str, str] | None = None,
        query: str = "",
        description: str = "",
    ) -> DynamicUniverse:
        filters = filters or {}
        results = self.search(
            query,
            limit=5000,
            instrument_type=filters.get("instrument_type"),
            exchange=filters.get("exchange"),
            country=filters.get("country"),
            sector=filters.get("sector"),
        )
        tickers = tuple(sorted({instrument.ticker for instrument in results}))
        if not tickers:
            raise EmptyUniverseSelectionError(name)
        return DynamicUniverse(
            name=name,
            built_from_snapshot=self._store.latest_snapshot_id() or "",
            created_at=datetime.now(UTC),
            filter_description=description,
            filters=dict(filters),
            tickers=tickers,
        )

    def build_standard_universe(self, name: str) -> DynamicUniverse:
        if name not in _STANDARD_UNIVERSE_NAMES:
            raise ValueError(
                f"Unbekanntes Standard-Universe: {name} "
                f"(dynamisch verfuegbar: {', '.join(_STANDARD_UNIVERSE_NAMES)})"
            )
        df = self._require_snapshot()

        filters: dict[str, str] = {}
        if name == "etfs":
            tickers = tuple(sorted(df.loc[df["instrument_type"].isin(_ETF_TYPES), "ticker"]))
            description = "ETFs/ETNs/ETCs aus dem aktuellen Katalog"
        elif name == "dax40":
            members = set(self._provider.fetch_index_membership("dax40"))
            stock_tickers = set(df.loc[df["instrument_type"] == "stock", "ticker"])
            tickers = tuple(sorted(members & stock_tickers))
            description = "DAX-Handelsgruppe der Deutschen Boerse (inkl. beider Aktiengattungen)"
        else:
            sectors = _CAPITAL_SECTORS if name == "capital" else _LABOR_SECTORS
            tickers = _tickers_in_sectors(df, sectors)
            description = f"US-Aktien in den Sektoren {', '.join(sectors)} (FMP-Profil)"
            filters = {"instrument_type": "stock", "sectors": ", ".join(sectors)}

        if not tickers:
            raise EmptyUniverseSelectionError(name)

        universe = DynamicUniverse(
            name=name,
            built_from_snapshot=self._store.latest_snapshot_id() or "",
            created_at=datetime.now(UTC),
            filter_description=description,
            filters=filters,
            tickers=tickers,
        )
        self._dynamic_store.save(universe, overwrite=True)
        return universe

    def _require_snapshot(self) -> pd.DataFrame:
        df = self._store.read()
        if df is None or df.empty:
            raise CatalogUnavailableError(None, "kein Snapshot vorhanden")
        return self._apply_sector_enrichment(df)

    def _apply_sector_enrichment(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill blank sectors from the enrichment store, never overwrite.

        Xetra rows already carry an exchange-group sector; only the US
        rows from NASDAQ Trader arrive blank, and those are exactly the
        ones the enrichment backfill targets.
        """
        if self._sector_source is None:
            return df
        sector_map = self._sector_source.sector_map()
        if not sector_map:
            return df
        out = df.copy()
        blank = out["sector"].astype(str).str.len() == 0
        out.loc[blank, "sector"] = out.loc[blank, "ticker"].map(sector_map).fillna("")
        return out


def _tickers_in_sectors(df: pd.DataFrame, sectors: tuple[str, ...]) -> tuple[str, ...]:
    wanted = {s.casefold() for s in sectors}
    mask = (df["instrument_type"] == "stock") & df["sector"].astype(str).str.casefold().isin(
        wanted
    )
    return tuple(sorted(set(df.loc[mask, "ticker"])))


def _normalise_ticker(ticker: str) -> str:
    """Collapse the dot/dash class-share spelling to one form."""
    return ticker.strip().upper().replace("-", ".")


def _optional_eq(df: pd.DataFrame, column: str, value: str | None) -> pd.Series:
    if not value:
        return pd.Series(True, index=df.index)
    return df[column].str.casefold() == value.casefold()


def _unique_sorted(series: pd.Series) -> tuple[str, ...]:
    return tuple(sorted({v for v in series if isinstance(v, str) and v}))


def _row_to_instrument(row: Mapping[str, object]) -> Instrument:
    return Instrument(
        ticker=str(row["ticker"]),
        name=str(row["name"]),
        exchange=str(row["exchange"]),
        currency=str(row["currency"]),
        instrument_type=str(row["instrument_type"]),
        country=str(row["country"]),
        sector=str(row["sector"]),
        exchange_full_name=str(row["exchange_full_name"]),
        is_active=bool(row["is_active"]),
    )


__all__ = [
    "CatalogProvider",
    "CatalogRefreshResult",
    "CatalogStatus",
    "FilterOptions",
    "InstrumentCatalogService",
    "InstrumentCatalogSnapshotStore",
]
