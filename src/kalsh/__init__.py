"""Minimal kalsh package placeholder."""

from .client import KalshiClient, KalshiEnvironment
from .env import KalshiCredentials, load_dotenv
from .ingestion import KalshiIngestor
from .storage import Market, SQLiteStore, Store, Trade

__all__ = [
    "__version__",
    "KalshiClient",
    "KalshiEnvironment",
    "KalshiCredentials",
    "load_dotenv",
    "Market",
    "Trade",
    "Store",
    "SQLiteStore",
    "KalshiIngestor",
]

__version__ = "0.1.0"

