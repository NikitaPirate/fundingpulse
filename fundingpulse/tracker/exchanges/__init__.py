"""Exchange adapters registry.

Each exchange is a class implementing BaseExchange ABC.
"""

import logging

from fundingpulse.tracker.exchanges import (
    aster,
    backpack,
    binance_coinm,
    binance_usdm,
    bybit,
    derive,
    dydx,
    extended,
    hyperliquid,
    hyperliquid_xyz,
    kucoin,
    lighter,
    okx,
    pacifica,
    paradex,
)
from fundingpulse.tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


def _validate_exchange(exchange_class: type[BaseExchange], name: str) -> None:
    """Validate exchange class has EXCHANGE_ID and required methods."""
    if not hasattr(exchange_class, "EXCHANGE_ID"):
        raise TypeError(f"{name}: missing EXCHANGE_ID class attribute")

    if not isinstance(exchange_class.EXCHANGE_ID, str):
        raise TypeError(f"{name}: EXCHANGE_ID must be str, got {type(exchange_class.EXCHANGE_ID)}")

    # Note: fetch_live validation handled by @abstractmethod in BaseExchange
    required_methods = ["_format_symbol", "get_contracts", "_fetch_history"]
    for method_name in required_methods:
        if not hasattr(exchange_class, method_name):
            raise TypeError(f"{name}: missing required method {method_name}()")

    logger.info(f"✓ {name}: implements fetch_live()")


def _build_registry() -> dict[str, BaseExchange]:
    """Build EXCHANGES registry with validation and instantiation."""
    exchange_classes: dict[str, type[BaseExchange]] = {
        "aster": aster.AsterExchange,
        "backpack": backpack.BackpackExchange,
        "binance_usd-m": binance_usdm.BinanceUsdmExchange,
        "binance_coin-m": binance_coinm.BinanceCoinmExchange,
        "bybit": bybit.BybitExchange,
        "derive": derive.DeriveExchange,
        "dydx": dydx.DydxExchange,
        "extended": extended.ExtendedExchange,
        "hyperliquid": hyperliquid.HyperliquidExchange,
        "hyperliquid-xyz": hyperliquid_xyz.HyperliquidXyzExchange,
        "kucoin": kucoin.KucoinExchange,
        "lighter": lighter.LighterExchange,
        "okx": okx.OkxExchange,
        "pacifica": pacifica.PacificaExchange,
        "paradex": paradex.ParadexExchange,
    }

    registry = {}
    for name, cls in exchange_classes.items():
        _validate_exchange(cls, name)
        registry[name] = cls()

    logger.info(f"Exchange adapter registry initialized with {len(registry)} exchanges")
    return registry


EXCHANGES: dict[str, BaseExchange] = _build_registry()

__all__ = ["EXCHANGES", "BaseExchange"]
