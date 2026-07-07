"""Smoke test for package import."""

from quant_trader import __version__


def test_version_is_string() -> None:
    assert isinstance(__version__, str)
    assert len(__version__.split(".")) == 3


def test_sample_ticker_fixture(sample_ticker: str) -> None:
    assert sample_ticker == "SPY"
