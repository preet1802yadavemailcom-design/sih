from __future__ import annotations

from dataclasses import dataclass
import os


class ConfigurationError(RuntimeError):
    """Raised when required connector configuration is missing or invalid."""


@dataclass(frozen=True)
class SourceHTTPConfig:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ConfigurationError("base_url must not be empty")

        if self.timeout_seconds <= 0:
            raise ConfigurationError(
                "timeout_seconds must be greater than zero"
            )

    @classmethod
    def from_environment(
        cls,
        *,
        base_url_variable: str,
        api_key_variable: str | None = None,
        timeout_variable: str | None = None,
    ) -> "SourceHTTPConfig":
        base_url = os.getenv(base_url_variable)

        if not base_url:
            raise ConfigurationError(
                f"missing required environment variable: "
                f"{base_url_variable}"
            )

        api_key = (
            os.getenv(api_key_variable)
            if api_key_variable
            else None
        )

        timeout_seconds = 10.0

        if timeout_variable:
            raw_timeout = os.getenv(timeout_variable)

            if raw_timeout:
                try:
                    timeout_seconds = float(raw_timeout)
                except ValueError as exc:
                    raise ConfigurationError(
                        f"invalid timeout in environment variable: "
                        f"{timeout_variable}"
                    ) from exc

        return cls(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
