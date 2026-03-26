"""
app.py — RWA Infinity Model v1.0
World-Class Real World Asset Tokenization Dashboard
Powered by Claude claude-sonnet-4-6 AI | DeFiLlama | CoinGecko

Run: streamlit run app.py
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta

# ─── Load .env file if present (python-dotenv) ─────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional — keys can also be set as shell env vars

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
try:
    from streamlit_autorefresh import st_autorefresh as _st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False

# ─── Page config (MUST be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="RWA Infinity | Real World Asset Intelligence",
    page_icon="♾️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Auto-refresh (silent background page rerun) ───────────────────────────────
_AR_OPTIONS = {"Off": 0, "30s": 30_000, "1 min": 60_000, "2 min": 120_000, "5 min": 300_000}
_ar_label   = st.session_state.get("ar_select", "1 min")
_ar_ms      = _AR_OPTIONS.get(_ar_label, 60_000)
if _HAS_AUTOREFRESH and _ar_ms > 0:
    _st_autorefresh(interval=_ar_ms, key="page_autorefresh")

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── Security Audit Logger (#15) ───────────────────────────────────────────────
# Dedicated logger for user-action events (API key changes, settings saves, etc.)
# Writes to rwa_audit.log alongside app.py; does NOT write to root logger.
_audit_handler = logging.FileHandler(
    os.path.join(os.path.dirname(__file__), "rwa_audit.log"),
    encoding="utf-8",
)
_audit_handler.setFormatter(logging.Formatter(
    "%(asctime)s [AUDIT] %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
))
_audit_log = logging.getLogger("rwa.audit")
_audit_log.addHandler(_audit_handler)
_audit_log.setLevel(logging.INFO)
_audit_log.propagate = False  # keep audit events out of the root logger


def audit(event: str, **ctx) -> None:
    """Log a security-relevant user action to the audit trail."""
    extra = " ".join(f"{k}={v!r}" for k, v in ctx.items())
    _audit_log.info("%s %s", event, extra)

# ─── Imports ───────────────────────────────────────────────────────────────────
import database as _db
import scheduler as _sched
import ai_agent as _agent
import data_feeds as _df
import pdf_export as _pdf
from config import (
    PORTFOLIO_TIERS, AI_AGENTS, CATEGORY_COLORS,
    RISK_LABELS, RWA_UNIVERSE, ARB_STRONG_THRESHOLD_PCT,
    XRPL_RLUSD_ISSUER, SENTRY_DSN, feature_enabled,
)

# ─── Sentry error monitoring (free tier — only loads when DSN is set) ──────────
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.05,   # 5% performance tracing (free tier budget)
            send_default_pii=False,    # NEVER send PII
            before_send=lambda event, hint: event,
        )
        logger.info("[App] Sentry error monitoring active")
    except ImportError:
        logger.debug("[App] sentry-sdk not installed — skipping error monitoring")

# ─────────────────────────────────────────────────────────────────────────────
# INITIALIZATION (once per process)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _init():
    """Initialize DB + scheduler once per process."""
    _db.init_db()
    _sched.start()
    return True

_init()

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base */
:root {
  --primary:   #00D4FF;
  --bg:        #0A0E1A;
  --card-bg:   #111827;
  --border:    #1F2937;
  --text:      #E2E8F0;
  --muted:     #6B7280;
  --success:   #34D399;
  --warning:   #FBBF24;
  --danger:    #EF4444;
}

/* Main background */
.stApp { background: var(--bg); }

/* Hide default Streamlit header & footer */
#MainMenu, header, footer { visibility: hidden; }

/* Metric cards */
.metric-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin: 4px 0;
    transition: border-color 0.2s ease;
}
.metric-card:hover { border-color: var(--primary); }

.metric-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 26px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
}
.metric-delta {
    font-size: 12px;
    margin-top: 4px;
}
.delta-up   { color: var(--success); }
.delta-down { color: var(--danger); }
.delta-flat { color: var(--muted); }

/* Tier badge */
.tier-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.05em;
}

/* Section headers */
.section-header {
    font-size: 13px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin: 16px 0 12px 0;
}

/* Arb signal badges */
.signal-extreme { background: #4B1C1C; color: #EF4444; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
.signal-strong  { background: #1C2E1C; color: #34D399; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
.signal-arb     { background: #1C2140; color: #00D4FF; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; }

/* Ticker bar */
.ticker-wrap {
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
    padding: 10px 0;
    overflow: hidden;
    white-space: nowrap;
}

/* Status dot */
.status-live { display: inline-block; width: 8px; height: 8px; background: var(--success); border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    background: var(--card-bg);
    border-radius: 10px;
    padding: 6px;
    gap: 4px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: var(--muted);
    font-weight: 700;
    font-size: 15px !important;
    padding: 10px 18px !important;
    min-height: 46px !important;
    letter-spacing: 0.01em;
}
.stTabs [aria-selected="true"] {
    background: var(--primary) !important;
    color: #000 !important;
}

/* Streamlit override */
div[data-testid="stHorizontalBlock"] { gap: 12px; }
.stMetric { background: var(--card-bg); border-radius: 10px; padding: 12px; border: 1px solid var(--border); }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_usd(n, decimals=0):
    if n is None: return "—"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    if n >= 1e6:  return f"${n/1e6:.1f}M"
    if n >= 1e3:  return f"${n/1e3:.0f}K"
    return f"${n:,.{decimals}f}"

def _fmt_pct(n, decimals=2):
    if n is None: return "—"
    return f"{n:.{decimals}f}%"

def _color_for_value(v, low, high, invert=False):
    """Return green/yellow/red CSS color based on value range."""
    if v is None: return "#6B7280"
    ratio = (v - low) / max(high - low, 0.001)
    ratio = max(0, min(1, ratio))
    if invert: ratio = 1 - ratio
    if ratio > 0.6: return "#34D399"
    if ratio > 0.3: return "#FBBF24"
    return "#EF4444"

def _metric_card(label, value, delta=None, delta_label="", color=None, tooltip=None):
    color_str = f"color: {color};" if color else ""
    title_attr = f' title="{tooltip}"' if tooltip else ""
    delta_html = ""
    if delta is not None:
        if isinstance(delta, str):
            # String delta: render as subtitle caption (no arrow)
            delta_html = f'<div class="metric-delta delta-flat">{delta}</div>'
        else:
            cls   = "delta-up" if delta > 0 else "delta-down" if delta < 0 else "delta-flat"
            arrow = "▲" if delta > 0 else "▼" if delta < 0 else "●"
            delta_html = f'<div class="metric-delta {cls}">{arrow} {abs(delta):.2f}% {delta_label}</div>'
    st.markdown(f"""
    <div class="metric-card"{title_attr} style="cursor:{'help' if tooltip else 'default'}">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="{color_str}">{value}</div>
        {delta_html}
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────

def _ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

_ss("selected_tier",    3)
_ss("portfolio_value",  100_000)
_ss("agent_name",       "HORIZON")
_ss("agent_running",    False)
_ss("agent_dry_run",    True)
_ss("show_mc",          False)
_ss("tab_index",        0)
_ss("api_key_set",      bool(os.environ.get("ANTHROPIC_API_KEY")))
_ss("user_anthropic_key", "")  # per-session user-supplied key — never written to os.environ
_ss("ai_news_brief",    "")

# ── Shareable URL params — read ?tier=X&value=Y on page load ─────────────────
try:
    _qp = st.query_params
    if "tier" in _qp:
        _t = int(_qp["tier"])
        if 1 <= _t <= 5:
            st.session_state["selected_tier"] = _t
    if "value" in _qp:
        _v = int(_qp["value"])
        if 1_000 <= _v <= 1_000_000_000:
            st.session_state["portfolio_value"] = _v
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS (cached per rerun)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_assets():
    df = _db.get_all_rwa_latest()
    if df.empty:
        # Scheduler populates DB in the background — return static config immediately
        # so the first render is fast. Real data appears on next cache expiry (~5 min).
        df = pd.DataFrame(RWA_UNIVERSE)
        df["current_yield_pct"]  = df["expected_yield_pct"]
        df["composite_score"]    = 50.0
        df["current_price"]      = 1.0
        df["tvl_usd"]            = 0.0
        df["last_updated"]       = datetime.now(timezone.utc).isoformat()
    return df

@st.cache_data(ttl=60, show_spinner=False)
def _load_portfolio(tier, value):
    from portfolio import build_portfolio
    try:
        return build_portfolio(tier, value)
    except Exception as e:
        logger.error("build_portfolio failed: %s", e)
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def _load_arb():
    from arbitrage import run_full_arb_scan, get_arb_summary
    try:
        df = _db.get_active_arb_opportunities(50)
        if df.empty:
            opps = run_full_arb_scan()
            df = _db.get_active_arb_opportunities(50)
        summary = get_arb_summary(df.to_dict("records") if not df.empty else [])
        return df, summary
    except Exception as e:
        logger.warning("load_arb failed: %s", e)
        return pd.DataFrame(), {}

@st.cache_data(ttl=1800, show_spinner=False)
def _load_news():
    return _db.get_recent_news(20)

@st.cache_data(ttl=30, show_spinner=False)
def _load_market_summary():
    """Fetch market summary with a hard 6-second timeout to keep the UI responsive.
    The TTL is short (30 s) so stale/empty results are retried quickly once the
    background scheduler has warmed the API caches."""
    import concurrent.futures
    try:
        from data_feeds import get_market_summary
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
            _fut = _ex.submit(get_market_summary)
            try:
                return _fut.result(timeout=6)
            except concurrent.futures.TimeoutError:
                return {}
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def _load_all_portfolios(value):
    from portfolio import build_all_portfolios, portfolio_comparison_df
    try:
        ports = build_all_portfolios(value)
        return ports, portfolio_comparison_df(ports)
    except Exception as e:
        logger.error("build_all_portfolios failed: %s", e)
        return {}, pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# TOP HEADER
# ─────────────────────────────────────────────────────────────────────────────

col_logo, col_title, col_status, col_ctrl = st.columns([1, 4, 2, 2])

with col_logo:
    st.markdown("## ♾️")

with col_title:
    st.markdown("""
    <div style="padding-top:4px">
        <span style="font-size:24px;font-weight:800;color:#E2E8F0;letter-spacing:-0.5px">RWA INFINITY</span>
        <span style="font-size:12px;color:#6B7280;margin-left:10px;letter-spacing:0.1em">REAL WORLD ASSET INTELLIGENCE</span>
    </div>
    """, unsafe_allow_html=True)

with col_status:
    scan_status = _db.read_scan_status()
    is_running  = scan_status.get("running", 0)
    last_ts     = scan_status.get("timestamp") or ""
    last_time   = ""
    if last_ts:
        try:
            dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            mins_ago = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() / 60))
            last_time = f"{mins_ago}m ago" if mins_ago < 60 else f"{mins_ago//60}h ago"
        except Exception:
            last_time = "—"

    if is_running:
        pct = scan_status.get("progress_pct", 0)
        task = scan_status.get("current_task", "...")[:30]
        st.markdown(f'<div style="font-size:12px;color:#FBBF24">⚡ Refreshing... {pct}%<br><span style="color:#6B7280">{task}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="font-size:12px"><span class="status-live"></span><span style="color:#34D399">Live</span>&nbsp;&nbsp;<span style="color:#6B7280">Updated {last_time}</span></div>', unsafe_allow_html=True)

with col_ctrl:
    if st.button("⟳ Refresh Now", use_container_width=True, key="btn_refresh"):
        _sched.trigger_refresh()
        st.cache_data.clear()
        st.rerun()
    st.selectbox(
        "Auto-refresh",
        list(_AR_OPTIONS.keys()),
        index=list(_AR_OPTIONS.keys()).index(_ar_label),
        key="ar_select",
        label_visibility="collapsed",
        help="Page auto-refresh interval — set to Off to disable",
    )

