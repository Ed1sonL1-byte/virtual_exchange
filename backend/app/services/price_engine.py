import asyncio
import logging
from decimal import Decimal

import httpx

from app.config import settings
from app.database import async_session
from app.models.price import PriceHistory
from app.websocket.broadcaster import manager

logger = logging.getLogger(__name__)

TRADING_PAIRS = ["ETHUSDT", "SOLUSDT", "BTCUSDT"]

# In-memory latest prices
current_prices: dict[str, Decimal] = {}


async def fetch_binance_prices() -> dict[str, Decimal]:
    prices = {}
    async with httpx.AsyncClient() as client:
        for pair in TRADING_PAIRS:
            try:
                resp = await client.get(f"{settings.binance_base_url}/api/v3/ticker/price", params={"symbol": pair})
                resp.raise_for_status()
                data = resp.json()
                prices[pair] = Decimal(data["price"])
            except Exception as e:
                logger.error(f"Failed to fetch {pair}: {e}")
                if pair in current_prices:
                    prices[pair] = current_prices[pair]
    return prices


async def save_prices(prices: dict[str, Decimal]):
    async with async_session() as db:
        for pair, price in prices.items():
            db.add(PriceHistory(pair=pair, price=price))
        await db.commit()


async def price_update_loop():
    while True:
        try:
            prices = await fetch_binance_prices()
            if prices:
                current_prices.update(prices)
                await save_prices(prices)
                await manager.broadcast("prices", {
                    "type": "price_update",
                    "data": {pair: str(price) for pair, price in prices.items()},
                })
                logger.info(f"Price update: {prices}")
                # Check for liquidations after price update
                from app.services.liquidation import check_liquidations
                await check_liquidations()
        except Exception as e:
            logger.error(f"Price update error: {e}")
        await asyncio.sleep(settings.price_update_interval)
