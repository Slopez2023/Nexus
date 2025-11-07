#!/usr/bin/env python3
"""CLI script to run the NEXUS Data API server."""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nexus.core.data_api import get_data_api
from nexus.core.logging import setup_logging


def main():
    """Run the Data API server."""
    parser = argparse.ArgumentParser(description="NEXUS Data API Server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind server to (default: 8000)"
    )
    parser.add_argument(
        "--config",
        help="Path to config file"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Get API instance
    config = {}
    if args.config:
        # TODO: Load config from file
        pass

    api = get_data_api(config)

    print("🚀 Starting NEXUS Data API...")
    print(f"📍 Server will be available at: http://{args.host}:{args.port}")
    print(f"📊 API Documentation: http://{args.host}:{args.port}/docs")
    print("🛑 Press Ctrl+C to stop")

    try:
        api.run_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\n👋 Shutting down NEXUS Data API...")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
