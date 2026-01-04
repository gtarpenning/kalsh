from __future__ import annotations

from functools import lru_cache
from typing import Any
from unittest.mock import Mock, patch

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from kalsh.client import KalshiClient, KalshiEnvironment


def _dummy_response(
    status_code: int,
    json_body: dict[str, Any],
    *,
    path: str = "",
) -> httpx.Response:
    uri = f"{KalshiEnvironment.DEMO.value}{path}"
    return httpx.Response(status_code, json=json_body, request=httpx.Request("GET", uri))


@lru_cache(maxsize=1)
def _sample_private_key() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _make_client(**kwargs: Any) -> KalshiClient:
    return KalshiClient(
        "key-id",
        _sample_private_key(),
        rate_limit_ms=0,
        **kwargs,
    )


def test_list_markets_builds_url_and_params():
    response = _dummy_response(200, {"markets": []}, path=KalshiClient.MARKETS_PATH)
    with patch("kalsh.client.httpx.Client.request", return_value=response) as mock_request:
        client = _make_client(environment=KalshiEnvironment.PROD)
        client.list_markets(status="open", per_page=10, cursor="abc")

        assert mock_request.call_count == 1
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert args[1] == KalshiClient.MARKETS_PATH
        assert kwargs["params"] == {"status": "open", "per_page": 10, "cursor": "abc"}
        assert client.base_url == KalshiEnvironment.PROD.value


def test_paginate_yields_all_pages():
    first = _dummy_response(
        200,
        {"data": [{"id": 1}], "next_cursor": "cursor-1"},
        path=KalshiClient.TRADES_PATH,
    )
    second = _dummy_response(
        200,
        {"data": [{"id": 2}], "next_cursor": None},
        path=KalshiClient.TRADES_PATH,
    )
    with patch(
        "kalsh.client.httpx.Client.request",
        side_effect=[first, second],
    ) as mock_request:
        client = _make_client()

        pages = list(client.paginate(KalshiClient.TRADES_PATH, params={"market_id": "foo"}))

        assert pages == [
            {"data": [{"id": 1}], "next_cursor": "cursor-1"},
            {"data": [{"id": 2}], "next_cursor": None},
        ]
        assert mock_request.call_count == 2
        assert mock_request.call_args_list[1][1]["params"]["cursor"] == "cursor-1"


def test_retry_on_transient_errors():
    transient = _dummy_response(429, {"error": "rate limited"}, path=KalshiClient.MARKETS_PATH)
    success = _dummy_response(200, {"markets": []}, path=KalshiClient.MARKETS_PATH)
    with patch(
        "kalsh.client.httpx.Client.request",
        side_effect=[transient, success],
    ) as mock_request:
        client = _make_client()
        client._sleep = Mock()

        client.list_markets()

        assert mock_request.call_count == 2
        client._sleep.assert_called()