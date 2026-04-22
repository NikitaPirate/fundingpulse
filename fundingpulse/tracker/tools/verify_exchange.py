"""Exchange adapter verification CLI."""

import argparse
import asyncio
import sys
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from rich.console import Console
from rich.table import Table

from fundingpulse.time import utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing
from fundingpulse.tracker.infrastructure import http_client

console = Console()
ROUND_CONTRACT_COUNT_WARNINGS = {50, 100, 200, 500, 1000}


@dataclass(slots=True)
class VerifySummary:
    exchange_id: str
    success: bool
    detail: str
    contract_count: int | None = None
    selected_contract: str | None = None
    history_count: int | None = None
    live_count: int | None = None
    round_count_warning: bool = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify exchange adapter against real exchange API without DB or scheduler"
    )
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
        "--all",
        action="store_true",
        help="Verify all registered exchanges and print a compact summary",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=7,
        help="How many past days to request in history check (default: 7)",
    )
    parser.add_argument(
        "--contract",
        type=str,
        default=None,
        help="Contract to use for deep checks in ASSET/QUOTE form (for example: BTC/USDT)",
    )
    parser.add_argument(
        "--contract-index",
        type=int,
        default=0,
        help=(
            "Index of contract from get_contracts() result to use for deep checks "
            "(used when --contract is not set, default: 0)"
        ),
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=5,
        help="How many contracts to show in preview table (default: 5)",
    )
    parser.add_argument(
        "--show-all-contracts",
        action="store_true",
        help="Print all contracts in adapter order instead of a short preview",
    )
    parser.add_argument(
        "--contracts-only",
        action="store_true",
        help="Only fetch and print contracts, then exit without history/live checks",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Optional timeout for a single exchange verification",
    )
    return parser


def _render_contracts(
    contracts: list[ExchangeContractListing], preview_limit: int, show_all: bool
) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Index", style="cyan", justify="right")
    table.add_column("Asset", style="cyan")
    table.add_column("Quote", style="yellow")
    table.add_column("Funding Interval", style="green", justify="right")

    contracts_to_render = contracts if show_all else contracts[:preview_limit]
    for index, contract_info in enumerate(contracts_to_render):
        table.add_row(
            str(index),
            contract_info.asset_name,
            contract_info.quote_name,
            f"{contract_info.funding_interval}h",
        )

    if not show_all and len(contracts) > preview_limit:
        table.add_row("...", "...", "...", "...")

    console.print(table)


def _build_contract_for_checks(
    exchange_id: str, listing: ExchangeContractListing
) -> TrackedContract:
    return TrackedContract(
        id=uuid4(),
        asset_name=listing.asset_name,
        quote_name=listing.quote_name,
        section_name=exchange_id,
        funding_interval=listing.funding_interval,
    )


def _warn_if_contract_count_looks_truncated(contracts: list[ExchangeContractListing]) -> None:
    count = len(contracts)
    if count in ROUND_CONTRACT_COUNT_WARNINGS:
        console.print(
            "  [yellow][WARN][/yellow] Contract count is a round number "
            f"({count}). If this exchange paginates, inspect full output with "
            "[bold]--show-all-contracts[/bold]."
        )


def _find_contract_index(
    contracts: list[ExchangeContractListing], contract_spec: str | None
) -> int | None:
    if contract_spec is None:
        return None

    asset_name, separator, quote = contract_spec.partition("/")
    if separator != "/" or not asset_name or not quote:
        raise ValueError("--contract must use ASSET/QUOTE form, for example BTC/USDT")

    normalized_asset = asset_name.strip().upper()
    normalized_quote = quote.strip().upper()

    for index, contract in enumerate(contracts):
        if (
            contract.asset_name.upper() == normalized_asset
            and contract.quote_name.upper() == normalized_quote
        ):
            return index

    available = ", ".join(
        f"{contract.asset_name}/{contract.quote_name}" for contract in contracts[:10]
    )
    raise ValueError(
        f"Contract {normalized_asset}/{normalized_quote} not found. "
        f"First contracts returned by adapter: {available}"
    )


