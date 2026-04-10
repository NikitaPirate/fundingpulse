# Tools

## verify

Verification command for exchange adapters. Makes real API calls to verify that an exchange adapter correctly implements the required protocol.

### Usage

```bash
uv run verify <exchange_id>
uv run verify --list
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
   - Shows table with first 5 contracts (asset, quote, funding interval)

3. **API: fetch_history_after(contract)**
   - Fetches funding history for selected contract (default: last 7 days)
   - Displays number of data points retrieved
   - Shows date range and sample rate

4. **API: Live rates**
   - Calls `fetch_live([contract])`
   - Displays sample live funding rate for returned contract

### Useful options

- `--list` - print available exchange IDs from registry
- `--history-days N` - change history lookback window (default: `7`)
- `--contract-index N` - pick contract index from fetched list for deep checks
- `--preview-limit N` - number of contracts to show in preview table

### Exit codes

- `0` - All checks passed
- `1` - Validation or API call failed

### When to use

- After implementing a new exchange adapter
- After modifying existing adapter
- To verify exchange API is still compatible
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
  [OK] Retrieved N funding points
  Date range: ...
  Sample rate: ...

Step 4: API - fetch_live
  [OK] fetch_live() returned N rates
  Sample: BTC/USD = ...

[OK] All checks passed for hyperliquid
```
