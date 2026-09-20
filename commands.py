"""Text command interpreter for the Command Center (rule-based, no external AI)."""
from __future__ import annotations

import numpy as np

from . import bots, market, portfolio
from .fmt import money, pct

HELP = """**Command reference**

| Command | What it does |
|---|---|
| `status` | Portfolio value, cash and allocation vs target |
| `report` | Daily performance report with top movers |
| `bot a` / `bot b` / `bot c` / `bot d` | That bot's current signals |
| `analyze <symbol>` | Ask the responsible bot about one instrument, e.g. `analyze BTC` |
| `alerts` | Active alerts |
| `risk` | Concentration, drawdown and volatility check |
| `income` | Rental and staking income earned |
| `milestones` | Venture milestone tracker (Bot D) |
| `rebalance` | Preview the weekly rebalance |
| `rebalance confirm` | Execute the rebalance (if the phase allows) |
| `buy <symbol> <amount>` | Manual buy, e.g. `buy TECH 2500` |
| `sell <symbol> <amount or all>` | Manual sell, e.g. `sell TECH all` |
| `advance <days>` | Move the simulated market forward (1 to 90 days) |
"""

WORKFLOWS: dict[str, list[str]] = {
    "Bot A · Daily equity routine": ["report", "bot a", "alerts"],
    "Bot B · Rental income review": ["bot b", "income"],
    "Bot C · Crypto risk sweep": ["bot c", "risk", "alerts"],
    "Bot D · Venture milestone check": ["bot d", "milestones"],
    "Coordinator · Weekly rebalance (preview)": ["status", "rebalance"],
}


def _table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _status(s) -> str:
    px = market.prices(s["tick"])
    total, cv, p = portfolio.total_value(s, px), portfolio.class_values(s, px), portfolio.profile(s)
    tg = portfolio.effective_targets(s)
    rows = [[c, money(cv[c]), pct(cv[c] / total, 1), pct(tg[c], 1)] for c in market.CLASSES]
    rows.append(["Cash", money(s["cash"]), pct(s["cash"] / total, 1), pct(p["cash_reserve"], 1)])
    return (f"**Status, day {s['tick']}** · {s['risk']} profile · {s['phase']}\n\n"
            f"Total value **{money(total)}** ({pct(total / s['initial'] - 1, 2, True)} since start)\n\n"
            + _table(["Bucket", "Value", "Weight", "Target"], rows))


def _report(s) -> str:
    px, prev = market.prices(s["tick"]), market.prices(s["tick"] - 1)
    total, total_prev = portfolio.total_value(s, px), portfolio.total_value(s, prev)
    moves = sorted(((sym, px[sym] / prev[sym] - 1) for sym in market.ASSETS), key=lambda t: t[1])
    gain = ", ".join(f"{a} {pct(b, 2, True)}" for a, b in moves[::-1][:3])
    lose = ", ".join(f"{a} {pct(b, 2, True)}" for a, b in moves[:3])
    return (f"**Daily performance report, day {s['tick']}**\n\n"
            f"- Portfolio value: **{money(total)}** ({pct(total / total_prev - 1, 2, True)} market move today)\n"
            f"- Return since start: {pct(total / s['initial'] - 1, 2, True)}\n"
            f"- Cash: {money(s['cash'])} · Fees paid: {money(s['fees_paid'], 2)} · Realised P&L: {money(s['realized_pnl'])}\n"
            f"- Top gainers: {gain}\n- Top decliners: {lose}")


def _bot_table(key, s) -> str:
    bot = bots.BOTS[key.upper()]
    rows = [[sg.symbol, money(sg.price, 2), pct(sg.chg, 2, True), sg.action, sg.reason] for sg in bot.analyze(s)]
    return f"**Bot {bot.key} · {bot.title}**\n\n" + _table(["Instrument", "Price", "1d", "Signal", "Rationale"], rows)


def _risk(s) -> str:
    px = market.prices(s["tick"])
    total, p = portfolio.total_value(s, px), portfolio.profile(s)
    hist = np.array([h["value"] for h in s["history"]])
    dd = float((hist / np.maximum.accumulate(hist) - 1).min())
    vol = None
    if len(hist) >= 11:
        vol = float(np.std(np.diff(np.log(hist[-31:])), ddof=1) * np.sqrt(252))
    top = sorted(((portfolio.position_value(s, sym, px) / total, sym) for sym in s["holdings"]), reverse=True)[:3]
    lines = [f"**Risk check, day {s['tick']}**", "",
             f"- Max drawdown since start: {pct(dd, 2)}",
             f"- Portfolio volatility (annualised): {pct(vol, 1) if vol is not None else 'not enough history yet'}",
             f"- Cash buffer: {pct(s['cash'] / total, 1)} (target {pct(p['cash_reserve'], 0)})",
             f"- Largest positions: " + (", ".join(f"{sym} {pct(w, 1)}" for w, sym in top) or "none")]
    breaches = [sym for w, sym in top if w > p["max_position"]]
    lines.append(f"- Position limit ({pct(p['max_position'], 0)}): " + ("**BREACHED** by " + ", ".join(breaches) if breaches else "within limits"))
    return "\n".join(lines)


def _income(s) -> str:
    re_rows = bots.BOTS["B"].income_rows(s)
    cr_total = sum(v for k, v in s["income"].items() if market.ASSETS[k]["cls"] == "Crypto")
    re_total = sum(r["accrued"] for r in re_rows)
    if not s["income"] and not re_rows:
        return "No rental or staking income yet. Hold income-producing assets and advance the market."
    rows = [[r["symbol"], money(r["value"]), pct(r["yield_"], 1), money(r["monthly"], 2), money(r["accrued"], 2), pct(r["roi"], 2, True)] for r in re_rows]
    txt = f"**Income earned:** rental {money(re_total, 2)} · staking {money(cr_total, 2)}"
    if rows:
        txt += "\n\n" + _table(["Property", "Value", "Yield", "Est. monthly rent", "Accrued", "ROI"], rows)
    return txt