async def _verify_exchange_summary(
    exchange_id: str,
    history_days: int,
    contract_spec: str | None,
    contract_index: int,
    contracts_only: bool,
) -> VerifySummary:
    if exchange_id not in EXCHANGES:
        available = ", ".join(sorted(EXCHANGES.keys()))
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail=f"unknown exchange, available: {available}",
        )

    adapter = EXCHANGES[exchange_id]()

    try:
        contracts = await adapter.get_contracts()
    except Exception as exc:
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail=f"get_contracts failed: {exc}",
        )

    if not contracts:
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail="get_contracts returned empty list",
        )

    round_count_warning = len(contracts) in ROUND_CONTRACT_COUNT_WARNINGS
    if contracts_only:
        return VerifySummary(
            exchange_id=exchange_id,
            success=True,
            detail="contracts fetched",
            contract_count=len(contracts),
            round_count_warning=round_count_warning,
        )

    try:
        selected_contract_index = _find_contract_index(contracts, contract_spec)
    except ValueError as exc:
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail=str(exc),
            contract_count=len(contracts),
            round_count_warning=round_count_warning,
        )

    if selected_contract_index is not None:
        contract_index = selected_contract_index

    if contract_index < 0 or contract_index >= len(contracts):
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail=f"invalid contract index {contract_index}, max={len(contracts) - 1}",
            contract_count=len(contracts),
            round_count_warning=round_count_warning,
        )

    listing = contracts[contract_index]
    contract = _build_contract_for_checks(exchange_id, listing)
    selected_contract = f"{contract.asset_name}/{contract.quote_name}"

    try:
        history = await adapter.fetch_history_after(
            contract,
            utc_now() - timedelta(days=history_days),
        )
    except Exception as exc:
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail=f"fetch_history_after failed: {exc}",
            contract_count=len(contracts),
            selected_contract=selected_contract,
            round_count_warning=round_count_warning,
        )

    try:
        live_rates = await adapter.fetch_live([contract])
    except Exception as exc:
        return VerifySummary(
            exchange_id=exchange_id,
            success=False,
            detail=f"fetch_live failed: {exc}",
            contract_count=len(contracts),
            selected_contract=selected_contract,
            history_count=len(history),
            round_count_warning=round_count_warning,
        )

    return VerifySummary(
        exchange_id=exchange_id,
        success=True,
        detail="all checks passed",
        contract_count=len(contracts),
        selected_contract=selected_contract,
        history_count=len(history),
        live_count=len(live_rates),
        round_count_warning=round_count_warning,
    )


async def _run_with_timeout[T](operation: Awaitable[T], timeout_seconds: float | None) -> T:
    if timeout_seconds is None:
        return await operation

    async with asyncio.timeout(timeout_seconds):
        return await operation


def _render_batch_summary(results: list[VerifySummary]) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Exchange", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Contracts", justify="right")
    table.add_column("Selected")
    table.add_column("History", justify="right")
    table.add_column("Live", justify="right")
    table.add_column("Details")

    for result in results:
        status = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
        if result.success and result.round_count_warning:
            status = "[yellow]WARN[/yellow]"

        table.add_row(
            result.exchange_id,
            status,
            str(result.contract_count) if result.contract_count is not None else "-",
            result.selected_contract or "-",
            str(result.history_count) if result.history_count is not None else "-",
            str(result.live_count) if result.live_count is not None else "-",
            result.detail,
        )

    console.print(table)

    success_count = sum(1 for result in results if result.success)
    warning_count = sum(1 for result in results if result.success and result.round_count_warning)
    failure_count = len(results) - success_count
    console.print(
        f"\nSummary: {success_count} ok, {warning_count} warnings, {failure_count} failed"
    )


async def verify_all_exchanges(
    history_days: int,
    contract_spec: str | None,
    contract_index: int,
    contracts_only: bool,
    timeout_seconds: float,
) -> bool:
    console.print("\n[bold cyan]Verifying all exchange adapters[/bold cyan]\n")

    results: list[VerifySummary] = []
    for exchange_id in sorted(EXCHANGES):
        try:
            result = await _run_with_timeout(
                _verify_exchange_summary(
                    exchange_id=exchange_id,
                    history_days=history_days,
                    contract_spec=contract_spec,
                    contract_index=contract_index,
                    contracts_only=contracts_only,
                ),
                timeout_seconds=timeout_seconds,
            )
        except TimeoutError:
            result = VerifySummary(
                exchange_id=exchange_id,
                success=False,
                detail=f"timed out after {timeout_seconds:g}s",
            )
        results.append(result)

    _render_batch_summary(results)
    return all(result.success for result in results)


