from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterator, Mapping, Sequence

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .env import KalshiCredentials


def _load_private_key(pem_or_content: str) -> rsa.RSAPrivateKey:
    stripped = pem_or_content.strip()
    if stripped.startswith("-----BEGIN"):
        raw = stripped.encode("utf-8")
    else:
        raw = base64.b64decode(stripped)
    return serialization.load_pem_private_key(raw, password=None)


class KalshiEnvironment(Enum):
    DEMO = "https://demo-api.kalshi.co"
    PROD = "https://api.elections.kalshi.com"


@dataclass(frozen=True)
class KalshiEndpointSpec:
    name: str
    method: str
    path: str
    description: str
    params: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "path": self.path,
            "description": self.description,
            "params": list(self.params),
        }


class KalshiAuth:
    def __init__(self, key_id: str, private_key: rsa.RSAPrivateKey) -> None:
        self._key_id = key_id
        self._private_key = private_key

    def headers(self, method: str, path: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        base_path = path.split("?", 1)[0]
        payload = (timestamp + method.upper() + base_path).encode("utf-8")
        signature = base64.b64encode(
            self._private_key.sign(
                payload,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH,
                ),
                hashes.SHA256(),
            )
        ).decode("utf-8")
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }


class KalshiClient:
    MARKETS_PATH = "/trade-api/v2/markets"
    TRADES_PATH = MARKETS_PATH + "/trades"
    EXCHANGE_STATUS_PATH = "/trade-api/v2/exchange/status"
    BALANCE_PATH = "/trade-api/v2/portfolio/balance"

    ENDPOINT_SPECS: Sequence[KalshiEndpointSpec] = (
        KalshiEndpointSpec(
            name="list_markets",
            method="GET",
            path=MARKETS_PATH,
            description="List visible markets.",
            params=("status", "per_page", "cursor"),
        ),
        KalshiEndpointSpec(
            name="list_trades",
            method="GET",
            path=TRADES_PATH,
            description="List trades for a market.",
            params=("market_id", "ticker", "limit", "cursor", "min_ts", "max_ts", "status"),
        ),
        KalshiEndpointSpec(
            name="get_exchange_status",
            method="GET",
            path=EXCHANGE_STATUS_PATH,
            description="Fetch exchange health or status.",
            params=(),
        ),
        KalshiEndpointSpec(
            name="get_balance",
            method="GET",
            path=BALANCE_PATH,
            description="Retrieve portfolio balance.",
            params=(),
        ),
    )

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        *,
        credentials: KalshiCredentials | None = None,
        environment: KalshiEnvironment = KalshiEnvironment.DEMO,
        client_factory: Callable[[], httpx.Client] | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        sleep_func: Callable[[float], None] | None = None,
        rate_limit_ms: int = 100,
    ) -> None:
        if credentials:
            api_key = credentials.api_key
            api_secret = credentials.api_secret
        if not api_key or not api_secret:
            raise ValueError("KalshiClient requires api_key and api_secret")
        self.base_url = environment.value
        self._client = client_factory() if client_factory else httpx.Client(base_url=self.base_url)
        self._auth = KalshiAuth(api_key, _load_private_key(api_secret))
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._sleep = sleep_func or time.sleep
        self._rate_limit_ms = max(rate_limit_ms, 0)
        self._last_api_call = datetime.now(timezone.utc) - timedelta(milliseconds=self._rate_limit_ms)

    def list_markets(
        self,
        *,
        status: str | None = None,
        per_page: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = self._build_params(status=status, per_page=per_page, cursor=cursor)
        return self._get(self.MARKETS_PATH, params=params)

    def list_trades(
        self,
        *,
        market_id: str | None = None,
        status: str | None = None,
        per_page: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
    ) -> dict[str, Any]:
        params = self._build_params(
            market_id=market_id,
            status=status,
            per_page=per_page,
            cursor=cursor,
            limit=limit,
            min_ts=min_ts,
            max_ts=max_ts,
        )
        return self._get(self.TRADES_PATH, params=params)

    def get_exchange_status(self) -> dict[str, Any]:
        return self._get(self.EXCHANGE_STATUS_PATH)

    def get_balance(self) -> dict[str, Any]:
        return self._get(self.BALANCE_PATH)

    def paginate(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        next_cursor: str | None = None
        while True:
            request_params = dict(params or {})
            if next_cursor:
                request_params["cursor"] = next_cursor
            response_json = self._request("GET", path, params=request_params).json()
            yield response_json
            next_cursor = response_json.get("next_cursor")
            if not next_cursor:
                break

    def _get(self, path: str, *, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params).json()

    def _build_params(self, **kwargs: Any) -> Mapping[str, Any] | None:
        filtered = {key: value for key, value in kwargs.items() if value is not None}
        return filtered or None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
        headers = self._auth.headers(method, path)
        attempt = 0
        while True:
            attempt += 1
            self._enforce_rate_limit()
            response = self._client.request(method, path, params=params, json=json, headers=headers)
            if not self._should_retry(response):
                return response
            if attempt > self._max_retries:
                response.raise_for_status()
            delay = self._backoff_factor * (2 ** (attempt - 1))
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    pass
            self._sleep(delay)

    def _should_retry(self, response: httpx.Response) -> bool:
        return response.status_code == 429 or 500 <= response.status_code < 600

    def _enforce_rate_limit(self) -> None:
        current = datetime.now(timezone.utc)
        if self._rate_limit_ms <= 0:
            self._last_api_call = current
            return
        elapsed = current - self._last_api_call
        required = timedelta(milliseconds=self._rate_limit_ms)
        remaining = required - elapsed
        if remaining.total_seconds() > 0:
            self._sleep(remaining.total_seconds())
        self._last_api_call = datetime.now(timezone.utc)