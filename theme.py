"""
theme.py - visual upgrade for the ARM Processor Simulator (Streamlit).

Usage in app.py (right after st.set_page_config(...)):

    from theme import apply_theme, render_header
    apply_theme()
    render_header()

Nothing else in your code needs to change.
"""

import streamlit as st

# ---- Palette -------------------------------------------------------------
BG = "#0b1220"
PANEL = "#111a2e"
PANEL_2 = "#16223d"
BORDER = "#24345a"
TEXT = "#e6edf7"
MUTED = "#8fa3c7"
ACCENT = "#22d3ee"      # cyan
ACCENT_2 = "#a78bfa"    # violet
GOOD = "#34d399"
WARN = "#fbbf24"
BAD = "#f87171"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], .stApp {{
    font-family: 'Inter', sans-serif;
}}
.stApp {{
    background: radial-gradient(1200px 600px at 10% -10%, #14234a 0%, {BG} 55%);
    color: {TEXT};
}}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.4rem; max-width: 1250px; }}

/* ---------- Hero header ---------- */
.sim-hero {{
    display: flex; align-items: center; gap: 18px;
    padding: 20px 26px; margin-bottom: 18px;
    background: linear-gradient(120deg, {PANEL_2} 0%, {PANEL} 60%);
    border: 1px solid {BORDER}; border-radius: 16px;
    box-shadow: 0 8px 30px rgba(0,0,0,.35);
    position: relative; overflow: hidden;
}}
.sim-hero::after {{
    content: ""; position: absolute; right: -60px; top: -60px;
    width: 220px; height: 220px; border-radius: 50%;
    background: radial-gradient(circle, {ACCENT}33 0%, transparent 70%);
}}
.sim-chip {{
    width: 58px; height: 58px; flex: 0 0 58px; border-radius: 14px;
    display: grid; place-items: center; font-size: 30px;
    background: linear-gradient(135deg, {ACCENT}, {ACCENT_2});
    box-shadow: 0 0 22px {ACCENT}55;
}}
.sim-title {{
    font-size: 1.7rem; font-weight: 700; line-height: 1.15; margin: 0;
    background: linear-gradient(90deg, {TEXT}, {ACCENT});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.sim-sub {{ color: {MUTED}; font-size: .92rem; margin-top: 4px; }}
.sim-tags {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }}
.sim-tag {{
    font-size: .72rem; font-weight: 600; letter-spacing: .04em;
    padding: 3px 10px; border-radius: 999px;
    color: {ACCENT}; background: {ACCENT}14; border: 1px solid {ACCENT}40;
}}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background: {PANEL}; padding: 6px;
    border: 1px solid {BORDER}; border-radius: 12px;
}}
.stTabs [data-baseweb="tab"] {{
    height: 40px; padding: 0 16px; border-radius: 8px;
    color: {MUTED}; font-weight: 500; background: transparent;
}}
.stTabs [data-baseweb="tab"]:hover {{ color: {TEXT}; background: {PANEL_2}; }}
.stTabs [aria-selected="true"] {{
    color: {BG} !important; font-weight: 600;
    background: linear-gradient(90deg, {ACCENT}, {ACCENT_2}) !important;
}}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button {{
    border-radius: 10px; font-weight: 600; padding: .45rem 1.1rem;
    background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER};
    transition: all .15s ease;
}}
.stButton > button:hover {{
    border-color: {ACCENT}; color: {ACCENT};
    box-shadow: 0 0 14px {ACCENT}33; transform: translateY(-1px);
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(90deg, {ACCENT}, {ACCENT_2});
    color: {BG}; border: none;
}}
.stButton > button[kind="primary"]:hover {{ color: {BG}; filter: brightness(1.1); }}

