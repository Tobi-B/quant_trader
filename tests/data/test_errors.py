"""Tests for data-layer error hierarchy."""

from __future__ import annotations

import pytest

from quant_trader.core.errors import (
    DataError,
    DataUnavailableError,
    ProviderError,
    RateLimitedError,
    TickerNotFoundError,
)


def test_data_error_is_base() -> None:
    assert issubclass(DataError, Exception)


def test_provider_error_carries_provider_name() -> None:
    err = ProviderError("alphavantage", "boom")

    assert err.provider == "alphavantage"
    assert "alphavantage" in str(err)
    assert "boom" in str(err)
    assert isinstance(err, DataError)


def test_rate_limited_is_provider_error() -> None:
    err = RateLimitedError("alphavantage", "HTTP 429")

    assert err.provider == "alphavantage"
    assert isinstance(err, ProviderError)
    assert isinstance(err, DataError)


def test_ticker_not_found_carries_ticker() -> None:
    err = TickerNotFoundError("ZZZZZ")

    assert err.ticker == "ZZZZZ"
    assert str(err) == "ZZZZZ"
    assert isinstance(err, DataError)


def test_data_unavailable_carries_reasons() -> None:
    err = DataUnavailableError("XYZ", ["primary failed", "secondary failed"])

    assert err.ticker == "XYZ"
    assert err.reasons == ["primary failed", "secondary failed"]
    assert "primary failed" in str(err)
    assert "secondary failed" in str(err)
    assert isinstance(err, DataError)


@pytest.mark.parametrize("exc_class", [DataError, ProviderError, RateLimitedError, TickerNotFoundError, DataUnavailableError])
def test_all_errors_subclass_data_error(exc_class: type) -> None:
    assert issubclass(exc_class, DataError)