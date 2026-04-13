# Tools

## verify

Verification command for exchange adapters. Makes real API calls against the exchange without starting scheduler jobs or touching the database.

### Usage

```bash
uv run verify <exchange_id>
uv run verify --list
uv run verify --all
```

### Example

```bash
uv run verify hyperliquid
```

### What it checks

1. **Protocol Validation**
   - Verifies `EXCHANGE_ID` constant exists
   - Verifies required methods: `get_contracts()`, `fetch_history_before()`, `fetch_history_after()`
   - Verifies live method: `fetch_live(list[Contract])`

2. **API: get_contracts()**
   - Makes real API call to exchange
   - Displays total number of contracts found
   - Shows contracts in adapter order
   - Warns when contract count looks suspiciously round (`50`, `100`, `200`, ...)

3. **API: fetch_history_after(contract)**
   - Fetches funding history for selected contract (default: last 7 days)
   - Displays number of data points retrieved
   - Shows date range and sample rate

4. **API: Live rates**
   - Calls `fetch_live([contract])`
   - Displays sample live funding rate for returned contract

5. **Batch mode**
   - `--all` runs the same verification sequentially for every registered exchange
   - Prints a compact summary with `ok`, `warning`, and `failed` statuses

### Useful options

- `--list` - print available exchange IDs from registry
- `--all` - verify all exchanges and print one summary table
- `--history-days N` - change history lookback window (default: `7`)
- `--contract ASSET/QUOTE` - pick contract by symbol pair, for example `BTC/USDT`
- `--contract-index N` - pick contract index from fetched list when `--contract` is not set
- `--preview-limit N` - number of contracts to show in preview table
- `--show-all-contracts` - print all returned contracts in adapter order
- `--contracts-only` - stop after `get_contracts()` and contract output
- `--timeout-seconds N` - optional timeout for one exchange verification; in `--all` mode defaults to `45`

### Exit codes

- `0` - All checks passed
- `1` - Validation or API call failed

### When to use

- After implementing a new exchange adapter
- After modifying existing adapter
- To verify exchange API is still compatible
- To quickly see which exchanges currently pass or fail in one run
- Before deploying changes to production

### Example output

```
Verifying exchange adapter: hyperliquid

Step 1: Protocol Validation
  [OK] EXCHANGE_ID: hyperliquid
  [OK] Required methods: get_contracts, fetch_history_before, fetch_history_after
  [OK] Live method: fetch_live(list[Contract])

Step 2: API - get_contracts()
  [OK] Retrieved N contracts
  ...

Step 3: API - fetch_history_after(contract)
  [OK] Selected contract: BTC/USDT (index 0)
  [OK] Retrieved N funding points
  Date range: ...
  Sample rate: ...

Step 4: API - fetch_live
  [OK] fetch_live() returned N rates
  Sample: BTC/USD = ...

[OK] All checks passed for hyperliquid
```