st.markdown('<hr style="border:none;border-top:1px solid #1F2937;margin:8px 0 16px">', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MARKET TICKER BAR
# ─────────────────────────────────────────────────────────────────────────────

market = _load_market_summary()
assets_df = _load_assets()

ticker_items = [
    f"🏦 Total RWA TVL: {_fmt_usd(market.get('total_rwa_tvl_usd', 0))}",
    f"📈 Avg RWA Yield: {_fmt_pct(market.get('avg_rwa_yield_pct', 0))}",
    f"🔗 Active Pools: {market.get('active_pools', 0)}",
    f"🥇 Gold: {_fmt_usd(market.get('gold_price_usd', 0), 0)}/oz",
    f"📊 Protocols: {market.get('protocol_count', 0)}",
]

# Add top asset yields to ticker
if not assets_df.empty:
    top_yield = assets_df.nlargest(5, "current_yield_pct")
    for _, row in top_yield.iterrows():
        yield_val = row.get("current_yield_pct") or 0
        if yield_val > 0:
            ticker_items.append(f"💎 {row.get('token_symbol', row.get('id', '?'))}: {_fmt_pct(yield_val)}")

# Add F&G and macro regime to ticker
_fg_val   = market.get("fear_greed_value", 50)
_fg_lbl   = market.get("fear_greed_label", "Neutral")
_fg_sig   = market.get("fear_greed_signal", "NEUTRAL")
_regime   = market.get("macro_regime", "NEUTRAL")
_stable   = market.get("stablecoin_total_bn", 0)
_fg_emoji = {"STRONG_BUY": "🟢", "BUY": "🟡", "NEUTRAL": "⚪", "SELL": "🟠", "STRONG_SELL": "🔴"}.get(_fg_sig, "⚪")
ticker_items.extend([
    f"{_fg_emoji} F&G: {_fg_val}/100 ({_fg_lbl})",
    f"🌐 Regime: {_regime}",
    f"💵 Stablecoin Supply: ${_stable:.0f}B",
])

ticker_text = "  ·  ".join(ticker_items)
st.markdown(f"""
<div class="ticker-wrap">
    <span style="font-size:15px;color:#9CA3AF;letter-spacing:0.03em">{ticker_text}</span>
</div>
""", unsafe_allow_html=True)

# ── Macro Intelligence Banner ────────────────────────────────────────────────
_REGIME_COLORS = {
    "RISK_ON":          ("#065F46", "#34D399", "🚀"),
    "RISK_OFF":         ("#7C2D12", "#F97316", "🛡️"),
    "STAGFLATION":      ("#78350F", "#FBBF24", "⚠️"),
    "LIQUIDITY_CRUNCH": ("#1E1B4B", "#818CF8", "🧊"),
    "NEUTRAL":          ("#1F2937", "#9CA3AF", "⚖️"),
}
_rc = _REGIME_COLORS.get(_regime, _REGIME_COLORS["NEUTRAL"])
_bias        = market.get("macro_bias", "MODERATE")
_macro_desc  = market.get("macro_description", "")

# F&G color gradient
if _fg_val <= 20:
    _fg_color = "#818CF8"
    _fg_bg    = "#1E1B4B"
elif _fg_val <= 40:
    _fg_color = "#F97316"
    _fg_bg    = "#431407"
elif _fg_val <= 60:
    _fg_color = "#9CA3AF"
    _fg_bg    = "#1F2937"
elif _fg_val <= 80:
    _fg_color = "#FBBF24"
    _fg_bg    = "#451A03"
else:
    _fg_color = "#34D399"
    _fg_bg    = "#064E3B"

_mac_col1, _mac_col2, _mac_col3 = st.columns([1.5, 1.5, 5])
with _mac_col1:
    st.markdown(f"""
    <div style="background:{_fg_bg};border:1px solid {_fg_color}40;border-radius:8px;
                padding:10px 14px;text-align:center;">
        <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.1em">Fear & Greed</div>
        <div style="font-size:28px;font-weight:800;color:{_fg_color}">{_fg_val}</div>
        <div style="font-size:11px;color:{_fg_color}">{_fg_lbl}</div>
        <div style="font-size:10px;color:#6B7280;margin-top:2px">Signal: {_fg_sig}</div>
    </div>
    """, unsafe_allow_html=True)

with _mac_col2:
    st.markdown(f"""
    <div style="background:{_rc[0]};border:1px solid {_rc[1]}40;border-radius:8px;
                padding:10px 14px;text-align:center;">
        <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.1em">Macro Regime</div>
        <div style="font-size:20px;font-weight:800;color:{_rc[1]}">{_rc[2]} {_regime}</div>
        <div style="font-size:11px;color:{_rc[1]}">Bias: {_bias}</div>
    </div>
    """, unsafe_allow_html=True)

with _mac_col3:
    if _macro_desc:
        st.markdown(f"""
        <div style="background:#0D1117;border:1px solid #1F2937;border-radius:8px;
                    padding:10px 14px;font-size:12px;color:#9CA3AF;line-height:1.5">
            <span style="color:#6B7280;font-size:10px;text-transform:uppercase;letter-spacing:0.08em">MACRO INTELLIGENCE · </span>
            {_macro_desc}
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO TIER SELECTOR
# ─────────────────────────────────────────────────────────────────────────────

# Portfolio value input + shareable link (above tier selector)
col_val, col_share, col_empty2 = st.columns([2, 3, 5])
with col_val:
    portfolio_value = st.number_input(
        "Portfolio Value (USD)",
        min_value=1_000,
        max_value=1_000_000_000,
        value=st.session_state["portfolio_value"],
        step=10_000,
        format="%d",
        key="portfolio_value_input",
        help="The total amount you want to invest. All dollar amounts (Annual Income, USD Value per holding, etc.) are calculated relative to this number",
    )
    st.session_state["portfolio_value"] = portfolio_value
with col_share:
    _share_url = f"?tier={st.session_state['selected_tier']}&value={portfolio_value}"
    st.text_input(
        "🔗 Share Portfolio",
        value=_share_url,
        key="share_url_display",
        help="Copy this URL to share your current portfolio configuration",
    )

st.markdown('<div class="section-header">Portfolio Strategy</div>', unsafe_allow_html=True)

tier_cols = st.columns(5)
tier_labels = {
    1: ("🛡️", "Ultra-Conservative", "#00D4FF"),
    2: ("⚓", "Conservative",        "#34D399"),
    3: ("⚖️", "Moderate",            "#FBBF24"),
    4: ("🔥", "Aggressive",          "#F97316"),
    5: ("⚡", "Ultra-Aggressive",    "#EF4444"),
}

for i, (tier, (icon, label, color)) in enumerate(tier_labels.items()):
    with tier_cols[i]:
        selected = st.session_state["selected_tier"] == tier
        border   = f"2px solid {color}" if selected else "1px solid #1F2937"
        bg       = f"{color}18" if selected else "#111827"
        tier_cfg = PORTFOLIO_TIERS[tier]
        if st.button(
            f"{icon} {label}\n{tier_cfg['target_yield_pct']}% target",
            key=f"tier_btn_{tier}",
            use_container_width=True,
        ):
            st.session_state["selected_tier"] = tier
            st.rerun()
        # Overlay styling with markdown
        st.markdown(
            f'<div style="font-size:10px;color:{color};text-align:center;margin-top:-8px">'
            f'Max DD: {tier_cfg["max_drawdown_pct"]}%</div>',
            unsafe_allow_html=True
        )

selected_tier = st.session_state["selected_tier"]
tier_cfg      = PORTFOLIO_TIERS[selected_tier]


# ─────────────────────────────────────────────────────────────────────────────
# SCREENER CACHE — defined here (module-level) so it is registered once per
# process and NOT re-registered on every Streamlit render cycle.
# ─────────────────────────────────────────────────────────────────────────────

from data_feeds import compute_screener_signals as _compute_screener_signals

_SCR_SYMS  = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

@st.cache_data(ttl=300, show_spinner=False)
def _load_screener_signals():
    return {sym: _compute_screener_signals(sym) for sym in _SCR_SYMS}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────────────────────

tab_portfolio, tab_universe, tab_arb, tab_carry, tab_compare, tab_ai, tab_news, tab_trades, tab_reg, tab_screener, tab_macro, tab_onchain, tab_options = st.tabs([
    "📊 Portfolio",
    "🌐 Asset Universe",
    "⚡ Arbitrage",
    "💱 Carry Trade",
    "📈 Compare Tiers",
    "🤖 AI Agent",
    "📰 News Feed",
    "📋 Trade Log",
    "🏛️ Regulatory",
    "🔍 Screener",
    "🌍 Macro",
    "⛓️ On-Chain",
    "📐 Options Flow",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════

with tab_portfolio:
    portfolio = _load_portfolio(selected_tier, portfolio_value)
    if not portfolio:
        st.warning("Loading portfolio data... Please wait or click Refresh Now.")
        metrics, holdings, cat_sum = {}, [], {}
    else:
        metrics  = portfolio.get("metrics", {})
        holdings = portfolio.get("holdings", [])
        cat_sum  = portfolio.get("category_summary", {})

    # ── KPI Row ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        _metric_card("Portfolio Yield", _fmt_pct(metrics.get("weighted_yield_pct")),
                     color=tier_cfg["color"],
                     tooltip="Weighted average yield across all portfolio holdings at current market rates")
    with k2:
        _metric_card("Annual Income", _fmt_usd(metrics.get("annual_return_usd")),
                     color="#34D399",
                     tooltip="Projected annual income in dollars at current yields, based on your portfolio value")
    with k3:
        _metric_card("Monthly Income", _fmt_usd(metrics.get("monthly_income_usd")),
                     color="#34D399",
                     tooltip="Projected monthly income in dollars — annual income divided by 12")
    with k4:
        _metric_card("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}",
                     color=_color_for_value(metrics.get("sharpe_ratio", 0), 0, 2),
                     tooltip="Risk-adjusted return = (portfolio yield − risk-free rate) ÷ volatility. Above 1.0 is good, above 2.0 is excellent")
    with k5:
        _metric_card("Max Drawdown", _fmt_pct(metrics.get("max_drawdown_pct")),
                     color=_color_for_value(metrics.get("max_drawdown_pct", 0), 0, 30, invert=True),
                     tooltip="Largest estimated peak-to-trough portfolio decline under stress conditions. Lower is better. This tier targets ≤" + str(tier_cfg['max_drawdown_pct']) + "%")
    with k6:
        _metric_card("VaR 95%", _fmt_pct(metrics.get("var_95_pct")),
                     color=_color_for_value(metrics.get("var_95_pct", 0), 0, 20, invert=True),
                     tooltip="Value at Risk (95%): estimated maximum portfolio loss on a bad day — this threshold is only exceeded 5% of the time")

    st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)

    # ── Charts Row ───────────────────────────────────────────────────────────
    chart_left, chart_right = st.columns([5, 7])

    with chart_left:
        st.markdown('<div class="section-header">Allocation by Category</div>', unsafe_allow_html=True)
        if cat_sum:
            labels  = list(cat_sum.keys())
            values  = [cat_sum[c]["weight_pct"] for c in labels]
            colors  = [cat_sum[c].get("color", "#888") for c in labels]
            # Rich hover: show yield per category
            hover   = [
                f"<b>{c}</b><br>Weight: {cat_sum[c]['weight_pct']:.1f}%<br>"
                f"Yield: {cat_sum[c]['yield_pct']:.2f}%<br>Holdings: {cat_sum[c]['count']}"
                for c in labels
            ]
            fig_pie = go.Figure(go.Pie(
                labels=labels, values=values,
                marker_colors=colors,
                hole=0.55,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover,
                textinfo="label+percent",
                textfont_size=11,
            ))
            fig_pie.add_annotation(
                text=f"<b>{_fmt_pct(metrics.get('weighted_yield_pct'))}</b><br><span style='font-size:11px'>yield</span>",
                x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#E2E8F0"),
            )
            fig_pie.update_layout(
                paper_bgcolor="#111827", plot_bgcolor="#111827",
                font_color="#E2E8F0",
                margin=dict(l=0, r=0, t=20, b=0),
                height=320,
                legend=dict(
                    font_size=11,
                    bgcolor="#111827",
                    bordercolor="#1F2937",
                    x=1.0, xanchor="right",
                    orientation="v",
                ),
                showlegend=True,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with chart_right:
        st.markdown('<div class="section-header">Holdings — Yield vs Risk</div>', unsafe_allow_html=True)
        if holdings:
            h_df = pd.DataFrame(holdings)
            fig_scatter = px.scatter(
                h_df,
                x="risk_score",
                y="current_yield_pct",
                size="weight_pct",
                color="category",
                color_discrete_map=CATEGORY_COLORS,
                hover_data={"name": True, "weight_pct": True, "protocol": True,
                            "current_yield_pct": True, "risk_score": True},
                labels={"risk_score": "Risk Score (1=lowest)", "current_yield_pct": "Yield (%)"},
                size_max=35,
            )
            fig_scatter.update_layout(
                paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
                font_color="#E2E8F0",
                margin=dict(l=40, r=20, t=20, b=40),
                height=320,
                xaxis=dict(gridcolor="#1F2937", range=[0, 11]),
                yaxis=dict(gridcolor="#1F2937"),
                legend=dict(bgcolor="#111827", bordercolor="#1F2937", font_size=10),
            )
            fig_scatter.add_vline(x=5, line_dash="dash", line_color="#374151",
                                  annotation_text="Risk midpoint")
            fig_scatter.add_hline(y=4.25, line_dash="dash", line_color="#374151",
                                  annotation_text="Risk-free rate (4.25%)")
            st.plotly_chart(fig_scatter, use_container_width=True)

    # ── Holdings Table ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Portfolio Holdings</div>', unsafe_allow_html=True)
    if holdings:
        h_df = pd.DataFrame(holdings)
        display_col_map = {
            "id": "ID", "name": "Name", "category": "Category", "chain": "Chain",
            "weight_pct": "Weight %", "usd_value": "USD Value",
            "current_yield_pct": "Yield %", "risk_score": "Risk",
            "liquidity_score": "Liquidity", "regulatory_score": "Regulatory", "score": "Score",
        }
        present_cols = [c for c in display_col_map if c in h_df.columns]
        display_df = h_df[present_cols].copy()
        display_df.columns = [display_col_map[c] for c in present_cols]

        def _highlight_yield(val):
            try:
                v = float(val)
                if v >= 10: return "color: #EF4444"
                if v >= 7:  return "color: #F97316"
                if v >= 4:  return "color: #34D399"
                return "color: #6B7280"
            except Exception:
                return ""

        styled = (display_df.style
            .format({
                "Weight %": "{:.1f}%",
                "USD Value": lambda x: _fmt_usd(x),
                "Yield %": "{:.2f}%",
                "Score": "{:.1f}",
            })
            .map(_highlight_yield, subset=["Yield %"])
            .set_properties(**{"background-color": "#111827", "color": "#E2E8F0",
                                "border": "1px solid #1F2937"})
        )
        st.dataframe(styled, use_container_width=True, height=min(400, 55 + 35 * len(display_df)))

    # ── Yield Breakdown Bar Chart (Phase 7 UI) ───────────────────────────────
    if holdings:
        _h_df_yb = pd.DataFrame(holdings)
        _yb_cols_needed = {"name", "current_yield_pct", "category", "weight_pct"}
        if _yb_cols_needed.issubset(set(_h_df_yb.columns)):
            _yb = _h_df_yb[_h_df_yb["current_yield_pct"].fillna(0) > 0].copy()
            _yb = _yb.nlargest(12, "current_yield_pct")
            if not _yb.empty:
                st.markdown('<div class="section-header">Top Holdings by Yield</div>', unsafe_allow_html=True)
                _bar_colors = [CATEGORY_COLORS.get(c, "#6366f1") for c in _yb["category"]]
                _fig_ybar = go.Figure(go.Bar(
                    x=_yb["name"],
                    y=_yb["current_yield_pct"],
                    marker_color=_bar_colors,
                    text=[f"{v:.1f}%" for v in _yb["current_yield_pct"]],
                    textposition="outside",
                    customdata=_yb[["category", "weight_pct"]].values,
                    hovertemplate="<b>%{x}</b><br>Yield: %{y:.2f}%<br>Category: %{customdata[0]}<br>Weight: %{customdata[1]:.1f}%<extra></extra>",
                ))
                _fig_ybar.update_layout(
                    paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
                    font_color="#E2E8F0",
                    margin=dict(l=40, r=20, t=30, b=80),
                    height=280,
                    xaxis=dict(gridcolor="#1F2937", tickangle=-35, tickfont_size=10),
                    yaxis=dict(gridcolor="#1F2937", ticksuffix="%"),
                    showlegend=False,
                )
                _fig_ybar.add_hline(y=metrics.get("weighted_yield_pct", 0), line_dash="dash",
                                    line_color="#A78BFA", opacity=0.7,
                                    annotation_text=f"Portfolio avg {metrics.get('weighted_yield_pct', 0):.1f}%",
                                    annotation_font_color="#A78BFA", annotation_font_size=10)
                st.plotly_chart(_fig_ybar, use_container_width=True)

    # ── Risk Metrics ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Risk Metrics</div>', unsafe_allow_html=True)
    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        _metric_card("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}",
                     tooltip="Like Sharpe but only penalizes downside volatility — better for yield-focused portfolios. Above 1.0 is solid, above 2.0 is strong")
    with r2:
        _metric_card("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}",
                     tooltip="Annual return ÷ max drawdown. Higher means you are earning more per unit of historical drawdown risk. Above 1.0 is good")
    with r3:
        _metric_card("VaR 99%", _fmt_pct(metrics.get("var_99_pct")),
                     tooltip="Value at Risk (99%): estimated worst-case daily portfolio loss — only exceeded 1% of the time. More conservative than VaR 95%")
    with r4:
        _metric_card("CVaR 95%", _fmt_pct(metrics.get("cvar_95_pct")),
                     tooltip="Conditional VaR (Expected Shortfall): the expected average loss when you are already in the worst 5% of outcomes. Best measure of true tail risk")
    with r5:
        _metric_card("Diversification", f"{metrics.get('diversification_ratio', 0):.2f}x",
                     tooltip="Diversification benefit: weighted avg individual volatility ÷ portfolio volatility. Above 1.0x means your asset mix actively reduces overall risk")

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Monte Carlo Simulation (10,000 scenarios)</div>',
                unsafe_allow_html=True)
    if st.button("▶ Run Monte Carlo Simulation", key="btn_mc",
                 help="Simulates 10,000 portfolio paths over 1 year using Jump-Diffusion GBM (Merton 1976). Shows the full distribution of outcomes from bear case (5th percentile) to bull case (95th percentile)"):
        st.session_state["show_mc"] = True

    if st.session_state.get("show_mc"):
        with st.spinner("Simulating 10,000 portfolio paths...", show_time=True):
            from portfolio import run_monte_carlo
            mc = run_monte_carlo(portfolio)

        if mc:
            mc_cols = st.columns(5)
            with mc_cols[0]:
                _metric_card("Bear Case (5th)", _fmt_usd(mc["percentile_5"]), color="#EF4444")
            with mc_cols[1]:
                _metric_card("Below Avg (25th)", _fmt_usd(mc["percentile_25"]), color="#F97316")
            with mc_cols[2]:
                _metric_card("Median", _fmt_usd(mc["percentile_50"]), color="#FBBF24")
            with mc_cols[3]:
                _metric_card("Above Avg (75th)", _fmt_usd(mc["percentile_75"]), color="#34D399")
            with mc_cols[4]:
                _metric_card("Bull Case (95th)", _fmt_usd(mc["percentile_95"]), color="#00D4FF")

            mc2 = st.columns(3)
            with mc2[0]:
                _metric_card("Prob of Loss", _fmt_pct(mc["prob_loss_pct"]), color="#EF4444")
            with mc2[1]:
                _metric_card("Prob of 10%+ Gain", _fmt_pct(mc["prob_10pct_gain_pct"]), color="#34D399")
            with mc2[2]:
                _metric_card("Avg Max Drawdown", _fmt_pct(mc["avg_max_drawdown_pct"]))

            # Path chart
            if mc.get("sample_paths"):
                fig_mc = go.Figure()
                days = list(range(mc["horizon_days"] + 1))
                for path in mc["sample_paths"][:30]:
                    path_full = [portfolio_value] + path
                    fig_mc.add_trace(go.Scatter(
                        x=days, y=path_full,
                        mode="lines", line=dict(width=0.5, color=tier_cfg["color"]),
                        opacity=0.3, showlegend=False,
                    ))
                # Add percentile bands
                for pct, label, color in [
                    (mc["percentile_5"], "5th %ile", "#EF4444"),
                    (mc["percentile_50"], "Median", "#FBBF24"),
                    (mc["percentile_95"], "95th %ile", "#34D399"),
                ]:
                    fig_mc.add_hline(y=pct, line_dash="dash", line_color=color,
                                     annotation_text=f"{label}: {_fmt_usd(pct)}", line_width=1.5)
                fig_mc.add_hline(y=portfolio_value, line_color="#6B7280", line_dash="dot",
                                 annotation_text="Initial")
                fig_mc.update_layout(
                    title=f"1-Year Monte Carlo Simulation — {mc['n_simulations']:,} scenarios",
                    paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
                    font_color="#E2E8F0",
                    xaxis=dict(title="Days", gridcolor="#1F2937"),
                    yaxis=dict(title="Portfolio Value ($)", gridcolor="#1F2937"),
                    margin=dict(l=60, r=20, t=40, b=40),
                    height=400,
                )
                st.plotly_chart(fig_mc, use_container_width=True)

    # ── Duration / Interest Rate Risk ────────────────────────────────────────
    if holdings:
        try:
            from portfolio import calculate_portfolio_duration, calculate_portfolio_liquidity
            from data_feeds import fetch_treasury_yield_curve, get_private_credit_warnings

            st.markdown('<div class="section-header">Interest Rate Risk</div>',
                        unsafe_allow_html=True)
            dur = calculate_portfolio_duration(holdings, portfolio_value)
            if dur:
                d1, d2, d3, d4 = st.columns(4)
                with d1:
                    _metric_card("Avg Duration",
                                 f"{dur['weighted_avg_duration']:.2f} yrs",
                                 dur["rate_exposure_label"],
                                 tooltip="Weighted average duration across all holdings — how many years to recover your investment if yields shift. Lower = less interest rate risk")
                with d2:
                    _metric_card("DV01 (per $1M)",
                                 f"${dur['dv01_per_million']:,.0f}",
                                 "$ loss per 1bp rate rise",
                                 tooltip="Dollar Value of 1 Basis Point: how many dollars your $1M position loses if interest rates rise by 0.01%. Multiply by your portfolio size to get full exposure")
                with d3:
                    zero_pct = dur.get("zero_duration_pct", 0)
                    _metric_card("Zero-Duration Assets",
                                 f"{zero_pct:.1f}%",
                                 "Commodities / Equity (no rate risk)",
                                 tooltip="Percentage of your portfolio in assets with no interest rate sensitivity (gold, commodities, equities) — these act as a natural rate-risk hedge")
                with d4:
                    curve = fetch_treasury_yield_curve()
                    rf    = curve.get("yields", {}).get("3m", 4.32)
                    _metric_card("Live Risk-Free Rate",
                                 f"{rf:.2f}%",
                                 f"3m T-bill — source: {curve.get('source', 'N/A')}",
                                 tooltip="Current 3-month US Treasury bill yield — the baseline risk-free rate used to calculate excess return (Sharpe/Sortino ratios) for your portfolio")

                # Rate scenario table
                scen_df = pd.DataFrame(dur["scenarios"])
                scen_df["Impact"] = scen_df["pnl_usd"].apply(
                    lambda v: f"{'▲' if v > 0 else '▼' if v < 0 else '—'} {_fmt_usd(abs(v))}"
                )
                scen_df["P&L %"] = scen_df["pnl_pct"].apply(
                    lambda v: f"{'+' if v > 0 else ''}{v:.3f}%"
                )
                st.caption("Parallel yield curve shift scenarios (estimated price impact)")
                st.dataframe(
                    scen_df[["label", "Impact", "P&L %"]].rename(
                        columns={"label": "Rate Shift"}
                    ).set_index("Rate Shift"),
                    use_container_width=True,
                    height=280,
                )

                # Duration breakdown
                with st.expander("Duration by Holding", expanded=False):
                    hdur_df = pd.DataFrame(dur["holdings_duration"])
                    if not hdur_df.empty:
                        st.dataframe(
                            hdur_df[["id", "category", "weight_pct",
                                     "duration_years", "contribution_years"]].rename(columns={
                                "id": "Asset", "category": "Category",
                                "weight_pct": "Weight %",
                                "duration_years": "Duration (yrs)",
                                "contribution_years": "Contribution (yrs)",
                            }).style.format({"Weight %": "{:.1f}", "Duration (yrs)": "{:.2f}",
                                             "Contribution (yrs)": "{:.4f}"}),
                            use_container_width=True,
                        )
        except Exception as e:
            logger.warning("[UI] Duration section failed: %s", e)

    # ── Liquidity Profile ────────────────────────────────────────────────────
    if holdings:
        try:
            from portfolio import calculate_portfolio_liquidity
            st.markdown('<div class="section-header">Liquidity Profile</div>',
                        unsafe_allow_html=True)
            liq = calculate_portfolio_liquidity(holdings, portfolio_value)
            if liq:
                l1, l2, l3, l4 = st.columns(4)
                with l1:
                    _metric_card("Liquidity Score",
                                 f"{liq['portfolio_liquidity_score']:.0f}/100",
                                 liq["liquidity_label"],
                                 tooltip="Composite liquidity score (0–100) based on redemption speed, secondary market depth, and lock-up periods. 80+ = highly liquid, below 40 = illiquid")
                with l2:
                    _metric_card("Liquid (<3 days)",
                                 f"{liq['liquid_pct']:.1f}%",
                                 f"{_fmt_usd(portfolio_value * liq['liquid_pct'] / 100)}",
                                 tooltip="Percentage of your portfolio that can be fully exited within 3 business days — DEX liquidity, T+1 redemptions, and money market funds")
                with l3:
                    _metric_card("30-Day Exit",
                                 _fmt_usd(liq["30d_exit_usd"]),
                                 f"{(liq['liquid_pct'] + liq['semi_liquid_pct']):.1f}% of portfolio",
                                 tooltip="Total dollar value you could exit within 30 days — includes liquid assets plus weekly/monthly redemption windows")
                with l4:
                    _metric_card("Illiquid (>30 days)",
                                 f"{liq['illiquid_pct']:.1f}%",
                                 f"{_fmt_usd(portfolio_value * liq['illiquid_pct'] / 100)}",
                                 tooltip="Percentage of your portfolio locked up for more than 30 days — private equity, some private credit, and illiquid real estate tokens")

                # Liquidity donut
                liq_labels = ["Liquid (<3d)", "Semi-Liquid (3-30d)", "Illiquid (>30d)"]
                liq_vals   = [liq["liquid_pct"], liq["semi_liquid_pct"], liq["illiquid_pct"]]
                fig_liq = go.Figure(go.Pie(
                    labels=liq_labels, values=liq_vals,
                    hole=0.55,
                    marker_colors=["#34D399", "#FBBF24", "#EF4444"],
                ))
                fig_liq.update_layout(
                    paper_bgcolor="#111827", font_color="#E2E8F0",
                    showlegend=True, height=250,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                st.plotly_chart(fig_liq, use_container_width=True)
        except Exception as e:
            logger.warning("[UI] Liquidity section failed: %s", e)

    # ── Private Credit Early Warnings ────────────────────────────────────────
    try:
        from data_feeds import get_private_credit_warnings
        pc_warnings = get_private_credit_warnings()
        if pc_warnings:
            st.markdown('<div class="section-header">⚠️ Private Credit Early Warnings</div>',
                        unsafe_allow_html=True)
            sev_colors = {"CRITICAL": "#EF4444", "HIGH": "#F97316",
                          "MEDIUM": "#FBBF24", "LOW": "#34D399"}
            for w in pc_warnings[:8]:
                color = sev_colors.get(w["severity"], "#6B7280")
                st.markdown(
                    f'<div style="border-left:3px solid {color};padding:8px 12px;'
                    f'margin:4px 0;background:#1F2937;border-radius:4px;">'
                    f'<span style="color:{color};font-weight:bold;">[{w["severity"]}] '
                    f'{w["protocol"]}</span> — {w["message"]}</div>',
                    unsafe_allow_html=True,
                )
    except Exception as e:
        logger.warning("[UI] Credit warnings failed: %s", e)

    # ── PDF Export ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Export Report</div>', unsafe_allow_html=True)
    if _pdf._REPORTLAB:
        # Build stress scenarios for PDF (crisis + moderate)
        from portfolio import stress_test_correlations as _stc
        _stress_for_pdf = {}
        if portfolio.get("holdings"):
            try:
                _stress_for_pdf["crisis"]   = _stc(portfolio, scenario="crisis")
                _stress_for_pdf["moderate"] = _stc(portfolio, scenario="moderate")
            except Exception:
                pass
        pdf_bytes = _pdf.generate_portfolio_pdf(
            portfolio,
            tier_cfg.get("name", f"Tier {selected_tier}"),
            macro_data=market,
            stress_results=_stress_for_pdf if _stress_for_pdf else None,
        )
        st.download_button(
            label="📄 Download Portfolio PDF",
            data=pdf_bytes,
            file_name=f"rwa_portfolio_tier{selected_tier}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key="btn_portfolio_pdf",
            help="Download a formatted PDF report — includes metrics, holdings, macro intelligence, and risk scenarios.",
        )
    else:
        st.caption("PDF export requires reportlab — `pip install reportlab`")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: ASSET UNIVERSE
# ══════════════════════════════════════════════════════════════════════════════

with tab_universe:
    st.markdown('<div class="section-header">Complete RWA Asset Universe</div>',
                unsafe_allow_html=True)

    # Filters
    _fsearch_col, f1, f2, f3, f4 = st.columns([2, 2, 1, 1, 2])
    with _fsearch_col:
        search_query = st.text_input("Search", placeholder="e.g. ONDO, treasury, real estate…",
                                     key="filter_search",
                                     help="Filter by asset name, ticker, or issuer (case-insensitive)")
    with f1:
        categories = ["All"] + sorted(assets_df["category"].dropna().unique().tolist()) \
                     if not assets_df.empty else ["All"]
        sel_cat = st.selectbox("Category", categories, key="filter_cat",
                               help="Filter by asset class (Government Bonds, Private Credit, Real Estate, Commodities, etc.)")
    with f2:
        risk_filter = st.slider("Max Risk", 1, 10, 10, key="filter_risk",
                                help="Show only assets with a risk score at or below this value. 1 = safest, 10 = highest risk")
    with f3:
        min_yield = st.number_input("Min Yield %", 0.0, 50.0, 0.0, 0.5, key="filter_yield",
                                    help="Show only assets with a gross or expected yield at or above this percentage per year")
    with f4:
        sort_by = st.selectbox("Sort By", ["composite_score", "current_yield_pct",
                                            "net_apy_pct", "liq_score_comp",
                                            "tvl_usd", "risk_score", "liquidity_score"],
                                key="filter_sort",
                                help="Rank assets by this metric. Composite Score = weighted blend of yield, risk, liquidity, and regulatory quality. Net APY = yield after management fees")

    filtered_df = assets_df.copy() if not assets_df.empty else pd.DataFrame()
    if not filtered_df.empty:
        # Text search across name, ticker/id, and issuer columns
        if search_query and search_query.strip():
            _sq = search_query.strip().lower()
            _empty_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
            _name_mask = filtered_df["name"].fillna("").str.lower().str.contains(_sq, regex=False) \
                         if "name" in filtered_df.columns else _empty_mask
            _id_mask   = filtered_df["id"].fillna("").str.lower().str.contains(_sq, regex=False) \
                         if "id" in filtered_df.columns else _empty_mask
            _iss_mask  = filtered_df["issuer"].fillna("").str.lower().str.contains(_sq, regex=False) \
                         if "issuer" in filtered_df.columns else _empty_mask
            filtered_df = filtered_df[_name_mask | _id_mask | _iss_mask]
        if sel_cat != "All":
            filtered_df = filtered_df[filtered_df["category"] == sel_cat]
        filtered_df = filtered_df[filtered_df["risk_score"].fillna(10) <= risk_filter]
        filtered_df = filtered_df[
            (filtered_df["current_yield_pct"].fillna(0) >= min_yield) |
            (filtered_df["expected_yield_pct"].fillna(0) >= min_yield)
        ]
        if sort_by in filtered_df.columns:
            filtered_df = filtered_df.sort_values(sort_by, ascending=False)

    st.caption(f"Showing {len(filtered_df)} of {len(assets_df)} assets")

    if not filtered_df.empty:
        # Category breakdown
        cat_counts = filtered_df["category"].value_counts()
        fig_cats = px.bar(
            x=cat_counts.index,
            y=cat_counts.values,
            color=cat_counts.index,
            color_discrete_map=CATEGORY_COLORS,
            labels={"x": "Category", "y": "Count"},
            height=200,
        )
        fig_cats.update_layout(
            paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
            font_color="#E2E8F0", showlegend=False,
            margin=dict(l=40, r=20, t=10, b=40),
            xaxis=dict(gridcolor="#1F2937"),
            yaxis=dict(gridcolor="#1F2937"),
        )
        st.plotly_chart(fig_cats, use_container_width=True)

        # Enrich with Net APY, composite liquidity, exit velocity, trust score
        try:
            from data_feeds import normalize_yield_to_net_apy
            from portfolio import calculate_asset_liquidity_score
            from config import get_asset_fee_bps, get_exit_velocity_score, get_asset_trust_score
            def _net_apy(row):
                gross = row.get("current_yield_pct") or row.get("expected_yield_pct") or 0
                fee   = get_asset_fee_bps(row.get("id", ""), row.get("category", ""))
                return normalize_yield_to_net_apy(float(gross), fee)
            def _liq_score(row):
                return calculate_asset_liquidity_score(
                    row.get("id", ""), row.get("category", ""),
                    int(row.get("liquidity_score", 5) or 5)
                )
            def _exit_score(row):
                return get_exit_velocity_score(row.get("id", ""), row.get("category", ""))["score"]
            def _exit_label(row):
                return get_exit_velocity_score(row.get("id", ""), row.get("category", ""))["label"]
            def _trust_score(row):
                return get_asset_trust_score(row.get("id", ""), row.get("category", ""))["trust_score"]
            filtered_df = filtered_df.copy()
            filtered_df["net_apy_pct"]      = filtered_df.apply(_net_apy, axis=1)
            filtered_df["liq_score_comp"]   = filtered_df.apply(_liq_score, axis=1)
            filtered_df["exit_velocity"]    = filtered_df.apply(_exit_score, axis=1)
            filtered_df["exit_label"]       = filtered_df.apply(_exit_label, axis=1)
            filtered_df["trust_score"]      = filtered_df.apply(_trust_score, axis=1)
        except Exception:
            filtered_df["net_apy_pct"]    = filtered_df.get("current_yield_pct", 0)
            filtered_df["liq_score_comp"] = filtered_df.get("liquidity_score", 5)
            filtered_df["exit_velocity"]  = 50.0
            filtered_df["exit_label"]     = "MODERATE"
            filtered_df["trust_score"]    = 5.0

        # Asset table
        show_cols = {
            "id": "ID", "name": "Name", "category": "Category",
            "chain": "Chain", "protocol": "Protocol",
            "current_yield_pct": "Gross Yield %",
            "net_apy_pct": "Net APY %",
            "tvl_usd": "TVL",
            "risk_score": "Risk",
            "liq_score_comp": "Liq Score",
            "exit_velocity": "Exit Score",
            "exit_label": "Exit Speed",
            "trust_score": "Trust /10",
            "regulatory_score": "Regulatory",
            "composite_score": "Score",
            "min_investment_usd": "Min Investment",
        }
        table_df = filtered_df[[c for c in show_cols if c in filtered_df.columns]].copy()
        table_df.columns = [show_cols[c] for c in show_cols if c in filtered_df.columns]

        def _fmt_tvl(v):
            try: return _fmt_usd(float(v))
            except Exception: return "—"
        def _fmt_min_inv(v):
            try:
                v = float(v)
                return "Public" if v == 0 else f"${v:,.0f}"
            except Exception: return "—"

        fmt_map = {"Gross Yield %": "{:.2f}%", "Net APY %": "{:.2f}%",
                   "Score": "{:.1f}", "Liq Score": "{:.0f}",
                   "Exit Score": "{:.0f}", "Trust /10": "{:.1f}"}
        for col in ["TVL", "Min Investment"]:
            if col in table_df.columns:
                fn = _fmt_tvl if col == "TVL" else _fmt_min_inv
                table_df[col] = table_df[col].apply(fn)

        st.dataframe(
            table_df.style
                .format({k: v for k, v in fmt_map.items() if k in table_df.columns})
                .set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
            use_container_width=True,
            height=min(600, 55 + 35 * len(table_df)),
        )

        # ── Exit Velocity Legend ──────────────────────────────────────────────
        with st.expander("📖 Exit Score & Trust Score Guide", expanded=False):
            st.markdown("""
**Exit Velocity Score (0–100)** — How quickly you can fully exit this position:
- **80–100 INSTANT**: Same-day redemption or DEX liquid (USDY, PAXG, Pendle PTs)
- **60–79 FAST**: T+1 redemption + some secondary market (BUIDL, OUSG, BENJI)
- **40–59 MODERATE**: Weekly redemption window (Clearpool, Huma, Lofty)
- **20–39 SLOW**: Monthly lock-up period (Maple, TrueFi, Tangible)
- **0–19 ILLIQUID**: Quarterly+ lock-up or no exit mechanism (Goldfinch, Propy)

**Trust Score (0–10)** — Issuer transparency and proof-of-reserve quality:
- **7–10**: Big4 audit + Chainlink PoR + daily NAV + CUSIP/ISIN (BUIDL, BENJI)
- **5–6**: Mid-tier audit + on-chain reserves or manual attestation (USDY, PAXG)
- **3–4**: On-chain only, no traditional audit (Maple, Centrifuge, Goldfinch)
- **0–2**: No public audit, no reserves proof, no CUSIP (STBT, REALT)
            """)



# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: ARBITRAGE
# ══════════════════════════════════════════════════════════════════════════════

with tab_arb:
    arb_df, arb_summary = _load_arb()

    # Summary KPIs
    a1, a2, a3, a4, a5 = st.columns(5)
    with a1:
        _metric_card("Total Opportunities", str(arb_summary.get("total", 0)),
                     color="#00D4FF",
                     tooltip="Total active arbitrage signals detected across all 8 scanner types: yield spread, price vs NAV, cross-chain, stablecoin yield, DeFi pool, carry trade, tokenized stocks, and institutional credit spread")
    with a2:
        _metric_card("Strong Arb", str(arb_summary.get("strong", 0)),
                     color="#34D399",
                     tooltip=f"Opportunities with net spread above {ARB_STRONG_THRESHOLD_PCT}% after estimated transaction costs — high-conviction signals worth investigating")
    with a3:
        _metric_card("Extreme Arb", str(arb_summary.get("extreme", 0)),
                     color="#EF4444",
                     tooltip="Highest-conviction signals with very large spreads — may indicate significant mispricing, low liquidity, or a time-sensitive opportunity")
    with a4:
        _metric_card("Best Spread", _fmt_pct(arb_summary.get("best_spread_pct", 0)),
                     color=tier_cfg["color"],
                     tooltip="The largest net spread (after estimated costs) found across all current opportunities")
    with a5:
        _metric_card("Avg Spread", _fmt_pct(arb_summary.get("avg_spread_pct", 0)),
                     tooltip="Average net spread across all active arbitrage opportunities — a measure of overall market efficiency")

    # By type breakdown
    by_type = arb_summary.get("by_type", {})
    if by_type:
        type_cols = st.columns(len(by_type))
        for i, (t, cnt) in enumerate(by_type.items()):
            with type_cols[i]:
                st.markdown(f"""
                <div class="metric-card" style="text-align:center">
                    <div class="metric-label">{t.replace('_', ' ').title()}</div>
                    <div class="metric-value" style="font-size:20px">{cnt}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">Arbitrage Opportunities</div>',
                unsafe_allow_html=True)

    if st.button("🔄 Rescan Arbitrage", key="btn_arb_rescan",
                 help="Runs all 8 arbitrage scanners: yield spread, price vs NAV, cross-chain, stablecoin yield, DeFi pool, carry trade, tokenized stocks, and institutional credit spread"):
        st.cache_data.clear()
        st.rerun()

    if not arb_df.empty:
        # Filter by type
        arb_types = ["All"] + sorted(arb_df["type"].dropna().unique().tolist())
        sel_arb_type = st.selectbox("Filter by Type", arb_types, key="arb_type_filter")
        if sel_arb_type != "All":
            arb_df = arb_df[arb_df["type"] == sel_arb_type]

        # Display opportunities as cards
        for _, row in arb_df.head(20).iterrows():
            signal = row.get("signal") or "ARB"
            net_spread = row.get("net_spread_pct") or 0
            sig_class = (
                "signal-extreme" if signal == "EXTREME_ARB" else
                "signal-strong"  if signal == "STRONG_ARB"  else
                "signal-arb"
            )
            sig_label = signal.replace("_", " ")

            with st.expander(
                f"[{(row.get('type') or '').upper()}] {row.get('asset_a_name') or row.get('asset_a_id','?')} → "
                f"Net Spread: {net_spread:.2f}%",
                expanded=(net_spread >= ARB_STRONG_THRESHOLD_PCT)
            ):
                st.markdown(f'<span class="{sig_class}">{sig_label}</span>', unsafe_allow_html=True)
                spread_color = "#34D399" if net_spread > 0 else "#EF4444"
                st.markdown(f"""
                <div style="display:flex;gap:12px;flex-wrap:wrap;margin:10px 0">
                    <div style="background:#1F2937;padding:10px 20px;border-radius:7px;min-width:160px">
                        <div style="font-size:18px;color:#9CA3AF">Net Spread</div>
                        <div style="font-size:26px;font-weight:700;color:{spread_color}">{net_spread:.3f}%</div>
                    </div>
                    <div style="background:#1F2937;padding:10px 20px;border-radius:7px;min-width:160px">
                        <div style="font-size:18px;color:#9CA3AF">Yield A</div>
                        <div style="font-size:26px;font-weight:700">{row.get('yield_a_pct', 0):.3f}%</div>
                    </div>
                    <div style="background:#1F2937;padding:10px 20px;border-radius:7px;min-width:160px">
                        <div style="font-size:18px;color:#9CA3AF">Yield B</div>
                        <div style="font-size:26px;font-weight:700">{row.get('yield_b_pct', 0):.3f}%</div>
                    </div>
                    <div style="background:#1F2937;padding:10px 20px;border-radius:7px;min-width:160px">
                        <div style="font-size:18px;color:#9CA3AF">Gross Spread</div>
                        <div style="font-size:26px;font-weight:700">{row.get('spread_pct', 0):.3f}%</div>
                    </div>
                    <div style="background:#1F2937;padding:10px 20px;border-radius:7px;min-width:160px">
                        <div style="font-size:18px;color:#9CA3AF">Est. APY</div>
                        <div style="font-size:26px;font-weight:700;color:{spread_color}">{row.get('estimated_apy', 0):.2f}%</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if row.get("action"):
                    st.markdown(
                        f'<div style="background:#0D1F2D;border-left:3px solid #00D4FF;padding:10px 18px;'
                        f'font-size:20px;border-radius:0 4px 4px 0;margin:6px 0">'
                        f'<span style="color:#00D4FF;font-weight:700">Action:</span> {row["action"]}</div>',
                        unsafe_allow_html=True
                    )
                if row.get("notes"):
                    st.markdown(f'<div style="font-size:18px;color:#6B7280;margin-top:4px">{row["notes"]}</div>', unsafe_allow_html=True)
    else:
        st.info("No arbitrage opportunities found. Click Rescan to update.")

    # Spread chart
    if not arb_df.empty and len(arb_df) > 3:
        fig_arb = px.bar(
            arb_df.head(15),
            x="asset_a_id",
            y="net_spread_pct",
            color="type",
            color_discrete_sequence=px.colors.qualitative.Set3,
            labels={"net_spread_pct": "Net Spread (%)", "asset_a_id": "Opportunity"},
            title="Top Arbitrage Opportunities by Net Spread",
            height=350,
        )
        fig_arb.update_layout(
            paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
            font_color="#E2E8F0", xaxis_tickangle=-35,
            margin=dict(l=40, r=20, t=40, b=80),
        )
        st.plotly_chart(fig_arb, use_container_width=True)

    # ── XRPL DEX Arbitrage Scanner (Item 15) ─────────────────────────────────
    st.markdown('<div class="section-header">XRPL DEX Arbitrage Scanner</div>',
                unsafe_allow_html=True)

    @st.cache_data(ttl=120, show_spinner=False)
    def _load_xrpl_dex_arb():
        return _df.fetch_xrpl_dex_arb()

    if st.button("⟳ Scan XRPL DEX", key="btn_xrpl_dex_arb"):
        _load_xrpl_dex_arb.clear()

    with st.spinner("Scanning XRPL DEX for arbitrage…"):
        dex_arb = _load_xrpl_dex_arb()

    xrpl_opps = dex_arb.get("opportunities", [])
    if xrpl_opps:
        xa1, xa2, xa3 = st.columns(3)
        with xa1:
            _metric_card("XRPL DEX Opps", str(dex_arb.get("count", 0)), color="#A78BFA")
        with xa2:
            best_net = max((o["net_spread_pct"] for o in xrpl_opps), default=0)
            _metric_card("Best Net Spread", _fmt_pct(best_net), color="#34D399")
        with xa3:
            best_apy = max((o.get("estimated_apy", 0) for o in xrpl_opps), default=0)
            _metric_card("Best Est. APY", _fmt_pct(best_apy), color=tier_cfg["color"])

        for opp in xrpl_opps:
            net = opp.get("net_spread_pct", 0)
            with st.expander(
                f"[{opp.get('type', 'UNK').upper()}] {opp.get('description', '—')} — Net: {net:.3f}%",
                expanded=(net >= 0.1),
            ):
                oc1, oc2, oc3, oc4 = st.columns(4)
                with oc1:
                    st.metric("Gross Spread", _fmt_pct(opp.get("gross_spread_pct", 0)))
                with oc2:
                    st.metric("Net Spread", _fmt_pct(net))
                with oc3:
                    st.metric("Est. APY", _fmt_pct(opp.get("estimated_apy", 0)))
                with oc4:
                    st.metric("Direction", opp.get("direction", "—"))
                if opp.get("action"):
                    st.markdown(
                        f'<div style="background:#0D1F2D;border-left:3px solid #A78BFA;'
                        f'padding:10px 18px;border-radius:0 4px 4px 0;margin:6px 0">'
                        f'<span style="color:#A78BFA;font-weight:700">Action:</span> '
                        f'{opp["action"]}</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.info("No XRPL DEX arbitrage opportunities detected. Try refreshing or check xrpl-py installation.")

    # ── PDF Export ────────────────────────────────────────────────────────────
    if _pdf._REPORTLAB and not arb_df.empty:
        pdf_arb_bytes = _pdf.generate_arb_pdf(arb_df.to_dict("records"))
        st.download_button(
            label="📄 Download Arbitrage PDF",
            data=pdf_arb_bytes,
            file_name=f"rwa_arbitrage_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key="btn_arb_pdf",
            help="Download a formatted PDF report of all current arbitrage opportunities.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: CARRY TRADE OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

with tab_carry:
    st.markdown('<div class="section-header">Carry Trade Optimizer</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#9CA3AF;font-size:13px;margin-bottom:16px'>"
        "Borrow stablecoins cheaply from DeFi lending protocols and invest in higher-yielding RWA assets. "
        "Net spread = RWA yield − borrow rate − estimated gas/ops cost (0.30%)."
        "</p>",
        unsafe_allow_html=True,
    )

    try:
        from data_feeds import fetch_lending_borrow_rates, get_normalized_universe
        from config import get_exit_velocity_score

        borrow_rates = fetch_lending_borrow_rates()
        rwa_universe = get_normalized_universe()

        # ── Borrow rate summary ───────────────────────────────────────────────
        st.markdown('<div class="section-header">Available Borrow Sources</div>', unsafe_allow_html=True)
        if borrow_rates:
            b_cols = st.columns(min(len(borrow_rates), 4))
            for i, br in enumerate(borrow_rates[:4]):
                with b_cols[i]:
                    _metric_card(
                        f"{br['protocol']} ({br['chain']})",
                        f"{br['borrow_apy']:.2f}%",
                        color="#EF4444",
                    )

        # ── Build carry trade opportunity table ───────────────────────────────
        OPS_COST = 0.30   # gas + execution overhead estimate
        MIN_SPREAD = 0.0  # show all (including negative for awareness)

        best_borrow = min(borrow_rates, key=lambda x: x["borrow_apy"]) if borrow_rates else {"protocol": "Morpho", "borrow_apy": 4.80, "symbol": "USDC", "chain": "Base"}
        best_borrow_apy = best_borrow["borrow_apy"]

        # Build opportunities: top RWA assets × all borrow sources
        opportunities = []
        for asset in rwa_universe:
            rwa_yield = float(asset.get("net_apy_pct") or asset.get("expected_yield_pct") or 0)
            if rwa_yield <= 0:
                continue
            asset_id  = asset.get("id", "")
            category  = asset.get("category", "")
            ev        = get_exit_velocity_score(asset_id, category)

            for br in borrow_rates:
                gross_spread = rwa_yield - br["borrow_apy"]
                net_spread   = gross_spread - OPS_COST
                opportunities.append({
                    "RWA Asset":     asset_id,
                    "Category":      category,
                    "RWA Yield %":   rwa_yield,
                    "Borrow From":   br["protocol"],
                    "Borrow Chain":  br["chain"],
                    "Borrow APY %":  br["borrow_apy"],
                    "Gross Spread %": round(gross_spread, 2),
                    "Net Spread %":  round(net_spread, 2),
                    "Exit Speed":    ev["label"],
                    "Exit Score":    ev["score"],
                    "Risk":          "LOW" if category in ("Government Bonds",) else
                                     "MEDIUM" if category in ("Commodities", "Tokenized Equities") else "HIGH",
                })

        if opportunities:
            carry_df = pd.DataFrame(opportunities)
            carry_df = carry_df.sort_values("Net Spread %", ascending=False).reset_index(drop=True)

            # ── Top opportunities KPI ─────────────────────────────────────────
            st.markdown('<div class="section-header">Best Carry Trade Opportunities</div>', unsafe_allow_html=True)
            top5 = carry_df[carry_df["Net Spread %"] > 0].head(5)
            if not top5.empty:
                kpi_cols = st.columns(min(len(top5), 5))
                for i, (_, row) in enumerate(top5.iterrows()):
                    with kpi_cols[i]:
                        _metric_card(
                            f"{row['RWA Asset']} vs {row['Borrow From'][:10]}",
                            f"+{row['Net Spread %']:.2f}%",
                            color="#34D399",
                        )

            # ── Carry trade bar chart ─────────────────────────────────────────
            top15 = carry_df[carry_df["Borrow From"] == best_borrow["protocol"]].head(15)
            if not top15.empty:
                fig_carry = go.Figure()
                colors = ["#34D399" if v > 0 else "#EF4444" for v in top15["Net Spread %"]]
                fig_carry.add_trace(go.Bar(
                    x=top15["RWA Asset"],
                    y=top15["Net Spread %"],
                    marker_color=colors,
                    text=[f"{v:+.2f}%" for v in top15["Net Spread %"]],
                    textposition="outside",
                    name="Net Spread",
                ))
                fig_carry.add_hline(y=0, line_color="#6B7280", line_dash="dash")
                fig_carry.update_layout(
                    title=f"Net Carry Spread vs {best_borrow['protocol']} ({best_borrow_apy:.2f}% borrow)",
                    paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
                    font_color="#E2E8F0",
                    xaxis=dict(tickangle=-35, gridcolor="#1F2937"),
                    yaxis=dict(title="Net Spread %", gridcolor="#1F2937"),
                    margin=dict(l=50, r=20, t=50, b=100),
                    height=380,
                )
                st.plotly_chart(fig_carry, use_container_width=True)

            # ── Full opportunity table ────────────────────────────────────────
            st.markdown('<div class="section-header">All Carry Trade Pairs</div>', unsafe_allow_html=True)
            ct1, ct2, ct3 = st.columns(3)
            with ct1:
                min_net = st.number_input("Min Net Spread %", -5.0, 20.0, 0.0, 0.25, key="ct_min_spread",
                                          help="Filter to pairs where net spread (RWA yield − borrow APY − 0.30% ops cost) exceeds this amount. Set to 0 to see only profitable trades")
            with ct2:
                ct_borrow = st.selectbox(
                    "Borrow Source",
                    ["All"] + sorted(carry_df["Borrow From"].unique().tolist()),
                    key="ct_borrow_filter",
                    help="Filter by the DeFi lending protocol you would borrow stablecoins from. Different protocols offer different rates depending on market conditions"
                )
            with ct3:
                ct_risk = st.selectbox("Risk Level", ["All", "LOW", "MEDIUM", "HIGH"], key="ct_risk",
                                       help="LOW = Government Bonds only (T-bills, treasuries); MEDIUM = Commodities and Tokenized Equities; HIGH = Private Credit, Real Estate, and other illiquid assets")

            show_carry = carry_df[carry_df["Net Spread %"] >= min_net]
            if ct_borrow != "All":
                show_carry = show_carry[show_carry["Borrow From"] == ct_borrow]
            if ct_risk != "All":
                show_carry = show_carry[show_carry["Risk"] == ct_risk]

            def _spread_color(val):
                try:
                    v = float(val)
                    return "color: #34D399" if v > 0.5 else ("color: #FBBF24" if v > 0 else "color: #EF4444")
                except Exception:
                    return ""

            st.dataframe(
                show_carry[["RWA Asset", "Category", "RWA Yield %", "Borrow From", "Borrow Chain",
                             "Borrow APY %", "Gross Spread %", "Net Spread %", "Exit Speed", "Risk"]]
                .head(50)
                .style
                .format({"RWA Yield %": "{:.2f}%", "Borrow APY %": "{:.2f}%",
                         "Gross Spread %": "{:+.2f}%", "Net Spread %": "{:+.2f}%"})
                .map(_spread_color, subset=["Net Spread %"])
                .set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
                use_container_width=True,
                height=min(500, 55 + 35 * len(show_carry.head(50))),
            )

            # ── Carry trade calculator ────────────────────────────────────────
            st.markdown('<div class="section-header">Carry Trade Calculator</div>', unsafe_allow_html=True)
            calc1, calc2, calc3 = st.columns(3)
            with calc1:
                calc_principal = st.number_input("Principal (USD)", 10_000, 10_000_000, 100_000, 10_000, key="ct_principal",
                                                 help="The total capital you would deploy — borrow this amount from DeFi and invest the full amount in the RWA asset")
            with calc2:
                calc_rwa_yield = st.number_input("RWA Net APY %", 0.0, 30.0, 5.5, 0.1, key="ct_rwa_yield",
                                                 help="The net yield on the RWA asset after management fees. Use the Net APY % column from the Asset Universe table for the most accurate figure")
            with calc3:
                calc_borrow   = st.number_input("Borrow APY %", 0.0, 15.0, best_borrow_apy, 0.1, key="ct_borrow",
                                                help="The variable borrow rate from your DeFi lending protocol. Check the Available Borrow Sources section above for live rates — these float with market conditions")

            net_annual = (calc_rwa_yield - calc_borrow - OPS_COST) / 100 * calc_principal
            net_monthly = net_annual / 12
            net_weekly  = net_annual / 52
            cx1, cx2, cx3, cx4 = st.columns(4)
            with cx1: _metric_card("Net Spread", f"{calc_rwa_yield - calc_borrow - OPS_COST:.2f}%",
                                    color="#34D399" if net_annual > 0 else "#EF4444",
                                    tooltip="RWA Net APY minus borrow APY minus 0.30% estimated gas and operational costs. This is your actual yield advantage.")
            with cx2: _metric_card("Annual P&L", _fmt_usd(net_annual),
                                    color="#34D399" if net_annual > 0 else "#EF4444",
                                    tooltip="Estimated annual profit on this carry trade at current rates. Does not account for liquidation risk or rate changes.")
            with cx3: _metric_card("Monthly P&L", _fmt_usd(net_monthly),
                                    color="#34D399" if net_monthly > 0 else "#EF4444",
                                    tooltip="Annual P&L divided by 12. Borrow rates are variable — actual monthly income will fluctuate.")
            with cx4: _metric_card("Weekly P&L",  _fmt_usd(net_weekly),
                                    color="#34D399" if net_weekly > 0 else "#EF4444",
                                    tooltip="Annual P&L divided by 52. Useful for estimating weekly cash flow from the carry position.")

            st.markdown(
                "<p style='color:#6B7280;font-size:11px;margin-top:8px'>"
                "⚠️ Carry trades involve smart contract risk, liquidation risk (if using leverage), "
                "and rate risk (borrow APY floats). Always verify current rates before executing. "
                "Net spread assumes 0.30% annual ops cost. Not financial advice."
                "</p>",
                unsafe_allow_html=True,
            )

    except Exception as e:
        st.error(f"Carry Trade Optimizer error: {e}")
        logger.warning("[UI] Carry Trade tab failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: COMPARE TIERS
# ══════════════════════════════════════════════════════════════════════════════

with tab_compare:
    st.markdown('<div class="section-header">Portfolio Tier Comparison</div>',
                unsafe_allow_html=True)

    all_ports, comp_df = _load_all_portfolios(portfolio_value)

    if not comp_df.empty:
        # Radar / comparison chart
        metrics_to_plot = ["Yield (%)", "Sharpe Ratio", "Sortino Ratio", "Holdings"]
        fig_compare = go.Figure()

        for _, row in comp_df.iterrows():
            tier_n = int(row["Tier"])
            color  = PORTFOLIO_TIERS[tier_n]["color"]
            fig_compare.add_trace(go.Bar(
                name=f"{row['Icon']} {row['Name']}",
                x=["Yield %", "Sharpe", "Sortino", "Max DD %"],
                y=[row.get("Yield (%)") or 0,
                   (row.get("Sharpe Ratio") or 0) * 5,   # scale for visibility
                   (row.get("Sortino Ratio") or 0) * 5,
                   row.get("Max Drawdown (%)") or 0],
                marker_color=color,
            ))

        fig_compare.update_layout(
            barmode="group",
            paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
            font_color="#E2E8F0",
            legend=dict(bgcolor="#111827", bordercolor="#1F2937"),
            xaxis=dict(gridcolor="#1F2937"),
            yaxis=dict(title="Value", gridcolor="#1F2937"),
            margin=dict(l=40, r=20, t=20, b=40),
            height=350,
        )
        st.plotly_chart(fig_compare, use_container_width=True)

        # Comparison table
        display_comp = comp_df[["Icon", "Name", "Yield (%)", "Annual Return ($)",
                                  "Volatility (%)", "Sharpe Ratio", "Max Drawdown (%)",
                                  "VaR 95% (%)", "Holdings"]].copy()
        display_comp["Annual Return ($)"] = display_comp["Annual Return ($)"].apply(_fmt_usd)
        st.dataframe(
            display_comp.style.format({
                "Yield (%)": "{:.2f}%",
                "Volatility (%)": "{:.2f}%",
                "Sharpe Ratio": "{:.2f}",
                "Max Drawdown (%)": "{:.2f}%",
                "VaR 95% (%)": "{:.2f}%",
            }).set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
            use_container_width=True,
        )

    # Efficient frontier
    st.markdown('<div class="section-header">Efficient Frontier</div>', unsafe_allow_html=True)
    if not assets_df.empty:
        if st.button("📐 Compute Efficient Frontier", key="btn_frontier"):
            with st.spinner("Computing efficient frontier...", show_time=True):
                from portfolio import compute_efficient_frontier
                ef = compute_efficient_frontier(assets_df.to_dict("records"))

            if ef.get("portfolios"):
                ef_df = pd.DataFrame(ef["portfolios"])
                fig_ef = px.scatter(
                    ef_df, x="vol_pct", y="return_pct",
                    color="sharpe",
                    color_continuous_scale="RdYlGn",
                    labels={"vol_pct": "Volatility (%)", "return_pct": "Expected Return (%)",
                            "sharpe": "Sharpe Ratio"},
                    title="Efficient Frontier — Randomly Sampled RWA Portfolios",
                    height=450,
                )
                # Mark tier portfolios
                for tier_id, tier_data in PORTFOLIO_TIERS.items():
                    fig_ef.add_trace(go.Scatter(
                        x=[tier_data["volatility_pct"]],
                        y=[tier_data["target_yield_pct"]],
                        mode="markers+text",
                        marker=dict(size=16, color=tier_data["color"], symbol="star"),
                        text=[tier_data["label"]],
                        textposition="top center",
                        name=tier_data["name"],
                        showlegend=True,
                    ))
                fig_ef.update_layout(
                    paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
                    font_color="#E2E8F0",
                    margin=dict(l=60, r=20, t=40, b=40),
                )
                st.plotly_chart(fig_ef, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: AI AGENT
# ══════════════════════════════════════════════════════════════════════════════

with tab_ai:
    # API Key check — session key takes priority over env; never mutate os.environ at runtime
    def _get_effective_claude_key() -> str:
        return (st.session_state.get("user_anthropic_key") or
                os.environ.get("ANTHROPIC_API_KEY", "")).strip()

    api_key_env = _get_effective_claude_key()
    if not api_key_env:
        st.warning("⚠️ ANTHROPIC_API_KEY not set. AI features require the key in your environment.")
        user_key = st.text_input("Enter API Key (session only)", type="password", key="api_key_input")
        if user_key and st.button("Apply Key", key="apply_key"):
            st.session_state["user_anthropic_key"] = user_key  # session-scoped only
            st.session_state["api_key_set"] = True
            st.success("Key applied for this session")
            st.rerun()

    st.markdown('<div class="section-header">Select AI Agent</div>', unsafe_allow_html=True)

    # Agent selector
    agent_cols = st.columns(5)
    for i, (agent_id, agent_cfg_a) in enumerate(AI_AGENTS.items()):
        with agent_cols[i]:
            selected_a = st.session_state["agent_name"] == agent_id
            if st.button(
                f"{agent_cfg_a['icon']} {agent_cfg_a['name']}",
                key=f"agent_btn_{agent_id}",
                use_container_width=True,
            ):
                st.session_state["agent_name"] = agent_id
                # Stop old agent if different
                if _agent.supervisor.status()["running"]:
                    _agent.supervisor.stop()
                st.rerun()
            tier_name = PORTFOLIO_TIERS[agent_cfg_a["risk_tier"]]["name"]
            st.caption(f"Tier {agent_cfg_a['risk_tier']}: {tier_name}")

    selected_agent = st.session_state["agent_name"]
    agent_detail   = AI_AGENTS[selected_agent]

    # Agent detail card
    st.markdown(f"""
    <div class="metric-card" style="border-color:{agent_detail['color']}">
        <div style="display:flex;align-items:center;gap:12px">
            <span style="font-size:32px">{agent_detail['icon']}</span>
            <div>
                <div style="font-size:18px;font-weight:700;color:{agent_detail['color']}">{agent_detail['name']}</div>
                <div style="font-size:13px;color:#9CA3AF;margin-top:4px">{agent_detail['description']}</div>
            </div>
        </div>
        <div style="display:flex;gap:24px;margin-top:12px">
            <span style="font-size:12px;color:#6B7280">Strategy: <b style="color:#E2E8F0">{agent_detail['strategy'].replace('_', ' ').title()}</b></span>
            <span style="font-size:12px;color:#6B7280">Max Trade: <b style="color:#E2E8F0">{agent_detail['max_trade_size_pct']}%</b></span>
            <span style="font-size:12px;color:#6B7280">Risk Tier: <b style="color:#E2E8F0">{agent_detail['risk_tier']}</b></span>
            <span style="font-size:12px;color:#6B7280">Daily Loss Limit: <b style="color:#EF4444">{agent_detail['daily_loss_limit_pct']}%</b></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Agent controls
    ac1, ac2, ac3, ac4 = st.columns(4)
    with ac1:
        dry_run = st.toggle("Dry Run Mode", value=True, key="dry_run_toggle",
                            help="When ON: agent decisions are logged but no trades execute")
    with ac2:
        interval = st.selectbox("Cycle Interval", [30, 60, 120, 300, 600],
                                index=1, key="agent_interval",
                                format_func=lambda x: f"{x}s" if x < 60 else f"{x//60}m",
                                help="How often the agent wakes up to analyze market data and make a portfolio decision. Shorter = more reactive but higher API usage. 60s is a good default.")
    with ac3:
        sup_status = _agent.supervisor.status()
        agent_is_running = sup_status.get("running", False)
        if not agent_is_running:
            if st.button(f"▶ Start {agent_detail['icon']} {agent_detail['name']}",
                         use_container_width=True, key="btn_start_agent",
                         type="primary"):
                _agent.supervisor.start(
                    agent_name=selected_agent,
                    dry_run=dry_run,
                    interval_seconds=interval,
                )
                st.session_state["agent_running"] = True
                st.success(f"Agent {selected_agent} started")
                st.rerun()
        else:
            if st.button("⏹ Stop Agent", use_container_width=True, key="btn_stop_agent",
                         type="secondary"):
                _agent.supervisor.stop()
                st.session_state["agent_running"] = False
                st.rerun()
    with ac4:
        if st.button("⚡ Run Now (1 cycle)", use_container_width=True, key="btn_one_cycle",
                     help="Execute one analysis cycle immediately — the agent reads live market data, calls Claude for a decision (HOLD/REBALANCE/DEPLOY/REDUCE), and logs the result. Great for testing without starting the full scheduler."):
            with st.spinner(f"Running {agent_detail['name']} cycle...", show_time=True):
                result = _agent.run_agent_cycle(selected_agent, dry_run=dry_run, cycle_number=0,
                                               api_key=_get_effective_claude_key())
            st.success(f"Cycle complete: {result.get('claude_decision', 'UNKNOWN')}")
            st.rerun()

    # Agent status
    if agent_is_running:
        st.markdown(f"""
        <div style="background:#0A1A0A;border:1px solid #34D399;border-radius:8px;padding:12px;margin:8px 0">
            <span class="status-live"></span>
            <span style="color:#34D399;font-weight:700">{agent_detail['name']} ACTIVE</span>
            &nbsp;·&nbsp;
            <span style="color:#9CA3AF">Cycles: {sup_status.get('cycle_count', 0)}</span>
            &nbsp;·&nbsp;
            <span style="color:#9CA3AF">{'🔒 Dry Run' if sup_status.get('dry_run') else '⚡ LIVE TRADING'}</span>
            &nbsp;·&nbsp;
            <span style="color:#9CA3AF">Interval: {sup_status.get('interval_sec', 60)}s</span>
        </div>
        """, unsafe_allow_html=True)

        last_cycle = sup_status.get("last_cycle") or {}
        if last_cycle:
            decision   = last_cycle.get("decision", "—")
            confidence = last_cycle.get("confidence", 0)
            dec_color  = {"REBALANCE": "#FBBF24", "DEPLOY": "#34D399",
                          "REDUCE": "#EF4444", "HOLD": "#6B7280", "SKIP": "#6B7280"}.get(decision, "#E2E8F0")
            st.markdown(f"""
            <div class="metric-card">
                <div style="display:flex;justify-content:space-between">
                    <span style="color:#9CA3AF;font-size:12px">Last Decision</span>
                    <span style="color:{dec_color};font-weight:700;font-size:14px">{decision}</span>
                </div>
                <div style="font-size:11px;color:#6B7280;margin-top:4px">
                    Confidence: {confidence:.0f}% &nbsp;·&nbsp; {last_cycle.get('timestamp', '')[:19]}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # AI Insights
    st.markdown('<div class="section-header">AI Market Insights</div>', unsafe_allow_html=True)
    if st.button(f"🧠 Generate {agent_detail['name']} Insights", key="btn_insights"):
        with st.spinner("Analyzing RWA market with Claude claude-sonnet-4-6...", show_time=True):
            insights = _agent.get_agent_insights(selected_agent, api_key=_get_effective_claude_key())
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:12px;color:{agent_detail['color']};font-weight:700;margin-bottom:8px">
                {agent_detail['icon']} {agent_detail['name']} · Market Analysis · {insights.get('timestamp', '')[:19]} UTC
            </div>
            <div style="font-size:14px;color:#E2E8F0;white-space:pre-line;line-height:1.7">{insights.get('insights', '—')}</div>
        </div>
        """, unsafe_allow_html=True)

    # Recent agent decisions
    st.markdown('<div class="section-header">Recent Agent Decisions</div>', unsafe_allow_html=True)
    decisions_df = _db.get_recent_agent_decisions(15)
    if not decisions_df.empty:
        show_d = decisions_df[["timestamp", "agent_name", "decision", "confidence_pct",
                                "rationale", "is_dry_run"]].copy()
        show_d.columns = ["Time", "Agent", "Decision", "Confidence %", "Rationale", "Dry Run"]
        show_d["Time"] = show_d["Time"].str[:19]
        st.dataframe(
            show_d.style.set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
            use_container_width=True,
            height=300,
        )
    else:
        st.info("No agent decisions yet. Start an agent or run a manual cycle above.")

    # ── Macro Factor Allocation Bias (Group 7) ───────────────────────────────────
    st.markdown('<div class="section-header">Macro Factor Allocation Bias</div>', unsafe_allow_html=True)

    with st.expander("📊 VIX · DXY · Yield Curve · Fear & Greed → Allocation Adjustments", expanded=True):
        from data_feeds import get_macro_factor_allocation_bias

        @st.cache_data(ttl=300, show_spinner=False)
        def _load_factor_bias():
            return get_macro_factor_allocation_bias()

        if st.button("⟳ Refresh Factor Bias", key="btn_factor_bias_refresh"):
            _load_factor_bias.clear()

        with st.spinner("Computing factor allocation bias…"):
            fb = _load_factor_bias()

        if "error" in fb:
            st.warning(f"Factor bias unavailable: {fb['error']}")
        else:
            adjs  = fb.get("adjustments", {})
            facts = fb.get("factors", {})
            rat   = fb.get("rationale", {})

            # Factor input cards (factors dict is flat: vix, dxy, yield_slope, fg_value, regime)
            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                vix_val = facts.get("vix", "—")
                st.metric("VIX", f"{vix_val:.1f}" if isinstance(vix_val, (int, float)) else str(vix_val))
            with fc2:
                dxy_val = facts.get("dxy", "—")
                st.metric("DXY", f"{dxy_val:.1f}" if isinstance(dxy_val, (int, float)) else str(dxy_val))
            with fc3:
                slope_val = facts.get("yield_slope", "—")
                st.metric("Yield Slope (10y-2y)",
                          f"{slope_val:+.2f}%" if isinstance(slope_val, (int, float)) else str(slope_val))
            with fc4:
                fg_val2 = facts.get("fg_value", "—")
                regime_val = facts.get("regime", "")
                st.metric("Fear & Greed", f"{fg_val2}/100" if isinstance(fg_val2, int) else str(fg_val2),
                          delta=regime_val)

            # Allocation adjustment table
            if adjs:
                st.markdown("**Category Allocation Adjustments (pp)**")
                adj_rows = [
                    {"Category": cat, "Adjustment (pp)": f"{val:+.1f}", "Direction": "▲ Increase" if val > 0 else ("▼ Decrease" if val < 0 else "— Neutral")}
                    for cat, val in sorted(adjs.items(), key=lambda x: -abs(x[1]))
                ]
                adj_df = pd.DataFrame(adj_rows)
                st.dataframe(adj_df, use_container_width=True, hide_index=True)

            # Rationale summary (rationale is a single string)
            if rat:
                st.caption(str(rat))

    # ── XRPL Intelligence + Tier 3 Status (Upgrades 10, 11, 12) ─────────────────
    st.markdown('<div class="section-header">XRPL Intelligence</div>', unsafe_allow_html=True)

    with st.expander("🔗 XRPL · RLUSD · Soil Protocol · XLS-81", expanded=False):
        from data_feeds import fetch_xrpl_stats

        @st.cache_data(ttl=120, show_spinner=False)
        def _load_xrpl_stats():
            return fetch_xrpl_stats()

        if st.button("⟳ Refresh XRPL", key="btn_xrpl_refresh"):
            _load_xrpl_stats.clear()

        with st.spinner("Fetching XRPL data…"):
            xrpl_d = _load_xrpl_stats()

        rlusd_d = xrpl_d.get("rlusd", {})
        bid     = rlusd_d.get("best_bid_xrp")
        ask     = rlusd_d.get("best_ask_xrp")
        spread  = rlusd_d.get("spread_pct")
        ob_err  = rlusd_d.get("orderbook_error")

        xc1, xc2, xc3, xc4 = st.columns(4)
        with xc1:
            st.metric("RLUSD Circulating", f"${rlusd_d.get('circulating_bn', 1.5):.1f}B")
        with xc2:
            st.metric("Best Bid (XRP)", f"{bid:.6f}" if bid else "—")
        with xc3:
            st.metric("Best Ask (XRP)", f"{ask:.6f}" if ask else "—")
        with xc4:
            st.metric("DEX Spread", f"{spread:.4f}%" if spread else "—")

        if ob_err:
            st.caption(f"Orderbook: {ob_err}")

        xrpl_rva, xrpl_rvb = st.columns(2)
        with xrpl_rva:
            st.markdown("**📊 RLUSD/XRP Bids (top 5)**")
            bids = rlusd_d.get("bids", [])
            if bids:
                st.dataframe(pd.DataFrame(bids), use_container_width=True, hide_index=True)
            else:
                st.caption("No bids available" if not ob_err else f"Error: {ob_err}")
        with xrpl_rvb:
            st.markdown("**📊 RLUSD/XRP Asks (top 5)**")
            asks = rlusd_d.get("asks", [])
            if asks:
                st.dataframe(pd.DataFrame(asks), use_container_width=True, hide_index=True)
            else:
                st.caption("No asks available" if not ob_err else f"Error: {ob_err}")

        st.markdown("**🌱 Soil Protocol — RLUSD Yield Vaults (XRPL)**")
        vaults = xrpl_d.get("soil_vaults", [])
        if vaults:
            vault_df = pd.DataFrame(vaults)
            st.dataframe(vault_df, use_container_width=True, hide_index=True)

        xls = xrpl_d.get("xls81", {})
        tvl = xrpl_d.get("xrpl_rwa_tvl_bn", 2.3)
        st.markdown(
            f"**XLS-81 Permissioned DEX:** `{xls.get('status', '—')}` — "
            f"activated {xls.get('activated', '—')} &nbsp;·&nbsp; "
            f"**Total XRPL RWA TVL:** ${tvl:.1f}B",
            unsafe_allow_html=False,
        )

    # ── Coinbase AgentKit status (Upgrade 11) ─────────────────────────────────
    with st.expander("🤖 Coinbase AgentKit — On-Chain Execution", expanded=False):
        ak_status = _agent.get_agentkit_status()
        if ak_status["available"]:
            st.success(
                f"✅ AgentKit ready — wallet `{ak_status.get('address', '?')}` "
                f"on **{ak_status.get('network', '?')}**"
            )
            st.caption(
                "AgentKit executes approved trades on Base mainnet when Dry Run is OFF. "
                "Supports USDC transfers, Aave/Morpho/Compound, and Pyth price feeds."
            )
        else:
            st.info(
                f"AgentKit inactive — {ak_status['reason']}. "
                "Set RWA_CDP_API_KEY_ID, RWA_CDP_API_KEY_SECRET, RWA_CDP_WALLET_SECRET "
                "to enable on-chain execution."
            )

    # ── x402 micropayment rail status (Upgrade 10) ────────────────────────────
    with st.expander("⚡ x402 Micropayment Rail", expanded=False):
        try:
            import x402  # noqa: F401
            x402_available = True
        except ImportError:
            x402_available = False

        if x402_available:
            st.success(
                "✅ x402 payment protocol available — "
                "HTTP 402 data services can be accessed via USDC micropayments."
            )
            st.caption(
                f"T54 XRPL facilitator: `https://xrpl-facilitator-mainnet.t54.ai` "
                "(RLUSD/XRP settlement). Coinbase facilitator: Base + Polygon + Solana."
            )
        else:
            st.info("x402 not installed — run `pip install x402` to enable micropayment rail.")

    # Performance feedback loop
    st.markdown('<div class="section-header">AI Feedback Loop</div>', unsafe_allow_html=True)
    perf_df = _db.get_agent_performance()
    if not perf_df.empty:
        perf_df["Win Rate %"] = (
            perf_df["wins"] / perf_df["total_decisions"].replace(0, 1) * 100
        ).round(1)
        st.dataframe(
            perf_df.style.format({"avg_return_pct": "{:.2f}%", "Win Rate %": "{:.1f}%"})
                        .set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
            use_container_width=True,
        )
    else:
        st.caption("Feedback data accumulates as the agent runs over multiple cycles.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: NEWS FEED
# ══════════════════════════════════════════════════════════════════════════════

with tab_news:
    st.markdown('<div class="section-header">RWA News & Sentiment</div>', unsafe_allow_html=True)

    nb1, nb2 = st.columns([1, 1])
    with nb1:
        if st.button("🔄 Refresh News", key="btn_news_refresh"):
            from data_feeds import refresh_news
            with st.spinner("Fetching latest RWA news...", show_time=True):
                refresh_news()
            st.cache_data.clear()
            st.session_state["ai_news_brief"] = ""
            st.rerun()
    with nb2:
        if st.button("🧠 Generate AI Market Brief", key="btn_ai_brief",
                     help="Uses Claude to synthesize recent headlines into an actionable market brief"):
            from data_feeds import fetch_live_rss_news, get_ai_news_brief
            with st.spinner("Generating AI market intelligence brief...", show_time=True):
                try:
                    live = fetch_live_rss_news()
                    news_df_tmp = _load_news()
                    all_headlines = (
                        [i.get("headline", "") for i in live if i.get("headline")] +
                        (news_df_tmp["headline"].tolist() if not news_df_tmp.empty else [])
                    )
                    brief = get_ai_news_brief(all_headlines[:15])
                    st.session_state["ai_news_brief"] = brief
                    st.session_state.pop("ai_news_brief_error", None)
                except Exception as e:
                    st.session_state["ai_news_brief"] = ""
                    st.session_state["ai_news_brief_error"] = str(e)
            st.rerun()

    # Show error if brief generation failed
    if st.session_state.get("ai_news_brief_error"):
        st.error(f"AI Brief failed: {st.session_state['ai_news_brief_error']}")

    # Show AI brief if generated
    if st.session_state.get("ai_news_brief"):
        st.markdown(f"""
        <div style="background:#0D1F2D;border:1px solid #00D4FF;border-radius:8px;
                    padding:16px;margin:12px 0">
            <div style="font-size:11px;font-weight:700;color:#00D4FF;
                        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">
                🧠 AI Market Brief — Powered by Claude
            </div>
            <div style="font-size:13px;color:#E2E8F0;line-height:1.8;white-space:pre-line">
                {st.session_state["ai_news_brief"]}
            </div>
        </div>
        """, unsafe_allow_html=True)

    news_df = _load_news()

    if not news_df.empty:
        # Sentiment summary + live count
        sentiments = news_df["sentiment"].value_counts()
        live_count = int(news_df.get("is_live", pd.Series(dtype=bool)).sum()) if "is_live" in news_df.columns else 0
        n1, n2, n3, n4 = st.columns(4)
        with n1:
            _metric_card("Bullish", str(sentiments.get("BULLISH", 0)), color="#34D399")
        with n2:
            _metric_card("Neutral", str(sentiments.get("NEUTRAL", 0)), color="#6B7280")
        with n3:
            _metric_card("Bearish", str(sentiments.get("BEARISH", 0)), color="#EF4444")
        with n4:
            _metric_card("Live RSS", str(live_count), color="#00D4FF")

        st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)

        # News cards
        for _, row in news_df.iterrows():
            sentiment  = row.get("sentiment", "NEUTRAL")
            score      = row.get("sentiment_score", 0) or 0
            is_live    = bool(row.get("is_live", False))
            sent_color = {"BULLISH": "#34D399", "BEARISH": "#EF4444", "NEUTRAL": "#6B7280"}.get(sentiment, "#6B7280")
            sent_icon  = {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "●"}.get(sentiment, "●")
            ts         = str(row.get("timestamp", ""))[:16]
            live_badge = '<span style="font-size:9px;background:#00D4FF22;color:#00D4FF;padding:1px 5px;border-radius:3px;margin-left:6px">LIVE</span>' if is_live else ""
            url        = row.get("url", "") or ""
            # Only allow http/https URLs to prevent javascript: injection
            safe_url   = url if url.startswith(("http://", "https://")) else ""
            headline   = row.get("headline", "")
            headline_html = f'<a href="{safe_url}" target="_blank" style="color:#E2E8F0;text-decoration:none">{headline}</a>' if safe_url else headline

            st.markdown(f"""
            <div class="metric-card" style="padding:12px">
                <div style="display:flex;justify-content:space-between;align-items:start">
                    <div style="flex:1;margin-right:12px">
                        <div style="font-size:14px;font-weight:600;line-height:1.4">{headline_html}</div>
                        <div style="font-size:11px;color:#6B7280;margin-top:4px">
                            {row.get('source','?')} · {ts}{live_badge}
                        </div>
                    </div>
                    <div style="text-align:right;min-width:80px">
                        <div style="font-size:13px;color:{sent_color};font-weight:700">{sent_icon} {sentiment}</div>
                        <div style="font-size:11px;color:#6B7280">Score: {score:+.2f}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No news loaded yet. Click 'Refresh News' above.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 7: TRADE LOG
# ══════════════════════════════════════════════════════════════════════════════

with tab_trades:
    st.markdown('<div class="section-header">Trade Execution Log</div>',
                unsafe_allow_html=True)

    trades_df = _db.get_trade_history(100)
    if not trades_df.empty:
        # Summary
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            _metric_card("Total Trades", str(len(trades_df)))
        with t2:
            live_trades = len(trades_df[trades_df["status"] == "FILLED"])
            _metric_card("Live Filled", str(live_trades), color="#34D399")
        with t3:
            dry_trades = len(trades_df[trades_df["status"] == "DRY_RUN"])
            _metric_card("Dry Run", str(dry_trades), color="#6B7280")
        with t4:
            total_volume = trades_df["size_usd"].fillna(0).sum()
            _metric_card("Total Volume", _fmt_usd(total_volume))

        # Table
        show_cols_t = {
            "timestamp": "Time", "agent_name": "Agent", "asset_id": "Asset",
            "action": "Action", "size_usd": "Size ($)", "status": "Status",
            "protocol": "Protocol", "notes": "Notes",
        }
        t_df = trades_df[[c for c in show_cols_t if c in trades_df.columns]].copy()
        t_df.columns = [show_cols_t[c] for c in show_cols_t if c in trades_df.columns]
        if "Time" in t_df.columns:
            t_df["Time"] = t_df["Time"].str[:19]

        st.dataframe(
            t_df.style
                .format({"Size ($)": lambda x: _fmt_usd(x) if pd.notna(x) else "—"})
                .set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
            use_container_width=True,
            height=500,
        )
    else:
        st.info("No trades logged yet. Start an AI agent to begin trading.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8: REGULATORY CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

with tab_reg:
    st.markdown('<div class="section-header">Regulatory Calendar & Compliance Tracker</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#9CA3AF;font-size:13px;margin-bottom:16px'>"
        "Key upcoming regulatory milestones affecting tokenized Real World Assets globally. "
        "Dates are best estimates based on published timelines — always verify with primary sources."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Live US Treasury Yield Curve ──────────────────────────────────────────
    try:
        from data_feeds import fetch_treasury_yield_curve
        st.markdown('<div class="section-header">Live US Treasury Yield Curve</div>',
                    unsafe_allow_html=True)
        curve_data = fetch_treasury_yield_curve()
        curve_ylds = curve_data.get("yields", {})
        tenor_order = ["1m", "3m", "6m", "1y", "2y", "5y", "10y", "30y"]
        tenor_labels = {"1m": "1M", "3m": "3M", "6m": "6M", "1y": "1Y",
                        "2y": "2Y", "5y": "5Y", "10y": "10Y", "30y": "30Y"}
        tenors = [t for t in tenor_order if t in curve_ylds]
        yields = [curve_ylds[t] for t in tenors]
        if tenors:
            fig_curve = go.Figure()
            fig_curve.add_trace(go.Scatter(
                x=[tenor_labels[t] for t in tenors], y=yields,
                mode="lines+markers",
                line=dict(color="#00D4FF", width=2.5),
                marker=dict(size=8, color="#00D4FF"),
                fill="tozeroy", fillcolor="rgba(0,212,255,0.08)",
                name="Treasury Yield",
            ))
            fig_curve.update_layout(
                paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
                font_color="#E2E8F0",
                xaxis=dict(title="Tenor", gridcolor="#1F2937"),
                yaxis=dict(title="Yield %", gridcolor="#1F2937"),
                height=280,
                margin=dict(l=50, r=20, t=20, b=40),
            )
            st.plotly_chart(fig_curve, use_container_width=True)
            # KPI row for key rates
            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            rate_kpis = [
                ("3M T-Bill", "3m"), ("1Y", "1y"), ("2Y", "2y"),
                ("10Y", "10y"), ("30Y", "30y"),
            ]
            for col, (label, tenor) in zip([rc1, rc2, rc3, rc4, rc5], rate_kpis):
                with col:
                    _metric_card(label, f"{curve_ylds.get(tenor, 'N/A')}%",
                                 f"Source: {curve_data.get('source', 'N/A')}")
        else:
            st.info("Yield curve data unavailable — check connection")
    except Exception as e:
        logger.warning("[UI] Yield curve: %s", e)

    from datetime import date as _date

    today = _date.today()

    # ── Regulatory events ─────────────────────────────────────────────────────
    REG_EVENTS = [
        {
            "date": _date(2025, 4, 1),
            "jurisdiction": "EU",
            "framework": "MiCA",
            "category": "Stablecoins",
            "title": "MiCA: E-Money Token (EMT) full compliance deadline",
            "description": (
                "All Euro-denominated e-money tokens (EMTs) must be fully MiCA-compliant. "
                "Issuers must hold authorization from an EU NCAs. Affects EURC, EURS, and other EUR stablecoins."
            ),
            "impact": "HIGH",
            "color": "#EF4444",
        },
        {
            "date": _date(2025, 6, 30),
            "jurisdiction": "USA",
            "framework": "GENIUS Act",
            "category": "Stablecoins",
            "title": "GENIUS Act: Senate vote expected (USD stablecoin regulation)",
            "description": (
                "The Guiding and Establishing National Innovation for US Stablecoins Act — "
                "if passed, creates a federal licensing framework for USD stablecoin issuers. "
                "Critical for USDC, USDM, USDY, and other yield-bearing stablecoins in the US market."
            ),
            "impact": "HIGH",
            "color": "#EF4444",
        },
        {
            "date": _date(2025, 9, 30),
            "jurisdiction": "USA",
            "framework": "SEC",
            "category": "Tokenized Securities",
            "title": "SEC: T+1 settlement — DLT pilot for tokenized securities",
            "description": (
                "SEC staff expected to issue guidance on DLT-based settlement for tokenized equity and bond "
                "instruments under the T+1 settlement framework adopted in 2024. Directly affects BUIDL, OUSG, USTB."
            ),
            "impact": "MEDIUM",
            "color": "#F59E0B",
        },
        {
            "date": _date(2026, 1, 1),
            "jurisdiction": "EU",
            "framework": "MiCA",
            "category": "Crypto-Asset Services",
            "title": "MiCA: CASP full authorization required for EU operations",
            "description": (
                "Crypto-Asset Service Providers (CASPs) must hold full MiCA authorization to operate across the EU. "
                "This gates trading platforms, custody providers, and token issuers including RWA protocols "
                "serving EU investors."
            ),
            "impact": "HIGH",
            "color": "#EF4444",
        },
        {
            "date": _date(2026, 3, 31),
            "jurisdiction": "EU",
            "framework": "DLT Pilot Regime",
            "category": "Tokenized Securities",
            "title": "EU DLT Pilot Regime: Review & potential expansion",
            "description": (
                "European Commission reviews the DLT Pilot Regime (Reg 2022/858), which allows EU exchanges and CSDs "
                "to operate DLT-based market infrastructures. A positive review could expand eligible instruments "
                "and TVL caps — unlocking large-scale tokenized bond markets."
            ),
            "impact": "MEDIUM",
            "color": "#F59E0B",
        },
        {
            "date": _date(2026, 7, 1),
            "jurisdiction": "EU",
            "framework": "MiCA",
            "category": "RWA Tokens",
            "title": "MiCA: Asset-Referenced Tokens (ART) — full supervisory regime",
            "description": (
                "Full supervisory enforcement of MiCA ART rules. Tokenized commodity funds, multi-asset "
                "basket products, and RWA-backed tokens that reference external assets must be fully compliant. "
                "Affects mBASIS, gold tokens (PAXG, XAUt), and emerging multi-collateral RWA products."
            ),
            "impact": "HIGH",
            "color": "#EF4444",
        },
        {
            "date": _date(2026, 9, 30),
            "jurisdiction": "Global",
            "framework": "IOSCO",
            "category": "DeFi / RWA",
            "title": "IOSCO: DeFi policy recommendations final implementation",
            "description": (
                "Final implementation deadline for IOSCO's 2023 DeFi policy recommendations by member regulators. "
                "Covers cross-border RWA token transfers, KYC requirements, and disclosure obligations for "
                "protocol-issued tokens including ONDO, MAPLE, and Centrifuge instruments."
            ),
            "impact": "MEDIUM",
            "color": "#F59E0B",
        },
        {
            "date": _date(2026, 12, 31),
            "jurisdiction": "UAE",
            "framework": "VARA",
            "category": "Tokenized Securities",
            "title": "UAE VARA: RWA Token Issuer licensing — full rollout",
            "description": (
                "Dubai's Virtual Assets Regulatory Authority (VARA) completes licensing of RWA token issuers "
                "under the Virtual Assets Law. Affects MANTRA (OM), Libre Protocol, and Middle East-focused "
                "tokenized fund platforms."
            ),
            "impact": "MEDIUM",
            "color": "#F59E0B",
        },
    ]

    # ── Separate past vs upcoming ──────────────────────────────────────────────
    upcoming = [e for e in REG_EVENTS if e["date"] >= today]
    past     = [e for e in REG_EVENTS if e["date"] < today]

    # ── Summary metrics ────────────────────────────────────────────────────────
    high_impact  = sum(1 for e in upcoming if e["impact"] == "HIGH")
    next_event   = upcoming[0] if upcoming else None
    days_to_next = (next_event["date"] - today).days if next_event else None

    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        _metric_card("Upcoming Events", str(len(upcoming)))
    with rc2:
        _metric_card("High Impact", str(high_impact), color="#EF4444")
    with rc3:
        _metric_card("Past Events", str(len(past)), color="#6B7280")
    with rc4:
        if days_to_next is not None:
            _metric_card("Next Event In", f"{days_to_next}d", color="#F59E0B")
        else:
            _metric_card("Next Event", "None", color="#34D399")

    st.markdown("<div style='margin:16px 0'></div>", unsafe_allow_html=True)

    # ── Filter ─────────────────────────────────────────────────────────────────
    jurisdictions = sorted({e["jurisdiction"] for e in REG_EVENTS})
    impacts       = ["ALL", "HIGH", "MEDIUM", "LOW"]

    rf1, rf2 = st.columns([2, 2])
    with rf1:
        jur_filter = st.selectbox("Filter by Jurisdiction", ["ALL"] + jurisdictions, key="reg_jur",
                                  help="Filter events by the regulatory authority's geographic jurisdiction (EU = MiCA/DLT Pilot; USA = SEC/GENIUS Act; UAE = VARA; Global = IOSCO)")
    with rf2:
        imp_filter = st.selectbox("Filter by Impact", impacts, key="reg_imp",
                                  help="HIGH = hard compliance deadline or major rule change affecting key RWA protocols; MEDIUM = regulatory guidance, pilot review, or framework extension; LOW = informational update")

    show_past = st.checkbox("Show past events", value=False, key="reg_past",
                            help="Include regulatory milestones that have already passed — useful for tracking compliance history and understanding how the regulatory landscape has evolved")

    events_to_show = REG_EVENTS if show_past else upcoming
    if jur_filter != "ALL":
        events_to_show = [e for e in events_to_show if e["jurisdiction"] == jur_filter]
    if imp_filter != "ALL":
        events_to_show = [e for e in events_to_show if e["impact"] == imp_filter]

    # ── Event cards ────────────────────────────────────────────────────────────
    st.markdown("<div style='margin:8px 0'></div>", unsafe_allow_html=True)

    if not events_to_show:
        st.info("No events match the selected filters.")
    else:
        for ev in events_to_show:
            is_past   = ev["date"] < today
            days_diff = (ev["date"] - today).days
            if is_past:
                days_label = f"<span style='color:#6B7280'>{abs(days_diff)}d ago</span>"
            elif days_diff == 0:
                days_label = "<span style='color:#F59E0B'>TODAY</span>"
            elif days_diff <= 30:
                days_label = f"<span style='color:#F59E0B'>{days_diff}d away</span>"
            else:
                days_label = f"<span style='color:#9CA3AF'>{days_diff}d away</span>"

            impact_bg = {"HIGH": "#7F1D1D", "MEDIUM": "#78350F", "LOW": "#14532D"}.get(ev["impact"], "#1F2937")
            impact_color = {"HIGH": "#FCA5A5", "MEDIUM": "#FCD34D", "LOW": "#6EE7B7"}.get(ev["impact"], "#9CA3AF")

            st.markdown(f"""
<div style="background:#111827;border:1px solid #1F2937;border-left:4px solid {ev['color']};
            border-radius:8px;padding:16px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-size:11px;color:#9CA3AF">{ev['date'].strftime('%B %d, %Y')}</span>
      &nbsp;{days_label}
      &nbsp;·&nbsp;
      <span style="font-size:11px;color:#60A5FA">{ev['jurisdiction']} · {ev['framework']}</span>
      &nbsp;·&nbsp;
      <span style="font-size:11px;color:#A78BFA">{ev['category']}</span>
    </div>
    <span style="background:{impact_bg};color:{impact_color};font-size:10px;
                 font-weight:700;padding:2px 8px;border-radius:4px">{ev['impact']} IMPACT</span>
  </div>
  <div style="font-size:14px;font-weight:600;color:#E2E8F0;margin:8px 0 4px">{ev['title']}</div>
  <div style="font-size:12px;color:#9CA3AF;line-height:1.6">{ev['description']}</div>
</div>
""", unsafe_allow_html=True)

    # ── Disclaimer ─────────────────────────────────────────────────────────────
    st.markdown(
        "<p style='color:#4B5563;font-size:11px;margin-top:16px'>"
        "⚠️ Regulatory timelines are subject to change. Always verify with official regulatory body publications "
        "(ESMA, SEC EDGAR, VARA, MAS, FCA). This calendar is for informational purposes only."
        "</p>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 10: CRYPTO SCREENER  (Upgrade 8)
# ══════════════════════════════════════════════════════════════════════════════

with tab_screener:
    _SCR_NAMES = {"BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "SOLUSDT": "Solana", "XRPUSDT": "XRP"}
    _SCR_ICONS = {"BTCUSDT": "₿", "ETHUSDT": "Ξ", "SOLUSDT": "◎", "XRPUSDT": "✕"}

    st.markdown("### 🔍 Crypto Screener")
    st.markdown(
        "<p style='color:#6B7280;font-size:13px;margin-top:-8px'>"
        "Multi-timeframe signals for BTC · ETH · SOL · XRP — "
        "RSI · EMA stack · Volume anomaly · Funding rate · Open interest · MTF confidence"
        "</p>",
        unsafe_allow_html=True,
    )

    _scr_refresh = st.button("⟳ Refresh Screener", key="btn_scr_refresh")

    if _scr_refresh:
        _load_screener_signals.clear()

    with st.spinner("Fetching Bybit data…"):
        sig_data = _load_screener_signals()

    # ── Signal cards ─────────────────────────────────────────────────────────
    cols = st.columns(4)
    for idx, sym in enumerate(_SCR_SYMS):
        s = sig_data.get(sym, {})
        with cols[idx]:
            signal    = s.get("signal", "HOLD")
            sig_color = {"BUY": "#34D399", "SELL": "#EF4444", "HOLD": "#FBBF24"}.get(signal, "#9CA3AF")
            sig_bg    = {"BUY": "#064E3B", "SELL": "#7F1D1D", "HOLD": "#78350F"}.get(signal, "#1F2937")

            price     = s.get("price") or 0.0
            chg       = s.get("change_24h_pct")
            chg_str   = f"{chg:+.2f}%" if chg is not None else "—"
            chg_color = "#34D399" if (chg or 0) >= 0 else "#EF4444"

            rsi       = s.get("rsi_14")
            rsi_str   = f"{rsi:.1f}" if rsi is not None else "—"
            rsi_color = ("#EF4444" if (rsi or 50) >= 70
                         else "#34D399" if (rsi or 50) <= 30 else "#E2E8F0")

            stack       = s.get("ema_stack", "UNKNOWN")
            stack_color = {"BULLISH": "#34D399", "BEARISH": "#EF4444", "MIXED": "#FBBF24"}.get(stack, "#9CA3AF")

            vol_anom  = s.get("volume_anomaly")
            vol_str   = f"{vol_anom:.2f}×" if vol_anom is not None else "—"
            vol_color = "#FBBF24" if (vol_anom or 1.0) >= 1.5 else "#9CA3AF"

            fr        = s.get("funding_rate_pct")
            fr_str    = f"{fr:+.4f}%" if fr is not None else "—"
            fr_color  = ("#EF4444" if (fr or 0) > 0.05
                         else "#34D399" if (fr or 0) < -0.01 else "#9CA3AF")

            oi_usd    = s.get("open_interest_usd")
            oi_str    = f"${oi_usd / 1e9:.2f}B" if oi_usd is not None else "—"

            corr      = s.get("btc_corr_30d")
            corr_str  = f"{corr:.2f}" if corr is not None else "—"

            mtf       = s.get("mtf_confidence")
            mtf_str   = f"{mtf * 100:.1f}%" if mtf is not None else "—"
            mtf_color = ("#34D399" if (mtf or 0) >= 0.65
                         else "#EF4444" if (mtf or 0) <= 0.35 else "#FBBF24")

            conf_bull  = s.get("confluence_bullish")
            conf_str   = f"{conf_bull}/4 TFs" if conf_bull is not None else "—"
            conf_color = ("#34D399" if (conf_bull or 0) >= 3
                          else "#FBBF24" if (conf_bull or 0) == 2 else "#EF4444")

            pos_size   = s.get("position_size_pct")
            pos_str    = f"{pos_size}% of max" if pos_size is not None else "—"
            pos_color  = sig_color  # mirror the signal colour

            st.markdown(f"""
<div style="background:#111827;border:1px solid #1F2937;border-top:3px solid {sig_color};
            border-radius:10px;padding:16px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <span style="font-size:18px;font-weight:700;color:#E2E8F0">
      {_SCR_ICONS[sym]}&nbsp;{_SCR_NAMES[sym]}
    </span>
    <span style="background:{sig_bg};color:{sig_color};font-size:11px;font-weight:700;
                 padding:3px 10px;border-radius:6px">{signal}</span>
  </div>
  <div style="font-size:22px;font-weight:700;color:#E2E8F0">${price:,.2f}</div>
  <div style="font-size:13px;color:{chg_color};margin-bottom:12px">{chg_str} (24 h)</div>
  <table style="width:100%;border-collapse:collapse;font-size:12px">
    <tr>
      <td style="color:#6B7280;padding:3px 0">RSI (14)</td>
      <td style="color:{rsi_color};text-align:right;font-weight:600">{rsi_str}</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">EMA Stack</td>
      <td style="color:{stack_color};text-align:right;font-weight:600">{stack}</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">Volume</td>
      <td style="color:{vol_color};text-align:right">{vol_str} vs avg</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">Funding Rate</td>
      <td style="color:{fr_color};text-align:right">{fr_str}</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">Open Interest</td>
      <td style="color:#9CA3AF;text-align:right">{oi_str}</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">BTC Corr (30 D)</td>
      <td style="color:#9CA3AF;text-align:right">{corr_str}</td>
    </tr>
    <tr style="border-top:1px solid #1F2937">
      <td style="color:#6B7280;padding:5px 0 3px"><b>MTF Confidence</b></td>
      <td style="color:{mtf_color};text-align:right;font-weight:700;font-size:14px">{mtf_str}</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">Confluence</td>
      <td style="color:{conf_color};text-align:right;font-weight:600">{conf_str}</td>
    </tr>
    <tr>
      <td style="color:#6B7280;padding:3px 0">Position Size</td>
      <td style="color:{pos_color};text-align:right;font-weight:600">{pos_str}</td>
    </tr>
  </table>
</div>
""", unsafe_allow_html=True)

    # ── Blood in the Streets · DCA Multiplier · Macro Overlay ────────────────
    st.markdown("---")
    _btc_sig   = sig_data.get("BTCUSDT", {})
    _btc_rsi   = _btc_sig.get("rsi_14")
    _bits      = _df.compute_blood_in_streets(_fg_val, _btc_rsi)
    _dca_mult  = _bits["dca_multiplier"]
    _macro_adj = _df.get_macro_signal_adjustment()

    _bits_color = {"BLOOD_IN_STREETS": "#ef4444", "EXTREME_FEAR": "#f59e0b", "NORMAL": "#6b7280"}.get(_bits["signal"], "#6b7280")
    _bits_bg    = {"BLOOD_IN_STREETS": "#1f0000",  "EXTREME_FEAR": "#1c1200", "NORMAL": "#111827"}.get(_bits["signal"], "#111827")
    _dca_color  = {0.0: "#ef4444", 0.5: "#f97316", 1.0: "#9ca3af", 2.0: "#10b981", 3.0: "#00d4aa"}.get(_dca_mult, "#9ca3af")
    _dca_label  = {0.0: "HOLD", 0.5: "0.5× reduce", 1.0: "1× base", 2.0: "2× accumulate", 3.0: "3× max accumulate"}.get(_dca_mult, f"{_dca_mult}×")
    _rc         = {"MACRO_HEADWIND": "#ef4444", "MILD_HEADWIND": "#f97316", "MACRO_NEUTRAL": "#6b7280", "MILD_TAILWIND": "#10b981", "MACRO_TAILWIND": "#00d4aa"}.get(_macro_adj["regime"], "#6b7280")

    _b1, _b2, _b3 = st.columns(3)
    with _b1:
        st.markdown(f"""
<div style="background:{_bits_bg};border:1px solid {_bits_color};border-top:3px solid {_bits_color};
            border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Blood in Streets</div>
  <div style="font-size:18px;font-weight:700;color:{_bits_color}">{_bits["signal"].replace("_", " ")}</div>
  <div style="font-size:12px;color:#9ca3af;margin-top:4px">{_bits["strength"]} · {_bits["criteria_met"]}/3 criteria met</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">{_bits["description"]}</div>
  <div style="margin-top:10px;font-size:11px;color:#6b7280">
    {"✅" if _bits["criteria"]["extreme_fear"] else "❌"} F&amp;G≤25 &nbsp;
    {"✅" if _bits["criteria"]["rsi_oversold"] else "❌"} RSI≤30 &nbsp;
    {"✅" if _bits["criteria"]["exchange_outflow"] else "❌"} Outflow
  </div>
</div>
""", unsafe_allow_html=True)
    with _b2:
        st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_dca_color};
            border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">DCA Multiplier</div>
  <div style="font-size:36px;font-weight:700;color:{_dca_color}">{_dca_mult}×</div>
  <div style="font-size:13px;color:#9ca3af;margin-top:4px">{_dca_label}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">F&amp;G: {_bits["fg_value"]}/100 · BTC RSI: {f"{_btc_rsi:.1f}" if _btc_rsi else "—"}</div>
</div>
""", unsafe_allow_html=True)
    with _b3:
        st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_rc};
            border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Macro Overlay</div>
  <div style="font-size:18px;font-weight:700;color:{_rc}">{_macro_adj["regime"].replace("_", " ")}</div>
  <div style="font-size:12px;color:#9ca3af;margin-top:4px">Confidence adj: {_macro_adj["adjustment"]:+.0f} pts</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">DXY {_macro_adj["dxy"]:.1f} ({_macro_adj["dxy_signal"]}) · 10Y {_macro_adj["ten_yr"]:.2f}% ({_macro_adj["yr_signal"]})</div>
</div>
""", unsafe_allow_html=True)

    # ── MTF breakdown table ───────────────────────────────────────────────────
    st.markdown("#### Timeframe Breakdown")
    tf_rows = []
    for sym in _SCR_SYMS:
        s  = sig_data.get(sym, {})
        bd = s.get("mtf_breakdown", {})
        row = {"Asset": _SCR_NAMES[sym]}
        for tf in ("1H", "4H", "1D", "1W"):
            v = bd.get(tf)
            row[tf] = f"{v * 100:.1f}%" if v is not None else "—"
        mtf = s.get("mtf_confidence")
        row["MTF Score"] = f"{mtf * 100:.1f}%" if mtf is not None else "—"
        row["Signal"]    = s.get("signal", "HOLD")
        conf_b = s.get("confluence_bullish")
        row["Confluence"] = f"{conf_b}/4" if conf_b is not None else "—"
        tf_rows.append(row)

    st.dataframe(
        pd.DataFrame(tf_rows).set_index("Asset"),
        use_container_width=True,
    )

    st.markdown(
        "<p style='color:#4B5563;font-size:11px;margin-top:8px'>"
        "Weights: 1H 5% · 4H 15% · 1D 40% · 1W 40%. "
        "Score ≥ 65% → BUY · ≤ 35% → SELL · else HOLD. "
        "Data: Bybit v5 perpetuals. Refreshes every 5 min. "
        "Not financial advice."
        "</p>",
        unsafe_allow_html=True,
    )



# ══════════════════════════════════════════════════════════════════════════════
# TAB 11: MACRO INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

with tab_macro:
    st.markdown('<div class="section-header">Macro Intelligence Dashboard</div>', unsafe_allow_html=True)
    st.caption("FRED + yfinance macro data · Rolling correlations with BTC · M2 84-day lead indicator")

    # ── Load data ──────────────────────────────────────────────────────────────
    @st.cache_data(ttl=1800, show_spinner=False)
    def _load_macro_snapshot():
        fred  = _df.fetch_macro_indicators()
        yf_m  = _df.fetch_yfinance_macro()
        return fred, yf_m

    @st.cache_data(ttl=1800, show_spinner=False)
    def _load_macro_ts(days: int):
        return _df.fetch_macro_timeseries(days)

    fred_data, yf_data = _load_macro_snapshot()

    # ── Macro Snapshot Metrics ─────────────────────────────────────────────────
    st.markdown("#### Current Macro Snapshot")
    mc1, mc2, mc3, mc4, mc5, mc6, mc7, mc8 = st.columns(8)
    mc1.metric("10Y Yield", f"{fred_data.get('ten_yr_yield', 4.35):.2f}%")
    mc2.metric("DXY", f"{fred_data.get('dxy', 104.0):.1f}")
    mc3.metric("VIX", f"{yf_data.get('vix', 18.0):.1f}")
    mc4.metric("Gold", f"${yf_data.get('gold_spot', 2900.0):,.0f}")
    mc5.metric("WTI Oil", f"${fred_data.get('wti_crude', 67.5):.1f}")
    mc6.metric("SPX", f"{yf_data.get('spx', 5800.0):,.0f}")
    mc7.metric("M2 ($B)", f"${fred_data.get('m2_supply_bn', 21500.0):,.0f}B")
    mc8.metric("ISM Mfg", f"{fred_data.get('ism_manufacturing', 52.0):.1f}")

    src_label = fred_data.get("source", "fallback")
    yf_src    = yf_data.get("source", "fallback")
    st.caption(f"FRED source: **{src_label}** · yfinance source: **{yf_src}** · Cached 30 min")

    st.markdown("---")

    # ── Rolling Correlation Section ────────────────────────────────────────────
    st.markdown("#### BTC Rolling Correlations vs Macro Factors")
    st.caption("Pearson correlation of daily returns over selected window. +1 = move together, -1 = inverse.")

    corr_days = st.select_slider(
        "Lookback window",
        options=[14, 30, 60, 90],
        value=30,
        key="macro_corr_days",
    )

    ts_data = _load_macro_ts(corr_days + 20)  # fetch extra days for rolling window

    if ts_data and "BTC" in ts_data:
        import pandas as pd
        import plotly.graph_objects as go

        # Build DataFrame from timeseries dicts
        frames: dict = {}
        for key in ["BTC", "VIX", "Gold", "SPX", "DXY", "Oil"]:
            series = ts_data.get(key)
            if series and isinstance(series, dict):
                frames[key] = pd.Series(series).rename(key)

        if len(frames) >= 2:
            df_ts = pd.DataFrame(frames).sort_index()
            df_ts.index = pd.to_datetime(df_ts.index)
            df_ret = df_ts.pct_change().dropna()

            # Rolling correlation of each factor vs BTC
            factors = [c for c in df_ret.columns if c != "BTC"]
            corr_results: dict = {}
            for fac in factors:
                if fac in df_ret.columns and "BTC" in df_ret.columns:
                    rolling_corr = df_ret["BTC"].rolling(corr_days).corr(df_ret[fac]).dropna()
                    if not rolling_corr.empty:
                        corr_results[fac] = rolling_corr

            if corr_results:
                fig_corr = go.Figure()
                colors = {"VIX": "#ef4444", "Gold": "#f59e0b", "SPX": "#10b981",
                          "DXY": "#6366f1", "Oil": "#f97316"}
                for fac, series in corr_results.items():
                    fig_corr.add_trace(go.Scatter(
                        x=series.index, y=series.values,
                        mode="lines", name=fac,
                        line=dict(color=colors.get(fac, "#888"), width=2),
                    ))
                fig_corr.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
                fig_corr.add_hline(y=0.5,  line_dash="dot", line_color="rgba(16,185,129,0.4)",
                                   annotation_text="Strong positive")
                fig_corr.add_hline(y=-0.5, line_dash="dot", line_color="rgba(239,68,68,0.4)",
                                   annotation_text="Strong negative")
                fig_corr.update_layout(
                    height=320,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=0, r=0, t=30, b=0),
                    yaxis=dict(range=[-1, 1], gridcolor="rgba(255,255,255,0.07)"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.07)"),
                )
                st.plotly_chart(fig_corr, use_container_width=True)

                # Current snapshot bar chart
                st.markdown(f"**Current {corr_days}-day correlations with BTC**")
                current_corrs = {
                    fac: float(series.iloc[-1])
                    for fac, series in corr_results.items()
                    if len(series) > 0
                }
                corr_df = pd.DataFrame(
                    list(current_corrs.items()), columns=["Factor", "Correlation"]
                ).sort_values("Correlation", ascending=True)
                bar_colors = ["#ef4444" if v < 0 else "#10b981" for v in corr_df["Correlation"]]
                fig_bar = go.Figure(go.Bar(
                    x=corr_df["Correlation"], y=corr_df["Factor"],
                    orientation="h",
                    marker_color=bar_colors,
                    text=[f"{v:.3f}" for v in corr_df["Correlation"]],
                    textposition="outside",
                ))
                fig_bar.update_layout(
                    height=220,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    margin=dict(l=0, r=0, t=10, b=0),
                    xaxis=dict(range=[-1, 1], gridcolor="rgba(255,255,255,0.07)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.07)"),
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Not enough data for rolling correlations. Try a smaller window.")
        else:
            st.info("Loading macro timeseries data... (requires yfinance installed)")
    else:
        st.info("Macro timeseries unavailable. Install yfinance: `pip install yfinance`")

    st.markdown("---")

    # ── M2 84-Day Lead Indicator ───────────────────────────────────────────────
    st.markdown("#### M2 Money Supply — 84-Day Lead Indicator")
    st.caption("M2 shifted forward 84 days overlaid on BTC price. Rising M2 historically precedes BTC rallies by ~3 months.")

    ts_long = _load_macro_ts(365)
    if ts_long and "BTC" in ts_long:
        import pandas as pd
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        btc_series = ts_long.get("BTC", {})
        if btc_series:
            btc_df = pd.Series(btc_series).rename("BTC")
            btc_df.index = pd.to_datetime(btc_df.index)

            # M2 from FRED (monthly series) — use current value as flat line if no history
            m2_now = fred_data.get("m2_supply_bn", 21500.0)

            fig_m2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig_m2.add_trace(
                go.Scatter(x=btc_df.index, y=btc_df.values,
                           name="BTC Price", line=dict(color="#f59e0b", width=2)),
                secondary_y=False,
            )
            # M2 annotation (full monthly timeseries would need FRED historical API)
            fig_m2.add_hline(
                y=m2_now, line_dash="dot", line_color="rgba(99,102,241,0.6)",
                annotation_text=f"M2 now: ${m2_now:,.0f}B",
                secondary_y=True,
            )
            fig_m2.update_layout(
                height=280,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                margin=dict(l=0, r=0, t=20, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis=dict(gridcolor="rgba(255,255,255,0.07)"),
                yaxis=dict(title="BTC Price (USD)", gridcolor="rgba(255,255,255,0.07)"),
                yaxis2=dict(title="M2 ($B)", gridcolor="rgba(255,255,255,0.03)"),
            )
            st.plotly_chart(fig_m2, use_container_width=True)
            st.caption("Note: M2 84-day shift requires FRED historical API key for full series. Set RWA_FRED_API_KEY in .env to enable.")
        else:
            st.info("BTC historical data unavailable.")
    else:
        st.info("Loading 1-year macro timeseries... (requires yfinance installed)")

    st.markdown("---")

    # ── Global M2 Composite + 90-Day Lag Signal ────────────────────────────────
    st.markdown("#### Global M2 Composite — 90-Day Lag BTC Signal")
    st.caption("US M2 × 4.2 scaling (US ≈ 24% of global M2). Rising M2 typically precedes BTC rallies by ~90 days.")

    @st.cache_data(ttl=21600, show_spinner=False)   # 6-hour TTL (monthly data)
    def _load_global_m2():
        return _df.fetch_global_m2_composite()

    _m2 = _load_global_m2()
    _m2_sig = _m2.get("lag_signal", "NEUTRAL")
    _m2_sig_colors = {"EXPANDING": "#10b981", "CONTRACTING": "#ef4444", "NEUTRAL": "#6b7280"}
    _m2_c = _m2_sig_colors.get(_m2_sig, "#6b7280")
    _m2c1, _m2c2, _m2c3, _m2c4 = st.columns(4)
    _m2c1.metric("US M2", f"${_m2.get('us_m2_bn', 21500.0):,.0f}B")
    _m2c2.metric("Global M2 Est.", f"${_m2.get('global_m2_est_bn', 90300.0):,.0f}B")
    _m2c3.metric("90d Change", f"{_m2.get('m2_90d_change_pct', 0.0):+.2f}%")
    _m2c4.metric("Lag Signal", _m2_sig)
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid {_m2_c};"
        f"border-radius:8px;padding:12px 16px;font-size:13px;color:{_m2_c};margin-top:8px'>"
        f"<b>BTC Signal:</b> {_m2.get('btc_signal','NEUTRAL')}</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Source: {_m2.get('source','fallback')} · Updated: {_m2.get('timestamp','')[:19]}")

    st.markdown("---")

    # ── Pi Cycle Top Indicator ────────────────────────────────────────────────
    st.markdown("#### Pi Cycle Top Indicator")
    st.caption("111-DMA vs 350-DMA×2 of BTC close. When 111-DMA crosses above 350-DMA×2, BTC is near a cycle top.")

    @st.cache_data(ttl=86400, show_spinner=False)   # daily TTL
    def _load_pi_cycle():
        return _df.fetch_pi_cycle_indicator()

    _pi = _load_pi_cycle()
    _pi_sig = _pi.get("signal", "N/A")
    _pi_sig_colors = {
        "APPROACHING_TOP": "#ef4444", "WARNING": "#f59e0b",
        "NEUTRAL": "#6b7280", "BOTTOM": "#10b981", "N/A": "#6b7280",
    }
    _pi_c = _pi_sig_colors.get(_pi_sig, "#6b7280")
    _pic1, _pic2, _pic3, _pic4 = st.columns(4)
    _pic1.metric("111-DMA", f"${_pi.get('ma_111') or 0:,.0f}" if _pi.get("ma_111") is not None else "N/A")
    _pic2.metric("350-DMA×2", f"${_pi.get('ma_350x2') or 0:,.0f}" if _pi.get("ma_350x2") is not None else "N/A")
    _pic3.metric("Gap %", f"{_pi.get('gap_pct') or 0:+.1f}%" if _pi.get("gap_pct") is not None else "N/A")
    _pic4.metric("Signal", _pi_sig)
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid {_pi_c};"
        f"border-radius:8px;padding:12px 16px;font-size:13px;color:{_pi_c};margin-top:8px'>"
        f"{_pi.get('description', 'Pi Cycle data unavailable.')}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Stablecoin Supply (USDT + USDC + RLUSD) ───────────────────────────────
    st.markdown("#### Stablecoin Supply — Dry Powder Indicator")
    st.caption("Rising stablecoin supply = capital waiting on the sidelines = bullish setup when deployed.")

    @st.cache_data(ttl=3600, show_spinner=False)
    def _load_stable():
        return _df.fetch_stablecoin_supply()

    _stb = _load_stable()
    _stb_c1, _stb_c2, _stb_c3, _stb_c4 = st.columns(4)
    _stb_c1.metric("USDT", f"${_stb.get('usdt_bn', 140.0):.1f}B")
    _stb_c2.metric("USDC", f"${_stb.get('usdc_bn', 58.0):.1f}B")
    _stb_c3.metric("RLUSD", f"${_stb.get('rlusd_bn', 0.0):.2f}B")
    _stb_c4.metric("Total", f"${_stb.get('total_bn', 198.0):.1f}B")
    st.caption(f"Source: {_stb.get('source','fallback')} · Updated: {_stb.get('timestamp','')[:19]}")

    st.markdown("---")

    # ── Macro Regime ───────────────────────────────────────────────────────────
    st.markdown("#### Macro Regime Classifier")
    regime_data = market.get("macro_regime", "NEUTRAL")
    regime_bias = market.get("macro_bias", "NEUTRAL")
    regime_desc = market.get("macro_description", "")
    regime_colors = {
        "RISK_ON": "#10b981", "RISK_OFF": "#ef4444",
        "STAGFLATION": "#f59e0b", "LIQUIDITY_CRUNCH": "#8b5cf6", "NEUTRAL": "#6b7280",
    }
    r_color = regime_colors.get(regime_data, "#6b7280")
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.04);border:1px solid {r_color};
    border-radius:8px;padding:16px 20px;margin-bottom:8px">
        <div style="font-size:18px;font-weight:700;color:{r_color}">{regime_data.replace('_', ' ')}</div>
        <div style="font-size:13px;color:#9ca3af;margin-top:6px">{regime_desc}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px">Bias: <b style="color:{r_color}">{regime_bias}</b></div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ON-CHAIN TAB (Group 4)
# ─────────────────────────────────────────────────────────────────────────────
with tab_onchain:
    st.markdown("### ⛓️ BTC On-Chain Intelligence")
    st.caption("CoinMetrics Community API · free, no key · MVRV Z-Score · SOPR · Active Addresses")

    _oc = _df.fetch_coinmetrics_onchain(days=400)

    if _oc.get("error") and not _oc.get("mvrv_z"):
        st.warning(f"On-chain data unavailable: {_oc.get('error')}. CoinMetrics Community API may be rate-limited — try again in a minute.")
    else:
        # ── Snapshot metric cards ─────────────────────────────────────────────
        _mz   = _oc.get("mvrv_z")
        _msig = _oc.get("mvrv_signal", "N/A")
        _sopr = _oc.get("sopr")
        _ssig = _oc.get("sopr_signal", "N/A")
        _rc   = _oc.get("realized_cap")
        _aa   = _oc.get("active_addresses")
        _mv   = _oc.get("mvrv_ratio")

        _mz_color = {
            "UNDERVALUED": "#00d4aa", "FAIR_VALUE": "#10b981",
            "OVERVALUED": "#f59e0b",  "EXTREME_HEAT": "#ef4444",
        }.get(_msig, "#6b7280")
        _sp_color = {
            "CAPITULATION": "#00d4aa", "MILD_LOSS": "#10b981",
            "NORMAL": "#6b7280",       "PROFIT_TAKING": "#f59e0b",
        }.get(_ssig, "#6b7280")

        _oc1, _oc2, _oc3, _oc4 = st.columns(4)
        with _oc1:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_mz_color};border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">MVRV Z-Score</div>
  <div style="font-size:32px;font-weight:700;color:{_mz_color}">{f"{_mz:+.2f}" if _mz is not None else "—"}</div>
  <div style="font-size:13px;color:#9ca3af;margin-top:4px">{_msig.replace("_", " ")}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:6px">MVRV ratio: {f"{_mv:.3f}" if _mv else "—"}</div>
</div>
""", unsafe_allow_html=True)
        with _oc2:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_sp_color};border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">SOPR</div>
  <div style="font-size:32px;font-weight:700;color:{_sp_color}">{f"{_sopr:.4f}" if _sopr is not None else "—"}</div>
  <div style="font-size:13px;color:#9ca3af;margin-top:4px">{_ssig.replace("_", " ")}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:6px">&gt;1 profit-taking · &lt;1 capitulation</div>
