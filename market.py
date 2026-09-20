"""Simulated market-data engine.

Prices are synthetic geometric random walks, seeded per instrument, so every
user sees the same market and no API keys are needed. To go live, replace
`_full()` / `series()` / `price_at()` with a real feed (yfinance, CoinGecko,
a broker or bank API). Everything else in the app reads prices only through
this module.

One "tick" = one simulated day.
"""
from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np

CLASSES = ["Stocks", "Real Estate", "Crypto", "Ventures"]
BOT_FOR_CLASS = {"Stocks": "A", "Real Estate": "B", "Crypto": "C", "Ventures": "D"}

HISTORY_DAYS = 180
MAX_TICKS = 3000


def _a(name, cls, price, vol, drift, income=0.0):
    # income = annual rental yield (real estate) or staking APY (crypto)
    return dict(name=name, cls=cls, price=price, vol=vol, drift=drift, income=income)


ASSETS = {
    # Bot A - equities
    "TECH": _a("Technology Leaders Fund", "Stocks", 182.40, 0.015, 0.0005),
    "FINX": _a("Financial Sector Fund", "Stocks", 96.20, 0.011, 0.0003),
    "HLTH": _a("Healthcare Fund", "Stocks", 128.70, 0.009, 0.0003),
    "ENRG": _a("Energy Fund", "Stocks", 74.50, 0.013, 0.0001),
    "CONS": _a("Consumer Staples Fund", "Stocks", 141.30, 0.008, 0.0003),
    # Bot B - real estate
    "RESI": _a("Residential Rentals Portfolio", "Real Estate", 210.00, 0.006, 0.0002, 0.045),
    "COMM": _a("Commercial Offices Portfolio", "Real Estate", 88.60, 0.009, 0.0001, 0.055),
    "INDL": _a("Industrial & Logistics Portfolio", "Real Estate", 154.20, 0.007, 0.0003, 0.038),
    "LAND": _a("Land Bank", "Real Estate", 64.00, 0.005, 0.0002, 0.0),
    # Bot C - digital assets
    "BTC": _a("Bitcoin", "Crypto", 64250.00, 0.032, 0.0008),
    "ETH": _a("Ethereum", "Crypto", 3180.00, 0.038, 0.0008, 0.035),
    "SOL": _a("Solana", "Crypto", 148.50, 0.048, 0.0009, 0.060),
    # Bot D - businesses & startups
    "NOVA": _a("NovaPay (Fintech)", "Ventures", 12.40, 0.028, 0.0012),
    "GRID": _a("GreenGrid (Clean energy)", "Ventures", 8.75, 0.024, 0.0010),
    "MEDI": _a("MediCore (Health tech)", "Ventures", 21.30, 0.030, 0.0011),
    "AGRI": _a("AgriSense (Agritech)", "Ventures", 5.60, 0.022, 0.0009),
}


def symbols_for(cls: str) -> list[str]:
    return [s for s, a in ASSETS.items() if a["cls"] == cls]


@lru_cache(maxsize=None)
def _full(symbol: str) -> np.ndarray:
    """History (ending at the base price) followed by MAX_TICKS future days."""
    a = ASSETS[symbol]
    seed = zlib.crc32(symbol.encode("utf-8"))
    hist_r = np.random.default_rng(seed).normal(a["drift"], a["vol"], HISTORY_DAYS)
    cum = np.cumsum(hist_r)
    hist = a["price"] * np.exp(cum - cum[-1])
    fut_r = np.random.default_rng(seed + 7919).normal(a["drift"], a["vol"], MAX_TICKS)
    fut = a["price"] * np.exp(np.cumsum(fut_r))
    return np.concatenate([hist, fut])


def series(symbol: str, tick: int) -> np.ndarray:
    tick = max(0, min(int(tick), MAX_TICKS))
    return _full(symbol)[: HISTORY_DAYS + tick].copy()


def price_at(symbol: str, tick: int) -> float:
    tick = max(-(HISTORY_DAYS - 1), min(int(tick), MAX_TICKS))
    return float(_full(symbol)[HISTORY_DAYS - 1 + tick])


def prices(tick: int) -> dict[str, float]:
    return {s: price_at(s, tick) for s in ASSETS}


def day_axis(tick: int) -> np.ndarray:
    return np.arange(-(HISTORY_DAYS - 1), int(tick) + 1)


# ------------------------------------------------------------ indicators
def sma(x: np.ndarray, n: int) -> float:
    return float(np.mean(x[-n:]))


def rsi(x: np.ndarray, n: int = 14) -> float:
    d = np.diff(x[-(n + 1):])
    gains = d[d > 0].sum()
    losses = -d[d < 0].sum()
    if losses == 0:
        return 100.0
    return float(100 - 100 / (1 + gains / losses))


def volatility(x: np.ndarray, n: int = 30, periods: int = 252) -> float:
    r = np.diff(np.log(x[-(n + 1):]))
    return float(np.std(r, ddof=1) * np.sqrt(periods))
