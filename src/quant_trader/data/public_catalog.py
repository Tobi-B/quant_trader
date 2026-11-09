"""Key-free public sources for the instrument catalog.

FMP's catalog list endpoints (`/stable/stock-list` etc.) require a paid
plan and return HTTP 402 on the free tier, so the catalog is built from
public exchange sources instead (ADR-0019):

- NASDAQ Trader symbol directory: all US stocks and ETFs. This is the
  only source that carries class shares in dotted form (`BRK.B`), which
  US-P1.10 requires verbatim.
- Deutsche Boerse Xetra instrument file: EU stocks, ETFs, ETNs and ETCs
  with ISIN/WKN, plus DAX/MDAX/SDAX trading-group membership.
- CoinGecko: the top cryptocurrencies by market cap.

All three are HTTP GETs without an API key and are refreshed daily by
their publishers, so a catalog refresh costs nothing against the FMP
free-tier budget (NFR-Data-3).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterator, Mapping
from typing import cast

import requests

from quant_trader.core.errors import ProviderError
from quant_trader.core.logging import get_logger
from quant_trader.core.types import ExchangeDescriptor, Instrument

log = get_logger(__name__)

_NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
_OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
_XETRA_URL = (
    "https://www.xetra.com/resource/blob/1528/"
    "6a1e1c1d0dcaaeafa8d5be0e0dee2b40/data/allTradableInstruments.csv"
)
_COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

_TRAILER_PREFIX = "File Creation Time"

# otherlisted.txt encodes the venue as a single letter.
_OTHER_EXCHANGE_MAP = {
    "N": "NYSE",
    "P": "NYSE ARCA",
    "A": "NYSE AMERICAN",
    "Z": "CBOE BZX",
    "V": "IEX",
    "M": "NYSE CHICAGO",
}

# Xetra `Instrument Type` -> our instrument_type vocabulary.
_XETRA_TYPE_MAP = {
    "CS": "stock",
    "ETF": "etf",
    "ETN": "etn",
    "ETC": "etc",
}

# Xetra `Product Assignment Group` ids for the German index families.
_XETRA_INDEX_GROUPS = {
    "dax40": "DAX1",
    "mdax": "MDX1",
    "sdax": "SDX1",
}

_USER_AGENT = "QuantTrader/1.0 (instrument catalog refresh)"


def _session_or_default(session: requests.Session | None) -> requests.Session:
    if session is not None:
        return session
    created = requests.Session()
    created.headers.update({"User-Agent": _USER_AGENT})
    return created


def _get_text(session: requests.Session, url: str, source: str) -> str:
    try:
        response = session.get(url, timeout=60)
    except requests.RequestException as exc:
        raise ProviderError(source, f"network: {exc}") from exc
    if response.status_code != 200:
        raise ProviderError(source, f"HTTP {response.status_code}")
    return response.content.decode("utf-8", errors="replace")


def _pipe_rows(text: str) -> Iterator[Mapping[str, str]]:
    """Yield rows of a NASDAQ Trader file, dropping its trailer line."""
    lines = [
        line for line in text.splitlines() if line and not line.startswith(_TRAILER_PREFIX)
    ]
    yield from csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|")


class NasdaqTraderSource:
    """US stocks and ETFs from the official NASDAQ Trader symbol directory."""

    name = "nasdaqtrader"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = _session_or_default(session)

    def fetch_all(self) -> list[Instrument]:
        return [*self._fetch_nasdaq_listed(), *self._fetch_other_listed()]

    def _fetch_nasdaq_listed(self) -> list[Instrument]:
        text = _get_text(self._session, _NASDAQ_LISTED_URL, self.name)
        out: list[Instrument] = []
        for row in _pipe_rows(text):
            if row.get("Test Issue") == "Y":
                continue
            symbol = (row.get("Symbol") or "").strip()
            if not symbol:
                continue
            out.append(
                Instrument(
                    ticker=symbol.upper(),
                    name=(row.get("Security Name") or symbol).strip(),
                    exchange="NASDAQ",
                    currency="USD",
                    instrument_type="etf" if row.get("ETF") == "Y" else "stock",
                    country="US",
                    exchange_full_name="NASDAQ Stock Market",
                )
            )
        return out

    def _fetch_other_listed(self) -> list[Instrument]:
        text = _get_text(self._session, _OTHER_LISTED_URL, self.name)
        out: list[Instrument] = []
        for row in _pipe_rows(text):
            if row.get("Test Issue") == "Y":
                continue
            # ACT Symbol keeps class shares dotted (BRK.B); the NASDAQ Symbol
            # column carries the dashed variant (BRK-B) for the same listing.
            symbol = (row.get("ACT Symbol") or "").strip()
            if not symbol:
                continue
            exchange = _OTHER_EXCHANGE_MAP.get((row.get("Exchange") or "").strip(), "US OTHER")
            out.append(
                Instrument(
                    ticker=symbol.upper(),
                    name=(row.get("Security Name") or symbol).strip(),
                    exchange=exchange,
                    currency="USD",
                    instrument_type="etf" if row.get("ETF") == "Y" else "stock",
                    country="US",
                    exchange_full_name=exchange,
                )
            )
        return out


class XetraSource:
    """EU instruments and German index membership from Deutsche Boerse."""

    name = "xetra"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = _session_or_default(session)

    def _rows(self) -> list[Mapping[str, str]]:
        text = _get_text(self._session, _XETRA_URL, self.name)
        lines = text.splitlines()
        header_index = next(
            (i for i, line in enumerate(lines) if line.startswith("Product Status;")), None
        )
        if header_index is None:
            raise ProviderError(self.name, "unexpected file layout: no header row")
        reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])), delimiter=";")
        return [cast(Mapping[str, str], row) for row in reader]

    def fetch_all(self) -> list[Instrument]:
        out: list[Instrument] = []
        for row in self._rows():
            if row.get("Instrument Status") != "Active":
                continue
            mnemonic = (row.get("Mnemonic") or "").strip()
            if not mnemonic:
                continue
            out.append(
                Instrument(
                    ticker=mnemonic.upper(),
                    name=(row.get("Instrument") or mnemonic).strip(),
                    exchange="XETRA",
                    currency="EUR",
                    instrument_type=_XETRA_TYPE_MAP.get(
                        (row.get("Instrument Type") or "").strip(), "other"
                    ),
                    country=_country_from_isin(row.get("ISIN") or ""),
                    sector=(row.get("Product Assignment Group Description") or "").strip(),
                    exchange_full_name="Deutsche Boerse Xetra",
                )
            )
        return out

    def fetch_index_membership(self, index_id: str) -> list[str]:
        group = _XETRA_INDEX_GROUPS.get(index_id)
        if group is None:
            return []
        return [
            (row.get("Mnemonic") or "").strip().upper()
            for row in self._rows()
            if row.get("Product Assignment Group") == group
            and row.get("Instrument Status") == "Active"
            and (row.get("Mnemonic") or "").strip()
        ]


class CoinGeckoSource:
    """Top cryptocurrencies by market cap.

    `/coins/list` returns ~19k entries including a long tail of spam
    tokens that collide on common symbols, so the market-cap ranked
    endpoint is used instead - fewer, but each one is real.
    """

    name = "coingecko"

    def __init__(self, session: requests.Session | None = None, *, limit: int = 250) -> None:
        self._session = _session_or_default(session)
        self._limit = max(1, min(limit, 250))

    def fetch_all(self) -> list[Instrument]:
        try:
            response = self._session.get(
                _COINGECKO_MARKETS_URL,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": str(self._limit),
                    "page": "1",
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            raise ProviderError(self.name, f"network: {exc}") from exc
        if response.status_code != 200:
            raise ProviderError(self.name, f"HTTP {response.status_code}")

        payload = cast(object, response.json())
        if not isinstance(payload, list):
            raise ProviderError(self.name, "invalid JSON response")

        out: list[Instrument] = []
        for raw_row in payload:
            if not isinstance(raw_row, dict):
                continue
            row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
            symbol = row.get("symbol")
            name = row.get("name")
            if not isinstance(symbol, str) or not symbol.strip():
                continue
            out.append(
                Instrument(
                    ticker=symbol.strip().upper(),
                    name=str(name).strip() if isinstance(name, str) else symbol.strip().upper(),
                    exchange="CRYPTO",
                    currency="USD",
                    instrument_type="crypto",
                    exchange_full_name="CoinGecko aggregated",
                )
            )
        return out


class PublicCatalogProvider:
    """Composes the key-free sources into the `CatalogProvider` contract.

    A failure in one source is not fatal for the whole refresh: the
    remaining sources still produce a usable catalog, and the failure is
    logged. Only a total failure (every source down) raises, so the
    service's snapshot-fallback path takes over.
    """

    name = "public"

    def __init__(
        self,
        nasdaq: NasdaqTraderSource | None = None,
        xetra: XetraSource | None = None,
        coingecko: CoinGeckoSource | None = None,
    ) -> None:
        self._nasdaq = nasdaq if nasdaq is not None else NasdaqTraderSource()
        self._xetra = xetra if xetra is not None else XetraSource()
        self._coingecko = coingecko if coingecko is not None else CoinGeckoSource()
        # One refresh calls fetch_stock_list/fetch_etf_list/fetch_crypto_list
        # in turn; without memoising, each of them would re-download every
        # source (~10 MB and several seconds apiece).
        self._cache: list[Instrument] | None = None

    def _safe(
        self, source_name: str, fetch: Callable[[], list[Instrument]]
    ) -> list[Instrument]:
        try:
            return fetch()
        except ProviderError as exc:
            log.warning("catalog.source.failed", source=source_name, reason=str(exc))
            return []

    def _all_instruments(self) -> list[Instrument]:
        if self._cache is not None:
            return self._cache
        us = self._safe(self._nasdaq.name, self._nasdaq.fetch_all)
        eu = self._safe(self._xetra.name, self._xetra.fetch_all)
        crypto = self._safe(self._coingecko.name, self._coingecko.fetch_all)
        if not us and not eu and not crypto:
            raise ProviderError(self.name, "all catalog sources failed")
        log.info(
            "catalog.sources.fetched",
            us=len(us),
            eu=len(eu),
            crypto=len(crypto),
        )
        self._cache = [*us, *eu, *crypto]
        return self._cache

    def invalidate(self) -> None:
        """Drop the in-memory source cache so the next call re-downloads."""
        self._cache = None

    def _by_type(self, *wanted: str) -> list[Instrument]:
        return [i for i in self._all_instruments() if i.instrument_type in wanted]

    def fetch_stock_list(self) -> list[Instrument]:
        return self._by_type("stock")

    def fetch_etf_list(self) -> list[Instrument]:
        return self._by_type("etf", "etn", "etc")

    def fetch_fund_list(self) -> list[Instrument]:
        """Mutual funds are not covered by any of the public sources."""
        log.info("catalog.fund_list.unavailable", reason="not covered by public sources")
        return []

    def fetch_index_list(self) -> list[Instrument]:
        """Index instruments are not tradable listings in these sources."""
        return []

    def fetch_crypto_list(self) -> list[Instrument]:
        return self._by_type("crypto")

    def fetch_exchanges(self) -> list[ExchangeDescriptor]:
        seen: dict[str, str] = {}
        for instrument in self._all_instruments():
            if instrument.exchange and instrument.exchange not in seen:
                seen[instrument.exchange] = instrument.exchange_full_name or instrument.exchange
        return [ExchangeDescriptor(code=code, name=name) for code, name in sorted(seen.items())]

    def fetch_sectors(self) -> list[str]:
        return sorted({i.sector for i in self._all_instruments() if i.sector})

    def fetch_countries(self) -> list[str]:
        return sorted({i.country for i in self._all_instruments() if i.country})

    def fetch_index_membership(self, index_id: str) -> list[str]:
        if index_id in _XETRA_INDEX_GROUPS:
            return self._xetra.fetch_index_membership(index_id)
        raise ProviderError(
            self.name,
            f"unbekannter Index '{index_id}' "
            f"(bekannt: {', '.join(sorted(_XETRA_INDEX_GROUPS))})",
        )


def _country_from_isin(isin: str) -> str:
    """ISIN prefix is the issuer country code (DE0007164600 -> DE)."""
    cleaned = isin.strip().upper()
    if len(cleaned) >= 2 and cleaned[:2].isalpha():
        return cleaned[:2]
    return ""


__all__ = [
    "CoinGeckoSource",
    "NasdaqTraderSource",
    "PublicCatalogProvider",
    "XetraSource",
]
