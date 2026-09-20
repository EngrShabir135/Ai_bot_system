"""The four specialised bots and the coordinator that unifies them.

Bot A  Stock & Equity Investment Manager
Bot B  Real Estate Investment Coordinator
Bot C  Cryptocurrency & Digital Assets Manager
Bot D  Business & Startup Investment Analyst

Each bot analyses its own asset class and proposes orders. The coordinator
(`rebalance_orders`, `advance`, `generate_alerts`) keeps the whole portfolio
on one strategy: weekly rebalancing, alerts, and compliance-checked execution.
The strategies are transparent rule-based models - simple by design so they
are easy to audit and replace with your own logic or an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import market
import portfolio
from .market import ASSETS

MILESTONES = [
    ("Pilot customers signed", 15),
    ("Seed round closed", 45),
    ("Break-even revenue", 90),
    ("Series A term sheet", 150),
]


@dataclass
class Signal:
    bot: str
    symbol: str
    action: str          # BUY / SELL / HOLD
    reason: str
    size: float = 1.0    # fraction of the position to sell
    price: float = 0.0
    chg: float = 0.0
    mom: float = 0.0
    rsi: float = 50.0
    vol: float = 0.0


class BaseBot:
    key = "?"
    icon = ""
    title = ""
    asset_class = ""
    mission = ""
    tasks: list[str] = []
    collaborates_with = ""
    periods = 252

    def symbols(self) -> list[str]:
        return market.symbols_for(self.asset_class)

    def metrics(self, x) -> dict[str, float]:
        s20, s50 = market.sma(x, 20), market.sma(x, 50)
        return dict(
            price=float(x[-1]), chg=float(x[-1] / x[-2] - 1), mom=s20 / s50 - 1,
            disc=float(x[-1]) / s50 - 1, rsi=market.rsi(x),
            vol=market.volatility(x, 30, self.periods),
        )

    def decide(self, state, sym, m, held) -> tuple[str, str, float]:
        raise NotImplementedError

    def analyze(self, state) -> list[Signal]:
        out = []
        for sym in self.symbols():
            m = self.metrics(market.series(sym, state["tick"]))
            action, reason, size = self.decide(state, sym, m, sym in state["holdings"])
            out.append(Signal(self.key, sym, action, reason, size, m["price"], m["chg"], m["mom"], m["rsi"], m["vol"]))
        return out

    def orders(self, state, signals: list[Signal] | None = None) -> list[dict[str, Any]]:
        signals = signals if signals is not None else self.analyze(state)
        prices = market.prices(state["tick"])
        total = portfolio.total_value(state, prices)
        size = round(total * portfolio.profile(state)["trade_size"], 2)
        out = []
        for sg in signals:
            if sg.action == "BUY":
                out.append(dict(bot=self.key, symbol=sg.symbol, side="buy", notional=size, reason=sg.reason))
            elif sg.action == "SELL":
                pv = portfolio.position_value(state, sg.symbol, prices)
                if pv > 0:
                    out.append(dict(bot=self.key, symbol=sg.symbol, side="sell", notional=pv * sg.size, reason=sg.reason))
        return out


class StockBot(BaseBot):
    key, icon, asset_class = "A", "📈", "Stocks"
    title = "Stock & Equity Investment Manager"
    mission = "Manages the equity portfolio, optimises trades to your risk tolerance and monitors market trends."
    tasks = [
        "Real-time market analysis (trend and momentum)",
        "Executes trades within your risk tolerance",
        "Generates daily performance reports",
        "Raises alerts on significant market moves and portfolio thresholds",
    ]
    collaborates_with = "Bot B and Bot C for asset allocation and rebalancing."

    def decide(self, state, sym, m, held):
        p = portfolio.profile(state)
        if held and m["mom"] < -0.03:
            return "SELL", f"Trend breakdown: 20-day average {m['mom']:+.1%} vs 50-day", 1.0
        if held and m["rsi"] > 80:
            return "SELL", f"Overbought (RSI {m['rsi']:.0f}), trim half", 0.5
        if m["mom"] > 0 and m["rsi"] < p["rsi_buy_max"]:
            return "BUY", f"Uptrend ({m['mom']:+.1%}), RSI {m['rsi']:.0f} below the {p['rsi_buy_max']} limit", 1.0
        return "HOLD", f"No edge: trend {m['mom']:+.1%}, RSI {m['rsi']:.0f}", 1.0


class RealEstateBot(BaseBot):
    key, icon, asset_class = "B", "🏢", "Real Estate"
    title = "Real Estate Investment Coordinator"
    mission = "Identifies, evaluates and manages property investments and tracks rental income, expenses and ROI."
    tasks = [
        "Screens properties by rental yield and price versus trend",
        "Handles (simulated) wallet transactions for acquisitions",
        "Tracks rental income and ROI per holding",
        "Recommends portfolio adjustments when the market shifts",
    ]
    collaborates_with = "Bot A and Bot D for cash-flow management and diversification."

    def decide(self, state, sym, m, held):
        y = ASSETS[sym]["income"]
        if m["disc"] < -0.02 and y >= 0.04:
            return "BUY", f"Trading {abs(m['disc']):.1%} below its 50-day average with a {y:.1%} yield", 1.0
        if held and m["disc"] > 0.08:
            return "SELL", f"{m['disc']:+.1%} above its 50-day average, take partial profit", 0.5
        if not held and y >= 0.04 and m["mom"] >= 0:
            return "BUY", f"Income asset ({y:.1%} yield) with a stable trend", 1.0
        return "HOLD", f"Yield {y:.1%}; price {m['disc']:+.1%} vs 50-day average", 1.0

    def income_rows(self, state) -> list[dict[str, Any]]:
        prices = market.prices(state["tick"])
        rows = []
        for sym in self.symbols():
            h = state["holdings"].get(sym)
            if not h:
                continue
            value = h["qty"] * prices[sym]
            accrued = state["income"].get(sym, 0.0)
            y = ASSETS[sym]["income"]
            rows.append(dict(
                symbol=sym, value=value, yield_=y, monthly=value * y / 12, accrued=accrued,
                roi=(value + accrued - h["cost"]) / h["cost"] if h["cost"] else 0.0,
            ))
        return rows


class CryptoBot(BaseBot):
    key, icon, asset_class = "C", "🪙", "Crypto"
    title = "Cryptocurrency & Digital Assets Manager"
    mission = "Manages digital assets, staking and risk assessment with security and compliance built in."
    tasks = [
        "AI-optimised trading using trend and volatility limits",
        "Oversees staking and yield opportunities",
        "Rates the risk of every digital asset",
        "Keeps crypto in balance with the rest of the portfolio",
    ]
    collaborates_with = "All bots, to keep the overall portfolio balanced."
    periods = 365

    @staticmethod
    def rating(vol: float) -> str:
        return "Low" if vol < 0.5 else "Medium" if vol < 0.8 else "High" if vol < 1.2 else "Extreme"

    def decide(self, state, sym, m, held):
        p = portfolio.profile(state)
        if held and m["mom"] < -0.05:
            return "SELL", f"Downtrend ({m['mom']:+.1%}), exit to protect capital", 1.0
        if m["mom"] > 0 and m["vol"] <= p["vol_cap"] and m["rsi"] < p["rsi_buy_max"]:
            return "BUY", f"Uptrend ({m['mom']:+.1%}), volatility {m['vol']:.0%} within your {p['vol_cap']:.0%} cap", 1.0
        if m["vol"] > p["vol_cap"]:
            return "HOLD", f"Volatility {m['vol']:.0%} above your {p['vol_cap']:.0%} cap", 1.0
        return "HOLD", f"No edge: trend {m['mom']:+.1%}, RSI {m['rsi']:.0f}", 1.0

    def risk_rows(self, state) -> list[dict[str, Any]]:
        p = portfolio.profile(state)
        rows = []
        for sg in self.analyze(state):
            apy = ASSETS[sg.symbol]["income"]
            rows.append(dict(
                symbol=sg.symbol, vol=sg.vol, rating=self.rating(sg.vol), cap=p["vol_cap"],
                within=sg.vol <= p["vol_cap"], apy=apy,
                staking=f"Stakeable at ~{apy:.1%} APY (simulated)" if apy else "Not stakeable",
            ))
        return rows


class VentureBot(BaseBot):
    key, icon, asset_class = "D", "🚀", "Ventures"
    title = "Business & Startup Investment Analyst"
    mission = "Evaluates and manages investments in startups and small businesses and tracks their milestones."
    tasks = [
        "Assesses viability from momentum and volatility",
        "Tracks investment milestones and multiple on invested capital (MOIC)",
        "Recommends scaling (follow-on) or exit strategies",
        "Feeds risk analysis and diversification advice to the whole system",
    ]
    collaborates_with = "Bot B for real-estate-related ventures."

    def _moic(self, state, sym) -> float | None:
        h = state["holdings"].get(sym)
        if not h or not h["cost"]:
            return None
        return h["qty"] * market.price_at(sym, state["tick"]) / h["cost"]

    def decide(self, state, sym, m, held):
        moic = self._moic(state, sym)
        if moic is not None:
            if moic >= 2.0:
                return "SELL", f"{moic:.2f}x MOIC, partial exit to lock in gains", 0.5
            if moic < 0.7:
                return "SELL", f"{moic:.2f}x MOIC, cut losses and review thesis", 1.0
            if moic >= 1.25 and m["mom"] > 0:
                return "BUY", f"{moic:.2f}x MOIC with positive momentum, follow-on investment", 1.0
            return "HOLD", f"{moic:.2f}x MOIC, monitor milestones", 1.0
        if m["mom"] > 0:
            return "BUY", f"New deal: positive momentum ({m['mom']:+.1%}), volatility {m['vol']:.0%}", 1.0
        return "HOLD", f"Wait for momentum (trend {m['mom']:+.1%})", 1.0

    def milestone_rows(self, state) -> list[dict[str, Any]]:
        rows = []
        for sym in self.symbols():
            h = state["holdings"].get(sym)
            if not h:
                continue
            days = state["tick"] - h["opened_tick"]
            row = dict(symbol=sym, days=days, moic=self._moic(state, sym))
            for name, due in MILESTONES:
                row[name] = "Achieved" if days >= due else f"Due day {due} ({due - days}d left)"
            rows.append(row)
        return rows


BOTS: dict[str, BaseBot] = {b.key: b for b in (StockBot(), RealEstateBot(), CryptoBot(), VentureBot())}


# ------------------------------------------------------------ coordinator
def all_signals(state) -> dict[str, list[Signal]]:
    return {k: b.analyze(state) for k, b in BOTS.items()}


def rebalance_orders(state) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Weekly-rebalance logic. Returns (orders, drift_table)."""
    prices = market.prices(state["tick"])
    total = portfolio.total_value(state, prices)
    p = portfolio.profile(state)
    cvals = portfolio.class_values(state, prices)
    tg = portfolio.effective_targets(state)
    signals = {s.symbol: s for sigs in all_signals(state).values() for s in sigs}
    threshold = 0.02 * total

    orders: list[dict[str, Any]] = []
    drift_rows = []
    sell_gross = 0.0
    needs: dict[str, float] = {}

    for cls in market.CLASSES:
        target_val = tg[cls] * total
        diff = target_val - cvals[cls]
        drift_rows.append(dict(cls=cls, weight=cvals[cls] / total, target=tg[cls], drift_value=-diff))
        bot = market.BOT_FOR_CLASS[cls]
        if diff < -threshold:
            held = {s: portfolio.position_value(state, s, prices) for s in market.symbols_for(cls)}
            held = {s: v for s, v in held.items() if v > 0}
            tv = sum(held.values())
            for s, v in held.items():
                amt = (-diff) * v / tv
                if amt >= portfolio.MIN_TRADE:
                    orders.append(dict(bot=bot, symbol=s, side="sell", notional=min(amt, v),
                                       reason=f"Rebalance: {cls} {cvals[cls]/total:.1%} vs {tg[cls]:.1%} target"))
                    sell_gross += min(amt, v)
        elif diff > threshold:
            needs[cls] = diff

    fee = portfolio.FEE_RATE
    cash_after_sells = state["cash"] + sell_gross * (1 - fee)
    invested_after_sells = portfolio.invested_value(state, prices) - sell_gross
    budget_cash = cash_after_sells - p["cash_reserve"] * total
    budget_room = portfolio.phase_cap(state) * total - invested_after_sells
    budget = max(0.0, min(budget_cash, budget_room)) / (1 + fee)
    need_total = sum(needs.values())
    scale = min(1.0, budget / need_total) if need_total > 0 else 0.0

    for cls, need in needs.items():
        alloc = need * scale
        cands = [s for s in market.symbols_for(cls) if signals[s].action != "SELL"]
        preferred = [s for s in cands if signals[s].action == "BUY"]
        cands = preferred or cands
        if not cands or alloc < portfolio.MIN_TRADE:
            continue
        share = alloc / len(cands)
        for s in cands:
            room = p["max_position"] * total * 0.995 - portfolio.position_value(state, s, prices)
            amt = min(share, room)
            if amt >= portfolio.MIN_TRADE:
                orders.append(dict(bot=market.BOT_FOR_CLASS[cls], symbol=s, side="buy", notional=amt,
                                   reason=f"Rebalance: {cls} {cvals[cls]/total:.1%} vs {tg[cls]:.1%} target"))
    return orders, drift_rows