/* ---------- Metric cards ---------- */
[data-testid="stMetric"] {{
    background: linear-gradient(160deg, {PANEL_2}, {PANEL});
    border: 1px solid {BORDER}; border-radius: 14px; padding: 14px 18px;
    box-shadow: 0 4px 16px rgba(0,0,0,.25);
}}
[data-testid="stMetricLabel"] p {{
    color: {MUTED}; font-size: .78rem; text-transform: uppercase; letter-spacing: .06em;
}}
[data-testid="stMetricValue"] {{
    font-family: 'JetBrains Mono', monospace; color: {ACCENT}; font-weight: 600;
}}

/* ---------- Code, editor, tables ---------- */
textarea, .stTextArea textarea, code, pre {{
    font-family: 'JetBrains Mono', monospace !important;
}}
.stTextArea textarea {{
    background: #0a1020 !important; color: #d6e4ff !important;
    border: 1px solid {BORDER} !important; border-radius: 12px !important;
    font-size: .88rem !important;
}}
.stTextArea textarea:focus {{ border-color: {ACCENT} !important; box-shadow: 0 0 0 1px {ACCENT}; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{
    border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden;
}}
[data-testid="stCodeBlock"] pre {{ background: #0a1020 !important; border-radius: 12px; border: 1px solid {BORDER}; }}

/* ---------- Inputs, sidebar, alerts ---------- */
[data-baseweb="select"] > div, .stNumberInput input, .stTextInput input {{
    background: {PANEL} !important; border-color: {BORDER} !important; border-radius: 10px !important;
}}
section[data-testid="stSidebar"] {{
    background: {PANEL}; border-right: 1px solid {BORDER};
}}
[data-testid="stAlert"] {{ border-radius: 12px; border: 1px solid {BORDER}; }}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: {ACCENT}; box-shadow: 0 0 10px {ACCENT}; }}
h1, h2, h3 {{ color: {TEXT}; letter-spacing: -.01em; }}
h3 {{ border-left: 3px solid {ACCENT}; padding-left: 10px; }}
hr {{ border-color: {BORDER}; }}

/* ---------- Helper classes (usable via st.markdown(..., unsafe_allow_html=True)) ---------- */
.pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; }}
.pill-hit   {{ color:{GOOD}; background:{GOOD}1f; border:1px solid {GOOD}55; }}
.pill-miss  {{ color:{BAD};  background:{BAD}1f;  border:1px solid {BAD}55; }}
.pill-stall {{ color:{WARN}; background:{WARN}1f; border:1px solid {WARN}55; }}
.pill-info  {{ color:{ACCENT}; background:{ACCENT}1f; border:1px solid {ACCENT}55; }}

/* Footer */
.sim-footer {{ text-align:center; color:{MUTED}; font-size:.78rem; margin-top:28px; padding-top:14px; border-top:1px solid {BORDER}; }}
</style>
"""


def apply_theme() -> None:
    """Inject the custom CSS. Call once, right after st.set_page_config()."""
    st.markdown(_CSS, unsafe_allow_html=True)


def render_header(
    title: str = "ARM Processor Architecture Simulator",
    subtitle: str = "A simplified ARM-like RISC CPU modelled for mobile-phone workloads",
    tags=("RISC", "5-STAGE PIPELINE", "FORWARDING", "L1 CACHE", "MEMORY-MAPPED I/O"),
) -> None:
    """Render the gradient hero header at the top of the page."""
    tag_html = "".join(f'<span class="sim-tag">{t}</span>' for t in tags)
    st.markdown(
        f"""
        <div class="sim-hero">
            <div class="sim-chip">🖥️</div>
            <div>
                <p class="sim-title">{title}</p>
                <div class="sim-sub">{subtitle}</div>
                <div class="sim-tags">{tag_html}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer(text: str = "Mini Project · Computer Architecture") -> None:
    """Optional footer. Call at the very end of app.py."""
    st.markdown(f'<div class="sim-footer">{text}</div>', unsafe_allow_html=True)


def pill(label: str, kind: str = "info") -> str:
    """Return HTML for a small coloured badge. kind: hit | miss | stall | info.
    Example: st.markdown(pill("HIT", "hit"), unsafe_allow_html=True)
    """
    return f'<span class="pill pill-{kind}">{label}</span>'