async def verify_exchange(
    exchange_id: str,
    history_days: int,
    contract_spec: str | None,
    contract_index: int,
    preview_limit: int,
    show_all_contracts: bool,
    contracts_only: bool,
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
    console.print("  [green][OK][/green] Live method: fetch_live(list[TrackedContract])")

    console.print("\n[bold]Step 2: API - get_contracts()[/bold]")
    try:
        contracts = await adapter.get_contracts()
        console.print(f"  [green][OK][/green] Retrieved {len(contracts)} contracts")
        if not contracts:
            console.print("  [bold red][FAIL][/bold red] get_contracts() returned empty list")
            return False
        _warn_if_contract_count_looks_truncated(contracts)
        _render_contracts(contracts, preview_limit, show_all_contracts)

    except Exception as exc:
        console.print(f"  [bold red][FAIL][/bold red] get_contracts() failed: {exc}")
        return False

    if contracts_only:
        console.print(
            "\n[bold green][OK] Contract fetch completed without "
            "history/live checks[/bold green]\n"
        )
        return True

    try:
        selected_contract_index = _find_contract_index(contracts, contract_spec)
    except ValueError as exc:
        console.print(f"  [bold red][FAIL][/bold red] {exc}")
        return False

    if selected_contract_index is not None:
        contract_index = selected_contract_index

    if contract_index < 0 or contract_index >= len(contracts):
        console.print(
            "  [bold red][FAIL][/bold red] Invalid --contract-index: "
            f"{contract_index}. Allowed range: 0..{len(contracts) - 1}"
        )
        return False

    listing = contracts[contract_index]
    contract = _build_contract_for_checks(exchange_id, listing)
    console.print(
        "  [green][OK][/green] Selected contract: "
        f"{contract.asset_name}/{contract.quote_name} (index {contract_index})"
    )

    contract_label = f"{contract.asset_name}/{contract.quote_name}"
    console.print(
        "\n[bold]Step 3: API - fetch_history_after(contract)[/bold] "
        f"for [cyan]{contract_label}[/cyan]"
    )
    try:
        after_ts = utc_now() - timedelta(days=history_days)
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
            _, sample_rate = next(iter(live_rates.items()))
            rate_pct = sample_rate.rate * 100
            console.print(
                f"  [dim]Sample: {contract_label} = {sample_rate.rate:.6f} ({rate_pct:.4f}%)[/dim]"
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

    if args.timeout_seconds is not None and args.timeout_seconds <= 0:
        console.print("[bold red][FAIL][/bold red] --timeout-seconds must be > 0")
        return 1

    if args.all and args.exchange_id is not None:
        console.print("[bold red][FAIL][/bold red] exchange_id cannot be used together with --all")
        return 1

    if args.all and args.show_all_contracts:
        console.print(
            "[bold red][FAIL][/bold red] --show-all-contracts is only supported "
            "for a single exchange"
        )
        return 1

    if args.all:
        timeout_seconds = 45.0 if args.timeout_seconds is None else args.timeout_seconds
        await http_client.startup()
        try:
            success = await verify_all_exchanges(
                history_days=args.history_days,
                contract_spec=args.contract,
                contract_index=args.contract_index,
                contracts_only=args.contracts_only,
                timeout_seconds=timeout_seconds,
            )
        finally:
            await http_client.shutdown()
        return 0 if success else 1

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

    await http_client.startup()
    try:
        try:
            success = await _run_with_timeout(
                verify_exchange(
                    exchange_id=args.exchange_id,
                    history_days=args.history_days,
                    contract_spec=args.contract,
                    contract_index=args.contract_index,
                    preview_limit=args.preview_limit,
                    show_all_contracts=args.show_all_contracts,
                    contracts_only=args.contracts_only,
                ),
                timeout_seconds=args.timeout_seconds,
            )
        except TimeoutError:
            console.print(
                f"\n[bold red][FAIL][/bold red] Verification timed out after "
                f"{args.timeout_seconds:g}s\n"
            )
            return 1
        return 0 if success else 1
    finally:
        await http_client.shutdown()


def main() -> int:
    return asyncio.run(amain())


def entrypoint() -> None:
    sys.exit(main())