def results_rows(results, dry_run: bool = False) -> list[dict[str, Any]]:
    ok_label = "Would execute" if dry_run else "Executed"
    return [dict(
        Bot=r["order"].get("bot", "-"), Side=r["order"]["side"].upper(), Instrument=r["order"]["symbol"],
        Amount=f"${float(r['order']['notional']):,.0f}", Status=ok_label if r["ok"] else "Rejected",
        Note=r["msg"] if not r["ok"] else r["order"].get("reason", ""),
    ) for r in results]


def events_from_results(results, actor: str) -> list[dict[str, str]]:
    ev = []
    for r in results:
        if r["ok"]:
            ev.append(dict(actor=f"Bot {r['order'].get('bot', '-')}" if actor == "bot" else actor,
                           action="TRADE", detail=f"{r['msg']}. {r['order'].get('reason', '')}", level="info"))
        else:
            o = r["order"]
            ev.append(dict(actor=f"Bot {o.get('bot', '-')}" if actor == "bot" else actor, action="REJECTED",
                           detail=f"{o['side'].upper()} {o['symbol']} ${float(o['notional']):,.0f}: {r['msg']}",
                           level="warning"))
    return ev


def advance(state, steps: int = 1) -> list[dict[str, str]]:
    """Advance the market; run the weekly rebalance if autopilot is on."""
    events: list[dict[str, str]] = []
    for _ in range(steps):
        portfolio.advance(state, 1)
        if state["autopilot"] and state["tick"] % 7 == 0 and portfolio.phase_cap(state) > 0:
            orders, _ = rebalance_orders(state)
            if orders:
                results, _s = portfolio.run_orders(state, orders)
                events += events_from_results(results, "Coordinator (weekly rebalance)")
    for a in generate_alerts(state):
        if a["level"] in ("danger", "warning"):
            events.append(dict(actor="Coordinator", action="ALERT", detail=f"{a['title']}: {a['detail']}",
                               level="critical" if a["level"] == "danger" else "warning"))
    return events


