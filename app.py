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

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ─── Page config (MUST be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="RWA Infinity | Real World Asset Intelligence",
    page_icon="♾️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── Imports ───────────────────────────────────────────────────────────────────
import database as _db
import scheduler as _sched
import ai_agent as _agent
from config import (
    PORTFOLIO_TIERS, AI_AGENTS, CATEGORY_COLORS,
    RISK_LABELS, RWA_UNIVERSE, ARB_STRONG_THRESHOLD_PCT
)

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
    padding: 6px 0;
    overflow: hidden;
    white-space: nowrap;
}

/* Status dot */
.status-live { display: inline-block; width: 8px; height: 8px; background: var(--success); border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    background: var(--card-bg);
    border-radius: 8px;
    padding: 4px;
    gap: 2px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    color: var(--muted);
    font-weight: 600;
    font-size: 13px;
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

def _metric_card(label, value, delta=None, delta_label="", color=None):
    color_str = f"color: {color};" if color else ""
    delta_html = ""
    if delta is not None:
        cls   = "delta-up" if delta > 0 else "delta-down" if delta < 0 else "delta-flat"
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "●"
        delta_html = f'<div class="metric-delta {cls}">{arrow} {abs(delta):.2f}% {delta_label}</div>'
    st.markdown(f"""
    <div class="metric-card">
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


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS (cached per rerun)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_assets():
    df = _db.get_all_rwa_latest()
    if df.empty:
        # Populate from config defaults on first run
        from data_feeds import refresh_all_assets
        try:
            assets = refresh_all_assets()
            df = _db.get_all_rwa_latest()
        except Exception:
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

@st.cache_data(ttl=120, show_spinner=False)
def _load_market_summary():
    try:
        from data_feeds import get_market_summary
        return get_market_summary()
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
            mins_ago = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
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

ticker_text = "  ·  ".join(ticker_items)
st.markdown(f"""
<div class="ticker-wrap">
    <span style="font-size:12px;color:#9CA3AF;letter-spacing:0.03em">{ticker_text}</span>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO TIER SELECTOR
# ─────────────────────────────────────────────────────────────────────────────

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

# Portfolio value input
col_val, col_empty = st.columns([2, 8])
with col_val:
    portfolio_value = st.number_input(
        "Portfolio Value (USD)",
        min_value=1_000,
        max_value=1_000_000_000,
        value=st.session_state["portfolio_value"],
        step=10_000,
        format="%d",
        key="portfolio_value_input",
    )
    st.session_state["portfolio_value"] = portfolio_value


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────────────────────

tab_portfolio, tab_universe, tab_arb, tab_compare, tab_ai, tab_news, tab_trades = st.tabs([
    "📊 Portfolio",
    "🌐 Asset Universe",
    "⚡ Arbitrage",
    "📈 Compare Tiers",
    "🤖 AI Agent",
    "📰 News Feed",
    "📋 Trade Log",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════

with tab_portfolio:
    portfolio = _load_portfolio(selected_tier, portfolio_value)
    if not portfolio:
        st.warning("Loading portfolio data... Please wait or click Refresh Now.")
        st.stop()

    metrics  = portfolio.get("metrics", {})
    holdings = portfolio.get("holdings", [])
    cat_sum  = portfolio.get("category_summary", {})

    # ── KPI Row ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        _metric_card("Portfolio Yield", _fmt_pct(metrics.get("weighted_yield_pct")),
                     color=tier_cfg["color"])
    with k2:
        _metric_card("Annual Income", _fmt_usd(metrics.get("annual_return_usd")),
                     color="#34D399")
    with k3:
        _metric_card("Monthly Income", _fmt_usd(metrics.get("monthly_income_usd")),
                     color="#34D399")
    with k4:
        _metric_card("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}",
                     color=_color_for_value(metrics.get("sharpe_ratio", 0), 0, 2))
    with k5:
        _metric_card("Max Drawdown", _fmt_pct(metrics.get("max_drawdown_pct")),
                     color=_color_for_value(metrics.get("max_drawdown_pct", 0), 0, 30, invert=True))
    with k6:
        _metric_card("VaR 95%", _fmt_pct(metrics.get("var_95_pct")),
                     color=_color_for_value(metrics.get("var_95_pct", 0), 0, 20, invert=True))

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
            fig_scatter.add_hline(y=5.0, line_dash="dash", line_color="#374151",
                                  annotation_text="Risk-free rate (5%)")
            st.plotly_chart(fig_scatter, use_container_width=True)

    # ── Holdings Table ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Portfolio Holdings</div>', unsafe_allow_html=True)
    if holdings:
        h_df = pd.DataFrame(holdings)
        display_cols = ["id", "name", "category", "chain", "weight_pct",
                        "usd_value", "current_yield_pct", "risk_score",
                        "liquidity_score", "regulatory_score", "score"]

        display_df = h_df[[c for c in display_cols if c in h_df.columns]].copy()
        display_df.columns = ["ID", "Name", "Category", "Chain", "Weight %", "USD Value",
                               "Yield %", "Risk", "Liquidity", "Regulatory", "Score"][:len(display_df.columns)]

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

    # ── Risk Metrics ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Risk Metrics</div>', unsafe_allow_html=True)
    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        _metric_card("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}")
    with r2:
        _metric_card("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}")
    with r3:
        _metric_card("VaR 99%", _fmt_pct(metrics.get("var_99_pct")))
    with r4:
        _metric_card("CVaR 95%", _fmt_pct(metrics.get("cvar_95_pct")))
    with r5:
        _metric_card("Diversification", f"{metrics.get('diversification_ratio', 0):.2f}x")

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Monte Carlo Simulation (10,000 scenarios)</div>',
                unsafe_allow_html=True)
    if st.button("▶ Run Monte Carlo Simulation", key="btn_mc"):
        st.session_state["show_mc"] = True

    if st.session_state.get("show_mc"):
        with st.spinner("Simulating 10,000 portfolio paths..."):
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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: ASSET UNIVERSE
# ══════════════════════════════════════════════════════════════════════════════

with tab_universe:
    st.markdown('<div class="section-header">Complete RWA Asset Universe</div>',
                unsafe_allow_html=True)

    # Filters
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        categories = ["All"] + sorted(assets_df["category"].dropna().unique().tolist()) \
                     if not assets_df.empty else ["All"]
        sel_cat = st.selectbox("Category", categories, key="filter_cat")
    with f2:
        risk_filter = st.slider("Max Risk Score", 1, 10, 10, key="filter_risk")
    with f3:
        min_yield = st.number_input("Min Yield %", 0.0, 50.0, 0.0, 0.5, key="filter_yield")
    with f4:
        sort_by = st.selectbox("Sort By", ["composite_score", "current_yield_pct",
                                            "tvl_usd", "risk_score", "liquidity_score"],
                                key="filter_sort")

    filtered_df = assets_df.copy() if not assets_df.empty else pd.DataFrame()
    if not filtered_df.empty:
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

        # Asset table
        show_cols = {
            "id": "ID", "name": "Name", "category": "Category",
            "chain": "Chain", "protocol": "Protocol",
            "current_yield_pct": "Yield %",
            "expected_yield_pct": "Expected Yield %",
            "tvl_usd": "TVL",
            "risk_score": "Risk",
            "liquidity_score": "Liquidity",
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

        fmt_map = {"Yield %": "{:.2f}%", "Expected Yield %": "{:.2f}%",
                   "Score": "{:.1f}"}
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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: ARBITRAGE
# ══════════════════════════════════════════════════════════════════════════════

with tab_arb:
    arb_df, arb_summary = _load_arb()

    # Summary KPIs
    a1, a2, a3, a4, a5 = st.columns(5)
    with a1:
        _metric_card("Total Opportunities", str(arb_summary.get("total", 0)),
                     color="#00D4FF")
    with a2:
        _metric_card("Strong Arb", str(arb_summary.get("strong", 0)),
                     color="#34D399")
    with a3:
        _metric_card("Extreme Arb", str(arb_summary.get("extreme", 0)),
                     color="#EF4444")
    with a4:
        _metric_card("Best Spread", _fmt_pct(arb_summary.get("best_spread_pct", 0)),
                     color=tier_cfg["color"])
    with a5:
        _metric_card("Avg Spread", _fmt_pct(arb_summary.get("avg_spread_pct", 0)))

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

    if st.button("🔄 Rescan Arbitrage", key="btn_arb_rescan"):
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
            signal = row.get("signal", "ARB")
            net_spread = row.get("net_spread_pct", 0)
            sig_class = (
                "signal-extreme" if signal == "EXTREME_ARB" else
                "signal-strong"  if signal == "STRONG_ARB"  else
                "signal-arb"
            )
            sig_label = signal.replace("_", " ")

            with st.expander(
                f"[{row.get('type','').upper()}] {row.get('asset_a_name') or row.get('asset_a_id','?')} → "
                f"Net Spread: {net_spread:.2f}%",
                expanded=(net_spread >= ARB_STRONG_THRESHOLD_PCT)
            ):
                ac1, ac2, ac3 = st.columns(3)
                with ac1:
                    st.markdown(f'<span class="{sig_class}">{sig_label}</span>', unsafe_allow_html=True)
                    st.metric("Net Spread", f"{net_spread:.3f}%")
                with ac2:
                    st.metric("Yield A", f"{row.get('yield_a_pct', 0):.3f}%")
                    st.metric("Yield B", f"{row.get('yield_b_pct', 0):.3f}%")
                with ac3:
                    st.metric("Gross Spread", f"{row.get('spread_pct', 0):.3f}%")
                    st.metric("Est. APY", f"{row.get('estimated_apy', 0):.2f}%")

                if row.get("action"):
                    st.info(f"**Action:** {row['action']}")
                if row.get("notes"):
                    st.caption(row["notes"])
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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: COMPARE TIERS
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
            with st.spinner("Computing efficient frontier..."):
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
    # API Key check
    api_key_env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key_env:
        st.warning("⚠️ ANTHROPIC_API_KEY not set. AI features require the key in your environment.")
        user_key = st.text_input("Enter API Key (session only)", type="password", key="api_key_input")
        if user_key and st.button("Apply Key", key="apply_key"):
            os.environ["ANTHROPIC_API_KEY"] = user_key
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
                                format_func=lambda x: f"{x}s" if x < 60 else f"{x//60}m")
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
        if st.button("⚡ Run Now (1 cycle)", use_container_width=True, key="btn_one_cycle"):
            with st.spinner(f"Running {agent_detail['name']} cycle..."):
                result = _agent.run_agent_cycle(selected_agent, dry_run=dry_run, cycle_number=0)
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
        with st.spinner("Analyzing RWA market with Claude claude-sonnet-4-6..."):
            insights = _agent.get_agent_insights(selected_agent)
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

    # Performance feedback loop
    st.markdown('<div class="section-header">AI Feedback Loop</div>', unsafe_allow_html=True)
    perf_df = _db.get_agent_performance()
    if not perf_df.empty:
        perf_df["Win Rate %"] = (
            perf_df["wins"] / perf_df["total_decisions"] * 100
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

    if st.button("🔄 Refresh News", key="btn_news_refresh"):
        from data_feeds import refresh_news
        with st.spinner("Fetching latest RWA news..."):
            refresh_news()
        st.cache_data.clear()
        st.rerun()

    news_df = _load_news()

    if not news_df.empty:
        # Sentiment summary
        sentiments = news_df["sentiment"].value_counts()
        n1, n2, n3 = st.columns(3)
        with n1:
            _metric_card("Bullish", str(sentiments.get("BULLISH", 0)), color="#34D399")
        with n2:
            _metric_card("Neutral", str(sentiments.get("NEUTRAL", 0)), color="#6B7280")
        with n3:
            _metric_card("Bearish", str(sentiments.get("BEARISH", 0)), color="#EF4444")

        st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)

        # News cards
        for _, row in news_df.iterrows():
            sentiment = row.get("sentiment", "NEUTRAL")
            score     = row.get("sentiment_score", 0) or 0
            sent_color = {"BULLISH": "#34D399", "BEARISH": "#EF4444", "NEUTRAL": "#6B7280"}.get(sentiment, "#6B7280")
            sent_icon  = {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "●"}.get(sentiment, "●")
            ts = str(row.get("timestamp", ""))[:16]

            st.markdown(f"""
            <div class="metric-card" style="padding:12px">
                <div style="display:flex;justify-content:space-between;align-items:start">
                    <div style="flex:1;margin-right:12px">
                        <div style="font-size:14px;font-weight:600;color:#E2E8F0;line-height:1.4">{row.get('headline', '')}</div>
                        <div style="font-size:11px;color:#6B7280;margin-top:4px">{row.get('source','?')} · {ts}</div>
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


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="margin-top:40px;padding:16px;border-top:1px solid #1F2937;text-align:center">
    <span style="font-size:11px;color:#374151">
        ♾️ RWA INFINITY MODEL v1.0 &nbsp;·&nbsp;
        Powered by Claude claude-sonnet-4-6 &nbsp;·&nbsp;
        Data: DeFiLlama · CoinGecko &nbsp;·&nbsp;
        ⚠️ For informational purposes only — not financial advice &nbsp;·&nbsp;
        Auto-refresh: every 60 minutes
    </span>
</div>
""", unsafe_allow_html=True)

# ─── Auto-rerun for live status updates ───────────────────────────────────────
# Only rerun while scan is running (to show progress)
if is_running or scan_status.get("running", 0):
    time.sleep(3)
    st.rerun()
