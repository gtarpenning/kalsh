from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ENV_COMMENT_PREFIX = "#"


def load_dotenv(path: Path | str = ".env") -> None:
    """Load key/value pairs from a dotenv-style file into `os.environ`."""
    dotenv_path = Path(path)
    if not dotenv_path.is_file():
        return

    for line in dotenv_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(ENV_COMMENT_PREFIX) or "=" not in stripped:
            continue
        key, value = map(str.strip, stripped.split("=", 1))
        if key and value:
            os.environ.setdefault(key, value)


def _read_secret_file(file_path: str | None) -> str | None:
    if not file_path:
        return None
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Secret file not found: {file_path}")
    return path.read_text().strip()


@dataclass(frozen=True)
class KalshiCredentials:
    api_key: str
    api_secret: str

    @classmethod
    def from_env(
        cls,
        *,
        dotenv: Path | str = ".env",
        env: Mapping[str, str] | None = None,
    ) -> "KalshiCredentials":
        load_dotenv(dotenv)

        mapping = env if env is not None else os.environ

        api_key = mapping.get("KALSHI_API_KEY") or _read_secret_file(
            mapping.get("KALSHI_API_KEY_FILE")
        )
        if not api_key:
            raise EnvironmentError("Missing Kalshi API key (set KALSHI_API_KEY or KALSHI_API_KEY_FILE)")

        api_secret = mapping.get("KALSHI_API_SECRET") or _read_secret_file(
            mapping.get("KALSHI_API_SECRET_FILE")
        )
        if not api_secret:
            raise EnvironmentError(
                "Missing Kalshi API secret (set KALSHI_API_SECRET or KALSHI_API_SECRET_FILE)"
            )

        return cls(api_key=api_key, api_secret=api_secret)

