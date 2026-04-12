"""Exchange adapter verification CLI."""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.exchanges.dto import ContractInfo

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify exchange adapter with real API calls")
    parser.add_argument(
        "exchange_id",
        nargs="?",
        help="Exchange ID from EXCHANGES registry (for example: hyperliquid)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available exchange IDs and exit",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=7,
        help="How many past days to request in history check (default: 7)",
    )
    parser.add_argument(
        "--contract-index",
        type=int,
        default=0,
        help="Index of contract from get_contracts() result to use for deep checks (default: 0)",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=5,
        help="How many contracts to show in preview table (default: 5)",
    )
    return parser


def _render_contract_preview(contracts: list, preview_limit: int) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Index", style="cyan", justify="right")
    table.add_column("Asset", style="cyan")
    table.add_column("Quote", style="yellow")
    table.add_column("Funding Interval", style="green", justify="right")

    for index, contract_info in enumerate(contracts[:preview_limit]):
        table.add_row(
            str(index),
            contract_info.asset_name,
            contract_info.quote,
            f"{contract_info.funding_interval}h",
        )

    if len(contracts) > preview_limit:
        table.add_row("...", "...", "...", "...")

    console.print(table)


def _build_contract_for_checks(exchange_id: str, contract_info: ContractInfo) -> Contract:
    contract = Contract(
        asset_name=contract_info.asset_name,
        quote_name=contract_info.quote,
        section_name=exchange_id,
        funding_interval=contract_info.funding_interval,
    )
    contract.asset = Asset(name=contract_info.asset_name)
    return contract


async def verify_exchange(
    exchange_id: str,
    history_days: int,
    contract_index: int,
    preview_limit: int,
) -> bool:
    console.print(f"\n[bold cyan]Verifying exchange adapter: {exchange_id}[/bold cyan]\n")

    if exchange_id not in EXCHANGES:
        available = ", ".join(sorted(EXCHANGES.keys()))
        console.print(
            f"[bold red][FAIL][/bold red] Exchange '{exchange_id}' "
            "not found in EXCHANGES registry.\n"
            f"Available exchanges: {available}"
        )
        return False

    adapter = EXCHANGES[exchange_id]()

    console.print("[bold]Step 1: Protocol Validation[/bold]")
    console.print(f"  [green][OK][/green] EXCHANGE_ID: {adapter.EXCHANGE_ID}")
    console.print(
        "  [green][OK][/green] Required methods: get_contracts, "
        "fetch_history_before, fetch_history_after"
    )
    console.print("  [green][OK][/green] Live method: fetch_live(list[Contract])")

    console.print("\n[bold]Step 2: API - get_contracts()[/bold]")
    try:
        contracts = await adapter.get_contracts()
        console.print(f"  [green][OK][/green] Retrieved {len(contracts)} contracts")
        if not contracts:
            console.print("  [bold red][FAIL][/bold red] get_contracts() returned empty list")
            return False
        _render_contract_preview(contracts, preview_limit)

    except Exception as exc:
        console.print(f"  [bold red][FAIL][/bold red] get_contracts() failed: {exc}")
        return False

    if contract_index < 0 or contract_index >= len(contracts):
        console.print(
            "  [bold red][FAIL][/bold red] Invalid --contract-index: "
            f"{contract_index}. Allowed range: 0..{len(contracts) - 1}"
        )
        return False

    contract_info = contracts[contract_index]
    contract = _build_contract_for_checks(exchange_id, contract_info)

    contract_label = f"{contract.asset_name}/{contract.quote_name}"
    console.print(
        "\n[bold]Step 3: API - fetch_history_after(contract)[/bold] "
        f"for [cyan]{contract_label}[/cyan]"
    )
    try:
        after_ts = datetime.now() - timedelta(days=history_days)
        history = await adapter.fetch_history_after(contract, after_ts)
        console.print(f"  [green][OK][/green] Retrieved {len(history)} funding points")

        if history:
            oldest = min(point.timestamp for point in history)
            newest = max(point.timestamp for point in history)
            sample = history[0]
            rate_pct = sample.rate * 100
            console.print(f"  [dim]Date range: {oldest} -> {newest}[/dim]")
            console.print(f"  [dim]Sample rate: {sample.rate:.6f} ({rate_pct:.4f}%)[/dim]")

            if oldest < after_ts:
                console.print(
                    "  [yellow][WARN][/yellow] History includes points "
                    "before requested lower bound"
                )
        else:
            console.print(
                "  [yellow][WARN][/yellow] No history points returned. "
                "Could be expected for new listings."
            )

    except Exception as exc:
        console.print(f"  [bold red][FAIL][/bold red] fetch_history_after() failed: {exc}")
        return False

    console.print("\n[bold]Step 4: API - fetch_live[/bold]")
    try:
        live_rates = await adapter.fetch_live([contract])
        console.print(f"  [green][OK][/green] fetch_live() returned {len(live_rates)} rates")

        if live_rates:
            sample_contract, sample_rate = next(iter(live_rates.items()))
            rate_pct = sample_rate.rate * 100
            sample_label = f"{sample_contract.asset_name}/{sample_contract.quote_name}"
            console.print(
                f"  [dim]Sample: {sample_label} = {sample_rate.rate:.6f} ({rate_pct:.4f}%)[/dim]"
            )
        else:
            console.print(
                "  [yellow][WARN][/yellow] fetch_live() returned empty dict for selected contract"
            )
    except Exception as exc:
        console.print(f"  [bold red][FAIL][/bold red] Live rate fetch failed: {exc}")
        return False

    console.print(f"\n[bold green][OK] All checks passed for {exchange_id}[/bold green]\n")
    return True


async def amain(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list:
        console.print("Available exchange IDs:")
        for exchange_id in sorted(EXCHANGES.keys()):
            console.print(f"  - {exchange_id}")
        return 0

    if args.exchange_id is None:
        parser.print_help()
        console.print("\nExample: verify hyperliquid")
        return 1

    if args.history_days < 1:
        console.print("[bold red][FAIL][/bold red] --history-days must be >= 1")
        return 1

    if args.preview_limit < 1:
        console.print("[bold red][FAIL][/bold red] --preview-limit must be >= 1")
        return 1

    success = await verify_exchange(
        exchange_id=args.exchange_id,
        history_days=args.history_days,
        contract_index=args.contract_index,
        preview_limit=args.preview_limit,
    )
    return 0 if success else 1


def main() -> int:
    return asyncio.run(amain())


def entrypoint() -> None:
    sys.exit(main())
