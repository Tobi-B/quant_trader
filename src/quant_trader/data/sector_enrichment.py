"""Sector enrichment: fills the catalog's sector column from FMP profiles.

The key-free catalog sources (ADR-0019) carry no GICS-style sector for US
stocks, and FMP's bulk endpoints are paywalled - but `/stable/profile` is
not. It costs one call per symbol against NFR-Data-3's 250/day budget, so
enrichment is a paced, resumable backfill: each run enriches the next
`limit` pending tickers and persists them, and sector data changes rarely
enough that a ticker is never re-fetched once recorded (ADR-0020).

Only US stocks are enriched. FMP's plain-symbol lookup is US-centric; a
Xetra mnemonic like "SAP" would resolve to the US-listed ADR, not the
Frankfurt line, so EU rows keep their exchange-group sector from Xetra.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from quant_trader.core.errors import (
    CatalogUnavailableError,
    ProviderError,
    RateLimitedError,
)
from quant_trader.core.logging import get_logger
from quant_trader.core.types import SectorProfile
from quant_trader.data.instrument_catalog import InstrumentCatalogSnapshotStore

log = get_logger(__name__)

_COLUMNS = ["ticker", "sector", "industry", "fetched_at"]


class SectorProfileProvider(Protocol):
    def fetch_sector_profile(self, symbol: str) -> SectorProfile | None: ...


@dataclass(frozen=True)
class SectorEnrichmentResult:
    attempted: int
    enriched: int
    missing: int
    failed: int
    rate_limited: bool
    remaining: int


class SectorEnrichmentStore:
    """One Parquet file mapping ticker -> sector/industry, written atomically.

    A ticker whose profile had no sector is stored with an empty sector so
    it is not retried on every run; `enriched_tickers()` therefore means
    "already looked up", not "has a sector".
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

    def enriched_tickers(self) -> set[str]:
        df = self.read()
        if df is None or df.empty:
            return set()
        return {str(t) for t in df["ticker"]}

    def sector_map(self) -> dict[str, str]:
        """ticker -> sector, only for tickers that actually have one."""
        df = self.read()
        if df is None or df.empty:
            return {}
        with_sector = df[df["sector"].astype(str).str.len() > 0]
        return {str(row.ticker): str(row.sector) for row in with_sector.itertuples(index=False)}

    def upsert(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        incoming = pd.DataFrame(rows, columns=_COLUMNS)
        existing = self.read()
        if existing is not None and not existing.empty:
            kept = existing[~existing["ticker"].isin(incoming["ticker"])]
            merged = pd.concat([kept, incoming], ignore_index=True)
        else:
            merged = incoming
        merged = merged.sort_values("ticker").reset_index(drop=True)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        merged.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, self._path)


class SectorEnrichmentService:
    """Paced backfill of sectors for the US stocks in the catalog snapshot."""

    def __init__(
        self,
        provider: SectorProfileProvider,
        catalog_store: InstrumentCatalogSnapshotStore,
        enrichment_store: SectorEnrichmentStore,
    ) -> None:
        self._provider = provider
        self._catalog_store = catalog_store
        self._enrichment_store = enrichment_store

    def pending_tickers(self) -> list[str]:
        df = self._catalog_store.read()
        if df is None or df.empty:
            raise CatalogUnavailableError(None, "kein Snapshot vorhanden")
        candidates = df[(df["instrument_type"] == "stock") & (df["country"] == "US")]
        done = self._enrichment_store.enriched_tickers()
        return sorted({str(t) for t in candidates["ticker"]} - done)

    def enrich_next(self, *, limit: int) -> SectorEnrichmentResult:
        pending = self.pending_tickers()
        batch = pending[: max(0, limit)]
        log.info(
            "catalog.enrich.start",
            pending=len(pending),
            batch=len(batch),
            limit=limit,
        )

        rows: list[dict[str, object]] = []
        enriched = missing = failed = 0
        rate_limited = False
        fetched_at = datetime.now(UTC).isoformat()

        for ticker in batch:
            try:
                profile = self._provider.fetch_sector_profile(ticker)
            except RateLimitedError as exc:
                log.warning("catalog.enrich.rate_limited", ticker=ticker, reason=str(exc))
                rate_limited = True
                break
            except ProviderError as exc:
                failed += 1
                log.warning("catalog.enrich.failed", ticker=ticker, reason=str(exc))
                continue

            if profile is None:
                missing += 1
                rows.append(
                    {"ticker": ticker, "sector": "", "industry": "", "fetched_at": fetched_at}
                )
                continue

            enriched += 1
            rows.append(
                {
                    "ticker": ticker,
                    "sector": profile.sector,
                    "industry": profile.industry,
                    "fetched_at": fetched_at,
                }
            )

        self._enrichment_store.upsert(rows)
        attempted = enriched + missing + failed
        remaining = len(pending) - attempted
        log.info(
            "catalog.enrich.complete",
            attempted=attempted,
            enriched=enriched,
            missing=missing,
            failed=failed,
            rate_limited=rate_limited,
            remaining=remaining,
        )
        return SectorEnrichmentResult(
            attempted=attempted,
            enriched=enriched,
            missing=missing,
            failed=failed,
            rate_limited=rate_limited,
            remaining=remaining,
        )


__all__ = [
    "SectorEnrichmentResult",
    "SectorEnrichmentService",
    "SectorEnrichmentStore",
    "SectorProfileProvider",
]
