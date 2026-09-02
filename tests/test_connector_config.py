from __future__ import annotations

import pytest

from packages.connectors.config import (
    ConfigurationError,
    SourceHTTPConfig,
)


def test_config_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("TEST_BASE_URL", "https://api.example.invalid")
    monkeypatch.setenv("TEST_API_KEY", "secret-test-key")
    monkeypatch.setenv("TEST_TIMEOUT", "7.5")

    config = SourceHTTPConfig.from_environment(
        base_url_variable="TEST_BASE_URL",
        api_key_variable="TEST_API_KEY",
        timeout_variable="TEST_TIMEOUT",
    )

    assert config.base_url == "https://api.example.invalid"
    assert config.api_key == "secret-test-key"
    assert config.timeout_seconds == 7.5


def test_config_requires_base_url(monkeypatch) -> None:
    monkeypatch.delenv("TEST_BASE_URL", raising=False)

    with pytest.raises(
        ConfigurationError,
        match="TEST_BASE_URL",
    ):
        SourceHTTPConfig.from_environment(
            base_url_variable="TEST_BASE_URL",
        )


def test_config_rejects_invalid_timeout() -> None:
    with pytest.raises(ConfigurationError, match="base_url"):
        SourceHTTPConfig(
            base_url="",
        )


def test_config_rejects_non_positive_timeout() -> None:
    with pytest.raises(
        ConfigurationError,
        match="greater than zero",
    ):
        SourceHTTPConfig(
            base_url="https://api.example.invalid",
            timeout_seconds=0,
        )


def test_config_rejects_invalid_timeout_environment(monkeypatch) -> None:
    monkeypatch.setenv("TEST_BASE_URL", "https://api.example.invalid")
    monkeypatch.setenv("TEST_TIMEOUT", "not-a-number")

    with pytest.raises(
        ConfigurationError,
        match="TEST_TIMEOUT",
    ):
        SourceHTTPConfig.from_environment(
            base_url_variable="TEST_BASE_URL",
            timeout_variable="TEST_TIMEOUT",
        )


def test_api_key_is_optional(monkeypatch) -> None:
    monkeypatch.setenv("TEST_BASE_URL", "https://api.example.invalid")
    monkeypatch.delenv("TEST_API_KEY", raising=False)

    config = SourceHTTPConfig.from_environment(
        base_url_variable="TEST_BASE_URL",
        api_key_variable="TEST_API_KEY",
    )

    assert config.api_key is None
