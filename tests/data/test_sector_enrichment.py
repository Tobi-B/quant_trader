"""Tests for the paced FMP sector backfill (ADR-0020)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from quant_trader.core.errors import (
    CatalogUnavailableError,
    ProviderError,
    RateLimitedError,
)
from quant_trader.core.types import SectorProfile
from quant_trader.data.instrument_catalog import InstrumentCatalogSnapshotStore
from quant_trader.data.sector_enrichment import (
    SectorEnrichmentService,
    SectorEnrichmentStore,
)


class _FakeProfileProvider:
    """Answers per ticker from a script; `RateLimitedError` stops the run."""

    def __init__(self, script: dict[str, SectorProfile | None | Exception]) -> None:
        self._script = script
        self.calls: list[str] = []

    def fetch_sector_profile(self, symbol: str) -> SectorProfile | None:
        self.calls.append(symbol)
        answer = self._script.get(symbol)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _snapshot_row(ticker: str, *, itype: str = "stock", country: str = "US") -> dict[str, object]:
    return {
        "ticker": ticker,
        "name": f"{ticker} Inc.",
        "exchange": "NASDAQ",
        "exchange_full_name": "NASDAQ",
        "currency": "USD",
        "instrument_type": itype,
        "country": country,
        "sector": "",
        "is_active": True,
    }


def _catalog(tmp_path: Path, rows: list[dict[str, object]]) -> InstrumentCatalogSnapshotStore:
    store = InstrumentCatalogSnapshotStore(tmp_path / "catalog" / "instruments.parquet")
    store.write(pd.DataFrame(rows), "snap-1")
    return store


def _service(
    tmp_path: Path,
    provider: _FakeProfileProvider,
    rows: list[dict[str, object]],
) -> tuple[SectorEnrichmentService, SectorEnrichmentStore]:
    enrichment = SectorEnrichmentStore(tmp_path / "catalog" / "sector_enrichment.parquet")
    service = SectorEnrichmentService(provider, _catalog(tmp_path, rows), enrichment)
    return service, enrichment


class TestSectorEnrichmentStore:
    def test_empty_store(self, tmp_path: Path) -> None:
        store = SectorEnrichmentStore(tmp_path / "x.parquet")
        assert store.exists() is False
        assert store.read() is None
        assert store.enriched_tickers() == set()
        assert store.sector_map() == {}

    def test_upsert_creates_parent_and_persists(self, tmp_path: Path) -> None:
        store = SectorEnrichmentStore(tmp_path / "deep" / "x.parquet")
        store.upsert(
            [{"ticker": "AAPL", "sector": "Technology", "industry": "", "fetched_at": "t"}]
        )
        assert store.exists()
        assert store.sector_map() == {"AAPL": "Technology"}

    def test_upsert_replaces_existing_ticker(self, tmp_path: Path) -> None:
        store = SectorEnrichmentStore(tmp_path / "x.parquet")
        store.upsert([{"ticker": "AAPL", "sector": "Old", "industry": "", "fetched_at": "t1"}])
        store.upsert([{"ticker": "AAPL", "sector": "New", "industry": "", "fetched_at": "t2"}])
        df = store.read()
        assert df is not None
        assert len(df) == 1
        assert store.sector_map() == {"AAPL": "New"}

    def test_empty_sector_counts_as_looked_up_but_not_mapped(self, tmp_path: Path) -> None:
        store = SectorEnrichmentStore(tmp_path / "x.parquet")
        store.upsert([{"ticker": "ZZZZ", "sector": "", "industry": "", "fetched_at": "t"}])
        assert store.enriched_tickers() == {"ZZZZ"}
        assert store.sector_map() == {}

    def test_upsert_with_no_rows_is_noop(self, tmp_path: Path) -> None:
        store = SectorEnrichmentStore(tmp_path / "x.parquet")
        store.upsert([])
        assert store.exists() is False

    def test_write_leaves_no_tmp_file(self, tmp_path: Path) -> None:
        store = SectorEnrichmentStore(tmp_path / "x.parquet")
        store.upsert([{"ticker": "A", "sector": "S", "industry": "", "fetched_at": "t"}])
        assert [p for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []


class TestSectorEnrichmentService:
    def test_pending_only_us_stocks_not_yet_enriched(self, tmp_path: Path) -> None:
        rows = [
            _snapshot_row("AAPL"),
            _snapshot_row("SPY", itype="etf"),
            _snapshot_row("SAP", country="DE"),
            _snapshot_row("MSFT"),
        ]
        service, enrichment = _service(tmp_path, _FakeProfileProvider({}), rows)
        enrichment.upsert(
            [{"ticker": "MSFT", "sector": "Technology", "industry": "", "fetched_at": "t"}]
        )

        assert service.pending_tickers() == ["AAPL"]

    def test_pending_without_snapshot_raises(self, tmp_path: Path) -> None:
        enrichment = SectorEnrichmentStore(tmp_path / "e.parquet")
        catalog = InstrumentCatalogSnapshotStore(tmp_path / "missing.parquet")
        service = SectorEnrichmentService(_FakeProfileProvider({}), catalog, enrichment)

        with pytest.raises(CatalogUnavailableError):
            service.pending_tickers()

    def test_enrich_next_respects_limit_and_persists(self, tmp_path: Path) -> None:
        provider = _FakeProfileProvider(
            {
                "AAPL": SectorProfile("Technology", "Consumer Electronics"),
                "JPM": SectorProfile("Financial Services", "Banks"),
                "MSFT": SectorProfile("Technology", "Software"),
            }
        )
        rows = [_snapshot_row("AAPL"), _snapshot_row("JPM"), _snapshot_row("MSFT")]
        service, enrichment = _service(tmp_path, provider, rows)

        result = service.enrich_next(limit=2)

        assert provider.calls == ["AAPL", "JPM"]
        assert result.attempted == 2
        assert result.enriched == 2
        assert result.remaining == 1
        assert result.rate_limited is False
        assert enrichment.sector_map() == {"AAPL": "Technology", "JPM": "Financial Services"}

    def test_enrich_next_is_resumable_across_runs(self, tmp_path: Path) -> None:
        provider = _FakeProfileProvider(
            {
                "AAPL": SectorProfile("Technology", ""),
                "JPM": SectorProfile("Financial Services", ""),
            }
        )
        service, enrichment = _service(
            tmp_path, provider, [_snapshot_row("AAPL"), _snapshot_row("JPM")]
        )

        service.enrich_next(limit=1)
        second = service.enrich_next(limit=1)

        assert provider.calls == ["AAPL", "JPM"]
        assert second.remaining == 0
        assert set(enrichment.sector_map()) == {"AAPL", "JPM"}

    def test_missing_profile_is_recorded_so_it_is_not_retried(self, tmp_path: Path) -> None:
        provider = _FakeProfileProvider({"ZZZZ": None})
        service, enrichment = _service(tmp_path, provider, [_snapshot_row("ZZZZ")])

        first = service.enrich_next(limit=10)
        second = service.enrich_next(limit=10)

        assert first.missing == 1
        assert second.attempted == 0
        assert provider.calls == ["ZZZZ"]
        assert enrichment.enriched_tickers() == {"ZZZZ"}
        assert enrichment.sector_map() == {}

    def test_provider_error_is_counted_and_retried_next_run(self, tmp_path: Path) -> None:
        provider = _FakeProfileProvider({"AAPL": ProviderError("fmp", "HTTP 500")})
        service, enrichment = _service(tmp_path, provider, [_snapshot_row("AAPL")])

        result = service.enrich_next(limit=10)

        assert result.failed == 1
        assert result.remaining == 0
        assert enrichment.enriched_tickers() == set()
        assert service.pending_tickers() == ["AAPL"]

    def test_rate_limit_stops_run_but_keeps_progress(self, tmp_path: Path) -> None:
        provider = _FakeProfileProvider(
            {
                "AAPL": SectorProfile("Technology", ""),
                "JPM": RateLimitedError("fmp", "HTTP 429"),
                "MSFT": SectorProfile("Technology", ""),
            }
        )
        rows = [_snapshot_row("AAPL"), _snapshot_row("JPM"), _snapshot_row("MSFT")]
        service, enrichment = _service(tmp_path, provider, rows)

        result = service.enrich_next(limit=10)

        assert result.rate_limited is True
        assert result.enriched == 1
        assert result.remaining == 2
        assert provider.calls == ["AAPL", "JPM"]
        assert enrichment.sector_map() == {"AAPL": "Technology"}

    def test_zero_limit_attempts_nothing(self, tmp_path: Path) -> None:
        provider = _FakeProfileProvider({"AAPL": SectorProfile("Technology", "")})
        service, _ = _service(tmp_path, provider, [_snapshot_row("AAPL")])

        result = service.enrich_next(limit=0)

        assert result.attempted == 0
        assert result.remaining == 1
        assert provider.calls == []
