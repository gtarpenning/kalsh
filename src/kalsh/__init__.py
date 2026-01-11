"""Minimal kalsh package placeholder."""

from .client import KalshiClient, KalshiEnvironment
from .env import KalshiCredentials, load_dotenv
from .ingestion import KalshiIngestor
from .pipeline import (
    DetectionCase,
    PipelineConfig,
    PipelineReporter,
    PipelineRunner,
    storage_trade_to_rule_trade,
)
from . import schemas
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
    "PipelineRunner",
    "PipelineReporter",
    "PipelineConfig",
    "DetectionCase",
    "storage_trade_to_rule_trade",
    "schemas",
]

__version__ = "0.1.0"