</div>
""", unsafe_allow_html=True)
        with _oc3:
            def _fmt_b(v):
                if v is None: return "—"
                if v >= 1e12: return f"${v/1e12:.2f}T"
                if v >= 1e9:  return f"${v/1e9:.1f}B"
                return f"${v/1e6:.0f}M"
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #6366f1;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Realized Cap</div>
  <div style="font-size:24px;font-weight:700;color:#6366f1">{_fmt_b(_rc)}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">Sum of all BTC at last-moved price</div>
</div>
""", unsafe_allow_html=True)
        with _oc4:
            _aa_fmt = f"{_aa:,}" if _aa else "—"
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #8b5cf6;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Active Addresses</div>
  <div style="font-size:24px;font-weight:700;color:#8b5cf6">{_aa_fmt}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">Unique BTC addresses active today</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("---")

        # ── Charts ────────────────────────────────────────────────────────────
        import pandas as pd
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        _mvrv_h = _oc.get("mvrv_history", {})
        _sopr_h = _oc.get("sopr_history", {})

        if _mvrv_h or _sopr_h:
            _fig_oc = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                subplot_titles=("MVRV Z-Score (365-day rolling)", "SOPR"),
                vertical_spacing=0.12,
            )
            if _mvrv_h:
                _mh_s   = pd.Series(_mvrv_h).sort_index()
                _mh_z   = (_mh_s - _mh_s.rolling(365, min_periods=30).mean()) / _mh_s.rolling(365, min_periods=30).std().clip(lower=1e-6)
                _z_clrs = ["#ef4444" if v > 3 else "#f59e0b" if v > 1.5 else "#10b981" if v > -0.5 else "#00d4aa" for v in _mh_z]
                _fig_oc.add_trace(
                    go.Scatter(x=_mh_z.index, y=_mh_z.values, mode="lines", name="MVRV Z",
                               line=dict(color="#6366f1", width=2)),
                    row=1, col=1,
                )
                for _thresh, _lbl, _clr in [(3.0, "Extreme (>3)", "#ef4444"), (1.5, "Overvalued (>1.5)", "#f59e0b"), (-0.5, "Undervalued (<-0.5)", "#00d4aa")]:
                    _fig_oc.add_hline(y=_thresh, line_dash="dash", line_color=_clr, opacity=0.4,
                                      annotation_text=_lbl, annotation_font_size=9, row=1, col=1)
            if _sopr_h:
                _sp_s = pd.Series(_sopr_h).sort_index()
                _fig_oc.add_trace(
                    go.Scatter(x=_sp_s.index, y=_sp_s.values, mode="lines", name="SOPR",
                               line=dict(color="#10b981", width=2)),
                    row=2, col=1,
                )
                _fig_oc.add_hline(y=1.0, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                                  annotation_text="Breakeven", annotation_font_size=9, row=2, col=1)
            _fig_oc.update_layout(
                height=480,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0", size=11),
                margin=dict(l=0, r=0, t=40, b=0),
                showlegend=False,
            )
            _fig_oc.update_yaxes(gridcolor="rgba(255,255,255,0.07)")
            _fig_oc.update_xaxes(gridcolor="rgba(255,255,255,0.07)")
            st.plotly_chart(_fig_oc, use_container_width=True)

        # ── Funding rates from Coinalyze (cross-exchange context) ─────────────
        st.markdown("---")
        st.markdown("#### 📡 Cross-Exchange Funding Rates (via Coinalyze)")
        _funding = _df.fetch_coinalyze_funding()
        if _funding:
            _fnd_cols = st.columns(len(_funding))
            for _ci, (_sym, _fdata) in enumerate(_funding.items()):
                _fr_pct = _fdata.get("funding_rate_pct", 0)
                _fr_sig = _fdata.get("signal", "NEUTRAL")
                _fr_clr = {"BEARISH": "#ef4444", "NEUTRAL": "#6b7280", "BULLISH": "#00d4aa"}.get(_fr_sig, "#6b7280")
                with _fnd_cols[_ci % len(_fnd_cols)]:
                    st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;text-align:center">
  <div style="font-size:11px;color:#6b7280;margin-bottom:4px">{_sym.replace("USDT_PERP.A", "")}</div>
  <div style="font-size:20px;font-weight:700;color:{_fr_clr}">{_fr_pct:+.4f}%</div>
  <div style="font-size:11px;color:#9ca3af">{_fr_sig}</div>
