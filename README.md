# United Union Bank

An AI command-bot system for unified investment portfolio management, built with Streamlit.
Four specialised bots manage one portfolio under a single strategy, behind a sign-up and sign-in screen.

> **Demonstration platform.** It runs on simulated market data and paper-trading funds ($100,000 per new account).
> No real money moves, no real broker, wallet or bank is connected, and nothing here is investment advice.

## What is inside

| Bot | Role |
|---|---|
| **A** Stock & Equity Investment Manager | Trend and momentum analysis, risk-aware trades, daily performance reports |
| **B** Real Estate Investment Coordinator | Yield and valuation screening, rental income and ROI tracking |
| **C** Cryptocurrency & Digital Assets Manager | Volatility-based risk ratings, trading signals, staking income |
| **D** Business & Startup Investment Analyst | Milestone tracking, MOIC, follow-on and exit recommendations |

The **coordinator** ties them together: a central dashboard, weekly rebalancing (optional autopilot),
automated alerts, and a compliance gate that every order must pass (minimum ticket, cash buffer,
single-position limit, and a capital-deployment limit set by the rollout phase).

The **rollout phases** from the action plan are built in: Setup, Integration Testing, Pilot Run (max 10% invested),
Optimization & Scaling (max 50%) and Full Deployment (100%).

The **Command Center** accepts plain commands (`status`, `report`, `bot c`, `analyze BTC`, `rebalance confirm`, `buy TECH 2500` ...)
and includes one ready-made workflow per bot.

Security: passwords are stored only as salted PBKDF2-SHA256 hashes, accounts lock for 10 minutes after
5 failed sign-ins, and sign-in errors do not reveal which emails exist.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository (see below).
2. Go to <https://share.streamlit.io> and sign in with GitHub.
3. Click **Create app**, pick the repository and branch `main`, and set the main file path to `app.py`.
4. Open **Advanced settings** and choose a subdomain such as `united-union-bank`.
5. Click **Deploy**. Your link will be `https://<subdomain>.streamlit.app`.

## Push to GitHub

```bash
git init
git add .
git commit -m "United Union Bank: AI portfolio command system"
git branch -M main
git remote add origin https://github.com/<your-username>/united-union-bank.git
git push -u origin main
```

## Before you share it widely

- **Accounts reset on restart.** The app stores users in a local SQLite file (`data/uub.db`). On Streamlit Community
  Cloud that disk is temporary, so accounts and portfolios are wiped whenever the app restarts or redeploys.
  For persistent accounts, point `core/db.py` at a hosted database (Supabase, Neon or another Postgres).
- **Sessions are per browser tab.** Refreshing the page signs the user out.
- **The app is public by default.** In the Streamlit dashboard, under **Share**, you can restrict viewing to
  specific email addresses if you only want selected clients to open it.
- **Data is simulated.** To use real prices, replace the functions in `core/market.py` with a market-data feed.
  Connecting real trading or wallets is a separate regulated project and needs proper legal, compliance and security review.

## Project layout

```
app.py                  entry point (routing between sign-in and the app)
core/market.py          simulated prices and indicators (swap for a live feed)
core/portfolio.py       state, risk profiles, phases, compliance checks, order execution
core/bots.py            Bots A-D, coordinator, rebalancing, alerts
core/commands.py        Command Center interpreter and workflows
core/auth.py, db.py     sign-up, sign-in, storage
ui/                     styles, sign-in screen and all pages
.streamlit/config.toml  theme
```
