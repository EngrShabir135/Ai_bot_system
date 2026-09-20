"""Small formatting helpers shared by the logic and UI layers."""
from __future__ import annotations


def money(x: float, decimals: int = 0) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.{decimals}f}"


def pct(x: float, decimals: int = 2, sign: bool = False) -> str:
    return f"{x:+.{decimals}%}" if sign else f"{x:.{decimals}%}"
