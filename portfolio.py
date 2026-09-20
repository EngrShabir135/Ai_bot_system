"""Portfolio state, compliance checks and (simulated) order execution.

All money here is simulated paper-trading capital. Nothing in this module
talks to a real broker, exchange, wallet or bank.
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from . import market

STARTING_CASH = 100_000.0
FEE_RATE = 0.001          # 0.10% per trade
MIN_TRADE = 100.0         # minimum ticket size

RISK_PROFILES: dict[str, dict[str, Any]] = {
    "Conservative": dict(
        targets={"Stocks": 0.35, "Real Estate": 0.30, "Crypto": 0.05, "Ventures": 0.05},
        cash_reserve=0.25, max_position=0.10, trade_size=0.015, rsi_buy_max=60, vol_cap=0.60,
    ),
    "Moderate": dict(
        targets={"Stocks": 0.40, "Real Estate": 0.25, "Crypto": 0.15, "Ventures": 0.10},
        cash_reserve=0.10, max_position=0.15, trade_size=0.025, rsi_buy_max=70, vol_cap=0.90,
    ),
    "Aggressive": dict(
        targets={"Stocks": 0.35, "Real Estate": 0.15, "Crypto": 0.25, "Ventures": 0.20},
        cash_reserve=0.05, max_position=0.25, trade_size=0.040, rsi_buy_max=78, vol_cap=1.40,
    ),
}

# Rollout phases from the action plan. `cap` = maximum share of total
# portfolio value the bots may have invested at any time.
PHASES: dict[str, dict[str, Any]] = {
    "1 · Setup": dict(cap=0.0, desc="Configure wallet access, AI parameters and bot roles. Analysis only - no orders execute."),
    "2 · Integration Testing": dict(cap=0.0, desc="Test cross-bot communication and workflows using dry runs. No orders execute."),
    "3 · Pilot Run": dict(cap=0.10, desc="Run the system with limited funds (max 10% of the portfolio invested) and monitor results."),
    "4 · Optimization & Scaling": dict(cap=0.50, desc="Tune strategies and expand scope (max 50% of the portfolio invested)."),
    "5 · Full Deployment": dict(cap=1.00, desc="Full automated, diversified management within risk-profile limits."),
}
DEFAULT_PHASE = "3 · Pilot Run"


# ------------------------------------------------------------------ state
def new_state() -> dict[str, Any]:
    return {
        "cash": STARTING_CASH,
        "initial": STARTING_CASH,
        "holdings": {},          # symbol -> {qty, cost, opened_tick}
        "tick": 0,
        "risk": "Moderate",
        "phase": DEFAULT_PHASE,
        "autopilot": False,
        "trades": [],
        "income": {},            # symbol -> accrued rent / staking income
        "fees_paid": 0.0,
        "realized_pnl": 0.0,
        "history": [{"tick": 0, "value": STARTING_CASH}],
    }


def normalize(state: dict[str, Any]) -> dict[str, Any]:
    for k, v in new_state().items():
        state.setdefault(k, v)
    if state["risk"] not in RISK_PROFILES:
        state["risk"] = "Moderate"
    if state["phase"] not in PHASES:
        state["phase"] = DEFAULT_PHASE
    return state


def profile(state: dict[str, Any]) -> dict[str, Any]:
    return RISK_PROFILES[state["risk"]]


def phase_cap(state: dict[str, Any]) -> float:
    return PHASES[state["phase"]]["cap"]


def effective_targets(state: dict[str, Any]) -> dict[str, float]:
    """Target weights scaled down to what the current phase allows to be invested."""
    targets = profile(state)["targets"]
    total_t = sum(targets.values())
    cap = phase_cap(state)
    scale = min(1.0, cap / total_t) if cap > 0 and total_t else 1.0
    return {c: v * scale for c, v in targets.items()}


# ------------------------------------------------------------- valuation
def position_value(state, symbol: str, prices: dict[str, float]) -> float:
    h = state["holdings"].get(symbol)
    return h["qty"] * prices[symbol] if h else 0.0


def invested_value(state, prices: Optional[dict[str, float]] = None) -> float:
    prices = prices or market.prices(state["tick"])
    return sum(h["qty"] * prices[s] for s, h in state["holdings"].items())


def total_value(state, prices: Optional[dict[str, float]] = None) -> float:
    prices = prices or market.prices(state["tick"])
    return state["cash"] + invested_value(state, prices)


def class_values(state, prices: Optional[dict[str, float]] = None) -> dict[str, float]:
    prices = prices or market.prices(state["tick"])
    out = {c: 0.0 for c in market.CLASSES}
    for s, h in state["holdings"].items():
        out[market.ASSETS[s]["cls"]] += h["qty"] * prices[s]
    return out


def holdings_rows(state) -> list[dict[str, Any]]:
    prices = market.prices(state["tick"])
    total = total_value(state, prices)
    rows = []
    for s, h in state["holdings"].items():
        value = h["qty"] * prices[s]
        rows.append(dict(
            symbol=s, name=market.ASSETS[s]["name"], cls=market.ASSETS[s]["cls"],
            qty=h["qty"], price=prices[s], value=value, cost=h["cost"],
            pnl=value - h["cost"], pnl_pct=(value / h["cost"] - 1) if h["cost"] else 0.0,
            weight=value / total if total else 0.0,
        ))
    return sorted(rows, key=lambda r: -r["value"])


# ------------------------------------------------------------- compliance
def check_order(state, order: dict[str, Any], prices: dict[str, float]) -> tuple[bool, str]:
    """Compliance gate that every order must pass before it executes."""
    sym, side, notional = order["symbol"], order["side"], float(order["notional"])
    if sym not in market.ASSETS:
        return False, "Unknown instrument."
    if side not in ("buy", "sell"):
        return False, "Unknown order side."
    if notional < MIN_TRADE:
        return False, f"Below the ${MIN_TRADE:,.0f} minimum ticket."

    p = profile(state)
    total = total_value(state, prices)

    if side == "buy":
        cap = phase_cap(state)
        if cap <= 0:
            return False, "Current phase is analysis-only; execution is disabled."
        cost = notional * (1 + FEE_RATE)
        if cost > state["cash"] + 1e-9:
            return False, "Insufficient cash."
        if state["cash"] - cost < 0.5 * p["cash_reserve"] * total - 1e-6:
            return False, "Would breach the minimum liquidity buffer."
        if invested_value(state, prices) + notional > cap * total + 1e-6:
            return False, f"Exceeds the {cap:.0%} capital-deployment limit for this phase."
        if position_value(state, sym, prices) + notional > p["max_position"] * total + 1e-6:
            return False, f"Exceeds the {p['max_position']:.0%} single-position limit."
    else:
        pv = position_value(state, sym, prices)
        if pv <= 0:
            return False, "No position to sell."
        if notional > pv + 1e-6:
            return False, "Sell amount exceeds the position size."
    return True, "OK"


def execute_order(state, order: dict[str, Any], prices: dict[str, float]) -> dict[str, Any]:
    ok, msg = check_order(state, order, prices)
    if not ok:
        return {"ok": False, "msg": msg, "order": order}

    sym, side, notional = order["symbol"], order["side"], float(order["notional"])
    px = prices[sym]

    if side == "buy":
        qty = notional / px
        fee = notional * FEE_RATE
        state["cash"] -= notional + fee
        state["fees_paid"] += fee
        h = state["holdings"].setdefault(sym, {"qty": 0.0, "cost": 0.0, "opened_tick": state["tick"]})
        h["qty"] += qty
        h["cost"] += notional
    else:
        h = state["holdings"][sym]
        pv = h["qty"] * px
        if notional >= pv * 0.999:            # treat as a full exit
            qty, notional = h["qty"], pv
        else:
            qty = notional / px
        fraction = qty / h["qty"]
        cost_out = h["cost"] * fraction
        fee = notional * FEE_RATE
        proceeds = notional - fee
        state["cash"] += proceeds
        state["fees_paid"] += fee
        state["realized_pnl"] += proceeds - cost_out
        h["qty"] -= qty
        h["cost"] -= cost_out
        if h["qty"] < 1e-9:
            del state["holdings"][sym]

    state["trades"].append(dict(
        tick=state["tick"], symbol=sym, side=side, qty=qty, price=px, notional=notional,
        bot=order.get("bot", "-"), reason=order.get("reason", ""),
    ))
    state["trades"] = state["trades"][-300:]
    msg = f"{side.upper()} {qty:,.4f} {sym} @ ${px:,.2f} (${notional:,.0f})"
    return {"ok": True, "msg": msg, "order": order}


def run_orders(state, orders: list[dict[str, Any]], dry_run: bool = False):
    """Run orders (sells first, so proceeds can fund buys). Returns (results, state)."""
    target = copy.deepcopy(state) if dry_run else state
    prices = market.prices(target["tick"])
    results = []
    for o in sorted(orders, key=lambda o: 0 if o["side"] == "sell" else 1):
        results.append(execute_order(target, o, prices))
    return results, target


# ---------------------------------------------------------------- time
def advance(state, steps: int = 1) -> None:
    """Move the simulated market forward, accrue rent/staking income, snapshot value."""
    for _ in range(steps):
        if state["tick"] >= market.MAX_TICKS:
            break
        state["tick"] += 1
        prices = market.prices(state["tick"])
        for sym, h in state["holdings"].items():
            rate = market.ASSETS[sym]["income"]
            if rate > 0:
                inc = h["qty"] * prices[sym] * rate / 365
                state["cash"] += inc
                state["income"][sym] = state["income"].get(sym, 0.0) + inc
        state["history"].append({"tick": state["tick"], "value": total_value(state, prices)})
    state["history"] = state["history"][-1500:]
