"""Sign-in and sign-up screen."""
import streamlit as st

from core import auth, db, portfolio

DISCLAIMER = (
    "United Union Bank is a demonstration platform. It runs on simulated market data and "
    "paper-trading funds. No real money moves, and nothing here is investment advice."
)


def _start_session(user: dict) -> None:
    st.session_state.user = user
    st.session_state.pop("pf", None)
    st.session_state.pop("console", None)
    st.rerun()


def render() -> None:
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        st.markdown(
            '<p class="uub-wordmark">United Union Bank</p><hr class="uub-rule"/>'
            '<p class="uub-tagline">Four AI bots. One portfolio. Stocks, real estate, crypto and '
            "ventures managed under a single strategy.</p>",
            unsafe_allow_html=True,
        )
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])

        with tab_in:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                go = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if go:
                if not email or not password:
                    st.error("Enter your email and password.")
                else:
                    user, msg = auth.login(email, password)
                    if user:
                        _start_session(user)
                    else:
                        st.error(msg)

        with tab_up:
            with st.form("signup_form"):
                name = st.text_input("Full name", key="su_name")
                email = st.text_input("Email", key="su_email")
                c1, c2 = st.columns(2)
                pw = c1.text_input("Password", type="password", key="su_pw", help="At least 8 characters, with a letter and a number.")
                pw2 = c2.text_input("Confirm password", type="password", key="su_pw2")
                agree = st.checkbox("I understand this is a demonstration with simulated funds.", key="su_agree")
                go = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if go:
                if not agree:
                    st.error("Please confirm that you understand this is a demonstration.")
                else:
                    user, msg = auth.signup(name, email, pw, pw2)
                    if user:
                        db.save_portfolio(user["id"], portfolio.new_state())
                        db.log_activity(user["id"], "System", "ACCOUNT", "Account created with $100,000 of simulated capital.")
                        _start_session(user)
                    else:
                        st.error(msg)

        st.markdown(f'<p class="uub-note">{DISCLAIMER}</p>', unsafe_allow_html=True)