</div>
""", unsafe_allow_html=True)
        else:
            st.caption("Set RWA_COINALYZE_API_KEY in .env for cross-exchange funding rates.")

        _src = _oc.get("source", "coinmetrics_community")
        _ts  = _oc.get("timestamp", "")[:19]
        st.caption(f"Source: {_src} · {_ts} UTC · Cached 1h")

    # ── RLUSD / XRPL Live Data (Group 6) ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🌊 RLUSD & XRP Ledger")
    st.caption("XRPL ledger gateway_balances + CoinGecko · Ripple USD · Cached 15 min")

    _rlusd = _df.fetch_xrpl_rlusd()

    if _rlusd.get("error") and not _rlusd.get("circulating_supply"):
        st.caption(f"RLUSD data unavailable: {_rlusd.get('error')}. XRPL cluster may be unreachable.")
    else:
        def _fmt_supply(v):
            if v is None: return "—"
            if v >= 1e9:  return f"${v/1e9:.2f}B"
            if v >= 1e6:  return f"${v/1e6:.1f}M"
            return f"${v:,.0f}"

        _rl_xrpl  = _rlusd.get("xrpl_supply")
        _rl_circ  = _rlusd.get("circulating_supply")
        _rl_price = _rlusd.get("price_usd", 1.0)
        _rl_mcap  = _rlusd.get("market_cap_usd")
        _rl_src   = _rlusd.get("source", "—")

        _rla, _rlb, _rlc, _rld = st.columns(4)
        with _rla:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #3b82f6;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">XRPL On-Ledger Supply</div>
  <div style="font-size:22px;font-weight:700;color:#3b82f6">{_fmt_supply(_rl_xrpl) if _rl_xrpl else "—"}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">RLUSD issued on XRPL ledger</div>
</div>
""", unsafe_allow_html=True)
        with _rlb:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #06b6d4;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Circulating Supply</div>
  <div style="font-size:22px;font-weight:700;color:#06b6d4">{_fmt_supply(_rl_circ)}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">All chains (CoinGecko)</div>
