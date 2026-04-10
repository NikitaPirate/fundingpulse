"""CLI argument parsing for funding tracker."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser used by the main entrypoint."""
    parser = argparse.ArgumentParser(
        description="Funding tracker - Crypto funding rate collection and analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all exchanges (default)
  funding-tracker

  # Run specific exchanges via CLI
  funding-tracker --exchanges hyperliquid,bybit

  # Run single exchange
  funding-tracker --exchanges hyperliquid

  # Enable debug logging for specific exchanges
  funding-tracker --exchanges hyperliquid --debug-exchanges hyperliquid,bybit

Instance Scaling:
  --instance-id N      Instance identifier (default: from env, fallback 0)
  --total-instances N  Total number of instances (default: from env, fallback 1)

Environment Variables:
  EXCHANGES            Comma-separated list of exchanges (overridden by CLI)
  DEBUG_EXCHANGES      Comma-separated list for debug logging
  DEBUG_EXCHANGES_LIVE Comma-separated list for live collection debug logging
  INSTANCE_ID          Instance identifier for multi-instance deployment
  TOTAL_INSTANCES      Total number of instances
        """,
    )

    parser.add_argument(
        "--exchanges",
        type=str,
        default=None,
        help="Comma-separated list of exchanges to run (default: all).",
    )
    parser.add_argument(
        "--debug-exchanges",
        type=str,
        default=None,
        help="Comma-separated list of exchanges for DEBUG logging.",
    )
    parser.add_argument(
        "--debug-exchanges-live",
        type=str,
        default=None,
        help="Comma-separated list of exchanges for live collection DEBUG logging.",
    )
    parser.add_argument(
        "--instance-id",
        type=int,
        default=None,
        help="Instance identifier for multi-instance deployment.",
    )
    parser.add_argument(
        "--total-instances",
        type=int,
        default=None,
        help="Total number of instances for exchange distribution.",
    )

    return parser
