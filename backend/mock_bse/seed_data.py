import random
from datetime import datetime, timedelta, timezone

from config import Settings


SYMBOL_PRICE_RANGES: dict[str, tuple[float, float]] = {
    "RELIANCE": (1_150, 1_650),
    "TCS": (3_200, 4_800),
    "HDFCBANK": (1_450, 2_100),
    "INFY": (1_300, 2_000),
    "ICICIBANK": (1_100, 1_600),
    "SBIN": (650, 950),
    "ITC": (350, 550),
    "LT": (2_800, 4_100),
    "BHARTIARTL": (1_100, 1_900),
    "AXISBANK": (900, 1_400),
    "KOTAKBANK": (1_500, 2_100),
    "MARUTI": (9_000, 14_000),
    "SUNPHARMA": (1_200, 2_000),
    "TITAN": (2_800, 4_000),
    "WIPRO": (400, 700),
}
CLIENTS = [f"CLT-{client_id}" for client_id in range(1001, 1021)]
IST = timezone(timedelta(hours=5, minutes=30), name="IST")
TRADING_DAY_START = datetime(2024, 1, 2, 9, 15, tzinfo=IST)
TRADING_DAY_SECONDS = (6 * 60 + 15) * 60


def generate_trades(settings: Settings) -> list[dict[str, str | int | float]]:
    randomizer = random.Random(settings.seed)
    symbols = tuple(SYMBOL_PRICE_RANGES)
    trades: list[dict[str, str | int | float]] = []

    for index in range(1, settings.total_trades + 1):
        symbol = randomizer.choice(symbols)
        low, high = SYMBOL_PRICE_RANGES[symbol]
        timestamp = TRADING_DAY_START + timedelta(
            seconds=randomizer.randint(0, TRADING_DAY_SECONDS)
        )
        trades.append(
            {
                "trade_id": f"T{index:06d}",
                "client": randomizer.choice(CLIENTS),
                "symbol": symbol,
                "quantity": randomizer.randint(1, 1000),
                "price": round(randomizer.uniform(low, high), 2),
                "timestamp": timestamp.isoformat(),
            }
        )

    return sorted(trades, key=lambda trade: (str(trade["timestamp"]), str(trade["trade_id"])))