def generate_alerts(state) -> list[dict[str, str]]:
    tick = state["tick"]
    px, prev = market.prices(tick), market.prices(tick - 1)
    total, total_prev = portfolio.total_value(state, px), portfolio.total_value(state, prev)
    p = portfolio.profile(state)
    alerts: list[dict[str, str]] = []

    move = total / total_prev - 1 if total_prev else 0.0
    if abs(move) >= 0.03:
        alerts.append(dict(level="danger" if move < 0 else "info", title="Significant portfolio move",
                           detail=f"Portfolio value moved {move:+.2%} in one day."))
    for sym in state["holdings"]:
        chg = px[sym] / prev[sym] - 1
        if abs(chg) >= 0.05:
            alerts.append(dict(level="warning", title=f"Large move in {sym}", detail=f"{sym} moved {chg:+.1%} in one day."))

    invested = portfolio.invested_value(state, px)
    if invested < 0.01 * total:
        alerts.append(dict(level="info", title="No capital deployed yet",
                           detail="Run a rebalance or a bot to deploy capital, within your phase limit."))
    else:
        cv = portfolio.class_values(state, px)
        tg = portfolio.effective_targets(state)
        for cls in market.CLASSES:
            drift = cv[cls] / total - tg[cls]
            if abs(drift) >= 0.05:
                alerts.append(dict(level="warning", title=f"{cls} allocation drift",
                                   detail=f"{cls} is {drift:+.1%} away from its {tg[cls]:.1%} target. Rebalance advised."))
    for sym in state["holdings"]:
        w = portfolio.position_value(state, sym, px) / total
        if w > p["max_position"] * 1.10:
            alerts.append(dict(level="danger", title=f"{sym} concentration limit exceeded",
                               detail=f"{sym} is {w:.1%} of the portfolio (limit {p['max_position']:.0%})."))
    if state["cash"] / total < 0.5 * p["cash_reserve"]:
        alerts.append(dict(level="warning", title="Low liquidity buffer",
                           detail=f"Cash is {state['cash']/total:.1%} of the portfolio (reserve target {p['cash_reserve']:.0%})."))
    for row in BOTS["D"].milestone_rows(state):
        for name, due in MILESTONES:
            if 0 <= row["days"] - due < 7:
                alerts.append(dict(level="info", title=f"{row['symbol']} milestone reached", detail=f"{name} (day {due})."))
    order = {"danger": 0, "warning": 1, "info": 2}
    return sorted(alerts, key=lambda a: order[a["level"]])
