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