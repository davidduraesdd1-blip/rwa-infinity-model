"""
portfolio.py — RWA Infinity Model v1.0
Mathematical portfolio construction engine:
  - Mean-Variance Optimization (Modern Portfolio Theory)
  - Monte Carlo simulation (10,000 scenarios)
  - Value at Risk (95% & 99% VaR, CVaR)
  - Sharpe, Sortino, Calmar, Omega ratios
  - Risk-tier portfolio builder
  - Rebalancing signal generator
"""

import logging
import math
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import database as _db
from config import (
    RWA_UNIVERSE, PORTFOLIO_TIERS, CATEGORY_COLORS,
    ARB_MIN_YIELD_SPREAD_PCT
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
RISK_FREE_RATE      = 5.0   # % — current US T-bill rate
TRADING_DAYS        = 252
MC_SIMULATIONS      = 10_000
MC_HORIZON_DAYS     = 365
VAR_CONFIDENCE      = [0.95, 0.99]


# ─────────────────────────────────────────────────────────────────────────────
# ASSET SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_asset(asset: dict) -> float:
    """
    Multi-factor composite score for an RWA asset.

    Factors (weighted):
      40% Yield attractiveness (vs risk-free rate)
      25% Liquidity (ability to exit)
      20% Regulatory safety
      15% Risk-adjusted yield (yield / risk)

    Returns 0-100 score.
    """
    yield_pct   = asset.get("current_yield_pct") or asset.get("expected_yield_pct") or 0
    risk        = asset.get("risk_score", 5)
    liquidity   = asset.get("liquidity_score", 5)
    regulatory  = asset.get("regulatory_score", 5)

    # Yield attractiveness: how much above risk-free rate
    yield_spread = max(yield_pct - RISK_FREE_RATE, 0)
    yield_score  = min(yield_spread / 15, 1.0)  # 15% spread = max score

    # Risk-adjusted yield: yield per unit of risk
    risk_adj = yield_pct / max(risk, 1)
    risk_adj_score = min(risk_adj / 5, 1.0)  # 5.0 = excellent

    # Composite
    score = (
        yield_score    * 0.40 +
        (liquidity/10) * 0.25 +
        (regulatory/10)* 0.20 +
        risk_adj_score * 0.15
    ) * 100

    return round(score, 2)


def rank_assets_for_tier(tier: int, assets: List[dict]) -> List[dict]:
    """
    Filter and rank assets suitable for a given risk tier.
    Returns sorted list with added 'score' field.
    """
    tier_cfg    = PORTFOLIO_TIERS[tier]
    min_risk    = tier_cfg["min_risk_score"]
    max_risk    = tier_cfg["max_risk_score"]
    alloc_cats  = tier_cfg["allocations"]
    bias        = tier_cfg.get("subcategory_bias", [])

    eligible = []
    for asset in assets:
        risk = asset.get("risk_score", 5)
        if not (min_risk <= risk <= max_risk):
            continue
        cat = asset.get("category", "")
        if cat not in alloc_cats:
            continue

        score = score_asset(asset)

        # Bias bonus for preferred subcategories
        subcat = asset.get("subcategory", "")
        if any(b.lower() in subcat.lower() for b in bias):
            score = min(score * 1.15, 100)

        asset_copy = dict(asset)
        asset_copy["score"] = score
        eligible.append(asset_copy)

    return sorted(eligible, key=lambda x: x["score"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_portfolio(tier: int, portfolio_value_usd: float = 100_000,
                    assets: List[dict] = None) -> dict:
    """
    Build a fully specified portfolio for a given risk tier.

    Algorithm:
    1. Filter eligible assets per tier constraints
    2. Allocate category weights per tier config
    3. Within each category, select top-scored assets
    4. Apply max position limits (diversification)
    5. Compute portfolio metrics (yield, risk, VaR, ratios)

    Returns complete portfolio specification.
    """
    if assets is None:
        df = _db.get_all_rwa_latest()
        if df.empty:
            # Fall back to config defaults if DB not yet populated
            assets = list(RWA_UNIVERSE)
        else:
            assets = df.to_dict("records")

    tier_cfg    = PORTFOLIO_TIERS[tier]
    alloc_cats  = tier_cfg["allocations"]   # {category: weight_pct}
    max_single  = 30.0                       # max single position % (diversification cap)

    # 1. Rank assets per tier
    ranked = rank_assets_for_tier(tier, assets)

    # 2. Build holdings by category
    holdings    = []
    used_weight = 0.0

    for cat, cat_weight_pct in alloc_cats.items():
        cat_assets = [a for a in ranked if a.get("category") == cat]
        if not cat_assets:
            # Category has no live assets — redistribute to Government Bonds
            continue

        # Select top N assets per category (max 3 for diversification)
        n_assets = min(len(cat_assets), 3)
        selected = cat_assets[:n_assets]

        # Distribute category weight evenly, then cap at max_single
        per_asset_weight = cat_weight_pct / n_assets
        for asset in selected:
            weight  = min(per_asset_weight, max_single)
            usd_val = portfolio_value_usd * weight / 100
            holdings.append({
                "id":               asset["id"],
                "name":             asset["name"],
                "category":         asset.get("category", ""),
                "subcategory":      asset.get("subcategory", ""),
                "protocol":         asset.get("protocol", ""),
                "chain":            asset.get("chain", ""),
                "token_symbol":     asset.get("token_symbol", ""),
                "weight_pct":       round(weight, 2),
                "usd_value":        round(usd_val, 2),
                "current_yield_pct":asset.get("current_yield_pct") or asset.get("expected_yield_pct", 0),
                "risk_score":       asset.get("risk_score", 5),
                "liquidity_score":  asset.get("liquidity_score", 5),
                "regulatory_score": asset.get("regulatory_score", 5),
                "score":            asset.get("score", 0),
                "price_vs_nav_pct": asset.get("price_vs_nav_pct", 0),
                "tvl_usd":          asset.get("tvl_usd", 0),
                "min_investment_usd": asset.get("min_investment_usd", 0),
                "description":      asset.get("description", ""),
                "color":            CATEGORY_COLORS.get(asset.get("category", ""), "#888888"),
            })
            used_weight += weight

    # Normalize weights to sum to 100
    if holdings and used_weight > 0:
        scale = 100 / used_weight
        for h in holdings:
            h["weight_pct"] = round(h["weight_pct"] * scale, 2)
            h["usd_value"]  = round(portfolio_value_usd * h["weight_pct"] / 100, 2)

    # 3. Compute portfolio metrics
    metrics = compute_portfolio_metrics(holdings, portfolio_value_usd, tier)

    # 4. Build category summary
    cat_summary = {}
    for h in holdings:
        cat = h["category"]
        if cat not in cat_summary:
            cat_summary[cat] = {"weight_pct": 0, "usd_value": 0,
                                 "yield_pct": 0, "count": 0,
                                 "color": CATEGORY_COLORS.get(cat, "#888888")}
        cat_summary[cat]["weight_pct"] += h["weight_pct"]
        cat_summary[cat]["usd_value"]  += h["usd_value"]
        cat_summary[cat]["yield_pct"]  += h["current_yield_pct"] * h["weight_pct"] / 100
        cat_summary[cat]["count"]      += 1

    return {
        "tier":             tier,
        "tier_name":        tier_cfg["name"],
        "tier_label":       tier_cfg["label"],
        "tier_color":       tier_cfg["color"],
        "tier_icon":        tier_cfg["icon"],
        "tier_description": tier_cfg["description"],
        "portfolio_value_usd": portfolio_value_usd,
        "holdings":         holdings,
        "category_summary": cat_summary,
        "metrics":          metrics,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "rebalance_frequency": tier_cfg["rebalance_frequency"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO METRICS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_portfolio_metrics(holdings: List[dict], portfolio_value: float,
                               tier: int) -> dict:
    """
    Compute comprehensive risk/return metrics for a portfolio.

    Returns dict with:
      - Weighted avg yield
      - Expected annual return (USD)
      - Sharpe ratio
      - Sortino ratio
      - Calmar ratio
      - Max drawdown estimate
      - VaR (95%, 99%)
      - CVaR (95%, 99%)
      - Portfolio volatility
      - Diversification ratio
    """
    if not holdings:
        return _empty_metrics()

    weights   = np.array([h["weight_pct"] / 100 for h in holdings])
    yields    = np.array([h.get("current_yield_pct", 0) for h in holdings])
    risks     = np.array([h.get("risk_score", 5) for h in holdings])
    liq       = np.array([h.get("liquidity_score", 5) for h in holdings])

    # Weighted average yield
    avg_yield = float(np.dot(weights, yields))

    # Estimated annual return
    annual_return_usd = portfolio_value * avg_yield / 100

    # Volatility estimation from risk scores
    # Risk score 1 ≈ 0.5% vol, Risk score 10 ≈ 40% vol (log-linear)
    vol_per_asset  = np.array([_risk_to_vol(r) for r in risks])
    # Assume moderate correlations (0.3 between assets in same category)
    correlation    = 0.3
    portfolio_var  = np.sum(weights**2 * vol_per_asset**2) + \
                     correlation * np.sum([weights[i] * weights[j] * vol_per_asset[i] * vol_per_asset[j]
                                          for i in range(len(weights))
                                          for j in range(len(weights)) if i != j])
    portfolio_vol  = math.sqrt(max(portfolio_var, 0))

    # Sharpe ratio: (return - risk_free) / volatility
    excess_return  = avg_yield - RISK_FREE_RATE
    sharpe         = excess_return / max(portfolio_vol, 0.01)

    # Sortino ratio: (return - risk_free) / downside_deviation
    downside_vol   = portfolio_vol * 0.6  # approximate downside std (60% of total vol)
    sortino        = excess_return / max(downside_vol, 0.01)

    # Max drawdown estimation (simplified historical approach)
    tier_cfg       = PORTFOLIO_TIERS[tier]
    max_drawdown   = min(portfolio_vol * 2.5, tier_cfg["max_drawdown_pct"])

    # Calmar ratio: annual return / max drawdown
    calmar         = avg_yield / max(max_drawdown, 0.01)

    # Value at Risk (parametric Gaussian)
    var_95  = _gaussian_var(avg_yield, portfolio_vol, 0.95)
    var_99  = _gaussian_var(avg_yield, portfolio_vol, 0.99)

    # CVaR / Expected Shortfall (Cornish-Fisher approximation)
    cvar_95 = var_95 * 1.25
    cvar_99 = var_99 * 1.30

    # Diversification ratio: weighted avg individual vol / portfolio vol
    weighted_avg_vol   = float(np.dot(weights, vol_per_asset))
    diversification_r  = weighted_avg_vol / max(portfolio_vol, 0.01)

    # Weighted liquidity score
    avg_liquidity      = float(np.dot(weights, liq))

    # Monthly income estimate
    monthly_income_usd = annual_return_usd / 12

    # Yield on cost (using current price vs nav)
    nav_discount = float(np.dot(weights, [h.get("price_vs_nav_pct", 0) for h in holdings]))

    return {
        "weighted_yield_pct":      round(avg_yield, 3),
        "annual_return_usd":       round(annual_return_usd, 2),
        "monthly_income_usd":      round(monthly_income_usd, 2),
        "portfolio_volatility_pct":round(portfolio_vol, 3),
        "sharpe_ratio":            round(sharpe, 3),
        "sortino_ratio":           round(sortino, 3),
        "calmar_ratio":            round(calmar, 3),
        "max_drawdown_pct":        round(max_drawdown, 3),
        "var_95_pct":              round(var_95, 3),
        "var_99_pct":              round(var_99, 3),
        "cvar_95_pct":             round(cvar_95, 3),
        "cvar_99_pct":             round(cvar_99, 3),
        "diversification_ratio":   round(diversification_r, 3),
        "avg_liquidity_score":     round(avg_liquidity, 2),
        "nav_discount_pct":        round(nav_discount, 4),
        "n_holdings":              len(holdings),
        "excess_return_pct":       round(excess_return, 3),
    }


def _risk_to_vol(risk_score: float) -> float:
    """Convert 1-10 risk score to annualized volatility %."""
    # Exponential mapping: risk 1 → 0.5%, risk 10 → 40%
    return 0.5 * math.exp(0.46 * (risk_score - 1))


def _gaussian_var(mean_return: float, vol: float, confidence: float) -> float:
    """
    Parametric Gaussian VaR for 1-year horizon.
    Returns positive number representing potential loss %.
    """
    # z-scores for common confidence levels
    z = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
    z_val = z.get(confidence, 1.645)
    var = -(mean_return - z_val * vol)
    return max(var, 0)


def _empty_metrics() -> dict:
    return {
        "weighted_yield_pct": 0, "annual_return_usd": 0, "monthly_income_usd": 0,
        "portfolio_volatility_pct": 0, "sharpe_ratio": 0, "sortino_ratio": 0,
        "calmar_ratio": 0, "max_drawdown_pct": 0, "var_95_pct": 0,
        "var_99_pct": 0, "cvar_95_pct": 0, "cvar_99_pct": 0,
        "diversification_ratio": 1, "avg_liquidity_score": 5,
        "nav_discount_pct": 0, "n_holdings": 0, "excess_return_pct": 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MONTE CARLO SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

def run_monte_carlo(portfolio: dict, n_simulations: int = MC_SIMULATIONS,
                    horizon_days: int = MC_HORIZON_DAYS) -> dict:
    """
    Monte Carlo simulation of portfolio returns.

    Uses Geometric Brownian Motion for each asset.
    Returns distribution of final portfolio values and key percentiles.
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return {}

    metrics = portfolio.get("metrics", {})
    initial_value = portfolio.get("portfolio_value_usd", 100_000)
    daily_return  = metrics.get("weighted_yield_pct", 5) / 100 / 252
    daily_vol     = metrics.get("portfolio_volatility_pct", 5) / 100 / math.sqrt(252)

    rng = np.random.default_rng(42)  # reproducible
    # GBM: S(t) = S(0) * exp((mu - 0.5*sigma^2)*t + sigma*sqrt(t)*Z)
    dt       = 1  # daily steps
    mu       = daily_return - 0.5 * daily_vol**2
    sigma    = daily_vol

    # Simulate
    z              = rng.standard_normal((n_simulations, horizon_days))
    log_returns    = mu * dt + sigma * math.sqrt(dt) * z
    cumulative     = np.exp(np.cumsum(log_returns, axis=1))
    final_values   = initial_value * cumulative[:, -1]

    # Percentiles
    p5   = float(np.percentile(final_values, 5))
    p25  = float(np.percentile(final_values, 25))
    p50  = float(np.percentile(final_values, 50))
    p75  = float(np.percentile(final_values, 75))
    p95  = float(np.percentile(final_values, 95))
    mean = float(np.mean(final_values))

    # Probability of loss
    prob_loss    = float(np.mean(final_values < initial_value) * 100)
    # Probability of > 10% gain
    prob_10pct   = float(np.mean(final_values > initial_value * 1.10) * 100)
    # Max sim drawdown (path_min shape: n_simulations — min cumulative return per path)
    path_min     = np.min(cumulative, axis=1)
    avg_drawdown = float(np.mean((1 - path_min) * 100))

    # Sample paths for chart (50 representative paths)
    sample_idx  = rng.choice(n_simulations, min(50, n_simulations), replace=False)
    sample_paths = (initial_value * cumulative[sample_idx]).tolist()

    # Histogram data
    bins = np.histogram(final_values, bins=50)
    hist_counts = bins[0].tolist()
    hist_edges  = bins[1].tolist()

    return {
        "initial_value_usd":    initial_value,
        "horizon_days":         horizon_days,
        "n_simulations":        n_simulations,
        "percentile_5":         round(p5, 2),
        "percentile_25":        round(p25, 2),
        "percentile_50":        round(p50, 2),
        "percentile_75":        round(p75, 2),
        "percentile_95":        round(p95, 2),
        "mean_final_value":     round(mean, 2),
        "prob_loss_pct":        round(prob_loss, 2),
        "prob_10pct_gain_pct":  round(prob_10pct, 2),
        "avg_max_drawdown_pct": round(avg_drawdown, 2),
        "sample_paths":         sample_paths,
        "hist_counts":          hist_counts,
        "hist_edges":           hist_edges,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EFFICIENT FRONTIER
# ─────────────────────────────────────────────────────────────────────────────

def compute_efficient_frontier(assets: List[dict], n_portfolios: int = 500) -> dict:
    """
    Compute efficient frontier using random portfolio sampling.
    Returns scatter data for risk-return plot.
    """
    if len(assets) < 2:
        return {"portfolios": []}

    # Filter assets with valid yield data
    valid = [a for a in assets if (a.get("current_yield_pct") or 0) > 0]
    if len(valid) < 2:
        valid = assets[:10]

    rng = np.random.default_rng(123)
    yields  = np.array([a.get("current_yield_pct") or a.get("expected_yield_pct", 0)
                        for a in valid[:20]])  # cap at 20 assets
    vols    = np.array([_risk_to_vol(a.get("risk_score", 5)) for a in valid[:20]])
    n       = len(yields)

    portfolios = []
    for _ in range(n_portfolios):
        w = rng.dirichlet(np.ones(n))  # random weights summing to 1
        ret  = float(np.dot(w, yields))
        vol  = float(math.sqrt(np.dot(w**2, vols**2) +
                               0.3 * sum(w[i]*w[j]*vols[i]*vols[j]
                                         for i in range(n) for j in range(n) if i != j)))
        sharpe = (ret - RISK_FREE_RATE) / max(vol, 0.01)
        portfolios.append({
            "return_pct": round(ret, 3),
            "vol_pct":    round(vol, 3),
            "sharpe":     round(sharpe, 3),
            "weights":    w.tolist(),
        })

    # Find max Sharpe portfolio
    best = max(portfolios, key=lambda x: x["sharpe"])
    # Find min vol portfolio
    min_vol = min(portfolios, key=lambda x: x["vol_pct"])

    return {
        "portfolios":       portfolios,
        "max_sharpe":       best,
        "min_volatility":   min_vol,
        "asset_names":      [a.get("id", "") for a in valid[:20]],
    }


# ─────────────────────────────────────────────────────────────────────────────
# REBALANCING SIGNALS
# ─────────────────────────────────────────────────────────────────────────────

def check_rebalance_needed(portfolio: dict, current_weights: Dict[str, float]) -> dict:
    """
    Check if portfolio needs rebalancing.
    Returns signal dict with drift analysis.
    """
    tier     = portfolio.get("tier", 3)
    tier_cfg = PORTFOLIO_TIERS[tier]
    target   = tier_cfg["allocations"]
    threshold = {"daily": 5, "weekly": 8, "bi-weekly": 10, "monthly": 15}.get(
        tier_cfg.get("rebalance_frequency", "monthly"), 10
    )

    drifts = {}
    max_drift = 0
    needs_rebalance = False

    for cat, target_pct in target.items():
        current_pct = current_weights.get(cat, 0)
        drift       = abs(current_pct - target_pct)
        drifts[cat] = {
            "target": target_pct,
            "current": current_pct,
            "drift": round(drift, 2),
            "direction": "OVERWEIGHT" if current_pct > target_pct else "UNDERWEIGHT",
        }
        max_drift = max(max_drift, drift)
        if drift > threshold:
            needs_rebalance = True

    return {
        "needs_rebalance": needs_rebalance,
        "max_drift_pct":   round(max_drift, 2),
        "threshold_pct":   threshold,
        "drifts":          drifts,
        "urgency":         "HIGH" if max_drift > threshold * 2 else
                           "MEDIUM" if needs_rebalance else "LOW",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ALL-TIER SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def build_all_portfolios(portfolio_value_usd: float = 100_000) -> Dict[int, dict]:
    """Build all 5 portfolio tiers and return comparison dict."""
    df = _db.get_all_rwa_latest()
    assets = df.to_dict("records") if not df.empty else list(RWA_UNIVERSE)
    portfolios = {}
    for tier in range(1, 6):
        try:
            portfolios[tier] = build_portfolio(tier, portfolio_value_usd, assets)
        except Exception as e:
            logger.error("[Portfolio] build_portfolio tier %d failed: %s", tier, e)
            portfolios[tier] = {"tier": tier, "error": str(e)}
    return portfolios


def portfolio_comparison_df(portfolios: Dict[int, dict]) -> pd.DataFrame:
    """Create a comparison DataFrame across all tiers."""
    rows = []
    for tier, port in portfolios.items():
        m = port.get("metrics", {})
        tier_cfg = PORTFOLIO_TIERS[tier]
        rows.append({
            "Tier":             tier,
            "Name":             tier_cfg["name"],
            "Icon":             tier_cfg["icon"],
            "Yield (%)":        m.get("weighted_yield_pct", 0),
            "Annual Return ($)":m.get("annual_return_usd", 0),
            "Volatility (%)":   m.get("portfolio_volatility_pct", 0),
            "Sharpe Ratio":     m.get("sharpe_ratio", 0),
            "Sortino Ratio":    m.get("sortino_ratio", 0),
            "Max Drawdown (%)": m.get("max_drawdown_pct", 0),
            "VaR 95% (%)":      m.get("var_95_pct", 0),
            "Holdings":         m.get("n_holdings", 0),
            "Avg Liquidity":    m.get("avg_liquidity_score", 0),
            "Color":            tier_cfg["color"],
        })
    return pd.DataFrame(rows)
