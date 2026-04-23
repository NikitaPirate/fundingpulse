"""KuCoin exchange adapter.

KuCoin has mixed funding intervals (1h, 4h, 8h). Minimum is 1 hour.
_FETCH_STEP = 100 hours (empirically tested).
"""

import logging

from fundingpulse.models.contract import Contract
from fundingpulse.time import from_unix_milliseconds, utc_now
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint

logger = logging.getLogger(__name__)


class KucoinExchange(BaseExchange):
    """KuCoin exchange adapter."""

    EXCHANGE_ID = "kucoin"
    API_ENDPOINT = "https://api-futures.kucoin.com"

    # Empirically tested
    _FETCH_STEP = 100

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}{contract.quote_name}M"

    async def get_contracts(self) -> list[ExchangeContractListing]:
        response = await self._api_get(f"{self.API_ENDPOINT}/api/v1/contracts/active")

        assert isinstance(response, dict)

        if response.get("code") != "200000":
            raise RuntimeError(f"KuCoin API error: {response}")

        contracts = []
        raw_contracts = response.get("data", [])

        for contract in raw_contracts:
            if contract["status"] != "Open":
                continue

            # Skip non-perpetual contracts (quarterly futures have fundingRateGranularity = None)
            funding_interval_ms = contract.get("fundingRateGranularity")
            if not funding_interval_ms:
                continue

            asset_name = contract["baseCurrency"]
            quote = contract["quoteCurrency"]
            funding_interval = int(funding_interval_ms / 1000 / 3600)

            contracts.append(
                ExchangeContractListing(
                    asset_name=asset_name,
                    quote_name=quote,
                    funding_interval=funding_interval,
                    section_name=self.EXCHANGE_ID,
                )
            )

        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response = await self._api_get(
            f"{self.API_ENDPOINT}/api/v1/contract/funding-rates",
            params={
                "symbol": symbol,
                "from": start_ms,
                "to": end_ms,
            },
        )

        assert isinstance(response, dict)

        if response.get("code") != "200000":
            raise RuntimeError(f"KuCoin API error for {symbol}: {response}")

        points = []
        raw_records = response.get("data") or []

        for raw_record in raw_records:
            rate = float(raw_record["fundingRate"])
            timestamp = from_unix_milliseconds(int(raw_record["timepoint"]))
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response = await self._api_get(f"{self.API_ENDPOINT}/api/v1/contracts/active")

        assert isinstance(response, dict)

        if response.get("code") != "200000":
            raise RuntimeError(f"KuCoin API error: {response}")

        now = utc_now()
        rates = {}
        raw_contracts = response.get("data", [])

        for contract in raw_contracts:
            if contract["status"] != "Open":
                continue

            funding_interval_ms = contract.get("fundingRateGranularity")
            if not funding_interval_ms:
                continue

            symbol = contract["symbol"]
            funding_fee_rate = contract.get("fundingFeeRate")

            if funding_fee_rate is not None:
                rates[symbol] = FundingPoint(
                    rate=float(funding_fee_rate),
                    timestamp=now,
                )

        return rates
