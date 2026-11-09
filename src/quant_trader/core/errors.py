"""Data layer error hierarchy."""

from __future__ import annotations


class DataError(Exception):
    """Base for all data-layer errors."""


class ProviderError(DataError):
    """A data provider failed; the failure may be transient or fallback-eligible."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider


class RateLimitedError(ProviderError):
    """Provider returned HTTP 429 or equivalent rate-limit response."""


class SearchUnavailableError(DataError):
    """The instrument search provider is unavailable."""

    def __init__(self, query: str, reason: str) -> None:
        super().__init__(f"{query}: {reason}")
        self.query = query
        self.reason = reason


class TickerNotFoundError(DataError):
    """The ticker does not exist on any provider."""

    def __init__(self, ticker: str) -> None:
        super().__init__(ticker)
        self.ticker = ticker


class DataUnavailableError(DataError):
    """All configured providers failed for a ticker."""

    def __init__(self, ticker: str, reasons: list[str]) -> None:
        super().__init__(f"{ticker}: {'; '.join(reasons)}")
        self.ticker = ticker
        self.reasons = reasons


class CatalogUnavailableError(DataError):
    """No instrument catalog snapshot could be produced or reused."""

    def __init__(self, last_snapshot_id: str | None, reason: str) -> None:
        super().__init__(f"{reason} (last_snapshot_id={last_snapshot_id})")
        self.last_snapshot_id = last_snapshot_id
        self.reason = reason


class CatalogRefreshError(DataError):
    """The catalog provider returned data that cannot be turned into a snapshot."""

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason


class EmptyUniverseSelectionError(DataError):
    """A filter/selection resolved to zero instruments; refuse to save it."""

    def __init__(self, name: str) -> None:
        super().__init__(f"'{name}' enthaelt keine Instrumente")
        self.name = name
