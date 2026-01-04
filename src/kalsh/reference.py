from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from rich.console import Console

from .client import KalshiClient, KalshiEndpointSpec


CONSOLE = Console()


def generate_endpoint_reference(
    output_path: Path | str,
    *,
    endpoints: Sequence[KalshiEndpointSpec] | None = None,
) -> Path:
    destination = Path(output_path)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoints": [endpoint.to_dict() for endpoint in endpoints or KalshiClient.ENDPOINT_SPECS],
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n")
    CONSOLE.log(f"Written {len(payload['endpoints'])} endpoint entries to {destination}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump Kalshi endpoint metadata to disk.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("kalshi_api_reference.json"),
        help="Destination file for the reference data.",
    )
    args = parser.parse_args()
    generate_endpoint_reference(args.output)


if __name__ == "__main__":
    main()

