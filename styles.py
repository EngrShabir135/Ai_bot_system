"""Global look and feel: navy and brass, serif headings, quiet cards."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');

.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp td, .stApp th, .stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricLabel"] {
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .uub-wordmark {
    font-family: 'Newsreader', Georgia, serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
}
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.2rem; max-width: 1280px; }

[data-testid="stMetric"] {
    background: #12233A;
    border: 1px solid #23405F;
    border-radius: 6px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] { color: #93A3B8; }
[data-testid="stMetricValue"] { font-weight: 500; }

button[data-testid^="stBaseButton-primary"] { color: #0B1626 !important; font-weight: 600; }
button[data-testid^="stBaseButton-secondary"] { border-color: #2C4A6E; }

[data-testid="stSidebar"] { border-right: 1px solid #23405F; }
[data-testid="stDataFrame"] { border: 1px solid #23405F; border-radius: 6px; }

.uub-wordmark { font-size: 2.6rem; line-height: 1.1; margin: 0; color: #EDE7DA; }
.uub-rule { width: 56px; height: 3px; background: #C9A45C; margin: 14px 0 12px 0; border: 0; }
.uub-tagline { color: #93A3B8; margin: 0 0 1.4rem 0; }
.uub-side-name { font-family: 'Newsreader', Georgia, serif; font-size: 1.35rem; font-weight: 600; margin: 0; }
.uub-note { color: #93A3B8; font-size: 0.85rem; }
.uub-pill {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    border: 1px solid #C9A45C; color: #C9A45C; font-size: 0.8rem;
}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