</div>
""", unsafe_allow_html=True)
        with _rlc:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #10b981;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Market Cap</div>
  <div style="font-size:22px;font-weight:700;color:#10b981">{_fmt_supply(_rl_mcap)}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">Target: $1.5B+ (Ripple 2026)</div>
</div>
""", unsafe_allow_html=True)
        with _rld:
            _peg_color = "#10b981" if abs((_rl_price or 1.0) - 1.0) < 0.005 else "#f59e0b"
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_peg_color};border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">RLUSD Price</div>
  <div style="font-size:28px;font-weight:700;color:{_peg_color}">${_rl_price:.4f}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">{'On peg' if abs((_rl_price or 1.0) - 1.0) < 0.005 else 'Off peg!'}</div>
</div>
""", unsafe_allow_html=True)

        _rl_ts = _rlusd.get("timestamp", "")[:19]
        st.caption(f"Source: {_rl_src} · {_rl_ts} UTC · XRPL issuer: {XRPL_RLUSD_ISSUER[:12]}…")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 13: OPTIONS FLOW
# ══════════════════════════════════════════════════════════════════════════════

with tab_options:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.markdown("### 📐 BTC Options Flow — Deribit")
    st.caption("Deribit public API · no key required · OI by Strike · Put/Call Ratio · IV Term Structure · Max Pain · Cached 15 min")

    _opt_curr = st.selectbox("Currency", ["BTC", "ETH"], key="opt_curr_sel")
    _oc5 = _df.fetch_deribit_options_chain(currency=_opt_curr)

    if _oc5.get("error") and not _oc5.get("oi_by_strike"):
        st.warning(f"Options data unavailable: {_oc5.get('error')}. Deribit may be temporarily unreachable.")
    else:
        _pc   = _oc5.get("put_call_ratio")
        _mp   = _oc5.get("max_pain")
        _tput = _oc5.get("total_put_oi", 0)
        _tcal = _oc5.get("total_call_oi", 0)
        _osig = _oc5.get("signal", "N/A")
        _spot = _oc5.get("spot_price")

        _sig_color = {
            "EXTREME_PUTS":  "#ef4444",
            "BEARISH":       "#f59e0b",
            "NEUTRAL":       "#6b7280",
            "BULLISH":       "#10b981",
            "EXTREME_CALLS": "#00d4aa",
        }.get(_osig, "#6b7280")

        _oc5a, _oc5b, _oc5c, _oc5d = st.columns(4)
        with _oc5a:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_sig_color};border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Put/Call Ratio</div>
  <div style="font-size:32px;font-weight:700;color:{_sig_color}">{f"{_pc:.3f}" if _pc is not None else "—"}</div>
  <div style="font-size:13px;color:#9ca3af;margin-top:4px">{_osig.replace("_", " ")}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:6px">&gt;1.1 bearish · &lt;0.9 bullish</div>
</div>
""", unsafe_allow_html=True)
        with _oc5b:
            _mp_dist = f"{abs(_mp - _spot) / _spot * 100:.1f}% {'below' if _mp < _spot else 'above'} spot" if _mp and _spot else ""
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #6366f1;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Max Pain</div>
  <div style="font-size:26px;font-weight:700;color:#6366f1">{f"${_mp:,.0f}" if _mp else "—"}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">{_mp_dist}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:2px">Strike minimising buyer payout</div>
