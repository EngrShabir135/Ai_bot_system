"""Signed-in pages: dashboard, the four bots, command center, activity, settings."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import auth
import bots
import commands
import db
import market
import portfolio
from fmt import money, pct

NAV = [
    "Dashboard",
    "Bot A · Stocks",
    "Bot B · Real Estate",
    "Bot C · Crypto",
    "Bot D · Ventures",
    "Command Center",
    "Activity & Alerts",
    "Settings",
]
BOT_NAV = {"Bot A · Stocks": "A", "Bot B · Real Estate": "B", "Bot C · Crypto": "C", "Bot D · Ventures": "D"}
COLORS = {"Stocks": "#C9A45C", "Real Estate": "#5B8DEF", "Crypto": "#9B7BFF", "Ventures": "#3CB8A6", "Cash": "#6F819A"}
BRASS, STEEL = "#C9A45C", "#4C6A92"
DISCLAIMER = "Simulated market data and paper-trading funds. United Union Bank is a demonstration, not a licensed bank, and nothing here is investment advice."


# ------------------------------------------------------------------ helpers
def _uid() -> int:
    return st.session_state.user["id"]


def _s() -> dict:
    return st.session_state.pf


def _save() -> None:
    db.save_portfolio(_uid(), _s())


def _log(events: list[dict]) -> None:
    for e in events:
        db.log_activity(_uid(), e["actor"], e["action"], e["detail"], e.get("level", "info"))


def _flash(level: str, text: str) -> None:
    st.session_state.setdefault("flash", []).append((level, text))


def _show_flash() -> None:
    fn = {"success": st.success, "warning": st.warning, "error": st.error, "info": st.info}
    for level, text in st.session_state.pop("flash", []):
        fn.get(level, st.info)(text)


def _style(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=28, b=8), height=height,
        legend=dict(orientation="h", y=1.12, x=0),
    )
    return fig


def _alerts_block(alerts: list[dict], limit: int | None = None) -> None:
    if not alerts:
        st.success("No active alerts. The portfolio is within its limits.")
        return
    fn = {"danger": st.error, "warning": st.warning, "info": st.info}
    for a in alerts[:limit]:
        fn[a["level"]](f"**{a['title']}.** {a['detail']}")


def _advance(days: int) -> None:
    events = bots.advance(_s(), days)
    _log(events)
    _save()
    _flash("success", f"Advanced the market by {days} day(s). Now on day {_s()['tick']}.")
    st.rerun()


def _ensure_state() -> None:
    if "pf" not in st.session_state:
        state = db.load_portfolio(_uid())
        st.session_state.pf = portfolio.normalize(state) if state else portfolio.new_state()
        if state is None:
            _save()


# ------------------------------------------------------------------ shell
def render() -> None:
    _ensure_state()
    page = _sidebar()
    _show_flash()
    if page == "Dashboard":
        dashboard()
    elif page in BOT_NAV:
        bot_page(BOT_NAV[page])
    elif page == "Command Center":
        command_center()
    elif page == "Activity & Alerts":
        activity()
    else:
        settings()
    st.divider()
    st.markdown(f'<p class="uub-note">{DISCLAIMER}</p>', unsafe_allow_html=True)


def _sidebar() -> str:
    s = _s()
    with st.sidebar:
        st.markdown('<p class="uub-side-name">United Union Bank</p>', unsafe_allow_html=True)
        st.caption(f"Signed in as {st.session_state.user['full_name']}")
        page = st.radio("Navigation", NAV, label_visibility="collapsed")
        st.divider()
        st.markdown(f'<span class="uub-pill">{s["phase"]}</span>', unsafe_allow_html=True)
        st.caption(f"{s['risk']} profile · simulation day {s['tick']}")
        if st.button("Sign out", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    return page


# -------------------------------------------------------------- dashboard
def dashboard() -> None:
    s = _s()
    tick = s["tick"]
    px, prev = market.prices(tick), market.prices(tick - 1)
    total, total_prev = portfolio.total_value(s, px), portfolio.total_value(s, prev)
    invested = portfolio.invested_value(s, px)

    st.title("Portfolio command dashboard")
    st.caption(f"Simulation day {tick}. All four bots report into this view.")

    c = st.columns(4)
    c[0].metric("Total portfolio value", money(total), f"{total / total_prev - 1:+.2%} market move today")
    c[1].metric("Cash", money(s["cash"]), f"{s['cash'] / total:.1%} of portfolio", delta_color="off")
    c[2].metric("Invested", money(invested), f"{invested / total:.1%} of portfolio", delta_color="off")
    c[3].metric("Return since start", money(total - s["initial"]), f"{total / s['initial'] - 1:+.2%}")

    st.markdown("##### Move the simulated market forward")
    b = st.columns([1, 1, 1, 3])
    for col, label, n in zip(b[:3], ["1 day", "1 week", "1 month"], [1, 7, 30]):
        if col.button(label, key=f"adv_{n}", use_container_width=True):
            _advance(n)

    st.markdown("##### Alerts")
    _alerts_block(bots.generate_alerts(s), limit=4)

    left, right = st.columns([3, 2])
    with left:
        st.markdown("##### Portfolio value")
        h = pd.DataFrame(s["history"])
        if len(h) < 2:
            st.info("Advance the market to start building a performance history.")
        fig = go.Figure(go.Scatter(x=h["tick"], y=h["value"], mode="lines", line=dict(color=BRASS, width=2.5)))
        fig.update_xaxes(title="Simulation day")
        fig.update_yaxes(tickprefix="$")
        st.plotly_chart(_style(fig, 300), use_container_width=True)
    with right:
        st.markdown("##### Allocation")
        cv = portfolio.class_values(s, px)
        labels = list(cv) + ["Cash"]
        values = list(cv.values()) + [s["cash"]]
        pie = go.Figure(go.Pie(labels=labels, values=values, hole=0.62, sort=False,
                               marker=dict(colors=[COLORS[l] for l in labels]), textinfo="percent"))
        st.plotly_chart(_style(pie, 300), use_container_width=True)

    st.markdown("##### Current allocation against target")
    tg = portfolio.effective_targets(s)
    bar = go.Figure()
    bar.add_bar(name="Current", x=market.CLASSES, y=[cv[k] / total * 100 for k in market.CLASSES], marker_color=BRASS)
    bar.add_bar(name="Target for this phase", x=market.CLASSES, y=[tg[k] * 100 for k in market.CLASSES], marker_color=STEEL)
    bar.update_layout(barmode="group")
    bar.update_yaxes(ticksuffix="%")
    st.plotly_chart(_style(bar, 260), use_container_width=True)

    st.markdown("##### Holdings")
    rows = portfolio.holdings_rows(s)
    if rows:
        df = pd.DataFrame([{
            "Instrument": r["symbol"], "Name": r["name"], "Class": r["cls"], "Quantity": f"{r['qty']:,.4f}",
            "Price": money(r["price"], 2), "Value": money(r["value"]), "Weight": pct(r["weight"], 1),
            "P&L": money(r["pnl"]), "P&L %": pct(r["pnl_pct"], 2, True),
        } for r in rows])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.info("No positions yet. Open a bot page and run it, or use the Command Center and type `rebalance confirm`.")


# ---------------------------------------------------------------- bot pages
def bot_page(key: str) -> None:
    s = _s()
    bot = bots.BOTS[key]
    st.title(f"{bot.icon} Bot {key}: {bot.title}")
    st.caption(bot.mission)
    with st.expander("What this bot does"):
        for t in bot.tasks:
            st.markdown(f"- {t}")
        st.markdown(f"**Works with:** {bot.collaborates_with}")

    px = market.prices(s["tick"])
    signals = bot.analyze(s)
    st.markdown("##### Signals")
    df = pd.DataFrame([{
        "Instrument": sg.symbol, "Name": market.ASSETS[sg.symbol]["name"], "Price": money(sg.price, 2),
        "1 day": pct(sg.chg, 2, True), "Trend": pct(sg.mom, 1, True), "RSI": f"{sg.rsi:.0f}",
        "Volatility": pct(sg.vol, 0), "Signal": sg.action, "Rationale": sg.reason,
        "Held": money(portfolio.position_value(s, sg.symbol, px)),
    } for sg in signals])
    st.dataframe(df, hide_index=True, use_container_width=True)

    orders = bot.orders(s, signals)
    can_execute = portfolio.phase_cap(s) > 0
    b1, b2, _ = st.columns([1, 1, 2])
    dry = b1.button("Preview orders", key=f"dry_{key}", use_container_width=True, disabled=not orders)
    run = b2.button("Execute orders", key=f"exec_{key}", type="primary", use_container_width=True,
                    disabled=(not orders) or (not can_execute))
    if not can_execute:
        st.caption(f"Execution is off in phase **{s['phase']}**. Change the phase in Settings to let bots trade.")
    elif not orders:
        st.caption("No BUY or SELL signals right now.")

    if dry:
        results, _ = portfolio.run_orders(s, orders, dry_run=True)
        st.session_state[f"last_{key}"] = ("Preview (nothing executed)", bots.results_rows(results, dry_run=True))
    if run:
        results, _ = portfolio.run_orders(s, orders)
        _log(bots.events_from_results(results, "bot"))
        _save()
        ok = sum(r["ok"] for r in results)
        st.session_state[f"last_{key}"] = ("Last execution", bots.results_rows(results))
        _flash("success" if ok else "warning", f"Bot {key}: {ok} of {len(results)} orders executed.")
        st.rerun()
    last = st.session_state.get(f"last_{key}")
    if last:
        st.markdown(f"##### {last[0]}")
        st.dataframe(pd.DataFrame(last[1]), hide_index=True, use_container_width=True)

    _bot_extras(key, s)

    st.markdown("##### Price chart")
    sym = st.selectbox("Instrument", bot.symbols(), key=f"sym_{key}", format_func=lambda x: f"{x} · {market.ASSETS[x]['name']}")
    x = market.series(sym, s["tick"])
    d = pd.DataFrame({"day": market.day_axis(s["tick"]), "Price": x})
    d["20-day average"] = d["Price"].rolling(20).mean()
    d["50-day average"] = d["Price"].rolling(50).mean()
    fig = go.Figure()
    for col, color, w in [("Price", BRASS, 2.5), ("20-day average", "#5B8DEF", 1.2), ("50-day average", "#9AA8BC", 1.2)]:
        fig.add_scatter(x=d["day"], y=d[col], name=col, mode="lines", line=dict(color=color, width=w))
    fig.update_xaxes(title="Simulation day (0 = account opening)")
    st.plotly_chart(_style(fig, 340), use_container_width=True)


def _bot_extras(key: str, s: dict) -> None:
    bot = bots.BOTS[key]
    if key == "B":
        st.markdown("##### Rental income and ROI")
        rows = bot.income_rows(s)
        if not rows:
            st.info("No properties held yet. Rent accrues daily once you hold an income-producing asset.")
            return
        m = st.columns(2)
        m[0].metric("Rental income earned", money(sum(r["accrued"] for r in rows), 2))
        m[1].metric("Estimated monthly rent", money(sum(r["monthly"] for r in rows), 2))
        st.dataframe(pd.DataFrame([{
            "Property": r["symbol"], "Value": money(r["value"]), "Yield": pct(r["yield_"], 1),
            "Est. monthly rent": money(r["monthly"], 2), "Income accrued": money(r["accrued"], 2),
            "ROI incl. rent": pct(r["roi"], 2, True),
        } for r in rows]), hide_index=True, use_container_width=True)
    elif key == "C":
        st.markdown("##### Risk assessment and staking")
        st.dataframe(pd.DataFrame([{
            "Asset": r["symbol"], "Volatility": pct(r["vol"], 0), "Risk rating": r["rating"],
            "Your cap": pct(r["cap"], 0), "Within cap": "Yes" if r["within"] else "No", "Staking": r["staking"],
        } for r in bot.risk_rows(s)]), hide_index=True, use_container_width=True)
        earned = sum(v for k, v in s["income"].items() if market.ASSETS[k]["cls"] == "Crypto")
        st.caption(f"Staking rewards earned so far: {money(earned, 2)}. Regulatory-change alerts need a live news or regulatory feed, which this demo does not connect.")
    elif key == "D":
        st.markdown("##### Milestones and multiple on invested capital")
        rows = bot.milestone_rows(s)
        if not rows:
            st.info("No venture positions yet. Milestones are tracked from the day you invest.")
            return
        st.dataframe(pd.DataFrame([{
            "Venture": r["symbol"], "Days held": r["days"], "MOIC": f"{r['moic']:.2f}x",
            **{m: r[m] for m, _ in bots.MILESTONES},
        } for r in rows]), hide_index=True, use_container_width=True)


# ---------------------------------------------------------- command center
def _run_cmd(text: str) -> None:
    s = _s()
    reply, events = commands.run_command(s, text)
    st.session_state.console.append(("user", text))
    st.session_state.console.append(("assistant", reply))
    _log(events)
    _save()


def command_center() -> None:
    st.title("Command Center")
    st.caption("Give the bots instructions in plain commands. Type `help` for the full list.")
    if "console" not in st.session_state:
        st.session_state.console = [("assistant", "Command Center ready. Type `help` to see what I can do, or run a workflow below.")]

    q = st.columns(6)
    for col, cmd in zip(q, ["status", "report", "alerts", "risk", "rebalance", "help"]):
        if col.button(cmd.capitalize(), key=f"q_{cmd}", use_container_width=True):
            _run_cmd(cmd)

    with st.expander("Workflows"):
        st.caption("A workflow runs a fixed sequence of commands for one bot.")
        name = st.selectbox("Workflow", list(commands.WORKFLOWS), key="wf_name")
        st.code("\n".join(commands.WORKFLOWS[name]), language="text")
        if st.button("Run workflow", key="wf_run", type="primary"):
            for c in commands.WORKFLOWS[name]:
                _run_cmd(c)

    prompt = st.chat_input("Type a command, e.g. bot c, analyze BTC, rebalance")
    if prompt:
        _run_cmd(prompt)

    for role, text in st.session_state.console[-24:]:
        with st.chat_message(role):
            st.markdown(text if role == "assistant" else f"`{text}`")


# --------------------------------------------------------------- activity
def activity() -> None:
    s = _s()
    st.title("Activity and alerts")
    st.markdown("##### Active alerts")
    _alerts_block(bots.generate_alerts(s))

    st.markdown("##### Activity log")
    rows = db.get_activity(_uid(), 300)
    if not rows:
        st.info("Nothing logged yet. Trades, rejected orders and alerts will appear here.")
    else:
        levels = st.multiselect("Show", ["info", "warning", "critical"], default=["info", "warning", "critical"], key="act_levels")
        df = pd.DataFrame(rows)
        df = df[df["level"].isin(levels)].rename(columns={"ts": "Time (UTC)", "actor": "Actor", "action": "Action", "detail": "Detail", "level": "Level"})
        st.dataframe(df, hide_index=True, use_container_width=True)

    st.markdown("##### Trade history")
    trades = list(reversed(s["trades"]))
    if trades:
        st.dataframe(pd.DataFrame([{
            "Day": t["tick"], "Bot": t["bot"], "Side": t["side"].upper(), "Instrument": t["symbol"],
            "Quantity": f"{t['qty']:,.4f}", "Price": money(t["price"], 2), "Amount": money(t["notional"]), "Reason": t["reason"],
        } for t in trades]), hide_index=True, use_container_width=True)
    else:
        st.info("No trades yet.")
    st.caption(f"Fees paid: {money(s['fees_paid'], 2)} · Realised P&L: {money(s['realized_pnl'])}")


# ---------------------------------------------------------------- settings
def settings() -> None:
    s = _s()
    user = st.session_state.user
    st.title("Settings")

    st.markdown("##### Account")
    st.write(f"**{user['full_name']}** · {user['email']}")
    st.caption(f"Member since {user['created_at'][:10]}")

    st.markdown("##### Rollout phase")
    st.dataframe(pd.DataFrame([{"Phase": k, "Max invested": f"{v['cap']:.0%}", "What happens": v["desc"]} for k, v in portfolio.PHASES.items()]),
                 hide_index=True, use_container_width=True)

    with st.form("strategy_form"):
        risk = st.selectbox("Risk profile", list(portfolio.RISK_PROFILES), index=list(portfolio.RISK_PROFILES).index(s["risk"]))
        phase = st.selectbox("Deployment phase", list(portfolio.PHASES), index=list(portfolio.PHASES).index(s["phase"]))
        auto = st.toggle("Weekly autopilot rebalance", value=s["autopilot"],
                         help="When on, the coordinator rebalances every 7 simulated days.")
        if st.form_submit_button("Save strategy", type="primary"):
            s["risk"], s["phase"], s["autopilot"] = risk, phase, auto
            _log([dict(actor="You", action="SETTINGS", detail=f"Risk {risk} · phase {phase} · autopilot {'on' if auto else 'off'}")])
            _save()
            _flash("success", "Strategy saved.")
            st.rerun()

    tg = portfolio.profile(s)
    st.dataframe(pd.DataFrame(
        [{"Bucket": k, "Target weight": pct(v, 0), "Bot": market.BOT_FOR_CLASS[k]} for k, v in tg["targets"].items()]
        + [{"Bucket": "Cash reserve", "Target weight": pct(tg["cash_reserve"], 0), "Bot": "-"}]
    ), hide_index=True, use_container_width=True)
    st.caption(f"Single-position limit {tg['max_position']:.0%} · trade size {tg['trade_size']:.1%} of the portfolio · fees {portfolio.FEE_RATE:.2%} per trade.")

    st.markdown("##### Change password")
    with st.form("pw_form", clear_on_submit=True):
        cur = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        new2 = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password"):
            ok, msg = auth.change_password(_uid(), cur, new, new2)
            (st.success if ok else st.error)(msg)

    st.markdown("##### Reset simulation")
    st.caption("Returns your portfolio to $100,000 of cash and clears your trades. Your activity log is kept.")
    sure = st.checkbox("I want to reset my portfolio", key="reset_sure")
    if st.button("Reset portfolio", disabled=not sure):
        st.session_state.pf = portfolio.new_state()
        _log([dict(actor="You", action="RESET", detail="Portfolio reset to $100,000 cash.", level="warning")])
        _save()
        _flash("success", "Portfolio reset.")
        st.rerun()
