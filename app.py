"""
app.py — RWA Infinity Model v1.0
World-Class Real World Asset Tokenization Dashboard
Powered by Claude claude-sonnet-4-6 AI | DeFiLlama | CoinGecko

Run: streamlit run app.py
"""

import json
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
# UPGRADE 23: make_subplots lazy-loaded at each call site (3 locations below)
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
try:
    from config import (
        PORTFOLIO_TIERS, AI_AGENTS, CATEGORY_COLORS,
        RISK_LABELS, RWA_UNIVERSE, ARB_STRONG_THRESHOLD_PCT,
        XRPL_RLUSD_ISSUER, SENTRY_DSN, feature_enabled, FEATURES,
        get_redemption_window,
        RWA_TAM_USD, RWA_ONCHAIN_USD, RWA_MILESTONES,
        BRAND_NAME, BRAND_LOGO_PATH,
    )
except Exception as _cfg_err:
    st.error(f"Configuration error: {_cfg_err}")
    st.stop()

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
    try:
        _sched.start()
    except Exception as e:
        logger.warning("Scheduler start failed: %s", e)
    return True

_init()

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Google Fonts — Inter (UI) + JetBrains Mono (data) */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');

/* Base */
:root {
  --primary:   #00d4aa;
  --bg:        #0d0e14;
  --card-bg:   #111827;
  --border:    #1F2937;
  --text:      #E2E8F0;
  --muted:     #6B7280;
  --success:   #22c55e;
  --warning:   #f59e0b;
  --danger:    #ef4444;
  --font-ui:   'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

/* Main background + fonts */
.stApp { background: var(--bg); font-family: var(--font-ui); }

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
    font-size: clamp(20px, 1.6vw, 26px);
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
    font-family: var(--font-mono);
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

/* Light mode (item 32) */
body.light-mode .stApp { background: #f1f5f9 !important; color: #1e293b !important; }
body.light-mode .metric-card { background: #ffffff !important; border-color: #e2e8f0 !important; }
body.light-mode .metric-label { color: #475569 !important; }
body.light-mode .metric-value { color: #0f172a !important; }
body.light-mode .stTabs [data-baseweb="tab-list"] { background: #ffffff !important; border-color: #e2e8f0 !important; }
body.light-mode .stTabs [data-baseweb="tab"] { color: #64748b !important; }
body.light-mode .ticker-wrap { background: #ffffff !important; border-color: #e2e8f0 !important; }

/* Mobile responsive (item 41) */
@media (max-width: 768px) {
    div[data-testid="stButton"] > button { min-height: 44px !important; }
    [data-testid="stRadio"] label { min-height: 44px !important; padding: 10px 0 !important; }
    [data-testid="stColumn"] { min-width: 100% !important; }
    .metric-value { font-size: clamp(18px, 5vw, 24px) !important; }
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# #13 — INPUT VALIDATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

import re as _re_input

def _validate_weights(weights: dict) -> tuple:
    """Validate that portfolio weights sum to at most 100%."""
    if not weights or not all(isinstance(v, (int, float)) for v in weights.values()):
        return False, "Invalid weights — all values must be numeric"
    total = sum(weights.values())
    if total > 1.001:
        return False, f"Weights sum to {total:.1%} — must be ≤ 100%"
    return True, ""


def _sanitize_text_input(value: str, max_len: int = 100) -> str:
    """Strip dangerous characters from free-text inputs.

    Allows alphanumeric, spaces, hyphens, underscores, and dots.
    Truncates to max_len characters.
    """
    if not value:
        return ""
    cleaned = _re_input.sub(r"[^\w\s\-\.]", "", value)
    return cleaned[:max_len].strip()


# ─────────────────────────────────────────────────────────────────────────────
# #17 — API KEY HEALTH CHECK (cached once per process)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _get_api_health():
    """Run lightweight API connectivity tests once on startup."""
    try:
        return _df.validate_api_keys()
    except Exception:
        return {}


# ─── Sidebar: API health status (#17) ─────────────────────────────────────────
# Placed here — after _get_api_health() is defined — to avoid NameError on startup.
with st.sidebar:
    # ── Brand header (Phase 1) ────────────────────────────────────────────────
    from pathlib import Path as _SBPath
    if BRAND_LOGO_PATH and _SBPath(BRAND_LOGO_PATH).exists():
        st.image(BRAND_LOGO_PATH, width=120)
    else:
        _sb_title = BRAND_NAME if BRAND_NAME else "♾️ RWA Infinity"
        st.markdown(
            f"<div style='font-size:1.2rem;font-weight:800;"
            f"background:linear-gradient(90deg,#00d4aa,#60a5fa);"
            f"-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
            f"background-clip:text;letter-spacing:-0.3px;margin-bottom:2px;'>{_sb_title}</div>"
            "<div style='font-size:0.65rem;letter-spacing:1.2px;text-transform:uppercase;"
            "color:#6B7280;margin-bottom:8px;'>Real World Asset Intelligence</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── User Level selector (Phase 1) — 3-tier experience system ────────────
    st.markdown(
        '<span style="font-size:11px;color:#6B7280;font-weight:600;'
        'text-transform:uppercase;letter-spacing:0.8px">Experience Level</span>',
        unsafe_allow_html=True,
    )
    _RWA_LEVEL_OPTIONS = ["beginner", "intermediate", "advanced"]
    _RWA_LEVEL_LABELS  = {
        "beginner":     "🟢 Beginner",
        "intermediate": "🟡 Intermediate",
        "advanced":     "🔴 Advanced",
    }
    _rwa_cur_level = st.session_state.get("user_level", "beginner")
    _rwa_level_val = st.radio(
        "User Level",
        options=_RWA_LEVEL_OPTIONS,
        format_func=lambda lv: _RWA_LEVEL_LABELS[lv],
        index=_RWA_LEVEL_OPTIONS.index(_rwa_cur_level),
        key="rwa_user_level_radio",
        label_visibility="collapsed",
        help=(
            "Beginner: plain-English view, tooltips always visible. "
            "Intermediate: key numbers + condensed explanations. "
            "Advanced: full technical detail, all raw numbers."
        ),
    )
    st.session_state["user_level"] = _rwa_level_val
    # Backward compat: pro_mode = True when Advanced
    st.session_state["pro_mode"] = (_rwa_level_val == "advanced")

    st.markdown("---")

    # ── Personal API Keys (session-only, never saved to disk) ─────────────────
    with st.expander("🔑 API Keys (Session Only)", expanded=False):
        st.caption("Keys stored in session only — cleared on refresh. Never saved to disk.")
        _user_cg_key     = st.text_input("CoinGecko Pro Key",  type="password", key="user_cg_key")
        _user_tiingo_key = st.text_input("Tiingo Key",         type="password", key="user_tiingo_key")
        _user_cm_key     = st.text_input("CoinMetrics Key",    type="password", key="user_cm_key")
        if st.button("Apply Keys", key="btn_apply_keys"):
            if _user_cg_key:
                st.session_state["runtime_cg_key"] = _user_cg_key
                audit("API_KEY_APPLIED", service="coingecko")
            if _user_tiingo_key:
                st.session_state["runtime_tiingo_key"] = _user_tiingo_key
                audit("API_KEY_APPLIED", service="tiingo")
            if _user_cm_key:
                st.session_state["runtime_cm_key"] = _user_cm_key
                audit("API_KEY_APPLIED", service="coinmetrics")
            st.success("Keys applied for this session")

    # ── Glossary (Phase 1) ────────────────────────────────────────────────────
    try:
        from glossary import glossary_popover as _rwa_glossary
        _rwa_glossary(st.session_state.get("user_level", "beginner"))
    except ImportError:
        pass

    st.markdown("---")

    # ── Theme toggle (item 32 — dark/light mode) ──────────────────────────────
    _rwa_is_light = st.session_state.get("_rwa_theme") == "light"
    if st.button(
        "☀ Light Mode" if not _rwa_is_light else "🌙 Dark Mode",
        key="_rwa_theme_toggle",
        help="Switch between dark and light mode",
        width="stretch",
    ):
        st.session_state["_rwa_theme"] = "dark" if _rwa_is_light else "light"
        st.rerun()
    # Apply light mode CSS class via JS
    _rwa_theme_js = "add" if not _rwa_is_light else "remove"
    st.markdown(
        f"<script>document.body.classList.{_rwa_theme_js}('light-mode')</script>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Refresh All Data (item 40) ────────────────────────────────────────────
    if st.button("🔄 Refresh All Data", help="Clear all caches and reload fresh data", width="stretch"):
        try:
            st.cache_data.clear()
        except Exception:
            for _fn in [_load_assets, _load_portfolio, _load_arb, _load_news, _load_macro_regime, _load_market_summary]:
                try:
                    _fn.clear()
                except Exception:
                    pass
        st.rerun()

    st.markdown("---")
    st.markdown("#### API Status")
    _api_health = _get_api_health()
    if _api_health:
        for _svc, _status in _api_health.items():
            if _status == "ok":
                _dot, _label = "🟢", "ok"
            elif _status == "no key":
                _dot, _label = "⚫", "no key"
            else:
                _dot, _label = "🔴", "error"
            st.markdown(
                f'<span style="font-size:11px">{_dot} <b>{_svc}</b>: {_label}</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("API health check unavailable")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_usd(n, decimals=0):
    if n is None: return "—"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    if n >= 1e6:  return f"${n/1e6:.1f}M"
    if n >= 1e3:  return f"${n/1e3:.0f}K"
    return f"${n:,.{decimals}f}"


def _freshness_badge(cache_key: str, ttl_seconds: int, label: str = "") -> str:
    """
    F6 — Return an HTML freshness badge for a data panel.
    Shows how old the cached data is with a color-coded age indicator:
      Green  = fresh (within 50% of TTL)
      Yellow = aging (50–90% of TTL)
      Red    = stale (>90% of TTL) or never fetched
    Args:
      cache_key   : key passed to _df._cached_get (e.g. "coingecko_prices")
      ttl_seconds : expected TTL in seconds — same value used in the feed
      label       : optional prefix text (e.g. "Prices" or "Yields")
    Returns inline HTML string safe for st.markdown(unsafe_allow_html=True).
    """
    age = _df.get_cache_age_seconds(cache_key)
    if age is None:
        color = "#6B7280"
        text  = "No data yet"
    else:
        age_min = int(age // 60)
        if age_min < 1:
            age_str = "< 1 min ago"
        elif age_min == 1:
            age_str = "1 min ago"
        elif age_min < 60:
            age_str = f"{age_min} min ago"
        else:
            age_str = f"{age_min // 60}h {age_min % 60}m ago"

        ratio = age / max(ttl_seconds, 1)
        if ratio < 0.5:
            color = "#22c55e"   # green
        elif ratio < 0.9:
            color = "#f59e0b"   # amber
        else:
            color = "#ef4444"   # red (stale)
        text = age_str

    prefix = f"{label} · " if label else ""
    return (
        f'<span style="font-size:11px;color:{color};font-family:monospace;'
        f'background:rgba(0,0,0,0.15);border-radius:4px;padding:1px 6px;">'
        f'⏱ {prefix}{text}</span>'
    )

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

def _csv_button(df: "pd.DataFrame", filename: str, label: str = "⬇ Export CSV",
                key: str | None = None) -> None:
    """
    F5 — Render a Streamlit download_button that exports *df* as UTF-8 CSV.
    No-op if df is None or empty. key must be unique per page render.
    """
    if df is None or df.empty:
        return
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        key=key or f"csv_{filename}_{id(df)}",
    )


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
_ss("pro_mode",         False)  # #65: True=Pro (all metrics), False=Beginner (simplified); default matches user_level default
_ss("user_level",       "beginner")  # Phase 1: 3-level system — beginner/intermediate/advanced
_ss("demo_mode",        False)  # #67: Demo/Sandbox — no real API calls, synthetic data
_ss("wallet_address",   "")     # #110: EVM wallet address for Zerion/ERC-3643 lookups

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

@st.cache_data(ttl=300, show_spinner=False)
def _load_briefing(tier: int, metrics_key: str, n_holdings: int) -> str:
    """Cache key uses tier + rounded yield + holding count to avoid stale briefs."""
    return ""  # populated lazily inside the tab to avoid blocking initial render

@st.cache_data(ttl=1800, show_spinner=False)
def _load_news():
    return _db.get_recent_news(20)

@st.cache_data(ttl=3600, show_spinner=False)
def _load_macro_regime() -> dict:
    """Load fetch_macro_regime() with 1-hour cache (regime changes slowly).
    Falls back to empty dict so callers can degrade gracefully."""
    import concurrent.futures
    try:
        from data_feeds import fetch_macro_regime
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
            _fut = _ex.submit(fetch_macro_regime)
            try:
                return _fut.result(timeout=8)
            except concurrent.futures.TimeoutError:
                return {}
    except Exception:
        return {}

@st.cache_data(ttl=90, show_spinner=False)
def _load_market_summary():
    """Fetch market summary with a hard 6-second timeout to keep the UI responsive.
    TTL raised to 90s (OPT-13): market summary changes slowly, 30s was wasteful."""
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


# ─── OPT-1: Module-level loaders (moved from inside tab blocks to prevent
#     Streamlit from re-registering a new cache entry on every render cycle) ────

@st.cache_data(ttl=900, show_spinner=False)
def _load_nav_premiums():
    return _df.fetch_nav_premiums()

@st.cache_data(ttl=300, show_spinner=False)
def _load_chainlink_prices():
    """OPT-13: TTL raised to 300s (was 60s inside tab_universe)."""
    return {pair: _df.fetch_chainlink_price(pair) for pair in ["XAU/USD", "XAG/USD", "BTC/USD", "ETH/USD"]}

@st.cache_data(ttl=120, show_spinner=False)
def _load_xrpl_dex_arb():
    return _df.fetch_xrpl_dex_arb()

@st.cache_data(ttl=300, show_spinner=False)
def _load_factor_bias():
    from data_feeds import get_macro_factor_allocation_bias
    return get_macro_factor_allocation_bias()

@st.cache_data(ttl=180, show_spinner=False)
def _load_factor_opt(tier_key: int, val: int):
    from portfolio import compute_factor_tilted_portfolio
    from data_feeds import get_macro_factor_allocation_bias
    _port  = _load_portfolio(tier_key, val)
    _holds = _port.get("holdings", []) if _port else []
    _fb    = get_macro_factor_allocation_bias()
    return compute_factor_tilted_portfolio(_holds, _fb, val)

@st.cache_data(ttl=300, show_spinner=False)
def _load_factor_opt_b7(tier_key: int, val: int):
    from portfolio import optimize_factor_portfolio as _ofp
    _port  = _load_portfolio(tier_key, val)
    _holds = _port.get("holdings", []) if _port else []
    if not _holds:
        return {"error": "No holdings"}
    return _ofp(_holds)

@st.cache_data(ttl=120, show_spinner=False)
def _load_xrpl_stats():
    from data_feeds import fetch_xrpl_stats
    return fetch_xrpl_stats()

@st.cache_data(ttl=1800, show_spinner=False)
def _load_macro_snapshot():
    fred  = _df.fetch_macro_indicators()
    yf_m  = _df.fetch_yfinance_macro()
    return fred, yf_m

@st.cache_data(ttl=1800, show_spinner=False)
def _load_macro_ts(days: int):
    return _df.fetch_macro_timeseries(days)

@st.cache_data(ttl=1800, show_spinner=False)
def _load_fred_extended():
    return _df.fetch_fred_extended()

@st.cache_data(ttl=900, show_spinner=False)
def _load_fg_history():
    return _df.fetch_fear_greed_index(limit=30)

@st.cache_data(ttl=21600, show_spinner=False)   # 6-hour TTL (monthly data)
def _load_global_m2():
    return _df.fetch_global_m2_composite()

@st.cache_data(ttl=86400, show_spinner=False)   # daily TTL
def _load_pi_cycle():
    return _df.fetch_pi_cycle_indicator()

@st.cache_data(ttl=3600, show_spinner=False)
def _load_stable():
    return _df.fetch_stablecoin_supply()

@st.cache_data(ttl=1800, show_spinner=False)
def _load_hmm_regime():
    try:
        return _df.fetch_hmm_macro_regime()
    except Exception:
        return None

@st.cache_data(ttl=900, show_spinner=False)
def _load_onchain_signals():
    try:
        return _df.fetch_crypto_onchain_signals()
    except Exception:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def _load_protocol_fees():
    try:
        return _df.fetch_protocol_fees()
    except Exception:
        return {}

# OPT-5: Cache get_private_credit_warnings (was called uncached in tab_portfolio)
@st.cache_data(ttl=300, show_spinner=False)
def _load_private_credit_warnings():
    from data_feeds import get_private_credit_warnings
    return get_private_credit_warnings()

# OPT-6: Cache treasury/duration/liquidity calls (was called uncached in tab_portfolio)
@st.cache_data(ttl=300, show_spinner=False)
def _load_treasury_yield_curve():
    from data_feeds import fetch_treasury_yield_curve
    return fetch_treasury_yield_curve()

# Note: calculate_portfolio_duration and calculate_portfolio_liquidity are
# pure-Python computations with no I/O, so they are not cached separately.
# OPT-6 caches fetch_treasury_yield_curve() (the only I/O in that section).

# OPT-7: Cache On-Chain tab fetches (was called uncached each render)
@st.cache_data(ttl=300, show_spinner=False)
def _load_coinmetrics_onchain(days: int = 400):
    return _df.fetch_coinmetrics_onchain(days=days)

@st.cache_data(ttl=300, show_spinner=False)
def _load_coinalyze_funding():
    return _df.fetch_coinalyze_funding()

@st.cache_data(ttl=300, show_spinner=False)
def _load_xrpl_rlusd():
    return _df.fetch_xrpl_rlusd()

# On-chain tab — additional loaders (OPT-1)
@st.cache_data(ttl=900, show_spinner=False)
def _load_xrpl_basic():
    return _df.fetch_xrpl_data()

@st.cache_data(ttl=60, show_spinner=False)
def _cl_prices():
    pairs = ["XAU/USD", "EUR/USD", "BTC/USD", "ETH/USD", "LINK/USD"]
    return _df.fetch_multicall3_prices(pairs)

@st.cache_data(ttl=120, show_spinner=False)
def _vault_data():
    return {sym: _df.fetch_erc4626_vault_data(sym)
            for sym in ["BUIDL", "OUSG", "USDY", "WSTETH"]}

@st.cache_data(ttl=180, show_spinner=False)
def _redeem_data():
    return {sym: _df.fetch_erc7540_redemption_depth(sym)
            for sym in ["BUIDL", "OUSG"]}

@st.cache_data(ttl=300, show_spinner=False)
def _load_erc7540_queue(addr: str) -> dict:
    return _df.fetch_erc7540_redemption_queue(addr)

@st.cache_data(ttl=300, show_spinner=False)
def _compliance_check(wallet: str):
    _ERC3643_ADDRS = {
        "BUIDL": "0x7712c34205737192402172409a8F7ccef8aA2AEc",
        "OUSG":  "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92",
    }
    return {sym: _df.fetch_erc3643_compliance(addr, wallet)
            for sym, addr in _ERC3643_ADDRS.items()}

@st.cache_data(ttl=180, show_spinner=False)
def _zerion_portfolio(wallet: str):
    return _df.fetch_zerion_portfolio(wallet)

@st.cache_data(ttl=300, show_spinner=False)
def _wh_vaas(chain_id: int):
    return _df.fetch_wormhole_rwa_vaa(emitter_chain_id=chain_id, page_size=15)

@st.cache_data(ttl=300, show_spinner=False)
def _load_xrpl_mpt():
    """Cached XRPL MPT issuance data (5 min TTL)."""
    return _df.fetch_xrpl_mpt_data()

@st.cache_data(ttl=900, show_spinner=False)
def _load_deribit_options(currency: str):
    """Cached Deribit options chain (15 min TTL, keyed by currency)."""
    return _df.fetch_deribit_options_chain(currency=currency)


# ─── UPGRADE 21: Cached chart builders ────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _build_pie_chart(cat_sum: dict, weighted_yield: float):
    """Allocation by Category donut chart. Inputs are plain dicts/scalars (hashable)."""
    labels  = list(cat_sum.keys())
    values  = [cat_sum[c]["weight_pct"] for c in labels]
    colors  = [cat_sum[c].get("color", "#888") for c in labels]
    hover   = [
        f"<b>{c}</b><br>Weight: {cat_sum[c]['weight_pct']:.1f}%<br>"
        f"Yield: {cat_sum[c]['yield_pct']:.2f}%<br>Holdings: {cat_sum[c]['count']}"
        for c in labels
    ]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.55,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover,
        textinfo="label+percent",
        textfont_size=11,
    ))
    fig.add_annotation(
        text=f"<b>{weighted_yield:.2f}%</b><br><span style='font-size:11px'>yield</span>",
        x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#E2E8F0"),
    )
    fig.update_layout(
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
    return fig


@st.cache_data(ttl=300, show_spinner=False)
def _build_holdings_scatter(holdings_records: list):
    """Holdings Yield vs Risk scatter. Takes list of dicts (serializable)."""
    h_df = pd.DataFrame(holdings_records)
    fig = px.scatter(
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
    fig.update_layout(
        paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
        font_color="#E2E8F0",
        margin=dict(l=40, r=20, t=20, b=40),
        height=320,
        xaxis=dict(gridcolor="#1F2937", range=[0, 11]),
        yaxis=dict(gridcolor="#1F2937"),
        legend=dict(bgcolor="#111827", bordercolor="#1F2937", font_size=10),
    )
    fig.add_vline(x=5, line_dash="dash", line_color="#374151",
                  annotation_text="Risk midpoint")
    fig.add_hline(y=4.25, line_dash="dash", line_color="#374151",
                  annotation_text="Risk-free rate (4.25%)")
    return fig


@st.cache_data(ttl=300, show_spinner=False)
def _build_category_bar(cat_names: tuple, cat_counts: tuple):
    """Asset browser category breakdown bar chart. Inputs are tuples (hashable)."""
    fig = px.bar(
        x=cat_names,
        y=cat_counts,
        color=cat_names,
        color_discrete_map=CATEGORY_COLORS,
        labels={"x": "Category", "y": "Count"},
        height=200,
    )
    fig.update_layout(
        paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
        font_color="#E2E8F0", showlegend=False,
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(gridcolor="#1F2937"),
        yaxis=dict(gridcolor="#1F2937"),
    )
    return fig


@st.cache_data(ttl=300, show_spinner=False)
def _build_arb_bar(arb_records: list):
    """Top Arbitrage Opportunities spread bar chart. Takes list of dicts."""
    df = pd.DataFrame(arb_records)
    fig = px.bar(
        df,
        x="asset_a_id",
        y="net_spread_pct",
        color="type",
        color_discrete_sequence=px.colors.qualitative.Set3,
        labels={"net_spread_pct": "Net Spread (%)", "asset_a_id": "Opportunity"},
        title="Top Arbitrage Opportunities by Net Spread",
        height=350,
    )
    fig.update_layout(
        paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
        font_color="#E2E8F0", xaxis_tickangle=-35,
        margin=dict(l=40, r=20, t=40, b=80),
    )
    return fig


@st.cache_data(ttl=300, show_spinner=False)
def _build_tier_comparison_bar(comp_records: list, tier_colors: dict):
    """Portfolio Tier Comparison grouped bar chart. Inputs are plain lists/dicts."""
    fig = go.Figure()
    for row in comp_records:
        tier_n = int(row["Tier"])
        color  = tier_colors.get(tier_n, "#888")
        fig.add_trace(go.Bar(
            name=f"{row['Icon']} {row['Name']}",
            x=["Yield %", "Sharpe", "Sortino", "Max DD %"],
            y=[row.get("Yield (%)") or 0,
               (row.get("Sharpe Ratio") or 0) * 5,
               (row.get("Sortino Ratio") or 0) * 5,
               row.get("Max Drawdown (%)") or 0],
            marker_color=color,
        ))
    fig.update_layout(
        barmode="group",
        paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
        font_color="#E2E8F0",
        legend=dict(bgcolor="#111827", bordercolor="#1F2937"),
        xaxis=dict(gridcolor="#1F2937"),
        yaxis=dict(title="Value", gridcolor="#1F2937"),
        margin=dict(l=40, r=20, t=20, b=40),
        height=350,
    )
    return fig


# OPT-14: Cached Plotly yield bar chart builder
@st.cache_data(ttl=300, show_spinner=False)
def _build_yield_bar(holdings_records: tuple, avg_yield_pct: float):
    """Top Holdings by Yield bar chart. Takes a tuple of (name, yield, category, weight) rows."""
    import plotly.graph_objects as _go14
    names  = [r[0] for r in holdings_records]
    yields = [r[1] for r in holdings_records]
    cats   = [r[2] for r in holdings_records]
    wts    = [r[3] for r in holdings_records]
    colors = [CATEGORY_COLORS.get(c, "#6366f1") for c in cats]
    fig = _go14.Figure(_go14.Bar(
        x=names,
        y=yields,
        marker_color=colors,
        text=[f"{v:.1f}%" for v in yields],
        textposition="outside",
        customdata=list(zip(cats, wts)),
        hovertemplate="<b>%{x}</b><br>Yield: %{y:.2f}%<br>Category: %{customdata[0]}<br>Weight: %{customdata[1]:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#111827", plot_bgcolor="#0A0E1A",
        font_color="#E2E8F0",
        margin=dict(l=40, r=20, t=30, b=80),
        height=280,
        xaxis=dict(gridcolor="#1F2937", tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#1F2937", ticksuffix="%"),
        showlegend=False,
    )
    fig.add_hline(y=avg_yield_pct, line_dash="dash",
                  line_color="#A78BFA", opacity=0.7,
                  annotation_text=f"Portfolio avg {avg_yield_pct:.1f}%",
                  annotation_font_color="#A78BFA", annotation_font_size=10)
    return fig


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
    if st.button("⟳ Refresh Now", width="stretch", key="btn_refresh"):
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

# ── Welcome Banner (item 33 — beginner only, once per session) ────────────────
if (st.session_state.get("user_level", "beginner") == "beginner"
        and not st.session_state.get("_rwa_welcome_dismissed")):
    _wb1, _wb2 = st.columns([11, 1])
    with _wb1:
        st.info(
            "👋 **Welcome to RWA Infinity!** Real World Assets (RWAs) are traditional financial "
            "instruments — bonds, real estate, treasury bills — tokenized on blockchain. "
            "This dashboard helps you find the best yielding RWA opportunities and build a "
            "diversified portfolio. **Pick a risk tier below, then explore the tabs.** "
            "Switch to Intermediate or Advanced in the sidebar to unlock more detail."
        )
    with _wb2:
        if st.button("✕", key="_rwa_dismiss_welcome", help="Dismiss welcome message"):
            st.session_state["_rwa_welcome_dismissed"] = True
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MARKET TICKER BAR
# ─────────────────────────────────────────────────────────────────────────────

market = _load_market_summary()
_macro_regime_data = _load_macro_regime()   # fetch_macro_regime() — enhanced signal-scored classifier
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
# Use fetch_macro_regime() when available; fall back to get_market_summary() value
_regime   = _macro_regime_data.get("regime") or market.get("macro_regime", "NEUTRAL")
_regime_confidence  = _macro_regime_data.get("confidence", 0.0)
_regime_score       = _macro_regime_data.get("score", 0)
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
    _conf_pct = int(_regime_confidence * 100) if _regime_confidence else 0
    _score_lbl = f"Score: {int(_regime_score):+d}" if _regime_score != 0 else "Score: 0"
    st.markdown(f"""
    <div style="background:{_rc[0]};border:1px solid {_rc[1]}40;border-radius:8px;
                padding:10px 14px;text-align:center;">
        <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.1em">Macro Regime</div>
        <div style="font-size:18px;font-weight:800;color:{_rc[1]}">{_rc[2]} {_regime}</div>
        <div style="font-size:11px;color:{_rc[1]}">Bias: {_bias}</div>
        <div style="font-size:10px;color:#9CA3AF;margin-top:2px">{_score_lbl} · Confidence: {_conf_pct}%</div>
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
            width="stretch",
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

# ── Mode row — Demo toggle + user level badge ─────────────────────────────────
_mode_col2, _mode_spacer = st.columns([2, 8])
with _mode_col2:
    _demo = st.toggle(
        "Demo / Sandbox",
        value=st.session_state["demo_mode"],
        key="demo_mode_toggle",
        help="Demo mode: uses synthetic placeholder data — no real API calls made. Safe for screenshots, demos, and onboarding.",
    )
    st.session_state["demo_mode"] = _demo
    if _demo:
        st.markdown('<div style="font-size:10px;color:#FBBF24;margin-top:-6px">⚠️ DEMO — synthetic data only</div>', unsafe_allow_html=True)

_pro_mode  = st.session_state["pro_mode"]   # True when user_level == "advanced"
_demo_mode = st.session_state["demo_mode"]
_user_level = st.session_state.get("user_level", "beginner")

# ── Level UX panels (item 35) — scaled orientation for each level ────────────
if _user_level == "beginner":
    st.markdown(
        "<div style='background:rgba(0,212,170,0.06);border:1px solid rgba(0,212,170,0.18);"
        "border-radius:8px;padding:8px 14px;font-size:0.79rem;color:#99f6e4;margin-bottom:8px'>"
        "📊 <b>Beginner Mode</b> — plain-English explanations throughout. "
        "Tooltips (ⓘ) appear on all technical terms. "
        "Switch to <b>Intermediate</b> or <b>Advanced</b> in the sidebar for more detail."
        "</div>",
        unsafe_allow_html=True,
    )
elif _user_level == "intermediate":
    st.markdown(
        "<div style='background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.18);"
        "border-radius:8px;padding:6px 14px;font-size:0.75rem;color:#fde68a;margin-bottom:6px'>"
        "🟡 <b>Intermediate Mode</b> — key numbers shown with condensed explanations. "
        "Switch to <b>Advanced</b> for full technical detail."
        "</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCREENER CACHE — defined here (module-level) so it is registered once per
# process and NOT re-registered on every Streamlit render cycle.
# ─────────────────────────────────────────────────────────────────────────────

from data_feeds import compute_screener_signals as _compute_screener_signals
from data_feeds import fetch_binance_ohlcv as _fetch_binance_ohlcv

# Item 39: Full 37-coin screener universe per CLAUDE.md
# Must-have coins always included; top-30 fetched dynamically from CoinGecko
_SCR_MUST_HAVE_SYMS = ["XRPUSDT", "XLMUSDT", "XDCUSDT", "HBARUSDT"]  # SHX/ZBCN: low Binance liquidity; CC: not on Binance

_SCR_TOP30_FALLBACK = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT",
    "TRXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT", "NEARUSDT", "UNIUSDT",
    "ATOMUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT",
    "TONUSDT", "SEIUSDT", "TIAUSDT", "STXUSDT", "FETUSDT", "IMXUSDT", "WLDUSDT",
    "AAVEUSDT", "MKRUSDT",
]

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_top30_screener_syms() -> list:
    """Fetch top 30 non-stablecoin coins from CoinGecko, mapped to Binance USDT pairs."""
    _STABLES = {"USDT","USDC","DAI","BUSD","TUSD","FDUSD","USDD","FRAX","GUSD","USDP","PYUSD"}
    _MUST    = {"XRP","XLM","XDC","HBAR","SHX","ZBCN"}
    try:
        _df._COINGECKO_LIMITER.acquire()
        resp = _df._session.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency":"usd","order":"market_cap_desc","per_page":60,"page":1},
            timeout=8,
        )
        if resp.status_code != 200:
            return _SCR_TOP30_FALLBACK
        top30, seen = [], set()
        for coin in resp.json():
            sym = (coin.get("symbol") or "").upper()
            if sym in _STABLES or sym in _MUST or sym in seen:
                continue
            seen.add(sym)
            top30.append(sym + "USDT")
            if len(top30) >= 30:
                break
        return top30 or _SCR_TOP30_FALLBACK
    except Exception:
        return _SCR_TOP30_FALLBACK

@st.cache_data(ttl=300, show_spinner=False)
def _load_screener_signals():
    # OPT-9: pre-fetch BTC bars once to avoid redundant HTTP calls per symbol
    _top30 = _fetch_top30_screener_syms()
    _syms  = list(dict.fromkeys(_SCR_MUST_HAVE_SYMS + _top30))
    _btc_bars = _fetch_binance_ohlcv("BTCUSDT", "1d", 35)
    return {sym: _compute_screener_signals(sym, btc_bars=_btc_bars) for sym in _syms}


# ─────────────────────────────────────────────────────────────────────────────
# OPT-12: Module-level portfolio cache — avoids storing large dicts in
# st.session_state (which causes serialization overhead on every rerun).
# _load_all_portfolios is already @st.cache_data(ttl=300) so calling it here
# is a cache lookup only; the heavy rebuild only runs when the TTL expires.
# Keep only lightweight scalars (ts, value key) in session_state.
# ─────────────────────────────────────────────────────────────────────────────
_all_ports, _comp_df = _load_all_portfolios(portfolio_value)
# Lightweight session_state markers so other components can detect staleness
st.session_state["portfolio_ts"]        = time.time()
st.session_state["portfolio_value_key"] = portfolio_value


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────────────────────

# ── #39 Anomaly Detection Banners (persistent — visible on all tabs) ─────────────
try:
    _anomalies = _df.detect_anomalies()
    _critical  = [a for a in _anomalies if a.get("severity") == "CRITICAL"]
    _warnings  = [a for a in _anomalies if a.get("severity") == "WARNING"]
    for _anom in _critical:
        st.error(
            f"CRITICAL TVL DROP — {_anom['asset_name']}: "
            f"{_anom['pct_change']:+.1f}% "
            f"(${abs(_anom.get('abs_drop_usd', 0)) / 1e6:.1f}M drop) "
            f"vs 24h baseline"
        )
    for _anom in _warnings:
        st.warning(
            f"TVL Warning — {_anom['asset_name']}: "
            f"{_anom['pct_change']:+.1f}% "
            f"(${abs(_anom.get('abs_drop_usd', 0)) / 1e6:.1f}M drop) "
            f"vs 24h baseline"
        )
except Exception as _anom_err:
    logger.debug("[UI] Anomaly detection skipped: %s", _anom_err)


tab_portfolio, tab_universe, tab_yield, tab_compare, tab_ai, tab_news, tab_trades, tab_reg, tab_screener, tab_research = st.tabs([
    "📊 Portfolio",
    "🌐 Asset Universe",
    "🌾 Yield Strategies",
    "📈 Compare Tiers",
    "🤖 AI Agent",
    "📰 News Feed",
    "📋 Trade Log",
    "🏛️ Regulatory",
    "🔍 Screener",
    "🔬 Research",
])



# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════

with tab_portfolio:
    # F6: freshness badge for portfolio data sources
    _port_badges = " &nbsp; ".join([
        _freshness_badge("coingecko_prices", 300, "Prices"),
        _freshness_badge("defillama_yields", 3600, "Yields"),
    ])
    st.markdown(_port_badges, unsafe_allow_html=True)

    portfolio = _load_portfolio(selected_tier, portfolio_value)
    if _demo_mode:
        # Demo mode: inject synthetic portfolio data so no real API call is needed
        metrics = {
            "weighted_yield_pct": 6.8, "annual_return_usd": 6800, "monthly_income_usd": 567,
            "sharpe_ratio": 1.42, "max_drawdown_pct": 8.2, "var_95_pct": 4.1,
            "sortino_ratio": 1.85, "calmar_ratio": 0.83, "var_99_pct": 6.3,
            "cvar_95_pct": 5.5, "diversification_ratio": 1.18,
        }
        holdings = [
            {"id": "DEMO_TBILL", "name": "Demo T-Bill", "category": "US Treasuries", "chain": "Ethereum",
             "weight_pct": 30.0, "usd_value": 30000, "current_yield_pct": 5.2, "risk_score": 2,
             "liquidity_score": 9, "regulatory_score": 9, "score": 88, "redemption_days": 1},
            {"id": "DEMO_CREDIT", "name": "Demo Credit", "category": "Private Credit", "chain": "Polygon",
             "weight_pct": 25.0, "usd_value": 25000, "current_yield_pct": 9.1, "risk_score": 6,
             "liquidity_score": 5, "regulatory_score": 7, "score": 74, "redemption_days": 30},
            {"id": "DEMO_RE", "name": "Demo Real Estate", "category": "Real Estate", "chain": "Ethereum",
             "weight_pct": 20.0, "usd_value": 20000, "current_yield_pct": 7.5, "risk_score": 5,
             "liquidity_score": 4, "regulatory_score": 7, "score": 71, "redemption_days": 90},
        ]
        cat_sum = {
            "US Treasuries": {"weight_pct": 30, "yield_pct": 5.2, "count": 1, "color": "#00D4FF"},
            "Private Credit": {"weight_pct": 25, "yield_pct": 9.1, "count": 1, "color": "#F97316"},
            "Real Estate":    {"weight_pct": 20, "yield_pct": 7.5, "count": 1, "color": "#A78BFA"},
        }
    elif not portfolio:
        st.warning("Loading portfolio data... Please wait or click Refresh Now.")
        metrics, holdings, cat_sum = {}, [], {}
    else:
        metrics  = portfolio.get("metrics", {})
        holdings = portfolio.get("holdings", [])
        cat_sum  = portfolio.get("category_summary", {})

    # ── Portfolio Health Score (#63) ─────────────────────────────────────────
    if metrics or holdings:
        try:
            from ai_agent import compute_portfolio_health_score
            _health = compute_portfolio_health_score(metrics, holdings)
        except Exception as _e:
            logger.warning("Health score failed: %s", _e)
            _health = None
        if _health:
            _h_score = _health["score"]
            _h_grade = _health["grade"]
            _h_color = _health["color"]
            _h_bar_w = int(_h_score)
        else:
            _h_score, _h_grade, _h_color, _h_bar_w = 0, "—", "#6B7280", 0

        st.markdown(
            f"""<div style="background:#111827;border:1px solid #1F2937;border-radius:10px;
                            padding:12px 18px;margin-bottom:14px;display:flex;align-items:center;gap:18px">
                <div style="min-width:64px;text-align:center">
                    <div style="font-size:32px;font-weight:900;color:{_h_color};line-height:1">{_h_grade}</div>
                    <div style="font-size:10px;color:#6B7280;margin-top:2px">HEALTH</div>
                </div>
                <div style="flex:1">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <span style="font-size:13px;font-weight:600;color:#E2E8F0">Portfolio Health Score</span>
                        <span style="font-size:13px;font-weight:700;color:{_h_color}">{_h_score:.0f} / 100</span>
                    </div>
                    <div style="background:#1F2937;border-radius:4px;height:8px;overflow:hidden">
                        <div style="background:{_h_color};width:{_h_bar_w}%;height:100%;border-radius:4px;
                                    transition:width 0.4s ease"></div>
                    </div>
                    <div style="font-size:10px;color:#6B7280;margin-top:4px">{(_health or {}).get("breakdown", "")}</div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── 30-Second AI Briefing (#64) ──────────────────────────────────────────
    if metrics and FEATURES["anthropic"]:
        _regime_nm  = _regime  # captured above from fetch_macro_regime / market fallback
        _brief_key  = (
            f"brief_{selected_tier}_{round(metrics.get('weighted_yield_pct', 0), 1)}"
            f"_{round(metrics.get('sharpe_ratio', 0), 2)}_{len(holdings)}_{_regime_nm}"
        )
        if _demo_mode:
            _briefing_text = (
                "Your demo portfolio is well-balanced across US Treasuries, Private Credit, and Real Estate "
                "with a blended yield of 6.8% and a solid Sharpe ratio of 1.42. "
                "The main opportunity is in Private Credit at 9.1% yield, while Real Estate redemption "
                "windows of 90 days are the key liquidity risk to watch. [DEMO MODE]"
            )
        elif _brief_key not in st.session_state:
            with st.spinner("Generating AI briefing…"):
                try:
                    from ai_agent import generate_ai_briefing
                    _portfolio_data = {"tier": selected_tier, "metrics": metrics, "holdings": holdings}
                    _briefing_text = generate_ai_briefing(
                        portfolio_data=_portfolio_data,
                        market_data=market,
                        regime=_macro_regime_data,
                    )
                except Exception as _be:
                    logger.warning("Briefing failed: %s", _be)
                    # Fall back to legacy briefing
                    try:
                        from ai_agent import get_30sec_briefing
                        _briefing_text = get_30sec_briefing(selected_tier, metrics, holdings)
                    except Exception:
                        _briefing_text = ""
                st.session_state[_brief_key] = _briefing_text
        else:
            _briefing_text = st.session_state[_brief_key]

        if _briefing_text:
            _brief_accent = {
                "RISK_ON": "#34D399", "RISK_OFF": "#F97316",
                "STAGFLATION": "#FBBF24", "LIQUIDITY_CRUNCH": "#818CF8",
            }.get(_regime_nm, "#6366f1")
            st.markdown(
                f"""<div style="background:#0D1117;border:1px solid #1F2937;border-left:3px solid {_brief_accent};
                                border-radius:8px;padding:12px 16px;margin-bottom:14px">
                    <div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.08em;
                                margin-bottom:6px">🤖 AI BRIEFING · 30-SEC SUMMARY</div>
                    <div style="font-size:13px;color:#D1D5DB;line-height:1.55">{_briefing_text}</div>
                </div>""",
                unsafe_allow_html=True,
            )

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
        if _pro_mode:
            _metric_card("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}",
                         color=_color_for_value(metrics.get("sharpe_ratio", 0), 0, 2),
                         tooltip="Risk-adjusted return = (portfolio yield − risk-free rate) ÷ volatility. Above 1.0 is good, above 2.0 is excellent")
        else:
            _sr = metrics.get("sharpe_ratio", 0) or 0
            _sr_label = "Excellent" if _sr >= 1.5 else "Good" if _sr >= 1.0 else "Fair" if _sr >= 0.5 else "Weak"
            _sr_color = "#34D399" if _sr >= 1.5 else "#A3E635" if _sr >= 1.0 else "#FBBF24" if _sr >= 0.5 else "#EF4444"
            _metric_card("Risk Quality", _sr_label, color=_sr_color,
                         tooltip="Overall risk-adjusted quality: Excellent = great return for the risk taken. Fair/Weak = lower reward for the risk.")
    with k5:
        if _pro_mode:
            _metric_card("Max Drawdown", _fmt_pct(metrics.get("max_drawdown_pct")),
                         color=_color_for_value(metrics.get("max_drawdown_pct", 0), 0, 30, invert=True),
                         tooltip="Largest estimated peak-to-trough portfolio decline under stress conditions. Lower is better. This tier targets ≤" + str(tier_cfg['max_drawdown_pct']) + "%")
        else:
            _dd = metrics.get("max_drawdown_pct", 0) or 0
            _dd_label = "Low Risk" if _dd <= 5 else "Moderate" if _dd <= 15 else "High Risk"
            _dd_color = "#34D399" if _dd <= 5 else "#FBBF24" if _dd <= 15 else "#EF4444"
            _metric_card("Downside Risk", _dd_label, color=_dd_color,
                         tooltip="How much the portfolio could fall in a bad scenario. Low Risk = protected capital, High Risk = larger potential losses.")
    with k6:
        if _pro_mode:
            _metric_card("VaR 95%", _fmt_pct(metrics.get("var_95_pct")),
                         color=_color_for_value(metrics.get("var_95_pct", 0), 0, 20, invert=True),
                         tooltip="Value at Risk (95%): estimated maximum portfolio loss on a bad day — this threshold is only exceeded 5% of the time")
        else:
            _holdings_count = len(holdings)
            _metric_card("Assets Held", str(_holdings_count),
                         tooltip="Number of different assets in your portfolio. More assets = better diversification across risk categories.")

    st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)

    # ── RWA Market Context (#94 / #101) ─────────────────────────────────────────
    # On-chain RWA TVL via fetch_rwaxyz_tvl() (DeFiLlama RWA proxy)
    # Falls back to get_total_rwa_tvl() then RWA_ONCHAIN_USD config baseline
    _OFF_CHAIN_TAM_B  = RWA_TAM_USD / 1e9          # $360B
    _BCG_2030_T       = RWA_MILESTONES["target_2030"] / 1e12   # $16T
    _ONCHAIN_FALLBACK = RWA_ONCHAIN_USD / 1e9       # $15B fallback
    try:
        if _demo_mode:
            _rwa_tvl = 18_400_000_000
            _rwaxyz_data = None
        else:
            _rwaxyz_data = _df.fetch_rwaxyz_tvl()
            _rwa_tvl = _rwaxyz_data.get("total_rwa_tvl", 0) or 0
            if _rwa_tvl == 0:
                _rwa_tvl = _df.get_total_rwa_tvl()
    except Exception:
        _rwa_tvl = 0.0
        _rwaxyz_data = None
    _rwa_tvl_b = (_rwa_tvl / 1e9) if _rwa_tvl > 0 else _ONCHAIN_FALLBACK
    if _rwa_tvl_b > 0:
        _pen_pct       = round(_rwa_tvl_b / _OFF_CHAIN_TAM_B * 100, 2)
        _bcg_pct       = round(_rwa_tvl_b / (_BCG_2030_T * 1000) * 100, 4)  # % of $16T (T→B)
        _pen_color     = "#34D399" if _pen_pct >= 5 else "#FBBF24" if _pen_pct >= 1 else "#9CA3AF"
        _bar_width_pct = min(_pen_pct * 4, 100)
        st.markdown(
            f"""<div style="background:linear-gradient(135deg,#111827,#0D1117);
                            border:1px solid #1F2937;border-radius:10px;
                            padding:14px 18px;margin-bottom:14px">
                <div style="font-size:11px;color:#6B7280;text-transform:uppercase;
                            letter-spacing:0.08em;margin-bottom:8px">
                    RWA Market Context
                </div>
                <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
                    <div style="min-width:64px;text-align:center">
                        <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.6px">On-Chain</div>
                        <div style="font-size:20px;font-weight:800;color:{_pen_color}">${_rwa_tvl_b:.1f}B</div>
                    </div>
                    <div style="flex:1;min-width:200px">
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                            <span style="font-size:12px;font-weight:600;color:#E2E8F0">Total On-Chain RWA</span>
                            <span style="font-size:12px;color:{_pen_color};font-weight:700">{_pen_pct:.2f}% tokenized</span>
                        </div>
                        <div style="background:#1F2937;border-radius:3px;height:5px;overflow:hidden;margin-bottom:6px">
                            <div style="background:linear-gradient(90deg,{_pen_color},{_pen_color}88);
                                        width:{_bar_width_pct:.0f}%;height:100%;border-radius:3px"></div>
                        </div>
                        <div style="font-size:10px;color:#4B5563;">
                            <b style="color:#9CA3AF">${_rwa_tvl_b:.1f}B</b> on-chain
                            &nbsp;/&nbsp; <b style="color:#6B7280">${_OFF_CHAIN_TAM_B:.0f}B TAM</b>
                            &nbsp;=&nbsp; <b style="color:{_pen_color}">{_pen_pct:.2f}% tokenized</b>
                        </div>
                        <div style="font-size:10px;color:#374151;margin-top:3px">
                            BCG projects $16T by 2030 — we are at
                            <b style="color:#6366f1">{_bcg_pct:.2f}%</b> of that target
                        </div>
                    </div>
                    <div style="font-size:10px;color:#374151;text-align:right;min-width:80px">
                        Source:<br>DeFiLlama RWA<br>BCG/RWA.xyz 2026
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Charts Row ───────────────────────────────────────────────────────────
    chart_left, chart_right = st.columns([5, 7])

    with chart_left:
        st.markdown('<div class="section-header">Allocation by Category</div>', unsafe_allow_html=True)
        # F3: chart view toggle — pie or treemap
        _chart_view = st.radio("View", ["Donut", "Treemap"], horizontal=True,
                               key="port_chart_view", label_visibility="collapsed")
        if cat_sum:
            if _chart_view == "Donut":
                # UPGRADE 21: use cached chart builder
                _weighted_yield = float(metrics.get("weighted_yield_pct") or 0)
                fig_pie = _build_pie_chart(cat_sum, _weighted_yield)
                st.plotly_chart(fig_pie, width="stretch")
            else:
                # F3: Treemap — holdings sized by weight, colored by yield
                if holdings:
                    _tm_df = pd.DataFrame(holdings)
                    _tm_cols = {"name", "category", "weight_pct", "current_yield_pct"}
                    if _tm_cols.issubset(_tm_df.columns):
                        _tm_df = _tm_df[_tm_df["weight_pct"].fillna(0) > 0].copy()
                        _tm_df["yield_pct"] = _tm_df["current_yield_pct"].fillna(0)
                        _tm_df["label"] = (
                            _tm_df["name"].str[:20] + "<br>"
                            + _tm_df["weight_pct"].apply(lambda x: f"{x:.1f}%")
                            + " · " + _tm_df["yield_pct"].apply(lambda x: f"{x:.1f}% APY")
                        )
                        _tm_fig = px.treemap(
                            _tm_df,
                            path=[px.Constant("Portfolio"), "category", "name"],
                            values="weight_pct",
                            color="yield_pct",
                            color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#22c55e"]],
                            color_continuous_midpoint=float(_tm_df["yield_pct"].median()),
                            custom_data=["yield_pct", "weight_pct"],
                            title="Portfolio Holdings Treemap — Size: Weight %, Color: Yield %",
                        )
                        _tm_fig.update_traces(
                            hovertemplate="<b>%{label}</b><br>Weight: %{customdata[1]:.1f}%<br>Yield: %{customdata[0]:.2f}%<extra></extra>"
                        )
                        _tm_fig.update_layout(
                            template="plotly_dark",
                            margin=dict(l=0, r=0, t=40, b=0),
                            coloraxis_colorbar=dict(title="Yield %", tickformat=".1f"),
                        )
                        st.plotly_chart(_tm_fig, width="stretch")

    with chart_right:
        st.markdown('<div class="section-header">Holdings — Yield vs Risk</div>', unsafe_allow_html=True)
        if holdings:
            # UPGRADE 21: use cached chart builder
            fig_scatter = _build_holdings_scatter(holdings)
            st.plotly_chart(fig_scatter, width="stretch")

    # ── Holdings Table ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Portfolio Holdings</div>', unsafe_allow_html=True)
    if holdings:
        h_df = pd.DataFrame(holdings)
        # Add redemption label column (#66)
        if "redemption_days" in h_df.columns:
            def _redeem_label(d):
                try:
                    d = int(d)
                    if d < 0:    return "—"
                    if d == 0:   return "Instant"
                    if d == 1:   return "1 day"
                    if d <= 30:  return f"{d} days"
                    return f"{d}d (illiquid)"
                except Exception:
                    return "—"
            h_df["redemption_label"] = h_df["redemption_days"].apply(_redeem_label)

        if _pro_mode:
            display_col_map = {
                "id": "ID", "name": "Name", "category": "Category", "chain": "Chain",
                "weight_pct": "Weight %", "usd_value": "USD Value",
                "current_yield_pct": "Yield %", "redemption_label": "Redeem",
                "risk_score": "Risk", "liquidity_score": "Liquidity",
                "regulatory_score": "Regulatory", "score": "Score",
            }
        else:
            display_col_map = {
                "name": "Asset", "category": "Category",
                "weight_pct": "Weight %", "usd_value": "USD Value",
                "current_yield_pct": "Yield %", "redemption_label": "Redeem",
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
        st.dataframe(styled, width="stretch", height=min(400, 55 + 35 * len(display_df)))
        # F5: CSV export for portfolio holdings
        _csv_button(display_df, "portfolio_holdings.csv", "⬇ Export Holdings CSV",
                    key="csv_holdings_table")

    # ── Yield Breakdown Bar Chart (Phase 7 UI) ───────────────────────────────
    # OPT-14: figure construction wrapped in @st.cache_data via _build_yield_bar()
    if holdings:
        _h_df_yb = pd.DataFrame(holdings)
        _yb_cols_needed = {"name", "current_yield_pct", "category", "weight_pct"}
        if _yb_cols_needed.issubset(set(_h_df_yb.columns)):
            _yb = _h_df_yb[_h_df_yb["current_yield_pct"].fillna(0) > 0]
            _yb = _yb.nlargest(12, "current_yield_pct")
            if not _yb.empty:
                st.markdown('<div class="section-header">Top Holdings by Yield</div>', unsafe_allow_html=True)
                _yb_records = tuple(
                    zip(_yb["name"].tolist(), _yb["current_yield_pct"].tolist(),
                        _yb["category"].tolist(), _yb["weight_pct"].tolist())
                )
                _avg_yield = float(metrics.get("weighted_yield_pct", 0))
                _fig_ybar = _build_yield_bar(_yb_records, _avg_yield)
                st.plotly_chart(_fig_ybar, width="stretch")

    # ── Risk Metrics (Pro mode only) ───────────────────────────────────────────
    if _pro_mode:
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

    # ── MTF Confidence per Asset (Pro Mode only) (#53) ───────────────────────
    if _pro_mode and holdings:
        st.markdown('<div class="section-header">Multi-Timeframe Confidence (Pro)</div>',
                    unsafe_allow_html=True)
        st.caption("MTF confidence: 1H(10%) · 4H(20%) · 1D(35%) · 1W(35%). "
                   "RWA assets use macro regime + NAV premium/discount as proxy.")
        _mtf_cols = st.columns(min(len(holdings), 4))
        for _mi, _h in enumerate(holdings[:8]):
            _col_idx = _mi % 4
            with _mtf_cols[_col_idx]:
                try:
                    _price_data = {
                        "price":      _h.get("current_price") or _h.get("price") or 0,
                        "nav_usd":    _h.get("nav_usd") or 0,
                    }
                    _mtf = _df.compute_mtf_confidence(_h.get("id", ""), _price_data)
                    _conf = _mtf.get("confidence", 0.5)
                    _trend = _mtf.get("trend", "NEUTRAL")
                    _tfs   = _mtf.get("timeframes", {})
                    _dom_tf = _mtf.get("dominant_tf", "1D")
                    _trend_color = "#34D399" if _trend == "BULLISH" else "#EF4444" if _trend == "BEARISH" else "#9CA3AF"
                    _bar_w = int(_conf * 100)
                    # 4-segment visual: one segment per timeframe
                    _seg_html = ""
                    for _tf_nm, _tf_w in [("1H", 10), ("4H", 20), ("1D", 35), ("1W", 35)]:
                        _tf_v = _tfs.get(_tf_nm, 0.5)
                        _seg_c = "#34D399" if _tf_v >= 0.65 else "#EF4444" if _tf_v <= 0.35 else "#9CA3AF"
                        _seg_html += (
                            f'<div style="flex:{_tf_w};background:{_seg_c}20;border:1px solid {_seg_c}60;'
                            f'border-radius:3px;padding:3px 0;text-align:center;font-size:9px;color:{_seg_c}">'
                            f'{_tf_nm}</div>'
                        )
                    st.markdown(f"""
<div style="background:#111827;border:1px solid #1F2937;border-radius:8px;padding:10px 12px;margin-bottom:8px">
  <div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px">
    {_h.get('token_symbol') or _h.get('id','?')}
  </div>
  <div style="font-size:16px;font-weight:800;color:{_trend_color}">{_trend}</div>
  <div style="font-size:10px;color:#9CA3AF;margin-bottom:6px">Conf: {_bar_w}% · Dom: {_dom_tf}</div>
  <div style="background:#1F2937;border-radius:3px;height:4px;overflow:hidden;margin-bottom:6px">
    <div style="background:{_trend_color};width:{_bar_w}%;height:100%;border-radius:3px"></div>
  </div>
  <div style="display:flex;gap:3px">{_seg_html}</div>
</div>""", unsafe_allow_html=True)
                except Exception as _mtf_err:
                    logger.debug("[MTF UI] %s: %s", _h.get("id"), _mtf_err)
        if len(holdings) > 8:
            st.caption(f"Showing 8 of {len(holdings)} holdings. All assets use macro regime proxy for RWA confidence.")

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
                st.plotly_chart(fig_mc, width="stretch")

    # ── Duration / Interest Rate Risk ────────────────────────────────────────
    if holdings:
        try:
            from portfolio import calculate_portfolio_duration

            st.markdown('<div class="section-header">Interest Rate Risk (Duration &amp; DV01)</div>',
                        unsafe_allow_html=True)
            # Item 37: beginner plain-English explanation
            if st.session_state.get("user_level", "beginner") == "beginner":
                st.info(
                    "📐 **What is Duration?** Duration tells you how sensitive your portfolio is to "
                    "interest rate changes. A 5-year duration means: if rates rise by 1%, your portfolio "
                    "value drops roughly 5%. Lower duration = safer when rates are rising. "
                    "**DV01** = how many dollars you lose per $1M invested if rates rise by just 0.01%."
                )
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
                    curve = _load_treasury_yield_curve()   # OPT-6: cached 300s
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
                    width="stretch",
                    height=280,
                )

                # F2: DV01 by category visualization
                _dur_by_cat: dict = {}
                for hd in dur.get("holdings_duration", []):
                    cat   = hd.get("category", "Other")
                    w_pct = hd.get("weight_pct", 0) / 100
                    dur_y = hd.get("duration_years", 0)
                    _dv01_asset = portfolio_value * w_pct * dur_y * 0.0001
                    _dur_by_cat[cat] = _dur_by_cat.get(cat, 0) + _dv01_asset

                if _dur_by_cat:
                    _dbc_df = pd.DataFrame([
                        {"Category": k, "DV01 ($)": round(v, 2)}
                        for k, v in sorted(_dur_by_cat.items(), key=lambda x: -x[1])
                        if v > 0
                    ])
                    if not _dbc_df.empty:
                        _dbc_fig = px.bar(
                            _dbc_df, x="DV01 ($)", y="Category", orientation="h",
                            title="DV01 by Category — $ loss per 1bp rate rise",
                            color_discrete_sequence=["#00d4aa"],
                            template="plotly_dark",
                        )
                        _dbc_fig.update_layout(height=max(200, 50 * len(_dbc_df)),
                                               margin=dict(l=0, r=0, t=40, b=0))
                        st.plotly_chart(_dbc_fig, width="stretch")

                # Duration breakdown with DV01 per asset
                with st.expander("Duration by Holding — DV01 Detail", expanded=False):
                    hdur_df = pd.DataFrame(dur["holdings_duration"])
                    if not hdur_df.empty:
                        # F2: compute per-asset DV01
                        hdur_df["dv01_usd"] = (
                            portfolio_value
                            * (hdur_df["weight_pct"] / 100)
                            * hdur_df["duration_years"]
                            * 0.0001
                        ).round(2)
                        hdur_display = hdur_df[["id", "category", "weight_pct",
                                                 "duration_years", "contribution_years",
                                                 "dv01_usd"]].rename(columns={
                            "id": "Asset", "category": "Category",
                            "weight_pct": "Weight %",
                            "duration_years": "Duration (yrs)",
                            "contribution_years": "Contribution (yrs)",
                            "dv01_usd": "DV01 ($)",
                        })
                        st.dataframe(
                            hdur_display.style.format({
                                "Weight %": "{:.1f}",
                                "Duration (yrs)": "{:.2f}",
                                "Contribution (yrs)": "{:.4f}",
                                "DV01 ($)": "${:,.2f}",
                            }),
                            width="stretch",
                        )
                        # F5: CSV export for DV01 per asset table
                        _csv_button(hdur_display, "dv01_by_holding.csv",
                                    "⬇ Export DV01 CSV", key="csv_dv01_holding")
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
                st.plotly_chart(fig_liq, width="stretch")
        except Exception as e:
            logger.warning("[UI] Liquidity section failed: %s", e)

    # ── Private Credit Early Warnings ────────────────────────────────────────
    try:
        pc_warnings = _load_private_credit_warnings()
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

    # ── #38 Scenario Simulation ───────────────────────────────────────────────
    with st.expander("Scenario Simulation", expanded=False):
        st.markdown(
            '<div style="font-size:12px;color:#9CA3AF;margin-bottom:10px">'
            'Enter macro shock parameters to estimate portfolio-level impact across all RWA assets. '
            'Positive HY spread and Fed rate = tightening. Negative M2 = liquidity contraction.'
            '</div>',
            unsafe_allow_html=True,
        )
        _sc_col1, _sc_col2, _sc_col3, _sc_col4 = st.columns(4)
        with _sc_col1:
            _sc_hy = st.number_input(
                "HY Spread Change (bps)", min_value=-500, max_value=500, value=0, step=25,
                key="sc_hy_spread",
                help="High-yield credit spread change in basis points. +200 = stress scenario",
            )
        with _sc_col2:
            _sc_fed = st.number_input(
                "Fed Rate Change (bps)", min_value=-200, max_value=200, value=0, step=25,
                key="sc_fed_rate",
                help="Federal funds rate change in basis points. +50 = one Fed hike",
            )
        with _sc_col3:
            _sc_m2 = st.number_input(
                "M2 Change (%)", min_value=-15.0, max_value=15.0, value=0.0, step=0.5,
                key="sc_m2",
                help="M2 money supply % change. Negative = liquidity tightening",
            )
        with _sc_col4:
            _sc_vix = st.number_input(
                "VIX Change (pts)", min_value=-20, max_value=40, value=0, step=5,
                key="sc_vix",
                help="VIX volatility index point change. +10 = elevated fear environment",
            )

        if abs(_sc_hy) >= 400:
            st.warning("HY spread change >= 400bp is extreme — results may be unreliable")

        if st.button("Run Scenario", key="btn_run_scenario", width="content"):
            _shocks = {
                "hy_spread_bps": _sc_hy,
                "fed_rate_bps":  _sc_fed,
                "m2_pct":        _sc_m2,
                "vix_change":    _sc_vix,
            }
            with st.spinner("Running scenario simulation..."):
                try:
                    _sim = _df.run_scenario_simulation(_shocks)
                except Exception as _sim_err:
                    logger.warning("[UI] Scenario sim error: %s", _sim_err)
                    _sim = None

            if _sim is None:
                st.error("Scenario simulation failed. Please try again.")
            else:
                _total_pct = _sim.get("total_portfolio_impact_pct", 0.0)
                _sc_color  = "#34D399" if _total_pct >= 0 else "#EF4444"
                _sc_arrow  = "▲" if _total_pct >= 0 else "▼"
                st.markdown(
                    f"""<div style="background:#111827;border:2px solid {_sc_color}40;
                        border-radius:10px;padding:14px 20px;margin:10px 0;text-align:center">
                        <div style="font-size:11px;color:#6B7280;text-transform:uppercase;
                                    letter-spacing:0.1em">Scenario: {_sim.get('scenario_name','')}</div>
                        <div style="font-size:32px;font-weight:900;color:{_sc_color}">
                            {_sc_arrow} {abs(_total_pct):.3f}%</div>
                        <div style="font-size:11px;color:#9CA3AF">
                            Estimated avg portfolio impact across {_sim.get('n_assets',0)} assets</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

                _sc_left, _sc_right = st.columns(2)
                with _sc_left:
                    st.markdown(
                        '<div style="font-size:12px;font-weight:700;color:#EF4444;'
                        'margin-bottom:6px">Most Impacted (Worst)</div>',
                        unsafe_allow_html=True,
                    )
                    _worst = _sim.get("worst_assets", [])
                    for _w in _worst[:5]:
                        _w_pct = _w.get("impact_pct", 0)
                        st.markdown(
                            f'<div style="background:#1F2937;border-radius:6px;padding:6px 10px;'
                            f'margin:3px 0;font-size:12px">'
                            f'<span style="color:#E2E8F0">{_w.get("name","")[:40]}</span>'
                            f'<span style="color:#EF4444;float:right;font-weight:700">'
                            f'{_w_pct:+.2f}%</span></div>',
                            unsafe_allow_html=True,
                        )

                with _sc_right:
                    st.markdown(
                        '<div style="font-size:12px;font-weight:700;color:#34D399;'
                        'margin-bottom:6px">Best Performers (Beneficiaries)</div>',
                        unsafe_allow_html=True,
                    )
                    _best = _sim.get("best_assets", [])
                    for _b in _best[:5]:
                        _b_pct = _b.get("impact_pct", 0)
                        st.markdown(
                            f'<div style="background:#1F2937;border-radius:6px;padding:6px 10px;'
                            f'margin:3px 0;font-size:12px">'
                            f'<span style="color:#E2E8F0">{_b.get("name","")[:40]}</span>'
                            f'<span style="color:#34D399;float:right;font-weight:700">'
                            f'{_b_pct:+.2f}%</span></div>',
                            unsafe_allow_html=True,
                        )

    # ── R3: Continuous Yield Accrual ─────────────────────────────────────────
    if holdings:
        try:
            st.markdown("---")
            st.markdown('<div class="section-header">Continuous Yield Accrual</div>', unsafe_allow_html=True)
            st.caption("Real-time yield accrual tracker — how much your portfolio earns over each time horizon")
            _accrual_rows = []
            for _h in holdings:
                _apy  = float(_h.get("current_yield_pct") or _h.get("expected_yield_pct") or 0)
                _usdv = float(_h.get("usd_value") or 0)
                if _usdv <= 0:
                    continue
                _daily   = _usdv * (_apy / 100) / 365
                _weekly  = _daily * 7
                _monthly = _daily * 30
                _annual  = _usdv * (_apy / 100)
                _accrual_rows.append({
                    "Asset": _h.get("name", _h.get("id", "?"))[:28],
                    "APY %": f"{_apy:.2f}%",
                    "Daily ($)": f"${_daily:,.2f}",
                    "Weekly ($)": f"${_weekly:,.2f}",
                    "Monthly ($)": f"${_monthly:,.2f}",
                    "Annual ($)": f"${_annual:,.0f}",
                    "_daily": _daily,
                    "_monthly": _monthly,
                })
            if _accrual_rows:
                _total_daily   = sum(r["_daily"]   for r in _accrual_rows)
                _total_monthly = sum(r["_monthly"] for r in _accrual_rows)
                _total_annual  = _total_daily * 365
                _a1, _a2, _a3 = st.columns(3)
                _a1.metric("Daily Accrual",   f"${_total_daily:,.2f}",   help="Total yield earned per calendar day at current APY rates")
                _a2.metric("Monthly Accrual", f"${_total_monthly:,.0f}", help="Total yield earned over 30 days at current APY rates")
                _a3.metric("Annual Accrual",  f"${_total_annual:,.0f}",  help="Projected full-year yield at current APY rates (not compounded)")
                # Bar chart — monthly income by asset
                _accrual_fig = go.Figure(go.Bar(
                    y=[r["Asset"]  for r in _accrual_rows],
                    x=[r["_monthly"] for r in _accrual_rows],
                    orientation="h",
                    marker_color="#00d4aa",
                    text=[r["Monthly ($)"] for r in _accrual_rows],
                    textposition="outside",
                ))
                _accrual_fig.update_layout(
                    height=max(200, 36 * len(_accrual_rows) + 60),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0", size=11),
                    margin=dict(l=0, r=80, t=20, b=0),
                    xaxis=dict(title="Monthly Income ($)", gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(_accrual_fig, width="stretch")
                # Table view
                _accrual_display = [{k: v for k, v in r.items() if not k.startswith("_")} for r in _accrual_rows]
                st.dataframe(pd.DataFrame(_accrual_display).set_index("Asset"), width="stretch")
                _user_level_r3 = st.session_state.get("user_level", "beginner")
                if _user_level_r3 == "beginner":
                    st.info("💡 **What does this mean for me?** This shows how much income your portfolio is generating every day, week, and month — even when you're not actively trading. These numbers assume interest rates stay the same and don't include compounding.")
        except Exception as _r3_err:
            logger.debug("[R3] Accrual panel skipped: %s", _r3_err)

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



    # ─── Wallet Intelligence & Cross-Chain Activity ──────────────────
    # ─── Wallet Address Input (#110) + ERC-3643 + Zerion ─────────────────────
    st.markdown("---")
    st.markdown("#### 👛 Wallet Intelligence")
    _wallet_input = st.text_input(
        "EVM Wallet Address",
        value=st.session_state.get("wallet_address", ""),
        placeholder="0x…",
        key="wallet_address_input",
        help="Enter an EVM-compatible wallet address (0x…) for ERC-3643 compliance checks and Zerion portfolio import.",
        max_chars=42,
    )
    # Sanitize: wallet addresses are hex strings (0x + 40 hex chars) — strip anything else
    _wallet_addr = _re_input.sub(r"[^0-9a-fA-Fx]", "", _wallet_input.strip())[:42]
    if _wallet_addr:
        st.session_state["wallet_address"] = _wallet_addr

    # ERC-3643 Compliance Check (#105)
    st.markdown("##### 🛡️ ERC-3643 / T-REX On-Chain Compliance")
    st.caption("Etherscan eth_call · isVerified(address) on BUIDL/OUSG — institutional compliance registry")

    _ERC3643_ADDRS = {
        "BUIDL": "0x7712c34205737192402172409a8F7ccef8aA2AEc",
        "OUSG":  "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92",
    }
    if _wallet_addr and (feature_enabled("onchainid") or feature_enabled("etherscan")):
        _compl = _compliance_check(_wallet_addr)
        _co_cols = st.columns(len(_compl))
        for _coi, (_sym, _cd) in enumerate(_compl.items()):
            _verified = _cd.get("is_verified")
            _co_lbl   = "VERIFIED" if _verified is True else ("NOT VERIFIED" if _verified is False else "—")
            _co_clr   = "#10b981" if _verified else ("#ef4444" if _verified is False else "#6b7280")
            with _co_cols[_coi]:
                st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;text-align:center">
  <div style="font-size:11px;color:#6b7280;margin-bottom:4px">{_sym}</div>
  <div style="font-size:18px;font-weight:700;color:{_co_clr}">{_co_lbl}</div>
  <div style="font-size:10px;color:#9ca3af">ERC-3643 isVerified</div>
</div>
""", unsafe_allow_html=True)
    elif not _wallet_addr:
        st.caption("Enter a wallet address above to check ERC-3643 compliance status.")
    else:
        st.caption("Set RWA_ETHERSCAN_API_KEY in .env to enable ERC-3643 compliance checks.")

    # ERC-3643 Eligibility Stub — #105 (Pro Mode)
    if st.session_state.get("pro_mode", False):
        with st.expander("🛡️ ERC-3643 Token Eligibility Check (Pro)", expanded=False):
            st.caption(
                "ERC-3643 (T-REX) is the institutional-grade token standard for regulated securities. "
                "Permissioned RWA tokens (BUIDL, OUSG, tokenized equity) use an Identity Registry contract "
                "to enforce KYC/AML compliance on-chain. Each transfer checks isVerified() against the "
                "investor's on-chain identity before allowing the transaction."
            )
            _el_token = st.text_input(
                "Token Contract Address",
                placeholder="0x… (e.g. BUIDL: 0x7712c34205737192402172409a8F7ccef8aA2AEc)",
                key="erc3643_token_addr",
                max_chars=42,
            )
            _el_token_clean = _re_input.sub(r"[^0-9a-fA-Fx]", "", (_el_token or "").strip())[:42]
            _el_wallet_clean = _wallet_addr  # reuse wallet from above

            if st.button("Check Eligibility", key="btn_erc3643_check"):
                if _el_token_clean and _el_wallet_clean:
                    _el_result = _df.check_erc3643_eligibility(_el_wallet_clean, _el_token_clean)
                    _el_v = _el_result.get("is_verified")
                    _el_clr = "#10b981" if _el_v is True else ("#ef4444" if _el_v is False else "#6b7280")
                    _el_lbl = "VERIFIED" if _el_v is True else ("NOT VERIFIED" if _el_v is False else "UNKNOWN")
                    st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:16px;margin-top:8px">
  <div style="font-size:13px;color:#6b7280">ERC-3643 isVerified() result</div>
  <div style="font-size:24px;font-weight:700;color:{_el_clr};margin:8px 0">{_el_lbl}</div>
  <div style="font-size:11px;color:#9ca3af">Standard: {_el_result.get("standard", "ERC-3643 (T-REX)")}</div>
  <div style="font-size:11px;color:#9ca3af">Source: {_el_result.get("source", "stub")}</div>
  <div style="font-size:11px;color:#4b5563;margin-top:8px">{_el_result.get("note", "")}</div>
</div>""", unsafe_allow_html=True)
                elif not _el_wallet_clean:
                    st.warning("Enter a wallet address in the EVM Wallet Address field above.")
                else:
                    st.warning("Enter a token contract address.")
            else:
                st.caption("Enter a wallet address above and a token address, then click Check Eligibility.")

    # Zerion Portfolio Import (#111)
    st.markdown("##### 🟣 Zerion On-Chain Portfolio")
    st.caption("Zerion API v1 · wallet positions across all EVM chains · Cached 3 min")

    if _wallet_addr and feature_enabled("zerion"):
        _zp = _zerion_portfolio(_wallet_addr)
        if _zp.get("source") in ("unavailable", "auth_error", "invalid_address"):
            st.caption(f"Zerion unavailable — {_zp.get('message', _zp.get('source', ''))}")
        else:
            _za, _zb, _zc = st.columns(3)
            _z_total  = _zp.get("total_usd", 0)
            _z_chains = _zp.get("chain_distribution", {})
            _z_npos   = len(_zp.get("positions", []))
            with _za:
                st.metric("Total Value", f"${_z_total:,.2f}" if _z_total else "—")
            with _zb:
                st.metric("Positions", str(_z_npos))
            with _zc:
                st.metric("Chains", str(len(_z_chains)))

            _z_pos = _zp.get("positions", [])
            if _z_pos:
                _z_rows = []
                for _zr in _z_pos[:20]:
                    _z_rows.append({
                        "Asset":  _zr.get("symbol", "—"),
                        "Chain":  _zr.get("chain", "—"),
                        "Value":  f"${_zr.get('value', 0):,.2f}",
                        "Amount": f"{_zr.get('qty', 0):.4f}",
                    })
                st.dataframe(pd.DataFrame(_z_rows), width="stretch", hide_index=True)
    elif not _wallet_addr:
        st.caption("Enter a wallet address above to load Zerion portfolio data.")
    else:
        st.caption("Set RWA_ZERION_API_KEY in .env to enable Zerion portfolio import.")

    # ─── Wormhole Cross-Chain VAA Activity (#113) ─────────────────────────────
    st.markdown("---")
    st.markdown("#### 🌉 Wormhole Cross-Chain Bridge Activity")
    st.caption("Wormhole Scan public API · Verified Action Approvals (VAAs) · RWA bridge flow tracker")

    _wh_chain_opts = {"Ethereum (2)": 2, "Solana (1)": 1, "BSC (4)": 4}
    _wh_sel = st.selectbox("Source Chain", list(_wh_chain_opts.keys()),
                           key="wh_chain_sel", index=0)
    _wh_chain_id = _wh_chain_opts[_wh_sel]
    _wh_data = _wh_vaas(_wh_chain_id)

    if _wh_data:
        _wh_rows = []
        for _wv in _wh_data:
            _ts_raw = _wv.get("timestamp", "")
            _ts_str = _ts_raw[:19].replace("T", " ") if _ts_raw else "—"
            _wh_rows.append({
                "Sequence":   _wv.get("sequence", "—"),
                "Emitter":    (_wv.get("emitter_address") or "")[:16] + "…",
                "Timestamp":  _ts_str,
                "Payload":    _wv.get("payload_type", 0),
                "Guardian":   _wv.get("guardian_set", 0),
                "Tx Hash":    (_wv.get("tx_hash") or "")[:16] + ("…" if _wv.get("tx_hash") else ""),
            })
        st.dataframe(pd.DataFrame(_wh_rows), width="stretch", hide_index=True)
        st.caption(f"{len(_wh_data)} VAAs · Chain ID {_wh_chain_id} · Wormhole Scan public API")
    else:
        st.caption("No recent VAA data found for this chain.")
# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: ASSET UNIVERSE
# ══════════════════════════════════════════════════════════════════════════════

with tab_universe:
    # F6: freshness badges
    st.markdown(
        " &nbsp; ".join([
            _freshness_badge("coingecko_prices", 300, "Prices"),
            _freshness_badge("defillama_yields", 3600, "DeFiLlama Yields"),
            _freshness_badge("defillama_protocols", 3600, "TVL"),
        ]),
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-header">Complete RWA Asset Universe</div>',
                unsafe_allow_html=True)

    # Filters
    _fsearch_col, f1, f2, f3, f4 = st.columns([2, 2, 1, 1, 2])
    with _fsearch_col:
        _raw_search = st.text_input("Search", placeholder="e.g. ONDO, treasury, real estate…",
                                    key="filter_search",
                                    help="Filter by asset name, ticker, or issuer (case-insensitive)")
        search_query = _sanitize_text_input(_raw_search, max_len=100)
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

    filtered_df = assets_df if not assets_df.empty else pd.DataFrame()  # UPGRADE 22: no copy needed — only sliced/reassigned
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
        # Category breakdown — UPGRADE 21: use cached chart builder
        cat_counts = filtered_df["category"].value_counts()
        fig_cats = _build_category_bar(
            tuple(cat_counts.index.tolist()),
            tuple(int(v) for v in cat_counts.values.tolist()),
        )
        st.plotly_chart(fig_cats, width="stretch")

        # Enrich with Net APY, composite liquidity, exit velocity, trust score
        # OPT-11: consolidated from 5 separate .apply() passes to 2 passes;
        #         _exit_score + _exit_label share a single get_exit_velocity_score() call per row.
        try:
            from data_feeds import normalize_yield_to_net_apy
            from portfolio import calculate_asset_liquidity_score
            from config import get_asset_fee_bps, get_exit_velocity_score, get_asset_trust_score
            def _enrich_row(row):
                """Single pass: compute all 4 enrichment columns for one row."""
                _id  = row.get("id", "")
                _cat = row.get("category", "")
                gross = row.get("current_yield_pct") or row.get("expected_yield_pct") or 0
                fee   = get_asset_fee_bps(_id, _cat)
                _ev   = get_exit_velocity_score(_id, _cat)
                return pd.Series({
                    "net_apy_pct":    normalize_yield_to_net_apy(float(gross), fee),
                    "liq_score_comp": calculate_asset_liquidity_score(
                                          _id, _cat, int(row.get("liquidity_score", 5) or 5)),
                    "exit_velocity":  _ev["score"],
                    "exit_label":     _ev["label"],
                    "trust_score":    get_asset_trust_score(_id, _cat)["trust_score"],
                })
            filtered_df = filtered_df.copy()
            _enriched = filtered_df.apply(_enrich_row, axis=1)
            filtered_df["net_apy_pct"]    = _enriched["net_apy_pct"]
            filtered_df["liq_score_comp"] = _enriched["liq_score_comp"]
            filtered_df["exit_velocity"]  = _enriched["exit_velocity"]
            filtered_df["exit_label"]     = _enriched["exit_label"]
            filtered_df["trust_score"]    = _enriched["trust_score"]
        except Exception:
            filtered_df["net_apy_pct"]    = filtered_df.get("current_yield_pct", 0)
            filtered_df["liq_score_comp"] = filtered_df.get("liquidity_score", 5)
            filtered_df["exit_velocity"]  = 50.0
            filtered_df["exit_label"]     = "MODERATE"
            filtered_df["trust_score"]    = 5.0

        # Add redemption_window column (#66) — "Yield | Redemption" display
        def _redeem_window(row):
            return get_redemption_window(row.get("id", ""), row.get("category", ""))
        filtered_df["redemption_window"] = filtered_df.apply(_redeem_window, axis=1)

        # #43/#44 — Enrich with regulatory_jurisdiction and audit_score from RWA_UNIVERSE
        if "regulatory_jurisdiction" not in filtered_df.columns or \
                filtered_df["regulatory_jurisdiction"].isna().all():
            _rj_map = {a["id"]: a.get("regulatory_jurisdiction", "US")
                       for a in RWA_UNIVERSE if a.get("id")}
            filtered_df["regulatory_jurisdiction"] = filtered_df["id"].map(_rj_map).fillna("US")
        if "audit_score" not in filtered_df.columns or \
                filtered_df["audit_score"].isna().all():
            _as_map = {a["id"]: a.get("audit_score", 70)
                       for a in RWA_UNIVERSE if a.get("id")}
            filtered_df["audit_score"] = filtered_df["id"].map(_as_map).fillna(70)

        # Asset table
        show_cols = {
            "id": "ID", "name": "Name", "category": "Category",
            "chain": "Chain", "protocol": "Protocol",
            "current_yield_pct": "Gross Yield %",
            "net_apy_pct": "Net APY %",
            "redemption_window": "Redemption",
            "tvl_usd": "TVL",
            "risk_score": "Risk",
            "liq_score_comp": "Liq Score",
            "exit_velocity": "Exit Score",
            "exit_label": "Exit Speed",
            "trust_score": "Trust /10",
            "regulatory_score": "Regulatory",
            "regulatory_jurisdiction": "Jurisdiction",
            "audit_score": "Audit Score",
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
            width="stretch",
            height=min(600, 55 + 35 * len(table_df)),
        )
        # F5: CSV export for Asset Universe
        _csv_button(table_df, "rwa_asset_universe.csv", "⬇ Export Universe CSV",
                    key="csv_universe_table")

        # ── F4: APY Trend History ──────────────────────────────────────────────
        with st.expander("📈 APY Trend History", expanded=False):
            st.caption(
                "Yield history per asset, recorded on each data scan. "
                "History accumulates over time — new installations will see more data after each refresh."
            )
            _avail_ids = sorted(filtered_df["id"].dropna().unique().tolist()) if "id" in filtered_df.columns else []
            if _avail_ids:
                _sel_asset = st.selectbox("Select asset", _avail_ids, key="yield_hist_asset")
                _hist_days = st.radio("Period", [7, 14, 30, 90], index=2, horizontal=True,
                                      format_func=lambda d: f"{d}d", key="yield_hist_days")
                if _sel_asset:
                    _yh_df = _db.get_yield_history(_sel_asset, days=_hist_days)
                    if not _yh_df.empty and "yield_pct" in _yh_df.columns:
                        _yh_df["timestamp"] = pd.to_datetime(_yh_df["timestamp"], errors="coerce")
                        _yh_fig = px.line(
                            _yh_df, x="timestamp", y="yield_pct",
                            title=f"{_sel_asset} — Yield % ({_hist_days}-day history)",
                            labels={"timestamp": "Date", "yield_pct": "Yield %"},
                            template="plotly_dark",
                            color_discrete_sequence=["#00d4aa"],
                        )
                        _yh_fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=300)
                        _yh_fig.add_hline(
                            y=_yh_df["yield_pct"].mean(), line_dash="dash",
                            line_color="#f59e0b",
                            annotation_text=f"Avg {_yh_df['yield_pct'].mean():.2f}%",
                        )
                        st.plotly_chart(_yh_fig, width="stretch")
                        _csv_button(_yh_df[["timestamp", "yield_pct", "tvl_usd"]],
                                    f"yield_history_{_sel_asset}.csv",
                                    "⬇ Export Yield History CSV",
                                    key="csv_yield_history")
                    else:
                        st.info(f"No yield history yet for {_sel_asset}. Run a data refresh to start recording.")
            else:
                st.info("Load assets first.")

        # ── Collateral Quality Scoring (item 38) ──────────────────────────────
        st.markdown('<div class="section-header">Collateral Quality Scoring</div>',
                    unsafe_allow_html=True)
        _ul38 = st.session_state.get("user_level", "beginner")
        if _ul38 == "beginner":
            st.caption(
                "💡 Collateral quality = how safe and reliable the assets backing each token are. "
                "Government bonds = highest quality (backed by US government). "
                "Private credit = medium (corporate loans). Real estate = location-dependent. "
                "Score 80–100 = excellent, 60–79 = good, below 60 = review carefully."
            )
        # Collateral quality: weighted composite of risk, regulatory, audit, and liquidity scores
        _CQ_CATEGORY_BASE = {
            "Government Bonds": 95, "Commodities": 85, "Real Estate": 70,
            "Private Credit": 60, "Equity": 65, "Infrastructure": 72,
        }
        _cq_rows = []
        for _, _cqrow in filtered_df.iterrows():
            _cat  = _cqrow.get("category", "")
            _base = _CQ_CATEGORY_BASE.get(_cat, 65)
            _rsk  = float(_cqrow.get("risk_score") or 5)          # 1=best, 10=worst
            _reg  = float(_cqrow.get("regulatory_score") or 5)    # 0–10 higher=better
            _aud  = float(_cqrow.get("audit_score") or 70)        # 0–100 higher=better
            _liq  = float(_cqrow.get("liquidity_score") or 5)     # 0–10 higher=better
            # Composite: base category + risk(-4 per point above 1) + regulatory(+1.5 per point)
            #            + audit offset(-0.1 per point below 80) + liquidity(+1 per point above 5)
            _cq_score = (
                _base
                - (_rsk - 1) * 3.5          # risk penalty
                + (_reg - 5) * 1.5          # regulatory premium
                + (_aud - 80) * 0.1         # audit premium/penalty
                + (_liq - 5) * 0.8          # liquidity premium
            )
            _cq_score = max(10, min(100, round(_cq_score, 1)))
            _cq_grade = (
                "AAA" if _cq_score >= 90 else
                "AA"  if _cq_score >= 80 else
                "A"   if _cq_score >= 70 else
                "BBB" if _cq_score >= 60 else
                "BB"
            )
            _cq_color = (
                "#00d4aa" if _cq_score >= 90 else
                "#22c55e" if _cq_score >= 80 else
                "#f59e0b" if _cq_score >= 70 else
                "#ef4444"
            )
            _cq_rows.append({
                "id": _cqrow.get("id", "?"),
                "name": (_cqrow.get("name") or "")[:35],
                "category": _cat,
                "score": _cq_score,
                "grade": _cq_grade,
                "color": _cq_color,
            })
        if _cq_rows:
            _cq_sorted = sorted(_cq_rows, key=lambda r: r["score"], reverse=True)
            # Show top 8 as colored tiles
            _cq_cols = st.columns(min(4, len(_cq_sorted)))
            for _ci, _cqr in enumerate(_cq_sorted[:8]):
                with _cq_cols[_ci % 4]:
                    st.markdown(
                        f"<div style='background:rgba(17,24,39,0.9);border:1px solid {_cqr['color']}33;"
                        f"border-left:4px solid {_cqr['color']};border-radius:8px;padding:10px 12px;"
                        f"margin-bottom:6px'>"
                        f"<div style='font-size:10px;color:#6b7280'>{_cqr['id']}</div>"
                        f"<div style='font-size:14px;font-weight:700;color:{_cqr['color']}'>"
                        f"{_cqr['grade']} · {_cqr['score']:.0f}</div>"
                        f"<div style='font-size:10px;color:#9ca3af;margin-top:2px'>"
                        f"{_cqr['category']}</div></div>",
                        unsafe_allow_html=True,
                    )
            if _ul38 == "advanced" and len(_cq_sorted) > 8:
                with st.expander(f"Show all {len(_cq_sorted)} collateral scores"):
                    _cq_df = pd.DataFrame([{k: v for k, v in r.items() if k != "color"}
                                           for r in _cq_sorted])
                    st.dataframe(_cq_df, width="stretch", height=300)

        # ── NAV Premium / Discount Tracker (#56) ─────────────────────────────
        st.markdown('<div class="section-header">NAV Premium / Discount Tracker</div>',
                    unsafe_allow_html=True)
        st.caption("Compares secondary-market price vs published NAV ($1.00 for tokenized T-bill / MM funds). "
                   "Green = trading at premium above NAV. Red = discount below NAV. Key RWA risk signal.")

        _nav_data = _load_nav_premiums()
        if _nav_data:
            # Filter out NO_DATA entries for the main table display
            _nav_display = [r for r in _nav_data if r["status"] != "NO_DATA"]
            if _nav_display:
                _nav_cols = st.columns(min(len(_nav_display), 5))
                for _ni, _nr in enumerate(_nav_display[:5]):
                    _col_idx = _ni % 5
                    with _nav_cols[_col_idx]:
                        _pr_pct = _nr["premium_pct"]
                        _status = _nr["status"]
                        if _status == "PREMIUM":
                            _nav_color = "#34D399"
                            _nav_bg    = "#064E3B"
                            _nav_arrow = "▲"
                        elif _status == "DISCOUNT":
                            _nav_color = "#EF4444"
                            _nav_bg    = "#7F1D1D"
                            _nav_arrow = "▼"
                        else:
                            _nav_color = "#9CA3AF"
                            _nav_bg    = "#1F2937"
                            _nav_arrow = "●"
                        _nav_mkt = _nr["market_price"]
                        _nav_nav = _nr["nav"]
                        st.markdown(f"""
<div style="background:{_nav_bg};border:1px solid {_nav_color}40;border-radius:8px;padding:12px;text-align:center;margin-bottom:8px">
  <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.08em">{_nr['symbol']}</div>
  <div style="font-size:20px;font-weight:800;color:{_nav_color}">{_nav_arrow} {_pr_pct:+.4f}%</div>
  <div style="font-size:10px;color:#9CA3AF;margin-top:2px">Mkt: ${_nav_mkt:.4f}</div>
  <div style="font-size:10px;color:#6B7280">NAV: ${_nav_nav:.4f}</div>
  <div style="font-size:10px;color:{_nav_color};margin-top:2px;font-weight:600">{_status}</div>
</div>""", unsafe_allow_html=True)

                # Show the rest in a compact table
                if len(_nav_display) > 5:
                    _nav_df = pd.DataFrame(_nav_display)
                    _nav_table = _nav_df[["symbol", "market_price", "nav", "premium_pct", "status", "source"]].copy()
                    _nav_table.columns = ["Symbol", "Market Price", "NAV", "Premium %", "Status", "Source"]

                    def _nav_status_color(val):
                        if val == "PREMIUM":  return "color: #34D399"
                        if val == "DISCOUNT": return "color: #EF4444"
                        return "color: #9CA3AF"

                    def _nav_pct_color(val):
                        try:
                            v = float(val)
                            if v > 0.1:  return "color: #34D399"
                            if v < -0.1: return "color: #EF4444"
                        except Exception:
                            pass
                        return "color: #9CA3AF"

                    st.dataframe(
                        _nav_table.style
                            .format({"Market Price": "${:.6f}", "NAV": "${:.6f}", "Premium %": "{:+.4f}%"})
                            .map(_nav_status_color, subset=["Status"])
                            .map(_nav_pct_color, subset=["Premium %"])
                            .set_properties(**{"background-color": "#111827", "color": "#E2E8F0"}),
                        width="stretch",
                        height=min(400, 55 + 35 * len(_nav_table)),
                    )
            else:
                st.info("NAV data loading... CoinGecko prices required for market price comparison.")
        else:
            st.info("NAV Premium tracker unavailable — CoinGecko price data required.")

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

    # ── Chainlink On-Chain Commodity Prices (#108) ────────────────────────────
    st.markdown("---")
    st.markdown("#### ⛓️ Chainlink On-Chain Prices")
    st.caption("Chainlink AggregatorV3 · latestAnswer() via Etherscan eth_call · Cached 60s · No Chainlink SDK required")

    _cl_prices_raw = _load_chainlink_prices()
    _cl_pairs  = [
        ("XAU/USD",  "Gold (XAU)",   "🥇", "PAXG / XAUt reference"),
        ("XAG/USD",  "Silver (XAG)", "🥈", "Tokenized silver reference"),
        ("BTC/USD",  "Bitcoin",      "₿",  "Chainlink on-chain oracle"),
        ("ETH/USD",  "Ethereum",     "Ξ",  "Chainlink on-chain oracle"),
    ]
    _cl_cols = st.columns(len(_cl_pairs))
    for _cli, (_pair, _label, _icon, _caption) in enumerate(_cl_pairs):
        _cd = _cl_prices_raw.get(_pair, {})
        _cp = _cd.get("price")
        _cs = _cd.get("source", "unavailable")
        _cl_clr = "#34D399" if _cs == "chainlink_etherscan" else "#6B7280"
        with _cl_cols[_cli]:
            st.markdown(f"""
<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;text-align:center">
  <div style="font-size:20px">{_icon}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:2px">{_label}</div>
  <div style="font-size:20px;font-weight:700;color:{_cl_clr};margin-top:4px">
    {"${:,.2f}".format(_cp) if _cp else "—"}
  </div>
  <div style="font-size:10px;color:#4b5563;margin-top:4px">{_caption}</div>
  <div style="font-size:9px;color:#374151;margin-top:2px">{_cs}</div>
</div>""", unsafe_allow_html=True)

    # ── R4: RWA Universe Dashboard ──────────────────────────────────────────────
    if not assets_df.empty:
        try:
            st.markdown("---")
            st.markdown('<div class="section-header">RWA Universe Dashboard</div>', unsafe_allow_html=True)
            st.caption("Aggregate metrics across the full RWA asset universe")
            _u_total     = len(assets_df)
            _u_avg_yield = assets_df["current_yield_pct"].fillna(assets_df.get("expected_yield_pct", pd.Series(dtype=float))).mean()
            _u_avg_risk  = assets_df["risk_score"].mean() if "risk_score" in assets_df.columns else 0
            _u_avg_liq   = assets_df["liquidity_score"].mean() if "liquidity_score" in assets_df.columns else 0
            _u_avg_reg   = assets_df["regulatory_score"].mean() if "regulatory_score" in assets_df.columns else 0
            _u_cats      = assets_df["category"].nunique() if "category" in assets_df.columns else 0
            _u_chains    = assets_df["chain"].nunique() if "chain" in assets_df.columns else 0
            _ud1, _ud2, _ud3, _ud4, _ud5, _ud6, _ud7 = st.columns(7)
            _ud1.metric("Total Assets",      _u_total,              help="Number of RWA assets in the universe")
            _ud2.metric("Avg Yield",         f"{_u_avg_yield:.2f}%", help="Average current yield across all assets")
            _ud3.metric("Avg Risk Score",    f"{_u_avg_risk:.1f}/10", help="Average risk score (1=safest, 10=riskiest)")
            _ud4.metric("Avg Liquidity",     f"{_u_avg_liq:.1f}/10",  help="Average liquidity score")
            _ud5.metric("Avg Regulatory",    f"{_u_avg_reg:.1f}/10",  help="Average regulatory compliance score")
            _ud6.metric("Categories",        _u_cats,               help="Number of distinct asset categories")
            _ud7.metric("Chains",            _u_chains,             help="Number of distinct blockchains represented")
            # Category yield comparison chart
            _u_cat_grp = assets_df.groupby("category")["current_yield_pct"].mean().sort_values(ascending=True)
            if not _u_cat_grp.empty:
                _u_fig = go.Figure(go.Bar(
                    y=_u_cat_grp.index.tolist(),
                    x=_u_cat_grp.values.tolist(),
                    orientation="h",
                    marker_color=["#00d4aa" if v >= 5 else "#f59e0b" if v >= 3 else "#6b7280" for v in _u_cat_grp.values],
                    text=[f"{v:.1f}%" for v in _u_cat_grp.values],
                    textposition="outside",
                ))
                _u_fig.update_layout(
                    title="Average Yield by Category",
                    height=max(200, 36 * len(_u_cat_grp) + 60),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0", size=11),
                    margin=dict(l=0, r=80, t=40, b=0),
                    xaxis=dict(title="Avg Yield (%)", gridcolor="rgba(255,255,255,0.05)"),
                )
                st.plotly_chart(_u_fig, width="stretch")
            _user_level_r4 = st.session_state.get("user_level", "beginner")
            if _user_level_r4 == "beginner":
                st.info("💡 **What does this mean for me?** This scorecard shows you an overview of the entire real world asset universe — how many types of assets exist, what they typically yield, and how risky they are on average.")
        except Exception as _r4_err:
            logger.debug("[R4] Universe dashboard skipped: %s", _r4_err)

    # ── R7: Private Credit Yield Tracker ────────────────────────────────────────
    if not assets_df.empty and "category" in assets_df.columns:
        try:
            _pc_df = assets_df[assets_df["category"].str.contains("Private Credit|Credit", case=False, na=False)].copy()
            if not _pc_df.empty:
                st.markdown("---")
                st.markdown('<div class="section-header">Private Credit Yield Tracker</div>', unsafe_allow_html=True)
                st.caption("Live yield comparison across tokenized private credit protocols")
                _pc_df_sorted = _pc_df.sort_values("current_yield_pct", ascending=False)
                _pc_names  = _pc_df_sorted["name"].fillna(_pc_df_sorted["id"]).tolist()
                _pc_yields = _pc_df_sorted["current_yield_pct"].fillna(_pc_df_sorted.get("expected_yield_pct", pd.Series(dtype=float))).tolist()
                _pc_risks  = _pc_df_sorted["risk_score"].fillna(5).tolist()
                _pc_colors = ["#ef4444" if r >= 7 else "#f59e0b" if r >= 5 else "#22c55e" for r in _pc_risks]
                _pc_fig = go.Figure(go.Bar(
                    x=[n[:25] for n in _pc_names],
                    y=_pc_yields,
                    marker_color=_pc_colors,
                    text=[f"{y:.1f}%" for y in _pc_yields],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Yield: %{y:.2f}%<br>Risk: " +
                                  "<br>".join(f"{n[:25]}: {r:.0f}/10" for n, r in zip(_pc_names, _pc_risks)) + "<extra></extra>",
                ))
                _pc_fig.update_layout(
                    height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0", size=11),
                    margin=dict(l=0, r=0, t=20, b=60),
                    yaxis=dict(title="Yield (%)", gridcolor="rgba(255,255,255,0.05)"),
                )
                st.plotly_chart(_pc_fig, width="stretch")
                st.caption("🟢 Risk ≤4  🟡 Risk 5–6  🔴 Risk ≥7")
        except Exception as _r7_err:
            logger.debug("[R7] Private credit tracker skipped: %s", _r7_err)

    # ── R1: ISO 20022 Badge ──────────────────────────────────────────────────────
    try:
        st.markdown("---")
        st.markdown('<div class="section-header">ISO 20022 Alignment</div>', unsafe_allow_html=True)
        st.caption("ISO 20022 is the international standard for financial messaging — adopted by SWIFT, the Federal Reserve, ECB, and 70+ central banks. Assets and blockchains natively aligned with this standard have a structural advantage for institutional settlement and cross-border payments.")
        _ISO_ASSETS = [
            {"symbol": "XRP",  "name": "XRP Ledger",    "status": "NATIVE",  "note": "XRPL built with ISO 20022 data structures. Ripple is a founding ISO 20022 member."},
            {"symbol": "XLM",  "name": "Stellar",        "status": "NATIVE",  "note": "Stellar's payment protocol is ISO 20022 compatible. Used by IBMs World Wire."},
            {"symbol": "XDC",  "name": "XDC Network",    "status": "NATIVE",  "note": "XDC is designed for trade finance and uses ISO 20022 payment messaging."},
            {"symbol": "HBAR", "name": "Hedera",         "status": "NATIVE",  "note": "Hedera partnered with ISO 20022 standards body. Used in central bank pilots."},
            {"symbol": "ALGO", "name": "Algorand",       "status": "ALIGNED", "note": "Algorand supports ISO 20022 via its CBDC and payments infrastructure."},
            {"symbol": "BUIDL","name": "BlackRock BUIDL","status": "RAILS",   "note": "Uses SWIFT ISO 20022 messaging for institutional settlement."},
            {"symbol": "BENJI","name": "Franklin BENJI", "status": "RAILS",   "note": "Franklin Templeton BENJI uses Stellar (ISO 20022) as its payment rail."},
            {"symbol": "OUSG", "name": "Ondo OUSG",      "status": "RAILS",   "note": "Multi-chain; Solana + Ethereum. Settlement via ISO 20022-compatible custodians."},
        ]
        _iso_status_color = {"NATIVE": "#00d4aa", "ALIGNED": "#22c55e", "RAILS": "#f59e0b"}
        _iso_status_label = {"NATIVE": "NATIVE ISO 20022", "ALIGNED": "ISO 20022 ALIGNED", "RAILS": "ISO 20022 RAILS"}
        _iso_cols = st.columns(min(4, len(_ISO_ASSETS)))
        for _ii, _ia in enumerate(_ISO_ASSETS):
            _ic  = _iso_status_color.get(_ia["status"], "#6b7280")
            _il  = _iso_status_label.get(_ia["status"], _ia["status"])
            with _iso_cols[_ii % 4]:
                st.markdown(f"""
<div style="background:#111827;border:1px solid {_ic}33;border-top:3px solid {_ic};
            border-radius:8px;padding:12px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:15px;font-weight:700;color:#e2e8f0">{_ia['symbol']}</div>
    <div style="font-size:9px;font-weight:700;color:{_ic};background:{_ic}22;
                padding:2px 6px;border-radius:4px">{_il}</div>
  </div>
  <div style="font-size:11px;color:#9ca3af;margin-top:4px">{_ia['name']}</div>
  <div style="font-size:10px;color:#6b7280;margin-top:6px;line-height:1.5">{_ia['note']}</div>
</div>""", unsafe_allow_html=True)
        _user_level_r1 = st.session_state.get("user_level", "beginner")
        if _user_level_r1 == "beginner":
            st.info("💡 **What does this mean for me?** ISO 20022 is the new global standard that banks and central banks are switching to for sending money between countries. Blockchains that already speak this language are more likely to be used by big financial institutions — which could drive adoption.")
    except Exception as _r1_err:
        logger.debug("[R1] ISO 20022 panel skipped: %s", _r1_err)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: ARBITRAGE
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: YIELD STRATEGIES (Arbitrage + Carry Trade)
# ══════════════════════════════════════════════════════════════════════════════

with tab_yield:
    # F6: freshness badges for yield data sources
    _yield_badges = " &nbsp; ".join([
        _freshness_badge("defillama_yields", 3600, "DeFiLlama Yields"),
        _freshness_badge("lending_borrow_rates", 3600, "Borrow Rates"),
        _freshness_badge("coingecko_prices", 300, "Prices"),
    ])
    st.markdown(_yield_badges, unsafe_allow_html=True)

    _ys_mode = st.radio(
        "Strategy",
        ["⚡ Arbitrage", "💱 Carry Trade"],
        horizontal=True,
        key="ys_mode_radio",
        label_visibility="collapsed",
    )
    st.caption("⚡ Arbitrage: exploit price differences across protocols. 💱 Carry Trade: profit from yield differentials between chains.")

    if _ys_mode == "⚡ Arbitrage":
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
                # Item 36: shape encoding — ▲ extreme/strong arb, ■ regular arb (color-blind safe)
                sig_shape = "▲" if signal in ("EXTREME_ARB", "STRONG_ARB") else "■"
                sig_label = f"{sig_shape} {signal.replace('_', ' ')}"

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

        # Spread chart — UPGRADE 21: use cached chart builder
        if not arb_df.empty and len(arb_df) > 3:
            _arb_slice = arb_df.head(15)[["asset_a_id", "net_spread_pct", "type"]].to_dict("records")
            fig_arb = _build_arb_bar(_arb_slice)
            st.plotly_chart(fig_arb, width="stretch")

        # ── XRPL DEX Arbitrage Scanner (Item 15) ─────────────────────────────────
        st.markdown('<div class="section-header">XRPL DEX Arbitrage Scanner</div>',
                    unsafe_allow_html=True)

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

        # ── Export buttons ────────────────────────────────────────────────────────
        if not arb_df.empty:
            _exp1, _exp2 = st.columns(2)
            with _exp1:
                # F5: CSV export for arbitrage
                _arb_csv_cols = [c for c in [
                    "type", "asset_a_name", "asset_b_name", "spread_pct",
                    "net_spread_pct", "estimated_apy", "signal", "tx_cost_pct",
                    "protocol_a", "chain_a", "action",
                ] if c in arb_df.columns]
                _csv_button(arb_df[_arb_csv_cols], "arbitrage_opportunities.csv",
                            "⬇ Export Arb CSV", key="csv_arb_table")
            with _exp2:
                if _pdf._REPORTLAB:
                    pdf_arb_bytes = _pdf.generate_arb_pdf(arb_df.to_dict("records"))
                    st.download_button(
                        label="📄 Download Arbitrage PDF",
                        data=pdf_arb_bytes,
                        file_name=f"rwa_arbitrage_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf",
                        mime="application/pdf",
                        key="btn_arb_pdf",
                        help="Download a formatted PDF report of all current arbitrage opportunities.",
                    )


    else:
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
                    st.plotly_chart(fig_carry, width="stretch")

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
                    width="stretch",
                    height=min(500, 55 + 35 * len(show_carry.head(50))),
                )
                # F5: CSV export for carry trade table
                _csv_button(
                    show_carry[["RWA Asset", "Category", "RWA Yield %", "Borrow From",
                                "Borrow Chain", "Borrow APY %", "Gross Spread %",
                                "Net Spread %", "Exit Speed", "Risk"]].head(50),
                    "carry_trade_opportunities.csv",
                    "⬇ Export Carry Trades CSV",
                    key="csv_carry_table",
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

        # ── R2: Treasury-Adjusted Spread ─────────────────────────────────────────
        try:
            if not assets_df.empty:
                from data_feeds import fetch_treasury_yield_curve as _fetch_tsy
                _tsy_data = _fetch_tsy()
                _tsy_3m   = _tsy_data.get("yields", {}).get("3m")
                _tsy_1y   = _tsy_data.get("yields", {}).get("1y")
                _tsy_2y   = _tsy_data.get("yields", {}).get("2y")
                _ref_yield = _tsy_3m or _tsy_1y or 4.25  # fallback 3m T-bill
                st.markdown("---")
                st.markdown('<div class="section-header">Treasury-Adjusted Spread</div>', unsafe_allow_html=True)
                st.caption(f"Yield spread above US 3M T-Bill ({_ref_yield:.2f}%) — the risk-free benchmark. Positive spread = risk premium earned above treasuries.")
                _spread_rows = []
                for _, _row in assets_df.sort_values("current_yield_pct", ascending=False).head(15).iterrows():
                    _y = float(_row.get("current_yield_pct") or _row.get("expected_yield_pct") or 0)
                    _spread = _y - _ref_yield
                    _spread_bps = _spread * 100  # basis points
                    _spread_rows.append({
                        "Asset": str(_row.get("name", _row.get("id", "?")))[:28],
                        "Yield": f"{_y:.2f}%",
                        "Spread (bps)": f"{_spread_bps:+.0f}",
                        "Category": str(_row.get("category", ""))[:20],
                        "_spread": _spread,
                    })
                if _spread_rows:
                    _sp_fig = go.Figure(go.Bar(
                        y=[r["Asset"] for r in _spread_rows],
                        x=[r["_spread"] for r in _spread_rows],
                        orientation="h",
                        marker_color=["#22c55e" if r["_spread"] > 0 else "#ef4444" for r in _spread_rows],
                        text=[f"{r['_spread']:+.2f}% ({float(r['Spread (bps)'].replace('+','')):.0f} bps)" for r in _spread_rows],
                        textposition="outside",
                    ))
                    _sp_fig.add_vline(x=0, line_dash="dash", line_color="#6b7280", line_width=1)
                    _sp_fig.update_layout(
                        height=max(250, 36 * len(_spread_rows) + 60),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#e2e8f0", size=11),
                        margin=dict(l=0, r=130, t=20, b=0),
                        xaxis=dict(title=f"Spread vs 3M T-Bill ({_ref_yield:.2f}%)", gridcolor="rgba(255,255,255,0.05)"),
                        yaxis=dict(autorange="reversed"),
                    )
                    st.plotly_chart(_sp_fig, width="stretch")
                    _col_sp1, _col_sp2 = st.columns(2)
                    with _col_sp1:
                        st.caption(f"🏛️ US 3M T-Bill (risk-free): {_ref_yield:.2f}%")
                        if _tsy_1y: st.caption(f"🏛️ US 1Y Treasury: {_tsy_1y:.2f}%")
                        if _tsy_2y: st.caption(f"🏛️ US 2Y Treasury: {_tsy_2y:.2f}%")
                    _user_level_r2 = st.session_state.get("user_level", "beginner")
                    if _user_level_r2 == "beginner":
                        st.info(f"💡 **What does this mean for me?** US Treasury bills are the safest investment in the world. They currently pay {_ref_yield:.2f}%. The bars above show how much MORE each RWA asset pays above that safe baseline — called the 'spread'. Bigger green bar = more reward for taking extra risk.")
        except Exception as _r2_err:
            logger.debug("[R2] T-spread panel skipped: %s", _r2_err)

        # ── R9: Stacked Yield Calculator ─────────────────────────────────────────
        try:
            st.markdown("---")
            st.markdown('<div class="section-header">Stacked Yield Calculator</div>', unsafe_allow_html=True)
            st.caption("Layer multiple yield sources to calculate total composite return on a single capital deployment")
            _sy_c1, _sy_c2 = st.columns(2)
            with _sy_c1:
                _sy_principal = st.number_input("Principal (USD)", 1_000, 10_000_000, 100_000, 10_000, key="sy_principal",
                                                help="The capital amount you are deploying")
                _sy_base  = st.slider("Base RWA Yield (%)", 0.0, 20.0, 4.5, 0.1, key="sy_base",
                                      help="The base yield from the RWA asset itself (e.g. OUSG = 4.37%)")
                _sy_defi  = st.slider("DeFi Boost — collateral / LP (%)", 0.0, 15.0, 2.0, 0.1, key="sy_defi",
                                      help="Extra yield from using the RWA token as collateral in Aave/Morpho, or providing liquidity")
                _sy_stake = st.slider("Staking / Restaking Premium (%)", 0.0, 10.0, 1.5, 0.1, key="sy_stake",
                                      help="Additional yield from staking the token or restaking via EigenLayer/Lombard")
                _sy_points = st.slider("Points / Airdrop Estimate (%)", 0.0, 10.0, 0.5, 0.1, key="sy_points",
                                       help="Estimated annualized value of protocol points or anticipated airdrops (speculative)")
            with _sy_c2:
                _sy_total = _sy_base + _sy_defi + _sy_stake + _sy_points
                _sy_annual = _sy_principal * _sy_total / 100
                _sy_monthly = _sy_annual / 12
                _sy_daily   = _sy_annual / 365
                st.markdown(f"""
        <div style="background:#111827;border:1px solid #00d4aa33;border-top:3px solid #00d4aa;
                border-radius:10px;padding:20px;margin-top:8px">
          <div style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px">Total Stacked Yield</div>
          <div style="font-size:42px;font-weight:700;color:#00d4aa;margin:8px 0">{_sy_total:.2f}%</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
        <div><div style="font-size:11px;color:#6b7280">Annual</div>
             <div style="font-size:20px;font-weight:700;color:#22c55e">${_sy_annual:,.0f}</div></div>
        <div><div style="font-size:11px;color:#6b7280">Monthly</div>
             <div style="font-size:20px;font-weight:700;color:#22c55e">${_sy_monthly:,.0f}</div></div>
        <div><div style="font-size:11px;color:#6b7280">Daily</div>
             <div style="font-size:16px;font-weight:600;color:#9ca3af">${_sy_daily:,.2f}</div></div>
        <div><div style="font-size:11px;color:#6b7280">Principal</div>
             <div style="font-size:16px;font-weight:600;color:#9ca3af">${_sy_principal:,.0f}</div></div>
          </div>
          <div style="margin-top:16px;border-top:1px solid #1f2937;padding-top:12px;font-size:11px;color:#4b5563">
        Base {_sy_base:.1f}% + DeFi {_sy_defi:.1f}% + Staking {_sy_stake:.1f}% + Points {_sy_points:.1f}%
          </div>
        </div>""", unsafe_allow_html=True)
            _user_level_r9 = st.session_state.get("user_level", "beginner")
            if _user_level_r9 == "beginner":
                st.info("💡 **What does this mean for me?** In DeFi, you can often earn multiple types of yield on the same money at the same time. For example: earn 4% on a T-bill token, then use that token as collateral to earn another 2% in lending, plus staking rewards on top. This calculator lets you add up all those layers.")
        except Exception as _r9_err:
            logger.debug("[R9] Stacked yield calculator skipped: %s", _r9_err)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: COMPARE TIERS
# ══════════════════════════════════════════════════════════════════════════════

with tab_compare:
    st.markdown('<div class="section-header">Portfolio Tier Comparison</div>',
                unsafe_allow_html=True)

    # OPT-12: use module-level cached result (_all_ports / _comp_df computed above)
    all_ports = _all_ports
    comp_df   = _comp_df
    if not all_ports:
        all_ports, comp_df = _load_all_portfolios(portfolio_value)

    if not comp_df.empty:
        # Radar / comparison chart — UPGRADE 21: use cached chart builder
        _tier_colors = {int(t): cfg["color"] for t, cfg in PORTFOLIO_TIERS.items()}
        fig_compare = _build_tier_comparison_bar(
            comp_df.to_dict("records"),
            _tier_colors,
        )
        st.plotly_chart(fig_compare, width="stretch")

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
            width="stretch",
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
                st.plotly_chart(fig_ef, width="stretch")


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
                width="stretch",
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
                         width="stretch", key="btn_start_agent",
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
            if st.button("⏹ Stop Agent", width="stretch", key="btn_stop_agent",
                         type="secondary"):
                _agent.supervisor.stop()
                st.session_state["agent_running"] = False
                st.rerun()
    with ac4:
        if st.button("⚡ Run Now (1 cycle)", width="stretch", key="btn_one_cycle",
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

    # G8: Emergency Stop — kill switch, shown prominently before config sliders
    _emg_is_active = _agent.is_emergency_stop()
    if _emg_is_active:
        st.error("🚨 **EMERGENCY STOP ACTIVE** — agent will reject all new entries until cleared.")
        if st.button("✅ Clear Emergency Stop", key="btn_rwa_emg_clear", type="primary"):
            _agent.set_emergency_stop(False)
            st.success("Emergency stop cleared.")
            st.rerun()
    else:
        if st.button("🚨 Activate Emergency Stop", key="btn_rwa_emg_activate", type="secondary"):
            _agent.set_emergency_stop(True)
            st.rerun()

    # G2: Agent Risk Parameters — sliding presets (overrides stored in rwa_agent_overrides.json)
    with st.expander("⚙️ Agent Risk Parameters", expanded=False):
        st.caption("Adjust risk limits for the selected agent. Values are saved persistently and take effect on the next cycle.")
        with st.form("rwa_agent_params_form"):
            _params = _agent.get_agent_params(selected_agent)
            _lim_info = _agent.get_active_agent_limits()
            ap1, ap2 = st.columns(2)
            with ap1:
                _p_min_conf = st.slider(
                    "Min Confidence to Act (%)", min_value=40.0, max_value=95.0,
                    value=float(_params.get("min_confidence_pct", 60.0)), step=1.0,
                    help="Claude must assign at least this confidence before the agent acts",
                )
                _p_max_trade = st.slider(
                    "Max Trade Size (% of portfolio)", min_value=1.0, max_value=25.0,
                    value=float(_params.get("max_trade_size_pct", 10.0)), step=0.5,
                    help="Hard cap on any single rebalance action",
                )
                _p_max_dd = st.slider(
                    "Max Drawdown from Peak (%)", min_value=5.0, max_value=40.0,
                    value=float(_params.get("max_drawdown_pct", 15.0)), step=1.0,
                    help="Agent halts if portfolio falls this % from its peak value",
                )
            with ap2:
                _p_loss_lim = st.slider(
                    "Daily Loss Limit (%)", min_value=0.5, max_value=20.0,
                    value=float(_params.get("daily_loss_limit_pct", 3.0)), step=0.5,
                    help="Pause all actions when daily P&L breaches this loss threshold",
                )
                _p_rebal_thresh = st.slider(
                    "Rebalance Threshold (% drift)", min_value=1.0, max_value=20.0,
                    value=float(_params.get("rebalance_threshold_pct", 5.0)), step=0.5,
                    help="How far an allocation must drift from target before triggering a rebalance",
                )
                _p_max_pos = st.number_input(
                    "Max Simultaneous Positions", min_value=1, max_value=20,
                    value=int(_params.get("max_positions", 8)), step=1,
                    help="Maximum number of distinct holdings the agent can hold at once",
                )
            if st.form_submit_button("💾 Save Parameters", type="primary", width="stretch"):
                _agent.save_agent_overrides({
                    "min_confidence_pct":      float(_p_min_conf),
                    "max_trade_size_pct":      float(_p_max_trade),
                    "daily_loss_limit_pct":    float(_p_loss_lim),
                    "max_drawdown_pct":        float(_p_max_dd),
                    "rebalance_threshold_pct": float(_p_rebal_thresh),
                    "max_positions":           int(_p_max_pos),
                })
                st.success("Agent parameters saved — will take effect on the next cycle.")
        # Active Limits display
        _active = _agent.get_active_agent_limits()
        if any(v["custom"] for v in _active.values()):
            st.caption("🔧 Custom overrides active:")
            for key, info in _active.items():
                if info["custom"]:
                    _label = key.replace("_", " ").title()
                    st.caption(f"  • {_label}: **{info['value']}** (default: {info['default']})")

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
            width="stretch",
            height=300,
        )
        # F5: CSV export for agent decisions
        _csv_button(show_d, "agent_decisions.csv", "⬇ Export Decisions CSV",
                    key="csv_decisions_table")
    else:
        st.info("No agent decisions yet. Start an agent or run a manual cycle above.")

    # G3: Dual-window accuracy panel
    try:
        from ai_feedback import get_dual_window_accuracy as _get_dwa, get_rolling_win_rate_history as _get_rwrh
        _dwa = _get_dwa(agent_name=selected_agent)
        _acc30 = _dwa.get("acc_30d", {})
        _acc7  = _dwa.get("acc_7d",  {})
        _trend = _dwa.get("trend", "stable")
        _wr30  = _acc30.get("win_rate", 0) or 0
        _wr7   = _acc7.get("win_rate",  0) or 0
        _trend_icon = {"improving": "📈", "degrading": "📉", "stable": "➡️"}.get(_trend, "➡️")
        _dwa_c1, _dwa_c2, _dwa_c3 = st.columns(3)
        _dwa_c1.metric("30-Day Win Rate", f"{_wr30:.0%}",
                       help=f"Correct decisions over the past 30 days ({_acc30.get('total', 0)} trades)")
        _dwa_c2.metric("7-Day Win Rate", f"{_wr7:.0%}",
                       delta=f"{(_wr7 - _wr30) * 100:+.1f}pp vs 30d",
                       help=f"Correct decisions over the past 7 days ({_acc7.get('total', 0)} trades)")
        _dwa_c3.metric("Accuracy Trend", f"{_trend_icon} {_trend.title()}",
                       help="Improving = 7-day win rate at least 5pp above 30-day baseline")

        # F1: Rolling win rate chart
        _rwrh = _get_rwrh(agent_name=selected_agent, window_days=30, rolling_window=7)
        if _rwrh:
            _rwrh_df = pd.DataFrame(_rwrh)
            _rwrh_fig = px.line(
                _rwrh_df, x="date", y="win_rate",
                title="7-Day Rolling Win Rate (past 30 days)",
                labels={"date": "Date", "win_rate": "Win Rate (%)"},
                template="plotly_dark",
                color_discrete_sequence=["#00d4aa"],
            )
            _rwrh_fig.add_hline(y=50, line_dash="dash", line_color="#6B7280",
                                annotation_text="50% breakeven")
            _rwrh_fig.update_layout(height=220, margin=dict(l=0, r=0, t=40, b=0),
                                    yaxis=dict(range=[0, 100], ticksuffix="%"))
            st.plotly_chart(_rwrh_fig, width="stretch")
        else:
            st.caption("Win rate history builds up as the agent makes and evaluates decisions.")
    except Exception:
        pass

    # ── Macro Factor Allocation Bias (Group 7) ───────────────────────────────────
    st.markdown('<div class="section-header">Macro Factor Allocation Bias</div>', unsafe_allow_html=True)

    with st.expander("📊 VIX · DXY · Yield Curve · Fear & Greed → Allocation Adjustments", expanded=True):
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
                st.dataframe(adj_df, width="stretch", hide_index=True)

            # Rationale summary (rationale is a single string)
            if rat:
                st.caption(str(rat))

    # ── Factor-Based Portfolio Optimization (#114) ───────────────────────────────
    st.markdown('<div class="section-header">Factor-Based Portfolio Optimization</div>', unsafe_allow_html=True)

    with st.expander("📐 Macro-Factor-Tilted Mean-Variance Optimizer", expanded=False):
        if st.button("⟳ Recompute Factor Optimization", key="btn_factor_opt"):
            _load_factor_opt.clear()

        with st.spinner("Running factor-tilted optimizer…"):
            _fopt = _load_factor_opt(selected_tier, portfolio_value)

        if _fopt.get("error"):
            st.caption(f"Factor optimizer: {_fopt['error']}")
        else:
            _foa, _fob, _foc, _fod = st.columns(4)
            _foa.metric("Expected Return", f"{_fopt.get('expected_return_pct', 0):.2f}%")
            _fob.metric("Expected Vol", f"{_fopt.get('expected_vol_pct', 0):.2f}%")
            _foc.metric("Factor Sharpe", f"{_fopt.get('sharpe', 0):.3f}")
            _regime_color = {"RISK_ON": "#10b981", "RISK_OFF": "#ef4444",
                             "STAGFLATION": "#f59e0b", "NEUTRAL": "#6b7280"}.get(
                _fopt.get("regime", "NEUTRAL"), "#6b7280")
            _fod.markdown(
                f'<div style="padding:8px;border-radius:8px;background:#111827;border:1px solid #1f2937">'
                f'<div style="font-size:10px;color:#6b7280">REGIME</div>'
                f'<div style="font-size:16px;font-weight:700;color:{_regime_color}">'
                f'{_fopt.get("regime", "—")}</div>'
                f'<div style="font-size:10px;color:#6b7280">VIX {_fopt.get("vix", "—")} · '
                f'corr ×{_fopt.get("correlation_scalar", 1)}</div>'
                f'</div>', unsafe_allow_html=True,
            )

            # Factor adjustment per category
            _f_adjs = _fopt.get("factor_adjustments", {})
            if _f_adjs:
                st.markdown("**Factor Yield Adjustments by Category**")
                _fadj_rows = [
                    {"Category": c,
                     "Yield Adj": f"{v:+.3f}%",
                     "Direction": "▲ Overweight" if v > 0 else ("▼ Underweight" if v < 0 else "— Neutral")}
                    for c, v in sorted(_f_adjs.items(), key=lambda x: -abs(x[1]))
                    if v != 0
                ]
                if _fadj_rows:
                    st.dataframe(pd.DataFrame(_fadj_rows), width="stretch", hide_index=True)

            # Max-Sharpe weight table
            _f_weights = _fopt.get("weights", {})
            if _f_weights:
                _fw_rows = [{"Asset": k, "Optimal Weight %": f"{v:.1f}%"}
                            for k, v in sorted(_f_weights.items(), key=lambda x: -x[1])
                            if v > 0.5]
                if _fw_rows:
                    st.markdown("**Factor-Optimal Weights (Max-Sharpe Portfolio)**")
                    st.dataframe(pd.DataFrame(_fw_rows), width="stretch", hide_index=True)

            if _fopt.get("rationale"):
                st.caption(f"Factor rationale: {_fopt['rationale']}")

    # ── Macro Factor Portfolio Optimizer (#114 Batch 7) ──────────────────────────
    if _pro_mode:
        st.markdown('<div class="section-header">Factor Portfolio Optimizer (Pro)</div>', unsafe_allow_html=True)

        with st.expander("🎯 Optimize Portfolio by Macro Factors (L-BFGS-B)", expanded=False):
            if st.button("Optimize Portfolio by Macro Factors", key="btn_factor_opt_b7"):
                _load_factor_opt_b7.clear()

            with st.spinner("Running factor optimizer (L-BFGS-B)…"):
                _b7opt = _load_factor_opt_b7(selected_tier, portfolio_value)

            if _b7opt.get("error"):
                st.caption(f"Factor optimizer: {_b7opt['error']}")
            else:
                _b7a, _b7b, _b7c, _b7d = st.columns(4)
                _b7a.metric("Factor Distance", f"{_b7opt.get('factor_distance', 0):.4f}")
                _b7b.metric("EW Benchmark Dist", f"{_b7opt.get('equal_weight_distance', 0):.4f}")
                _b7c.metric("Improvement vs EW", f"{_b7opt.get('improvement_vs_equal_weight', 0):.1f}%")
                _b7d.metric("Assets Optimized", str(_b7opt.get("n_assets", 0)))

                # Comparison table: optimized vs equal-weight
                _b7_weights = _b7opt.get("weights", {})
                _port_for_cmp = _load_portfolio(selected_tier, portfolio_value)
                _cur_holdings = _port_for_cmp.get("holdings", []) if _port_for_cmp else []
                _cur_w = {h.get("id"): h.get("weight_pct", 0) for h in _cur_holdings}
                n_assets = _b7opt.get("n_assets", 0)
                _eq_w = round(100.0 / n_assets, 2) if n_assets > 0 else 0.0

                if _b7_weights:
                    st.markdown("**Optimized Weights vs Current Portfolio**")
                    _b7_rows = []
                    for asset_id, opt_w in sorted(_b7_weights.items(), key=lambda x: -x[1]):
                        cur_w = _cur_w.get(asset_id, _eq_w)
                        delta = opt_w - cur_w
                        _b7_rows.append({
                            "Asset": asset_id,
                            "Current Weight %": f"{cur_w:.1f}%",
                            "Optimized Weight %": f"{opt_w:.1f}%",
                            "Delta": f"{delta:+.1f}%",
                            "Direction": "▲ Overweight" if delta > 1 else ("▼ Underweight" if delta < -1 else "— Neutral"),
                        })
                    if _b7_rows:
                        st.dataframe(pd.DataFrame(_b7_rows), width="stretch", hide_index=True)

                # Factor exposure bar chart
                _pf_factors = _b7opt.get("portfolio_factors", {})
                _tgt_factors = _b7opt.get("target_factors", {})
                if _pf_factors and _tgt_factors:
                    import plotly.graph_objects as _go_b7
                    from plotly.subplots import make_subplots as _ms_b7
                    _f_names  = list(_pf_factors.keys())
                    _f_port   = [_pf_factors.get(f, 0) for f in _f_names]
                    _f_target = [_tgt_factors.get(f, 0) for f in _f_names]
                    _fig_f = _go_b7.Figure()
                    _fig_f.add_trace(_go_b7.Bar(name="Portfolio", x=_f_names, y=_f_port,
                                                 marker_color="#00D4FF"))
                    _fig_f.add_trace(_go_b7.Bar(name="Target (RISK_ON)", x=_f_names, y=_f_target,
                                                 marker_color="#34D399"))
                    _fig_f.update_layout(
                        title="Factor Exposure: Portfolio vs Target",
                        barmode="group",
                        height=320,
                        plot_bgcolor="#0A0E1A",
                        paper_bgcolor="#0A0E1A",
                        font_color="#E2E8F0",
                        legend=dict(orientation="h", y=1.1),
                    )
                    st.plotly_chart(_fig_f, width="stretch")

                st.caption(f"Optimizer: {_b7opt.get('source', '—')} · Scipy L-BFGS-B minimizes factor vector distance to RISK_ON target")

    # ── XRPL Intelligence + Tier 3 Status (Upgrades 10, 11, 12) ─────────────────
    st.markdown('<div class="section-header">XRPL Intelligence</div>', unsafe_allow_html=True)

    with st.expander("🔗 XRPL · RLUSD · Soil Protocol · XLS-81", expanded=False):
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
                st.dataframe(pd.DataFrame(bids), width="stretch", hide_index=True)
            else:
                st.caption("No bids available" if not ob_err else f"Error: {ob_err}")
        with xrpl_rvb:
            st.markdown("**📊 RLUSD/XRP Asks (top 5)**")
            asks = rlusd_d.get("asks", [])
            if asks:
                st.dataframe(pd.DataFrame(asks), width="stretch", hide_index=True)
            else:
                st.caption("No asks available" if not ob_err else f"Error: {ob_err}")

        st.markdown("**🌱 Soil Protocol — RLUSD Yield Vaults (XRPL)**")
        vaults = xrpl_d.get("soil_vaults", [])
        if vaults:
            vault_df = pd.DataFrame(vaults)
            st.dataframe(vault_df, width="stretch", hide_index=True)

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

    # ── RWA Agent Tool Query (#115) ──────────────────────────────────────────
    st.markdown('<div class="section-header">Ask the RWA Agent</div>', unsafe_allow_html=True)
    st.caption(
        "Natural-language questions dispatched to live data tools. "
        "Examples: 'What is the health of BUIDL?' · 'Run a scenario with HY spreads +200bp' · "
        "'What is the current macro regime?'"
    )
    _agent_question = st.text_input(
        "Your question",
        placeholder="e.g. What is the health of BUIDL? or Run a scenario with HY spreads +200bp",
        key="agent_tool_question",
        max_chars=300,
    )
    if st.button("Ask Agent", key="btn_ask_agent", type="primary"):
        if _agent_question.strip():
            with st.spinner("Thinking…"):
                try:
                    _q_lower = _agent_question.lower()
                    # Detect intent and dispatch matching tool(s)
                    _tool_ctx: dict = {}
                    if any(kw in _q_lower for kw in ("macro", "regime", "risk", "fear", "vix")):
                        _tool_ctx["macro_regime"] = _agent.dispatch_agent_tool("get_macro_regime")
                    if any(kw in _q_lower for kw in ("health", "portfolio", "score", "sharpe")):
                        _tool_ctx["portfolio_health"] = _agent.dispatch_agent_tool("get_portfolio_health")
                    if any(kw in _q_lower for kw in ("scenario", "stress", "shock", "spread", "bp")):
                        _tool_ctx["scenario"] = _agent.dispatch_agent_tool(
                            "run_scenario", shocks={"hy_spread_bps": 200}
                        )
                    # Try asset lookup for known RWA symbols
                    for _sym in ["BUIDL", "OUSG", "USDY", "WSTETH", "STBT", "USYC", "ONDO"]:
                        if _sym.lower() in _q_lower:
                            _tool_ctx[f"asset_{_sym}"] = _agent.dispatch_agent_tool(
                                "get_asset_data", asset_id=_sym
                            )

                    # Build context summary for Claude
                    _ctx_lines = []
                    for _tn, _td in _tool_ctx.items():
                        if _td and not _td.get("error"):
                            _ctx_lines.append(f"[{_tn}] {json.dumps(_td, default=str)[:400]}")
                    _ctx_str = "\n".join(_ctx_lines) if _ctx_lines else "No tool data available."

                    # Generate answer with Claude
                    _key_for_q = _get_effective_claude_key()
                    _q_sanitized = _agent_question[:300].replace("<", "&lt;").replace(">", "&gt;")
                    _agent_answer = None
                    if _key_for_q:
                        try:
                            import anthropic as _ant_q
                            _client_q = _ant_q.Anthropic(api_key=_key_for_q, timeout=20.0)
                            _msg_q = _client_q.messages.create(
                                model="claude-haiku-4-5",
                                max_tokens=400,
                                messages=[{
                                    "role": "user",
                                    "content": (
                                        f"You are the RWA Infinity portfolio assistant. "
                                        f"Answer concisely using the tool data below.\n\n"
                                        f"Tool data:\n{_ctx_str}\n\n"
                                        f"User question: {_q_sanitized}"
                                    ),
                                }],
                            )
                            _agent_answer = _msg_q.content[0].text.strip() if _msg_q.content else "No answer."
                        except Exception as _claude_err:
                            logger.warning("[AgentQuery] Claude call failed: %s", _claude_err)
                            _agent_answer = None
                    # Rule-based fallback when no key or Claude call failed
                    if _agent_answer is None:
                        if _tool_ctx:
                            _agent_answer = (
                                f"Tool data retrieved: {', '.join(_tool_ctx.keys())}. "
                                f"Connect ANTHROPIC_API_KEY for AI-synthesized answers."
                            )
                        else:
                            _agent_answer = (
                                "No matching tool found for that question. Try asking about "
                                "'macro regime', 'portfolio health', a specific asset like BUIDL, "
                                "or 'run a stress scenario'."
                            )
                    st.markdown(
                        f"""<div style="background:#0D1117;border:1px solid #00D4FF;border-radius:8px;
                                        padding:14px 16px;margin-top:8px">
                            <div style="font-size:10px;color:#00D4FF;font-weight:700;
                                        text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">
                                RWA Agent Response
                            </div>
                            <div style="font-size:13px;color:#E2E8F0;line-height:1.6;white-space:pre-line">
                                {_agent_answer}
                            </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if _tool_ctx:
                        with st.expander("Tool data used", expanded=False):
                            for _tn2, _td2 in _tool_ctx.items():
                                st.caption(f"**{_tn2}**: {str(_td2)[:200]}")
                except Exception as _aq_err:
                    st.warning(f"Agent query failed: {_aq_err}")
        else:
            st.warning("Please enter a question above.")

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
            width="stretch",
        )
    else:
        st.caption("Feedback data accumulates as the agent runs over multiple cycles.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: NEWS FEED
# ══════════════════════════════════════════════════════════════════════════════

with tab_news:
    # F6: freshness badge
    st.markdown(
        " &nbsp; ".join([
            _freshness_badge("rwa_news", 1800, "News"),
            _freshness_badge("live_rss_news", 900, "RSS"),
        ]),
        unsafe_allow_html=True,
    )
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
            sent_icon  = {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "■"}.get(sentiment, "■")
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
            width="stretch",
            height=500,
        )
        # F5: CSV export for trade log
        _csv_button(t_df, "trade_log.csv", "⬇ Export Trade Log CSV", key="csv_trade_log")
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
            st.plotly_chart(fig_curve, width="stretch")
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

    # ── R6: Key Rate Duration Breakdown ─────────────────────────────────────
    try:
        from data_feeds import fetch_treasury_yield_curve as _fetch_tsy_reg
        _tsy_reg = _fetch_tsy_reg()
        _tsy_yields = _tsy_reg.get("yields", {})
        if _tsy_yields and not assets_df.empty:
            st.markdown("---")
            st.markdown('<div class="section-header">Key Rate Duration (KRD) Breakdown</div>', unsafe_allow_html=True)
            st.caption("Dollar sensitivity of RWA portfolio value to a 1 basis point (0.01%) move at each key rate tenor — DV01 analysis per the Basel III interest rate risk framework")
            _krd_tenors   = ["1m","3m","6m","1y","2y","5y","10y","30y"]
            _krd_durations = {"1m": 0.083, "3m": 0.25, "6m": 0.5, "1y": 1.0, "2y": 2.0, "5y": 4.5, "10y": 8.5, "30y": 20.0}
            _krd_weight    = {"Government Bonds": 0.6, "Private Credit": 0.25, "Commodities": 0.05, "Real Estate": 0.1}
            _port_value_krd = float(portfolio_value)
            _krd_rows = []
            for _t in _krd_tenors:
                if _t not in _tsy_yields:
                    continue
                _dur = _krd_durations.get(_t, 1.0)
                _wt  = _krd_weight.get("Government Bonds", 0.3)
                _dv01 = _port_value_krd * _dur * _wt / 10000  # DV01 = PV × Duration × weight / 10000
                _yield_val = _tsy_yields[_t]
                _krd_rows.append({"Tenor": _t.upper(), "Yield (%)": _yield_val, "Mod. Duration": _dur, "DV01 ($)": _dv01, "_dv01": _dv01})
            if _krd_rows:
                _krd_c1, _krd_c2 = st.columns([2, 3])
                with _krd_c1:
                    _krd_display = [{"Tenor": r["Tenor"], "Yield (%)": f"{r['Yield (%)']:.3f}%",
                                     "Mod. Duration": f"{r['Mod. Duration']:.2f}",
                                     "DV01 ($)": f"${r['DV01 ($)']:,.2f}"} for r in _krd_rows]
                    st.dataframe(pd.DataFrame(_krd_display).set_index("Tenor"), width="stretch")
                with _krd_c2:
                    _krd_fig = go.Figure(go.Bar(
                        x=[r["Tenor"] for r in _krd_rows],
                        y=[r["_dv01"]  for r in _krd_rows],
                        marker_color="#6366f1",
                        text=[f"${r['DV01 ($)']:,.1f}" for r in _krd_rows],
                        textposition="outside",
                    ))
                    _krd_fig.update_layout(
                        title="DV01 by Key Rate Tenor",
                        height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#e2e8f0", size=11),
                        margin=dict(l=0, r=0, t=40, b=0),
                        yaxis=dict(title="DV01 ($)", gridcolor="rgba(255,255,255,0.05)"),
                    )
                    st.plotly_chart(_krd_fig, width="stretch")
                st.caption(f"DV01 = dollar loss for 1bps parallel shift · Portfolio: ${portfolio_value:,.0f} · Model: 60% govn bonds, 25% credit, 15% other")
                _user_level_r6 = st.session_state.get("user_level", "beginner")
                if _user_level_r6 == "beginner":
                    st.info("💡 **What does this mean for me?** When interest rates go up, bond prices go down. 'Key Rate Duration' tells you exactly how much your portfolio loses in dollars if interest rates rise by just 0.01% at different time horizons. Shorter tenors (1M, 3M) affect short bonds; longer tenors (10Y, 30Y) affect long bonds. Bigger bar = more sensitive to rate changes at that tenor.")
    except Exception as _r6_err:
        logger.debug("[R6] KRD panel skipped: %s", _r6_err)

    # ── R10: Basel IV FRTB Capital Widget ────────────────────────────────────
    try:
        st.markdown("---")
        st.markdown('<div class="section-header">Basel IV FRTB Capital Requirements</div>', unsafe_allow_html=True)
        st.caption("Fundamental Review of the Trading Book (FRTB) — Basel IV SA framework capital charges for tokenized RWA asset categories. Effective for banks from January 2025 (EU CRR3).")
        _FRTB_TABLE = [
            {"Category": "US Treasuries / Govt Bonds", "Risk Weight": "0%",   "SA Capital Factor": "0.0%", "FRTB Bucket": "GIRR",  "Notes": "Zero credit risk weight under CRR3. Government bond SA delta = duration × yield sensitivity × 0.0001."},
            {"Category": "Investment Grade Corp Bonds", "Risk Weight": "20%",  "SA Capital Factor": "0.5%", "FRTB Bucket": "CSR",   "Notes": "Credit Spread Risk bucket. SA: 0.5% per unit of CS01 for IG bonds (spread duration × 0.5bps)."},
            {"Category": "Private Credit / Sub-IG",     "Risk Weight": "100%", "SA Capital Factor": "3.0%", "FRTB Bucket": "CSR",   "Notes": "Sub-IG and unrated = higher CSR bucket. 3% capital factor. Tokenized private credit treated equivalently."},
            {"Category": "Tokenized Real Estate",       "Risk Weight": "100%", "SA Capital Factor": "8.0%", "FRTB Bucket": "Equity","Notes": "Equity risk bucket — real estate tokens treated as equity-like instruments. High capital charge."},
            {"Category": "Gold / Commodities",          "Risk Weight": "0%",   "SA Capital Factor": "16%",  "FRTB Bucket": "Cmdty", "Notes": "Commodity risk bucket. Gold SA charge = 16% × spot position × vega add-on. High volatility bucket."},
            {"Category": "Tokenized BTC / Crypto",      "Risk Weight": "1250%","SA Capital Factor": "100%", "FRTB Bucket": "Other", "Notes": "1250% risk weight under Basel III Art. 501c. FRTB: full deduction from capital. Effectively 100% capital charge."},
        ]
        _rw_colors = {"0%": "#22c55e", "20%": "#10b981", "100%": "#f59e0b", "1250%": "#ef4444"}
        _frtb_cols = st.columns(3)
        for _fi, _fr in enumerate(_FRTB_TABLE):
            _frw = _fr["Risk Weight"]
            _fcolor = _rw_colors.get(_frw, "#6b7280")
            with _frtb_cols[_fi % 3]:
                st.markdown(f"""
<div style="background:#111827;border:1px solid {_fcolor}33;border-top:3px solid {_fcolor};
            border-radius:8px;padding:12px;margin-bottom:8px">
  <div style="font-size:11px;font-weight:700;color:#e2e8f0;margin-bottom:6px">{_fr['Category']}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
    <div><div style="font-size:10px;color:#6b7280">Risk Weight</div>
         <div style="font-size:16px;font-weight:700;color:{_fcolor}">{_frw}</div></div>
    <div><div style="font-size:10px;color:#6b7280">SA Capital</div>
         <div style="font-size:16px;font-weight:700;color:{_fcolor}">{_fr['SA Capital Factor']}</div></div>
  </div>
  <div style="font-size:10px;color:#6366f1;font-weight:600;margin-bottom:4px">Bucket: {_fr['FRTB Bucket']}</div>
  <div style="font-size:10px;color:#6b7280;line-height:1.5">{_fr['Notes']}</div>
</div>""", unsafe_allow_html=True)
        st.caption("Source: Basel Committee FRTB (d457) · EU CRR3 (Reg. 2024/1623) · Effective Jan 2025. For informational purposes only.")
        _user_level_r10 = st.session_state.get("user_level", "beginner")
        if _user_level_r10 == "beginner":
            st.info("💡 **What does this mean for me?** Basel IV is a set of global rules that tell banks how much capital they must hold against different types of investments. A higher 'risk weight' means the bank needs more reserve money — making that asset more expensive for them to hold. Assets with low or zero risk weights (like government bonds) are cheapest for banks, which is why institutions prefer them. This chart shows where each RWA category falls in those rules.")
    except Exception as _r10_err:
        logger.debug("[R10] FRTB panel skipped: %s", _r10_err)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 10: CRYPTO SCREENER  (Upgrade 8)
# ══════════════════════════════════════════════════════════════════════════════

with tab_screener:
    # Item 39: extended name/icon maps to cover all MUST_HAVE coins
    _SCR_NAMES = {
        "BTCUSDT":  "Bitcoin",  "ETHUSDT": "Ethereum", "SOLUSDT": "Solana",
        "XRPUSDT":  "XRP",      "XLMUSDT": "Stellar",  "XDCUSDT": "XDC Network",
        "HBARUSDT": "Hedera",
    }
    _SCR_ICONS = {
        "BTCUSDT": "₿", "ETHUSDT": "Ξ", "SOLUSDT": "◎", "XRPUSDT": "✕",
        "XLMUSDT": "★", "XDCUSDT": "◆", "HBARUSDT": "ℏ",
    }

    st.markdown("### 🔍 Crypto Screener")
    st.markdown(
        "<p style='color:#6B7280;font-size:13px;margin-top:-8px'>"
        "Multi-timeframe signals for BTC · ETH · SOL · XRP · XLM · XDC · HBAR — "
        "RSI · EMA stack · Volume anomaly · Funding rate · Open interest · MTF confidence"
        "</p>",
        unsafe_allow_html=True,
    )
    # F6: freshness badge
    st.markdown(
        _freshness_badge("coingecko_prices", 300, "Prices"),
        unsafe_allow_html=True,
    )

    _scr_refresh = st.button("⟳ Refresh Screener", key="btn_scr_refresh")

    if _scr_refresh:
        _load_screener_signals.clear()

    with st.spinner("Fetching Bybit data…"):
        sig_data = _load_screener_signals()

    # ── Signal cards — 4 per row, chunked (item 39: 7 coins across 2 rows) ──────
    # Pre-collect all symbols into rows of 4 then render row by row
    _scr_per_row = 4
    _scr_chunks  = [_SCR_SYMS[i:i + _scr_per_row] for i in range(0, len(_SCR_SYMS), _scr_per_row)]
    _scr_flat_cols: list = []
    for _chunk in _scr_chunks:
        _chunk_cols = st.columns(len(_chunk))
        _scr_flat_cols.extend(_chunk_cols)

    for idx, sym in enumerate(_SCR_SYMS):
        s = sig_data.get(sym, {})
        with _scr_flat_cols[idx]:
            signal    = s.get("signal", "HOLD")
            sig_color = {"BUY": "#34D399", "SELL": "#EF4444", "HOLD": "#FBBF24"}.get(signal, "#9CA3AF")
            sig_bg    = {"BUY": "#064E3B", "SELL": "#7F1D1D", "HOLD": "#78350F"}.get(signal, "#1F2937")
            # Shape encoding for color-blind safety: ▲ BUY / ▼ SELL / ■ HOLD (NEUTRAL)
            sig_shape = {"BUY": "▲", "SELL": "▼", "HOLD": "■"}.get(signal, "■")
            sig_label = f"{sig_shape} {signal}"

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
      {_SCR_ICONS.get(sym, "◎")}&nbsp;{_SCR_NAMES.get(sym, sym.replace("USDT",""))}
    </span>
    <span style="background:{sig_bg};color:{sig_color};font-size:11px;font-weight:700;
                 padding:3px 10px;border-radius:6px">{sig_label}</span>
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
        row = {"Asset": _SCR_NAMES.get(sym, sym.replace("USDT", ""))}
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
        width="stretch",
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
# TAB 10: RESEARCH (Macro Intelligence + RWA On-Chain Activity)
# ══════════════════════════════════════════════════════════════════════════════

with tab_research:
    # F6: freshness badges for research data sources
    _res_badges = " &nbsp; ".join([
        _freshness_badge("macro_indicators", 3600, "FRED Macro"),
        _freshness_badge("yfinance_macro", 3600, "yfinance"),
        _freshness_badge("fear_greed_index", 3600, "Fear & Greed"),
        _freshness_badge("fred_extended", 3600, "FRED Extended"),
    ])
    st.markdown(_res_badges, unsafe_allow_html=True)

    with st.expander("🌍 Macro Intelligence", expanded=True):
        st.markdown('<div class="section-header">Macro Intelligence Dashboard</div>', unsafe_allow_html=True)
        st.caption("FRED + yfinance macro data · Rolling correlations with BTC · M2 84-day lead indicator")

        # ── Load data ──────────────────────────────────────────────────────────────
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

        # ── FRED Extended Series (#29) ─────────────────────────────────────────────
        st.markdown("#### Credit Spreads · Inflation Breakevens · SOFR · Jobless Claims")
        st.caption("FRED extended series — key risk signals for RWA credit quality and macro stress")

        _fred_ext = _load_fred_extended()

        _fe1, _fe2, _fe3, _fe4, _fe5, _fe6, _fe7, _fe8 = st.columns(8)
        _t10_be  = _fred_ext.get("t10_breakeven", 2.3)
        _t5_be   = _fred_ext.get("t5_breakeven",  2.5)
        _sofr    = _fred_ext.get("sofr",           5.3)
        _rrp     = _fred_ext.get("rrp_bn",         300.0)
        _jclaims = _fred_ext.get("jobless_claims", 220.0)
        _hy_sp   = _fred_ext.get("hy_spread_bp",   340.0)
        _ig_sp   = _fred_ext.get("ig_spread_bp",   100.0)
        _fed_ass = _fred_ext.get("fed_assets_mn",  6_800_000.0)

        _fe1.metric("10Y Breakeven", f"{_t10_be:.2f}%",
                    help="10-year inflation breakeven (T10YIE). Market's 10-year inflation expectation.")
        _fe2.metric("5Y Breakeven",  f"{_t5_be:.2f}%",
                    help="5-year inflation breakeven (T5YIE). Near-term inflation expectation.")
        _fe3.metric("SOFR",          f"{_sofr:.2f}%",
                    help="Secured Overnight Financing Rate — the benchmark short-term US dollar rate.")
        _fe4.metric("ON RRP ($B)",   f"${_rrp:.0f}B",
                    help="Fed Overnight Reverse Repo facility — measures excess liquidity parked at the Fed.")
        _fe5.metric("Jobless Claims", f"{_jclaims:.0f}K",
                    help="Initial jobless claims (ICSA). Rising = labor market weakening.")
        _fe6.metric("HY Spread (bp)", f"{_hy_sp:.0f}",
                    help="US High Yield OAS spread (BAMLH0A0HYM2). Rising = credit stress, risk-off.")
        _fe7.metric("IG Spread (bp)", f"{_ig_sp:.0f}",
                    help="US Investment Grade OAS spread (BAMLC0A0CM). Rising = credit tightening.")
        _fed_ass_bn = _fed_ass / 1000.0   # convert millions → billions
        _fe8.metric("Fed Assets ($B)", f"${_fed_ass_bn:,.0f}B",
                    help="Fed total balance sheet assets (WTREGEN). Rising = QE / liquidity injection.")

        _credit_regime = _fred_ext.get("credit_regime", "NEUTRAL")
        _cr_color = {"RISK_ON": "#34D399", "CAUTION": "#FBBF24", "RISK_OFF": "#EF4444", "NEUTRAL": "#9CA3AF"}.get(_credit_regime, "#9CA3AF")
        st.markdown(
            f"<div style='background:rgba(255,255,255,0.04);border:1px solid {_cr_color}40;"
            f"border-radius:6px;padding:8px 14px;font-size:12px;color:{_cr_color};margin-top:4px'>"
            f"<b>Credit Regime:</b> {_credit_regime} "
            f"&nbsp;·&nbsp; Source: <b>{_fred_ext.get('source','fallback')}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ── Fear & Greed — 30-Day Sparkline (#27) ─────────────────────────────────
        st.markdown("#### Fear & Greed Index — 30-Day History")
        st.caption("Crypto Fear & Greed Index (alternative.me) — daily value over the past 30 days. "
                   "0 = Extreme Fear (buy signal), 100 = Extreme Greed (sell signal).")

        _fg_full = _load_fg_history()
        _fg_history = _fg_full.get("history", [])
        _fg_current = _fg_full.get("current", {})

        if _fg_history:
            # Reverse so oldest → newest (API returns newest first)
            _fg_rev = list(reversed(_fg_history))
            _fg_vals  = [h.get("value", 50) for h in _fg_rev]
            _fg_dates = [h.get("date", "") for h in _fg_rev]

            import plotly.graph_objects as go

            # Colour each bar by F&G zone
            def _fg_bar_color(v):
                if v <= 20:  return "#8B5CF6"   # Extreme Fear — purple
                if v <= 40:  return "#F97316"   # Fear — orange
                if v <= 60:  return "#9CA3AF"   # Neutral — grey
                if v <= 80:  return "#FBBF24"   # Greed — yellow
                return "#34D399"                 # Extreme Greed — green

            _bar_colors = [_fg_bar_color(v) for v in _fg_vals]

            fig_fg = go.Figure(go.Bar(
                x=_fg_dates,
                y=_fg_vals,
                marker_color=_bar_colors,
                hovertemplate="<b>%{x}</b><br>F&G: %{y}<extra></extra>",
            ))
            fig_fg.add_hline(y=25, line_dash="dot", line_color="rgba(239,68,68,0.5)",
                             annotation_text="Extreme Fear ≤25", annotation_font_size=10)
            fig_fg.add_hline(y=75, line_dash="dot", line_color="rgba(52,211,153,0.5)",
                             annotation_text="Extreme Greed ≥75", annotation_font_size=10)
            fig_fg.update_layout(
                height=220,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.07)", ticksuffix=""),
                xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=-45, tickfont=dict(size=9)),
                showlegend=False,
            )
            st.plotly_chart(fig_fg, width="stretch")
            _fg_now_val = _fg_current.get("value", _fg_val)
            _fg_now_lbl = _fg_current.get("label", _fg_lbl)
            st.caption(
                f"Current: **{_fg_now_val}/100** ({_fg_now_lbl}) · "
                f"Signal: **{_fg_full.get('signal','NEUTRAL')}** · "
                f"Source: {_fg_full.get('source','fallback')}"
            )
        else:
            # Fallback: show single value card when no history
            st.metric("Fear & Greed", f"{_fg_val}/100", delta=_fg_lbl)
            st.caption("30-day history unavailable — requires alternative.me API connection.")

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
                    st.plotly_chart(fig_corr, width="stretch")

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
                    st.plotly_chart(fig_bar, width="stretch")
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
                # add_hline() does not support secondary_y — use add_trace on secondary axis instead
                fig_m2.add_trace(
                    go.Scatter(
                        x=[btc_df.index[0], btc_df.index[-1]],
                        y=[m2_now, m2_now],
                        mode="lines",
                        name=f"M2 now: ${m2_now:,.0f}B",
                        line=dict(dash="dot", color="rgba(99,102,241,0.6)", width=1.5),
                        showlegend=True,
                    ),
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
                st.plotly_chart(fig_m2, width="stretch")
                st.caption("Note: M2 84-day shift requires FRED historical API key for full series. Set RWA_FRED_API_KEY in .env to enable.")
            else:
                st.info("BTC historical data unavailable.")
        else:
            st.info("Loading 1-year macro timeseries... (requires yfinance installed)")

        st.markdown("---")

        # ── Global M2 Composite + 90-Day Lag Signal ────────────────────────────────
        st.markdown("#### Global M2 Composite — 90-Day Lag BTC Signal")
        st.caption("US M2 × 4.2 scaling (US ≈ 24% of global M2). Rising M2 typically precedes BTC rallies by ~90 days.")

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

        _stb = _load_stable()
        _stb_c1, _stb_c2, _stb_c3, _stb_c4 = st.columns(4)
        _stb_c1.metric("USDT", f"${_stb.get('usdt_bn', 140.0):.1f}B")
        _stb_c2.metric("USDC", f"${_stb.get('usdc_bn', 58.0):.1f}B")
        _stb_c3.metric("RLUSD", f"${_stb.get('rlusd_bn', 0.0):.2f}B")
        _stb_c4.metric("Total", f"${_stb.get('total_bn', 198.0):.1f}B")
        st.caption(f"Source: {_stb.get('source','fallback')} · Updated: {_stb.get('timestamp','')[:19]}")

        st.markdown("---")

        # ── Macro Regime — HMM Probabilistic Classifier (#55) ─────────────────────
        st.markdown("#### Macro Regime — HMM Probabilistic Classifier")
        st.caption("Gaussian observation scoring across 4 macro states (VIX, yield spread, DXY, WTI oil). "
                   "Bars show soft probability assignment — not binary classification.")

        _hmm = _load_hmm_regime()
        regime_data = (_hmm.get("regime") if _hmm else None) or market.get("macro_regime", "NEUTRAL")
        regime_bias = market.get("macro_bias", "NEUTRAL")
        regime_desc = (_hmm.get("description") if _hmm else None) or market.get("macro_description", "")
        regime_colors = {
            "RISK_ON": "#10b981", "RISK_OFF": "#ef4444",
            "STAGFLATION": "#f59e0b", "LIQUIDITY_CRUNCH": "#8b5cf6", "NEUTRAL": "#6b7280",
        }
        r_color = regime_colors.get(regime_data, "#6b7280")

        # Probability bars
        _hmm_probs = (_hmm.get("probabilities") if _hmm else None) or {}
        _hmm_conf  = (_hmm.get("confidence") if _hmm else None) or 0.0
        _hmm_dom   = (_hmm.get("dominant_signal") if _hmm else None) or "—"
        _hmm_src   = (_hmm.get("source") if _hmm else "fallback")

        # Show regime label + description
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border:1px solid {r_color};
        border-radius:8px;padding:16px 20px;margin-bottom:8px">
            <div style="font-size:18px;font-weight:700;color:{r_color}">{regime_data.replace('_', ' ')}</div>
            <div style="font-size:13px;color:#9ca3af;margin-top:6px">{regime_desc}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px">
                Bias: <b style="color:{r_color}">{regime_bias}</b>
                &nbsp;·&nbsp; Confidence: <b style="color:{r_color}">{int(_hmm_conf*100)}%</b>
                &nbsp;·&nbsp; Dominant signal: <b style="color:#9ca3af">{_hmm_dom}</b>
                &nbsp;·&nbsp; Source: <b style="color:#4b5563">{_hmm_src}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 3-bar probability display
        if _hmm_probs:
            _prob_defs = [
                ("RISK_ON",  _hmm_probs.get("RISK_ON",  0.33), "#10b981", "Risk On"),
                ("NEUTRAL",  _hmm_probs.get("NEUTRAL",  0.34), "#6b7280", "Neutral"),
                ("RISK_OFF", _hmm_probs.get("RISK_OFF", 0.33), "#ef4444", "Risk Off"),
            ]
            st.markdown("**Regime Probability Distribution**")
            for _pkey, _pval, _pcol, _plabel in _prob_defs:
                _pw = int(_pval * 100)
                st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:5px">
          <div style="min-width:72px;font-size:11px;color:{_pcol};text-transform:uppercase;letter-spacing:0.04em">{_plabel}</div>
          <div style="flex:1;background:#1F2937;border-radius:4px;height:16px;overflow:hidden">
        <div style="background:{_pcol};width:{_pw}%;height:100%;border-radius:4px;
                    display:flex;align-items:center;padding-left:6px">
          <span style="font-size:10px;color:#fff;font-weight:700">{_pval:.1%}</span>
        </div>
          </div>
        </div>""", unsafe_allow_html=True)
            st.caption("RISK_ON = green · NEUTRAL = grey · RISK_OFF = red")

        st.markdown("---")

        # ── BTC/ETH On-Chain Signals (#54) ─────────────────────────────────────────
        st.markdown("#### BTC / ETH Perpetual Funding & Open Interest")
        st.caption("Bybit v5 perpetual markets · Funding rate per 8h · Open interest in USD")

        _ocs = _load_onchain_signals()
        _btc_fr   = _ocs.get("btc_funding_rate")
        _eth_fr   = _ocs.get("eth_funding_rate")
        _btc_fsig = _ocs.get("btc_funding_signal", "NORMAL")
        _eth_fsig = _ocs.get("eth_funding_signal", "NORMAL")
        _btc_oi   = _ocs.get("btc_oi_usd")
        _eth_oi   = _ocs.get("eth_oi_usd")
        _btc_oi7  = _ocs.get("btc_oi_7d_change_pct")
        _eth_oi7  = _ocs.get("eth_oi_7d_change_pct")
        _oc_src   = _ocs.get("source", "unavailable")

        _oc_sig_colors = {
            "OVERHEATED": "#ef4444", "NORMAL": "#9ca3af", "DISCOUNTED": "#10b981"
        }
        _oc_tooltips = {
            "OVERHEATED":  "High positive funding = longs paying shorts = market overextended. Bearish signal.",
            "NORMAL":      "Funding rate within normal range. Market balanced between longs and shorts.",
            "DISCOUNTED":  "Negative funding = shorts paying longs = market underextended. Potential bullish reversal.",
        }

        def _fmt_fr(v):
            if v is None: return "—"
            return f"{v*100:.4f}%"

        def _fmt_oi(v):
            if v is None: return "—"
            if v >= 1e9: return f"${v/1e9:.2f}B"
            return f"${v/1e6:.0f}M"

        def _fmt_oi7(v):
            if v is None: return "—"
            return f"{v:+.1f}%"

        _oc1, _oc2, _oc3, _oc4 = st.columns(4)
        with _oc1:
            _fc = _oc_sig_colors.get(_btc_fsig, "#9ca3af")
            st.markdown(f"""
        <div style="background:#111827;border:1px solid {_fc}40;border-radius:8px;padding:12px;
                border-top:3px solid {_fc}">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.6px">BTC Funding Rate</div>
          <div style="font-size:20px;font-weight:800;color:{_fc}">{_fmt_fr(_btc_fr)}</div>
          <div style="font-size:11px;color:{_fc};font-weight:600">{_btc_fsig}</div>
          <div style="font-size:9px;color:#4b5563;margin-top:3px">{_oc_tooltips.get(_btc_fsig,'')}</div>
        </div>""", unsafe_allow_html=True)
        with _oc2:
            _fc = _oc_sig_colors.get(_eth_fsig, "#9ca3af")
            st.markdown(f"""
        <div style="background:#111827;border:1px solid {_fc}40;border-radius:8px;padding:12px;
                border-top:3px solid {_fc}">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.6px">ETH Funding Rate</div>
          <div style="font-size:20px;font-weight:800;color:{_fc}">{_fmt_fr(_eth_fr)}</div>
          <div style="font-size:11px;color:{_fc};font-weight:600">{_eth_fsig}</div>
          <div style="font-size:9px;color:#4b5563;margin-top:3px">{_oc_tooltips.get(_eth_fsig,'')}</div>
        </div>""", unsafe_allow_html=True)
        with _oc3:
            _oi7_c = "#10b981" if (_btc_oi7 or 0) >= 0 else "#ef4444"
            st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;
                border-top:3px solid #6366f1">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.6px">BTC Open Interest</div>
          <div style="font-size:20px;font-weight:800;color:#6366f1">{_fmt_oi(_btc_oi)}</div>
          <div style="font-size:11px;color:{_oi7_c}">7d: {_fmt_oi7(_btc_oi7)}</div>
          <div style="font-size:9px;color:#4b5563;margin-top:3px">Rising OI + rising price = healthy trend</div>
        </div>""", unsafe_allow_html=True)
        with _oc4:
            _oi7_c = "#10b981" if (_eth_oi7 or 0) >= 0 else "#ef4444"
            st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;
                border-top:3px solid #8b5cf6">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.6px">ETH Open Interest</div>
          <div style="font-size:20px;font-weight:800;color:#8b5cf6">{_fmt_oi(_eth_oi)}</div>
          <div style="font-size:11px;color:{_oi7_c}">7d: {_fmt_oi7(_eth_oi7)}</div>
          <div style="font-size:9px;color:#4b5563;margin-top:3px">Rising OI + rising price = healthy trend</div>
        </div>""", unsafe_allow_html=True)
        st.caption(f"Source: {_oc_src} · Cached 15 min · Updated: {_ocs.get('timestamp','')[:19]}")

        st.markdown("---")

        # ── Protocol Health — DeFiLlama Fee Revenue (#57) ─────────────────────────
        st.markdown("#### RWA Protocol Health — Fee Revenue")
        st.caption("DeFiLlama fees endpoint · 24h and 30d fee collection for top RWA protocols. "
                   "Declining fees = shrinking origination. GREEN = on pace, YELLOW = slowing, RED = declining.")

        _pf = _load_protocol_fees()
        _pf_ts = _pf.get("timestamp", "")

        # Key RWA protocol slugs to display
        _PF_DISPLAY = [
            ("centrifuge",    "Centrifuge"),
            ("maple",         "Maple Finance"),
            ("goldfinch",     "Goldfinch"),
            ("clearpool",     "Clearpool"),
            ("truefi",        "TrueFi"),
            ("ondo-finance",  "Ondo Finance"),
        ]
        _PF_HEALTH_COLORS = {"GREEN": "#10b981", "YELLOW": "#f59e0b", "RED": "#ef4444"}

        def _fmt_fee(v):
            if v is None or v == 0: return "—"
            if v >= 1e6: return f"${v/1e6:.2f}M"
            if v >= 1e3: return f"${v/1e3:.1f}K"
            return f"${v:.0f}"

        _pf_entries = [(slug, label, _pf.get(slug)) for slug, label in _PF_DISPLAY if _pf.get(slug)]
        if _pf_entries:
            _pf_cols = st.columns(min(len(_pf_entries), 3))
            for _pfi, (slug, label, pdata) in enumerate(_pf_entries):
                with _pf_cols[_pfi % 3]:
                    _health     = pdata.get("health", "YELLOW")
                    _h_color    = _PF_HEALTH_COLORS.get(_health, "#9ca3af")
                    _fees24h    = pdata.get("fees_24h", 0)
                    _fees30d    = pdata.get("fees_30d", 0)
                    _annualized = pdata.get("annualized", 0)
                    st.markdown(f"""
        <div style="background:#111827;border:1px solid {_h_color}40;border-radius:8px;
                padding:12px;margin-bottom:8px;border-top:3px solid {_h_color}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <div style="font-size:12px;font-weight:600;color:#e2e8f0">{label}</div>
        <div style="font-size:10px;font-weight:700;color:{_h_color};background:{_h_color}20;
                    padding:2px 8px;border-radius:4px">{_health}</div>
          </div>
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px">Fees 24h</div>
          <div style="font-size:16px;font-weight:700;color:{_h_color}">{_fmt_fee(_fees24h)}</div>
          <div style="font-size:10px;color:#4b5563;margin-top:4px">
        30d: {_fmt_fee(_fees30d)} &nbsp;·&nbsp; Ann: {_fmt_fee(_annualized)}
          </div>
        </div>""", unsafe_allow_html=True)
            st.caption(f"Source: DeFiLlama Fees · Cached 1h · Updated: {_pf_ts[:19]}")
        else:
            st.info("Protocol fee data loading... Requires DeFiLlama fees API connection (api.llama.fi).")

        # ── R5: RWA Adoption Velocity ─────────────────────────────────────────────
        try:
            st.markdown("---")
            st.markdown('<div class="section-header">RWA Adoption Velocity</div>', unsafe_allow_html=True)
            st.caption("Tokenized asset market growth trajectory — TVL milestones and quarter-over-quarter adoption acceleration. Source: RWA.xyz / DeFiLlama historical estimates.")
            # Static milestones (best public data available without paid API)
            _RWA_MILESTONES = [
                {"quarter": "Q1 2021", "tvl_bn": 0.3,  "label": "Centrifuge + MakerDAO pioneer RWA collateral"},
                {"quarter": "Q2 2022", "tvl_bn": 0.7,  "label": "Maple Finance + Goldfinch scale private credit"},
                {"quarter": "Q4 2022", "tvl_bn": 1.5,  "label": "MakerDAO adds US Treasuries as collateral"},
                {"quarter": "Q2 2023", "tvl_bn": 3.5,  "label": "BlackRock BUIDL launch — institutional watershed"},
                {"quarter": "Q4 2023", "tvl_bn": 7.5,  "label": "Ondo OUSG crosses $500M TVL; Franklin BENJI $300M"},
                {"quarter": "Q2 2024", "tvl_bn": 12.0, "label": "Total tokenized treasuries hit $1B milestone"},
                {"quarter": "Q4 2024", "tvl_bn": 16.5, "label": "BUIDL crosses $500M; Apollo tokenized credit fund"},
                {"quarter": "Q1 2025", "tvl_bn": 19.0, "label": "Ondo OUSG $2B+; Ethena sUSDe integration"},
                {"quarter": "Q4 2025", "tvl_bn": 28.0, "label": "Cross-chain RWA expansion; AAVE Horizon announced"},
                {"quarter": "Q1 2026", "tvl_bn": 35.0, "label": "Total tokenized asset market approaches $40B"},
            ]
            _qvl = [m["tvl_bn"] for m in _RWA_MILESTONES]
            _qbns = [m["quarter"] for m in _RWA_MILESTONES]
            # QoQ growth calculation
            _qgrowth = [None] + [(_qvl[i] - _qvl[i-1]) / _qvl[i-1] * 100 for i in range(1, len(_qvl))]
            _r5_c1, _r5_c2, _r5_c3 = st.columns(3)
            _r5_c1.metric("Current Est. TVL",   f"${_qvl[-1]:.0f}B",                  help="Estimated total tokenized RWA market TVL (Q1 2026 estimate)")
            _r5_c2.metric("QoQ Growth",          f"{_qgrowth[-1]:+.1f}%",             help="Quarter-over-quarter TVL growth rate — latest period vs prior quarter")
            _r5_c3.metric("Growth Since 2021",   f"{((_qvl[-1]/_qvl[0])-1)*100:.0f}%", help="Total market growth from Q1 2021 baseline to today")
            _r5_fig = go.Figure()
            _r5_fig.add_trace(go.Scatter(
                x=_qbns, y=_qvl,
                mode="lines+markers+text",
                line=dict(color="#00d4aa", width=2.5),
                marker=dict(size=8, color="#00d4aa"),
                text=[f"${v:.1f}B" for v in _qvl],
                textposition="top center",
                textfont=dict(size=9),
                fill="tozeroy",
                fillcolor="rgba(0,212,170,0.08)",
                hovertemplate="<b>%{x}</b><br>TVL: $%{y:.1f}B<extra></extra>",
            ))
            for _mi, _m in enumerate(_RWA_MILESTONES):
                if "BUIDL" in _m["label"] or "watershed" in _m["label"] or "billion" in _m["label"].lower():
                    _r5_fig.add_annotation(
                        x=_m["quarter"], y=_m["tvl_bn"],
                        text=_m["label"][:35] + "…",
                        showarrow=True, arrowhead=2, arrowcolor="#f59e0b",
                        font=dict(size=8, color="#f59e0b"),
                        bgcolor="rgba(17,24,39,0.9)", bordercolor="#f59e0b",
                        borderwidth=1, ax=0, ay=-40,
                    )
            _r5_fig.update_layout(
                height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0", size=11),
                margin=dict(l=0, r=0, t=20, b=60),
                xaxis=dict(tickangle=-30, gridcolor="rgba(255,255,255,0.04)"),
                yaxis=dict(title="TVL ($ Billions)", gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(_r5_fig, width="stretch")
            _user_level_r5 = st.session_state.get("user_level", "beginner")
            if _user_level_r5 == "beginner":
                st.info("💡 **What does this mean for me?** This chart shows how fast the real-world asset tokenization market has been growing. In 2021, barely $300 million of real assets were tokenized. By 2026, it's estimated to be $35+ billion and accelerating. Early positioning in high-quality RWA assets puts you ahead of institutional adoption.")
        except Exception as _r5_err:
            logger.debug("[R5] Adoption velocity skipped: %s", _r5_err)

        # ── Crypto Derivatives Context (moved from Options Flow tab) ──────────────
        st.markdown("---")
        with st.expander("📐 Crypto Derivatives Context — BTC/ETH Options (Deribit)", expanded=False):
            st.caption("Deribit public API · no key required · Put/Call Ratio · Max Pain · IV Term Structure · Cached 15 min · Useful for macro timing of RWA entries/exits")
            import plotly.graph_objects as _go_m
            from plotly.subplots import make_subplots as _msp_m
            _d_curr = st.selectbox("Currency", ["BTC", "ETH"], key="macro_opt_curr_sel")
            _d_oc   = _load_deribit_options(_d_curr)
            if _d_oc.get("error") and not _d_oc.get("oi_by_strike"):
                st.warning(f"Options data unavailable: {_d_oc.get('error')}. Deribit may be temporarily unreachable.")
            else:
                _d_pc   = _d_oc.get("put_call_ratio")
                _d_mp   = _d_oc.get("max_pain")
                _d_tput = _d_oc.get("total_put_oi", 0)
                _d_tcal = _d_oc.get("total_call_oi", 0)
                _d_osig = _d_oc.get("signal", "N/A")
                _d_spot = _d_oc.get("spot_price")
                _d_sc = {
                    "EXTREME_PUTS":  "#ef4444", "BEARISH": "#f59e0b",
                    "NEUTRAL":       "#6b7280", "BULLISH": "#10b981",
                    "EXTREME_CALLS": "#00d4aa",
                }.get(_d_osig, "#6b7280")
                _dc1, _dc2, _dc3, _dc4 = st.columns(4)
                with _dc1:
                    st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_d_sc};border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">Put/Call Ratio</div>
          <div style="font-size:28px;font-weight:700;color:{_d_sc}">{f"{_d_pc:.3f}" if _d_pc is not None else "—"}</div>
          <div style="font-size:12px;color:#9ca3af">{_d_osig.replace("_", " ")}</div>
        </div>""", unsafe_allow_html=True)
                with _dc2:
                    _d_mp_dist = (f"{abs(_d_mp - _d_spot) / _d_spot * 100:.1f}% {'below' if _d_mp < _d_spot else 'above'} spot"
                                  if _d_mp and _d_spot else "")
                    st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #6366f1;border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">Max Pain</div>
          <div style="font-size:24px;font-weight:700;color:#6366f1">{f"${_d_mp:,.0f}" if _d_mp else "—"}</div>
          <div style="font-size:11px;color:#6b7280">{_d_mp_dist}</div>
        </div>""", unsafe_allow_html=True)
                with _dc3:
                    st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #ef4444;border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">Total Put OI</div>
          <div style="font-size:24px;font-weight:700;color:#ef4444">{f"{_d_tput:,.0f}" if _d_tput else "—"}</div>
          <div style="font-size:11px;color:#6b7280">contracts</div>
        </div>""", unsafe_allow_html=True)
                with _dc4:
                    st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #10b981;border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">Total Call OI</div>
          <div style="font-size:24px;font-weight:700;color:#10b981">{f"{_d_tcal:,.0f}" if _d_tcal else "—"}</div>
          <div style="font-size:11px;color:#6b7280">contracts</div>
        </div>""", unsafe_allow_html=True)
                _d_oi = _d_oc.get("oi_by_strike", [])
                _d_ts = _d_oc.get("term_structure", [])
                if _d_oi or _d_ts:
                    _dm_c1, _dm_c2 = st.columns([3, 2])
                    with _dm_c1:
                        if _d_oi:
                            _d_fig = _go_m.Figure()
                            _d_strikes = [str(int(r["strike"])) for r in _d_oi]
                            _d_fig.add_trace(_go_m.Bar(name="Puts", x=_d_strikes, y=[r["put_oi"] for r in _d_oi], marker_color="rgba(239,68,68,0.75)"))
                            _d_fig.add_trace(_go_m.Bar(name="Calls", x=_d_strikes, y=[r["call_oi"] for r in _d_oi], marker_color="rgba(16,185,129,0.75)"))
                            _d_fig.update_layout(barmode="group", height=280, paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0", size=10),
                                margin=dict(l=0, r=0, t=30, b=0), title="OI by Strike",
                                xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
                                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"))
                            st.plotly_chart(_d_fig, width="stretch")
                    with _dm_c2:
                        _d_ts_valid = [t for t in _d_ts if t.get("atm_iv") and t.get("dte") is not None]
                        if _d_ts_valid:
                            _d_figb = _go_m.Figure()
                            _d_figb.add_trace(_go_m.Scatter(
                                x=[t["dte"] for t in _d_ts_valid], y=[t["atm_iv"] for t in _d_ts_valid],
                                mode="lines+markers", name="ATM IV",
                                line=dict(color="#6366f1", width=2), marker=dict(size=7)))
                            _d_figb.update_layout(height=280, paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0", size=10),
                                margin=dict(l=0, r=0, t=30, b=0), title="IV Term Structure",
                                xaxis=dict(title="DTE", gridcolor="rgba(255,255,255,0.04)"),
                                yaxis=dict(title="IV (%)", gridcolor="rgba(255,255,255,0.05)"))
                            st.plotly_chart(_d_figb, width="stretch")
                _d_ts_str = _d_oc.get("timestamp", "")[:19]
                st.caption(f"Source: Deribit · {_d_ts_str} UTC · For macro timing context — not a direct RWA signal")


    with st.expander("⛓️ RWA On-Chain Activity", expanded=True):
        st.markdown("### ⛓️ RWA On-Chain Intelligence")
        st.caption("DeFiLlama RWA category · Centrifuge · Maple · Tokenized Treasury TVL · Protocol adoption trends · Cached 1h")

        # ── RWA Total TVL ─────────────────────────────────────────────────────────
        try:
            _rwa_total = _df.get_total_rwa_tvl()
            _rwa_protos_raw = _df.fetch_defillama_protocols()
            _rwa_protos = [
                p for p in (_rwa_protos_raw or [])
                if str(p.get("category") or "").lower() in ("rwa", "real world assets", "tokenized-assets")
                   or any(str(c).lower() in ("rwa", "tokenized assets", "real world assets") for c in (p.get("chains") or []))
            ]
            # Also pick known RWA protocols by slug
            _RWA_SLUGS = {"ondo-finance", "centrifuge", "maple-finance", "goldfinch", "clearpool",
                          "backed-finance", "superstate", "frax", "pendle", "morpho",
                          "franklin-templeton", "blackrock-buidl"}
            _rwa_protos_extra = [
                p for p in (_rwa_protos_raw or [])
                if any(slug in str(p.get("slug","")).lower() or slug in str(p.get("name","")).lower()
                       for slug in _RWA_SLUGS)
                and p not in _rwa_protos
            ]
            _rwa_protos = (_rwa_protos + _rwa_protos_extra)[:20]

            _rwa_tvl_total_fmt = (f"${_rwa_total/1e9:.2f}B" if _rwa_total and _rwa_total >= 1e9
                                  else f"${_rwa_total/1e6:.0f}M" if _rwa_total and _rwa_total >= 1e6
                                  else f"${_rwa_total:,.0f}" if _rwa_total else "—")

            _rt1, _rt2, _rt3, _rt4 = st.columns(4)
            with _rt1:
                st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #00d4aa;border-radius:10px;padding:16px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Total RWA TVL</div>
          <div style="font-size:28px;font-weight:700;color:#00d4aa">{_rwa_tvl_total_fmt}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">DeFiLlama RWA category</div>
        </div>""", unsafe_allow_html=True)
            with _rt2:
                st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #6366f1;border-radius:10px;padding:16px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Tracked Protocols</div>
          <div style="font-size:28px;font-weight:700;color:#6366f1">{len(_rwa_protos)}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">Active RWA issuers</div>
        </div>""", unsafe_allow_html=True)
            # Centrifuge data
            _cf_pools = _df.fetch_centrifuge_pools() or []
            _cf_tvl = sum(float(p.get("tvl_usd") or p.get("tvl") or 0) for p in _cf_pools)
            _cf_fmt = f"${_cf_tvl/1e6:.0f}M" if _cf_tvl >= 1e6 else f"${_cf_tvl:,.0f}"
            with _rt3:
                st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #f59e0b;border-radius:10px;padding:16px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Centrifuge TVL</div>
          <div style="font-size:28px;font-weight:700;color:#f59e0b">{_cf_fmt if _cf_tvl else "—"}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">{len(_cf_pools)} active pools</div>
        </div>""", unsafe_allow_html=True)
            # Maple data
            _mpl = _df.fetch_maple_stats() or {}
            _mpl_tvl = _mpl.get("tvl_usd") or _mpl.get("totalValueLocked") or 0
            _mpl_fmt = f"${float(_mpl_tvl)/1e6:.0f}M" if float(_mpl_tvl or 0) >= 1e6 else f"${float(_mpl_tvl or 0):,.0f}"
            with _rt4:
                st.markdown(f"""<div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #10b981;border-radius:10px;padding:16px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Maple Finance TVL</div>
          <div style="font-size:28px;font-weight:700;color:#10b981">{_mpl_fmt if float(_mpl_tvl or 0) > 0 else "—"}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">Private credit pools</div>
        </div>""", unsafe_allow_html=True)

            # ── RWA Protocol Table ────────────────────────────────────────────────
            if _rwa_protos:
                st.markdown("---")
                st.markdown("#### Top RWA Protocols by TVL")
                _rwa_rows = []
                for _rp in sorted(_rwa_protos, key=lambda x: float(x.get("tvl") or 0), reverse=True)[:15]:
                    _rp_tvl = float(_rp.get("tvl") or 0)
                    _rp_chg = _rp.get("change_1d") or _rp.get("change_7d")
                    _rwa_rows.append({
                        "Protocol":  str(_rp.get("name") or _rp.get("slug") or "—"),
                        "TVL":       (f"${_rp_tvl/1e9:.2f}B" if _rp_tvl >= 1e9
                                      else f"${_rp_tvl/1e6:.0f}M" if _rp_tvl >= 1e6
                                      else f"${_rp_tvl:,.0f}"),
                        "7d Change": (f"{float(_rp_chg):+.1f}%" if _rp_chg is not None else "—"),
                        "Category":  str(_rp.get("category") or "RWA"),
                        "Chains":    ", ".join((str(c) for c in (_rp.get("chains") or [])[:3])) or "—",
                    })
                if _rwa_rows:
                    import pandas as _pd_oc
                    st.dataframe(_pd_oc.DataFrame(_rwa_rows), hide_index=True, width="stretch")

            # ── Centrifuge Pool Detail ────────────────────────────────────────────
            if _cf_pools:
                with st.expander(f"Centrifuge Pools ({len(_cf_pools)} active)"):
                    _cf_rows = []
                    for _cp in sorted(_cf_pools, key=lambda x: float(x.get("tvl_usd") or x.get("tvl") or 0), reverse=True)[:10]:
                        _cp_tvl = float(_cp.get("tvl_usd") or _cp.get("tvl") or 0)
                        _cf_rows.append({
                            "Pool": str(_cp.get("name") or _cp.get("id") or "—"),
                            "TVL":  f"${_cp_tvl/1e6:.1f}M" if _cp_tvl >= 1e6 else f"${_cp_tvl:,.0f}",
                            "APY":  f"{float(_cp.get('apy') or _cp.get('yield') or 0):.2f}%",
                            "Asset Class": str(_cp.get("asset_class") or _cp.get("type") or "Credit"),
                        })
                    if _cf_rows:
                        import pandas as _pd_cf
                        st.dataframe(_pd_cf.DataFrame(_cf_rows), hide_index=True, width="stretch")

            _user_lvl_oc = st.session_state.get("user_level", "beginner")
            if _user_lvl_oc == "beginner":
                st.info("💡 **What does this mean for me?** This shows the total amount of real-world assets (treasuries, real estate, private credit) that have been tokenized on blockchain. Growing TVL means more institutions are adopting this technology. Centrifuge and Maple are two of the largest real-world lending protocols — they connect traditional businesses with on-chain capital.")

        except Exception as _oc_rwa_err:
            st.warning(f"RWA on-chain data unavailable: {_oc_rwa_err}")

        # ── RLUSD / XRPL Live Data (Group 6) ─────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 🌊 RLUSD & XRP Ledger")
        st.caption("XRPL ledger gateway_balances + CoinGecko · Ripple USD · Cached 15 min")

        _rlusd = _load_xrpl_rlusd()

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

        # ── XRPL MPT (XLS-33d Multi-Purpose Token) (#106) ────────────────────────
        st.markdown("---")
        st.markdown("#### 🔷 XRPL Multi-Purpose Tokens (XLS-33d)")
        st.caption("XRPL JSON-RPC ledger_data · MPT issuances + RLUSD gateway supply · Cached 5 min")

        _mpt = _load_xrpl_mpt()
        if _mpt.get("source") == "unavailable":
            st.caption("MPT data unavailable — XRPL RPC unreachable.")
        else:
            _mpt_rlusd = _mpt.get("rlusd_supply")
            _mpt_total = _mpt.get("mpt_issuance_count", 0)
            _mpt_a, _mpt_b = st.columns(2)
            with _mpt_a:
                _rlusd_fmt = f"${_mpt_rlusd/1e6:.1f}M" if _mpt_rlusd and _mpt_rlusd >= 1e6 else (f"${_mpt_rlusd:,.0f}" if _mpt_rlusd else "—")
                st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #06b6d4;border-radius:10px;padding:16px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">RLUSD Gateway Supply</div>
          <div style="font-size:26px;font-weight:700;color:#06b6d4">{_rlusd_fmt}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">On-ledger RLUSD via gateway_balances</div>
        </div>
        """, unsafe_allow_html=True)
            with _mpt_b:
                st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-top:3px solid #8b5cf6;border-radius:10px;padding:16px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Active MPT Issuances</div>
          <div style="font-size:26px;font-weight:700;color:#8b5cf6">{_mpt_total:,}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">XLS-33d MPT objects on ledger</div>
        </div>
        """, unsafe_allow_html=True)

        # ── XRPL Basic Data (#97) — XRP price + RLUSD supply via fetch_xrpl_data() ─
        st.markdown("---")
        st.markdown("#### 🌐 XRPL Basic Integration (#97)")
        st.caption("XRP price via CoinGecko · RLUSD supply via XRPL cluster / xrpl-py · Cached 15 min")

        if st.button("⟳ Refresh XRPL Basic", key="btn_xrpl_basic"):
            _load_xrpl_basic.clear()

        with st.spinner("Fetching XRPL data…"):
            _xrpl_basic = _load_xrpl_basic()

        _xb_xrp   = _xrpl_basic.get("xrp_price_usd", 0)
        _xb_rlusd = _xrpl_basic.get("rlusd_supply", 0)
        _xb_avail = _xrpl_basic.get("xrpl_available", False)
        _xb_src   = _xrpl_basic.get("source", "—")
        _xb_ts    = (_xrpl_basic.get("timestamp") or "")[:19]

        _xb_c1, _xb_c2, _xb_c3 = st.columns(3)
        with _xb_c1:
            _xrp_clr = "#10b981" if _xb_xrp > 0 else "#6b7280"
            _xrp_fmt = f"${_xb_xrp:.4f}" if _xb_xrp else "—"
            st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_xrp_clr};border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">XRP Price (USD)</div>
          <div style="font-size:24px;font-weight:700;color:{_xrp_clr}">{_xrp_fmt}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">Source: CoinGecko</div>
        </div>
        """, unsafe_allow_html=True)
        with _xb_c2:
            _rlusd_s = (f"${_xb_rlusd/1e9:.2f}B" if _xb_rlusd and _xb_rlusd >= 1e9
                        else f"${_xb_rlusd/1e6:.1f}M" if _xb_rlusd and _xb_rlusd >= 1e6
                        else f"${_xb_rlusd:,.0f}" if _xb_rlusd else "—")
            _rlusd_clr = "#3b82f6" if _xb_rlusd and _xb_rlusd > 0 else "#6b7280"
            st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_rlusd_clr};border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">RLUSD Supply</div>
          <div style="font-size:24px;font-weight:700;color:{_rlusd_clr}">{_rlusd_s}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">XRPL ledger issuance</div>
        </div>
        """, unsafe_allow_html=True)
        with _xb_c3:
            _lib_clr  = "#10b981" if _xb_avail else "#6b7280"
            _lib_lbl  = "xrpl-py installed" if _xb_avail else "xrpl-py not installed"
            st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_lib_clr};border-radius:10px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">xrpl-py Status</div>
          <div style="font-size:16px;font-weight:700;color:{_lib_clr}">{_lib_lbl}</div>
          <div style="font-size:11px;color:#6b7280;margin-top:6px">Source: {_xb_src}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Source: {_xb_src} · {_xb_ts} UTC · pip install xrpl-py>=2.4.0 for direct ledger reads")

        # ─── Chainlink Reference Price Feeds (#108 + #109) ───────────────────────
        st.markdown("---")
        st.markdown("#### 🔗 Chainlink Reference Price Feeds")
        st.caption("Etherscan eth_call proxy · latestAnswer() + decimals() · Cached 1 min")

        if feature_enabled("etherscan"):
            _cl_data = _cl_prices()
            if _cl_data:
                _cl_cols = st.columns(len(_cl_data))
                for _ci, (_pair, _pv) in enumerate(_cl_data.items()):
                    _pv_fmt = f"${_pv:,.4f}" if _pv else "—"
                    _clr = "#10b981" if _pv else "#6b7280"
                    with _cl_cols[_ci]:
                        st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;text-align:center">
          <div style="font-size:10px;color:#6b7280;margin-bottom:4px">{_pair}</div>
          <div style="font-size:18px;font-weight:700;color:{_clr}">{_pv_fmt}</div>
          <div style="font-size:10px;color:#9ca3af">Chainlink</div>
        </div>
        """, unsafe_allow_html=True)
            else:
                st.caption("No Chainlink data — check ETHERSCAN_API_KEY.")
        else:
            st.caption("Set RWA_ETHERSCAN_API_KEY in .env to enable Chainlink price feeds.")

        # ─── ERC-4626 Vault Reader (#103) ────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 🏦 ERC-4626 Tokenized Vault Metrics")
        st.caption("Etherscan eth_call · pricePerShare() + totalAssets() · BUIDL / OUSG / USDY / wstETH")

        if feature_enabled("erc4626") or feature_enabled("etherscan"):
            _vaults = _vault_data()
            _v_cols = st.columns(4)
            for _vi, (_sym, _vd) in enumerate(_vaults.items()):
                _err    = _vd.get("error")
                _pps    = _vd.get("price_per_share")
                _ta     = _vd.get("total_assets")
                _pps_s  = f"${_pps:.6f}" if _pps else "—"
                _ta_s   = (f"${_ta/1e9:.2f}B" if _ta and _ta >= 1e9 else f"${_ta/1e6:.1f}M" if _ta else "—")
                _vc     = "#10b981" if _pps else "#6b7280"
                with _v_cols[_vi]:
                    st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-top:3px solid {_vc};border-radius:10px;padding:14px">
          <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px">{_sym}</div>
          <div style="font-size:10px;color:#6b7280">pricePerShare</div>
          <div style="font-size:16px;font-weight:700;color:{_vc}">{_pps_s}</div>
          <div style="font-size:10px;color:#6b7280;margin-top:6px">totalAssets</div>
          <div style="font-size:14px;color:#9ca3af">{_ta_s}</div>
        </div>
        """, unsafe_allow_html=True)
        else:
            st.caption("Set RWA_ETHERSCAN_API_KEY in .env to enable ERC-4626 vault reader.")

        # ─── ERC-7540 Redemption Queue (#104) ────────────────────────────────────
        st.markdown("---")
        st.markdown("#### ⏳ ERC-7540 Async Redemption Depth")
        st.caption("Etherscan eth_call · totalPendingRedemptions() · BUIDL / OUSG")

        if feature_enabled("erc4626") or feature_enabled("etherscan"):
            _redeems = _redeem_data()
            _rd_cols = st.columns(2)
            for _ri, (_sym, _rd) in enumerate(_redeems.items()):
                _pending = _rd.get("pending_redemptions")
                _p_s     = (f"${_pending/1e6:.1f}M" if _pending and _pending >= 1e6 else
                            f"${_pending:,.0f}" if _pending else "—")
                _rc2     = "#f59e0b" if _pending and _pending > 0 else "#10b981"
                with _rd_cols[_ri]:
                    st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-radius:8px;padding:14px">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.8px">{_sym} Pending Redemptions</div>
          <div style="font-size:22px;font-weight:700;color:{_rc2};margin-top:6px">{_p_s}</div>
          <div style="font-size:11px;color:#9ca3af;margin-top:4px">Queued for settlement (ERC-7540)</div>
        </div>
        """, unsafe_allow_html=True)
        else:
            st.caption("Set RWA_ETHERSCAN_API_KEY in .env to enable ERC-7540 queue depth.")

        # ─── ERC-7540 Redemption Queue — Coverage & Risk Signal (#104 enhanced) ──
        if _pro_mode and (feature_enabled("erc4626") or feature_enabled("etherscan")):
            st.markdown("---")
            st.markdown("#### 🔒 ERC-7540 Vault Coverage & Risk Signal (Pro)")
            st.caption(
                "totalAssets / totalSupply coverage ratio — below 1.0 = undercollateralized. "
                "RED signal if coverage < 0.95."
            )

            _ERC7540_VAULTS = {
                "BUIDL": "0x7712c34205737192402172409a8F7ccef8aA2AEc",
                "OUSG":  "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92",
            }

            _rq_cols = st.columns(len(_ERC7540_VAULTS))
            for _rqi, (_rq_sym, _rq_addr) in enumerate(_ERC7540_VAULTS.items()):
                _rqd = _load_erc7540_queue(_rq_addr)
                _cov     = _rqd.get("coverage_ratio", 1.0)
                _sig     = _rqd.get("risk_signal", "GREEN")
                _ta7     = _rqd.get("total_assets", 0.0)
                _ts7     = _rqd.get("total_supply", 0.0)
                _qdepth  = _rqd.get("queue_depth_usd")
                _compat  = _rqd.get("erc7540_compatible", False)
                _sig_clr = {"GREEN": "#10b981", "YELLOW": "#f59e0b", "RED": "#ef4444"}.get(_sig, "#6b7280")
                _cov_str = f"{_cov:.4f}" if _cov else "—"
                _qdep_str = (f"${_qdepth/1e6:.1f}M" if _qdepth and _qdepth >= 1e6
                             else f"${_qdepth:,.0f}" if _qdepth else "N/A")
                with _rq_cols[_rqi]:
                    st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2937;border-left:4px solid {_sig_clr};
                border-radius:10px;padding:14px">
          <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px">
        {_rq_sym}
        <span style="font-size:10px;font-weight:400;color:{_sig_clr};margin-left:8px">{_sig}</span>
          </div>
          <div style="font-size:10px;color:#6b7280">Coverage Ratio</div>
          <div style="font-size:20px;font-weight:700;color:{_sig_clr}">{_cov_str}</div>
          <div style="font-size:10px;color:#6b7280;margin-top:6px">Queue Depth</div>
          <div style="font-size:13px;color:#9ca3af">{_qdep_str}</div>
          <div style="font-size:10px;color:#6b7280;margin-top:4px">
        ERC-7540: {"Compatible" if _compat else "Standard ERC-4626"}
          </div>
        </div>
        """, unsafe_allow_html=True)


        # ── R8: DeFi Collateral Utility Panel ────────────────────────────────────
        try:
            st.markdown("---")
            st.markdown('<div class="section-header">DeFi Collateral Utility</div>', unsafe_allow_html=True)
            st.caption("Tokenized RWA assets deployed as collateral in DeFi protocols — unlocking additional liquidity on top of base yield. Data: DeFiLlama + on-chain research.")
            _DEFI_COLLATERAL = [
                {
                    "asset": "BUIDL", "protocol": "Aave Horizon / Ondo",
                    "collateral_tvl_m": 180, "supported": True,
                    "utility": "Used as collateral to borrow USDC — earn T-bill yield + DeFi borrow capacity. Aave Horizon institutional pool.",
                    "ltv": 85, "chains": "Ethereum",
                },
                {
                    "asset": "OUSG", "protocol": "Morpho Blue",
                    "collateral_tvl_m": 220, "supported": True,
                    "utility": "Listed as collateral on Morpho Blue. Users borrow USDC against OUSG at up to 86% LTV.",
                    "ltv": 86, "chains": "Ethereum / Solana",
                },
                {
                    "asset": "USDY", "protocol": "Pendle Finance",
                    "collateral_tvl_m": 95, "supported": True,
                    "utility": "USDY yield-tokenized on Pendle. Split into Principal Token + Yield Token — trade future yield.",
                    "ltv": 0, "chains": "Ethereum / Mantle / Solana",
                },
                {
                    "asset": "USDM", "protocol": "Curve + Aave",
                    "collateral_tvl_m": 55, "supported": True,
                    "utility": "USDM in Curve liquidity pools. Used as collateral in Aave v3 on Polygon. Rebasing yield passes to LP.",
                    "ltv": 75, "chains": "Ethereum / Polygon",
                },
                {
                    "asset": "sDAI (DAI via Maker)", "protocol": "MakerDAO Spark",
                    "collateral_tvl_m": 1800, "supported": True,
                    "utility": "DAI collateralized by US Treasuries via Maker RWA vaults. sDAI earns DSR (DAI Savings Rate).",
                    "ltv": 80, "chains": "Ethereum",
                },
                {
                    "asset": "stETH / sUSDe", "protocol": "Ethena x RWA",
                    "collateral_tvl_m": 450, "supported": True,
                    "utility": "sUSDe backed partially by tokenized Tbills as reserves. Used as DeFi collateral in Aave, Morpho.",
                    "ltv": 77, "chains": "Ethereum",
                },
            ]
            _r8_cols = st.columns(3)
            for _r8i, _r8a in enumerate(_DEFI_COLLATERAL):
                _r8c = "#00d4aa" if _r8a["supported"] else "#6b7280"
                _r8_ltv_str = f"LTV: {_r8a['ltv']}%" if _r8a["ltv"] > 0 else "Yield-only (no LTV)"
                with _r8_cols[_r8i % 3]:
                    _r8_tvl = _r8a["collateral_tvl_m"]
                    _r8_tvl_str = f"${_r8_tvl:,.0f}M" if _r8_tvl < 1000 else f"${_r8_tvl/1000:.1f}B"
                    st.markdown(f"""
        <div style="background:#111827;border:1px solid {_r8c}33;border-top:3px solid {_r8c};
                border-radius:8px;padding:12px;margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <div style="font-size:14px;font-weight:700;color:#e2e8f0">{_r8a['asset']}</div>
        <div style="font-size:10px;color:{_r8c};background:{_r8c}22;padding:2px 7px;border-radius:4px">
          {_r8_tvl_str} TVL</div>
          </div>
          <div style="font-size:11px;color:#6366f1;margin-bottom:4px">{_r8a['protocol']}</div>
          <div style="font-size:10px;color:#6b7280;margin-bottom:4px">{_r8_ltv_str} · {_r8a['chains']}</div>
          <div style="font-size:10px;color:#9ca3af;line-height:1.5">{_r8a['utility']}</div>
        </div>""", unsafe_allow_html=True)
            # Bar chart — collateral TVL comparison
            _r8_names = [a["asset"][:20] for a in _DEFI_COLLATERAL]
            _r8_tvls  = [a["collateral_tvl_m"] for a in _DEFI_COLLATERAL]
            _r8_fig = go.Figure(go.Bar(
                x=_r8_names, y=_r8_tvls,
                marker_color="#6366f1",
                text=[f"${v:,.0f}M" if v < 1000 else f"${v/1000:.1f}B" for v in _r8_tvls],
                textposition="outside",
            ))
            _r8_fig.update_layout(
                title="RWA Collateral TVL by Asset",
                height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0", size=11),
                margin=dict(l=0, r=0, t=40, b=40),
                yaxis=dict(title="Collateral TVL ($M)", gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(_r8_fig, width="stretch")
            _user_level_r8 = st.session_state.get("user_level", "beginner")
            if _user_level_r8 == "beginner":
                st.info("💡 **What does this mean for me?** In DeFi, you can use your RWA tokens as collateral to borrow stablecoins — without selling your position. For example, deposit OUSG earning 4.37%, borrow USDC at 3%, and deploy that USDC elsewhere. This is called 'capital efficiency' — you're making your money work in multiple places at once.")
        except Exception as _r8_err:
            logger.debug("[R8] DeFi collateral panel skipped: %s", _r8_err)


        # ─────────────────────────────────────────────────────────────────────────────
        # FOOTER
        # ─────────────────────────────────────────────────────────────────────────────

        st.markdown("""
        <div style="margin-top:40px;padding:16px;border-top:1px solid #1F2937;text-align:center">
        <span style="font-size:11px;color:#374151">
            ♾️ RWA INFINITY MODEL v1.0 &nbsp;·&nbsp;
            Powered by Claude (claude-sonnet-4-6) &nbsp;·&nbsp;
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