</div>
""", unsafe_allow_html=True)
        with _oc5c:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #ef4444;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Total Put OI</div>
  <div style="font-size:28px;font-weight:700;color:#ef4444">{f"{_tput:,.0f}" if _tput else "—"}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">contracts</div>
</div>
""", unsafe_allow_html=True)
        with _oc5d:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #10b981;border-radius:10px;padding:16px">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Total Call OI</div>
  <div style="font-size:28px;font-weight:700;color:#10b981">{f"{_tcal:,.0f}" if _tcal else "—"}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:8px">contracts</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Dual panel: OI by Strike + IV Term Structure ──────────────────────
        _oi5  = _oc5.get("oi_by_strike", [])
        _ts5  = _oc5.get("term_structure", [])
        _col5a, _col5b = st.columns([3, 2])

        with _col5a:
            if _oi5:
                _fig5a = go.Figure()
                _strikes5 = [str(int(r["strike"])) for r in _oi5]
                _fig5a.add_trace(go.Bar(
                    name="Puts", x=_strikes5,
                    y=[r["put_oi"] for r in _oi5],
                    marker_color="rgba(239,68,68,0.8)",
                ))
                _fig5a.add_trace(go.Bar(
                    name="Calls", x=_strikes5,
                    y=[r["call_oi"] for r in _oi5],
                    marker_color="rgba(16,185,129,0.8)",
                ))
                if _mp:
                    _fig5a.add_vline(x=str(int(_mp)), line_dash="dash",
                                     line_color="#6366f1", opacity=0.8,
                                     annotation_text=f"Max Pain ${_mp:,.0f}",
                                     annotation_font_size=10)
                if _spot:
                    _fig5a.add_vline(x=str(int(_spot)), line_dash="dot",
                                     line_color="#f59e0b", opacity=0.6,
                                     annotation_text="Spot",
                                     annotation_font_size=10)
                _fig5a.update_layout(
                    title="OI by Strike (Top 20)", barmode="stack",
                    height=360, paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0", size=11),
                    margin=dict(l=0, r=0, t=40, b=60),
                    legend=dict(orientation="h", y=1.08),
                    xaxis=dict(tickangle=-45, gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.07)", title="OI (contracts)"),
                )
                st.plotly_chart(_fig5a, use_container_width=True)
            else:
                st.info("No OI by strike data available.")

        with _col5b:
            _ts5_valid = [t for t in _ts5 if t.get("atm_iv") is not None and t.get("dte", 0) <= 365]
            if _ts5_valid:
                _fig5b = go.Figure()
                _fig5b.add_trace(go.Scatter(
                    x=[t["dte"] for t in _ts5_valid],
                    y=[t["atm_iv"] for t in _ts5_valid],
                    mode="lines+markers",
                    name="ATM IV",
                    line=dict(color="#6366f1", width=2),
                    marker=dict(size=7),
                    text=[t["expiry"] for t in _ts5_valid],
                    hovertemplate="%{text}<br>DTE: %{x}<br>IV: %{y:.1f}%<extra></extra>",
                ))
                _fig5b.update_layout(
                    title="IV Term Structure (ATM)",
                    height=360, paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0", size=11),
                    margin=dict(l=0, r=0, t=40, b=0),
                    xaxis=dict(title="Days to Expiry", gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(title="IV (%)", gridcolor="rgba(255,255,255,0.07)"),
                )
                st.plotly_chart(_fig5b, use_container_width=True)
            else:
                st.info("IV term structure unavailable.")

        _ts5_str = _oc5.get("timestamp", "")[:19]
        st.caption(f"Source: Deribit · {_ts5_str} UTC · Spot: ${_spot:,.0f}" if _spot else f"Source: Deribit · {_ts5_str} UTC")


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="margin-top:40px;padding:16px;border-top:1px solid #1F2937;text-align:center">
    <span style="font-size:11px;color:#374151">
        ♾️ RWA INFINITY MODEL v1.0 &nbsp;·&nbsp;
        Powered by Claude claude-sonnet-4-6 &nbsp;·&nbsp;
        Data: DeFiLlama · CoinGecko &nbsp;·&nbsp;
        Protocols: Ondo · BlackRock · Pendle · Morpho · Ethena · EigenLayer · Lido · Jito · Lombard · Aave Horizon · Plume · Apollo · Clearpool · Falcon · Agora &nbsp;·&nbsp;
        ⚠️ For informational purposes only — not financial advice &nbsp;·&nbsp;
        Auto-refresh: every 60 minutes
    </span>
</div>
""", unsafe_allow_html=True)

# ─── Live scan progress fragment (Upgrade 9) ─────────────────────────────────
# @st.fragment(run_every=3) polls only this fragment every 3 s while a scan is
# running, avoiding costly full-page reruns.
@st.fragment(run_every=3)
def _scan_live_progress():
    status = _db.read_scan_status()
    if status.get("running", 0):
        pct  = status.get("progress_pct", 0)
        task = (status.get("current_task") or "Processing…")[:50]
        st.progress(pct / 100, text=f"⚡ Scan in progress — {pct}%  ·  {task}")

_scan_live_progress()
