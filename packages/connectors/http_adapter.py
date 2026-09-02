from __future__ import annotations

from abc import abstractmethod
from typing import Any

from packages.connectors.adapter import SourceAdapter
from packages.connectors.base import CollectionRequest
from packages.connectors.config import SourceHTTPConfig
from packages.connectors.transport import (
    HTTPResponse,
    HTTPTransport,
    RetryingTransport,
    build_auth_headers,
    validate_http_url,
)
from packages.contracts.models import QuoteIn


class HTTPAdapterError(RuntimeError):
    """Raised when an HTTP source adapter receives an invalid payload."""


class HTTPSourceAdapter(SourceAdapter):
    """Reusable boundary for authorized HTTP-based source adapters."""

    def __init__(
        self,
        *,
        capability,
        config: SourceHTTPConfig,
        transport: HTTPTransport,
    ) -> None:
        self.source_id = capability.source_id
        self.capability = capability
        self.config = config
        self.transport = RetryingTransport(transport)

        validate_http_url(config.base_url)

    @property
    @abstractmethod
    def endpoint_path(self) -> str:
        raise NotImplementedError

    @property
    def http_method(self) -> str:
        return "POST"

    def build_request(
        self,
        request: CollectionRequest,
    ) -> tuple[dict[str, Any] | None, Any]:
        return None, {
            "origin": request.origin_iata,
            "destination": request.destination_iata,
            "departure_at": request.departure_at.isoformat(),
        }

    def extract_payloads(
        self,
        payload: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(payload, list):
            raise HTTPAdapterError(
                "source response payload must be a list"
            )

        if not all(isinstance(item, dict) for item in payload):
            raise HTTPAdapterError(
                "source response items must be objects"
            )

        return payload

    def fetch(
        self,
        request: CollectionRequest,
    ) -> list[dict[str, Any]]:
        validate_http_url(self.config.base_url)

        endpoint = (
            f"{self.config.base_url.rstrip('/')}/"
            f"{self.endpoint_path.lstrip('/')}"
        )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **build_auth_headers(self.config.api_key),
        }

        params, body = self.build_request(request)

        response: HTTPResponse = self.transport.request(
            self.http_method,
            endpoint,
            headers=headers,
            params=params,
            json=body,
            timeout_seconds=self.config.timeout_seconds,
        )

        return self.extract_payloads(response.payload)

    def canonicalize(
        self,
        payloads: list[dict[str, Any]],
    ) -> list[QuoteIn]:
        """Convert source payloads into APIx canonical quote contracts."""
        canonical: list[QuoteIn] = []

        for payload in payloads:
            try:
                quote = self.map_quote(payload)
            except Exception as exc:
                raise HTTPAdapterError(
                    "source payload could not be mapped to QuoteIn"
                ) from exc

            if not isinstance(quote, QuoteIn):
                raise HTTPAdapterError(
                    "map_quote must return QuoteIn"
                )

            canonical.append(quote)

        return canonical
