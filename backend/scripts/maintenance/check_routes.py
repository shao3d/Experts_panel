#!/usr/bin/env python3
"""Check available FastAPI routes."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="maintenance.check_routes",
)
from src.api.main import app


def main() -> int:
    print("Available routes:")
    print("=" * 60)

    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            methods = ",".join(route.methods) if route.methods else "N/A"
            print(f"{methods:10s} {route.path}")

    print("=" * 60)

    experts_route = any(
        hasattr(route, "path") and route.path == "/api/v1/experts"
        for route in app.routes
    )

    if experts_route:
        print("✅ /api/v1/experts endpoint found!")
        return 0

    print("❌ /api/v1/experts endpoint NOT found!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