def _milestones(s) -> str:
    rows = bots.BOTS["D"].milestone_rows(s)
    if not rows:
        return "No venture positions yet."
    heads = ["Venture", "Days held", "MOIC"] + [m for m, _ in bots.MILESTONES]
    return "**Venture milestones**\n\n" + _table(heads, [[r["symbol"], r["days"], f"{r['moic']:.2f}x"] + [r[m] for m, _ in bots.MILESTONES] for r in rows])


def _alerts(s) -> str:
    al = bots.generate_alerts(s)
    if not al:
        return "No active alerts."
    icon = {"danger": "🔴", "warning": "🟠", "info": "🔵"}
    return "**Active alerts**\n\n" + "\n".join(f"- {icon[a['level']]} **{a['title']}**: {a['detail']}" for a in al)


def _rebalance(s, confirm: bool):
    orders, drift = bots.rebalance_orders(s)
    if not orders:
        return "Portfolio is within tolerance of its targets. Nothing to rebalance.", []
    if not confirm:
        results, _ = portfolio.run_orders(s, orders, dry_run=True)
        rows = [[r["Bot"], r["Side"], r["Instrument"], r["Amount"], r["Status"], r["Note"]] for r in bots.results_rows(results, dry_run=True)]
        return "**Rebalance preview** (nothing executed)\n\n" + _table(["Bot", "Side", "Instrument", "Amount", "Status", "Note"], rows) + "\n\nType `rebalance confirm` to execute.", []
    if portfolio.phase_cap(s) <= 0:
        return f"⛔ Execution is disabled in phase **{s['phase']}**. Move to Pilot Run or later in Settings.", []
    results, _ = portfolio.run_orders(s, orders)
    ok = sum(r["ok"] for r in results)
    rows = [[r["Bot"], r["Side"], r["Instrument"], r["Amount"], r["Status"], r["Note"]] for r in bots.results_rows(results)]
    return f"**Rebalance executed:** {ok} of {len(results)} orders filled.\n\n" + _table(["Bot", "Side", "Instrument", "Amount", "Status", "Note"], rows), \
        bots.events_from_results(results, "Coordinator (rebalance)")


def _trade(s, side, args):
    if len(args) < 2:
        return f"Usage: `{side} <symbol> <amount>`" + (" or `sell <symbol> all`" if side == "sell" else ""), []
    sym = args[0].upper()
    if sym not in market.ASSETS:
        return f"Unknown instrument `{sym}`. Available: {', '.join(market.ASSETS)}", []
    px = market.prices(s["tick"])
    if side == "sell" and args[1] == "all":
        notional = portfolio.position_value(s, sym, px)
    else:
        try:
            notional = float(args[1].replace("$", "").replace(",", ""))
        except ValueError:
            return "Amount must be a number, e.g. `buy TECH 2500`.", []
    order = dict(bot="M", symbol=sym, side=side, notional=notional, reason="Manual command")
    results, _ = portfolio.run_orders(s, [order])
    r = results[0]
    return ("✅ " if r["ok"] else "⛔ ") + r["msg"], bots.events_from_results(results, "Manual command")


def run_command(state, text: str) -> tuple[str, list[dict[str, str]]]:
    """Returns (markdown reply, activity events). May mutate `state`."""
    parts = text.strip().lower().split()
    if not parts:
        return "Type `help` to see the available commands.", []
    cmd, args = parts[0], parts[1:]
    try:
        if cmd in ("help", "?"):
            return HELP, []
        if cmd == "status":
            return _status(state), []
        if cmd == "report":
            return _report(state), []
        if cmd == "bot":
            if not args or args[0] not in ("a", "b", "c", "d"):
                return "Usage: `bot a`, `bot b`, `bot c` or `bot d`.", []
            return _bot_table(args[0], state), []
        if cmd == "analyze":
            if not args or args[0].upper() not in market.ASSETS:
                return "Usage: `analyze <symbol>`. Available: " + ", ".join(market.ASSETS), []
            sym = args[0].upper()
            bot = bots.BOTS[market.BOT_FOR_CLASS[market.ASSETS[sym]["cls"]]]
            sg = next(x for x in bot.analyze(state) if x.symbol == sym)
            return (f"**Bot {bot.key} on {sym}** ({market.ASSETS[sym]['name']}): **{sg.action}**\n\n{sg.reason}\n\n"
                    f"Price {money(sg.price, 2)} · 1d {pct(sg.chg, 2, True)} · RSI {sg.rsi:.0f} · volatility {sg.vol:.0%}"), []
        if cmd == "alerts":
            return _alerts(state), []
        if cmd == "risk":
            return _risk(state), []
        if cmd == "income":
            return _income(state), []
        if cmd == "milestones":
            return _milestones(state), []
        if cmd == "rebalance":
            return _rebalance(state, bool(args and args[0] == "confirm"))
        if cmd in ("buy", "sell"):
            return _trade(state, cmd, args)
        if cmd == "advance":
            n = int(args[0]) if args else 1
            n = max(1, min(n, 90))
            events = bots.advance(state, n)
            return f"Advanced {n} day(s). Now on day **{state['tick']}**.\n\n" + _status(state), events
    except ValueError:
        return "Could not read that command. Type `help`.", []
    return f"Unknown command `{cmd}`. Type `help`.", []
