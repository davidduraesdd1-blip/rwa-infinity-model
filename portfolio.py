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

import hashlib
import json
import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import database as _db
from config import (
    RWA_UNIVERSE, PORTFOLIO_TIERS, CATEGORY_COLORS,
    ARB_MIN_YIELD_SPREAD_PCT,
    get_asset_duration, get_asset_liquidity_meta, get_asset_fee_bps,
)

logger = logging.getLogger(__name__)

# ─── Monte Carlo cache (UPGRADE 13) ───────────────────────────────────────────
_mc_cache: Dict[str, dict] = {}
_MC_CACHE_TTL = 600  # 10-minute TTL for Monte Carlo results


def _mc_cache_key(portfolio: dict) -> str:
    """Generate a stable cache key from portfolio metrics and holdings."""
    try:
        metrics = portfolio.get("metrics", {})
        holdings = portfolio.get("holdings", [])
        payload = json.dumps({
            "tier":   portfolio.get("tier"),
            "yield":  round(metrics.get("weighted_yield_pct", 0), 2),
            "vol":    round(metrics.get("portfolio_volatility_pct", 0), 2),
            "value":  portfolio.get("portfolio_value_usd", 100_000),
            "n":      len(holdings),
            "ids":    sorted(h.get("id", "") for h in holdings),
        }, sort_keys=True)
        return hashlib.md5(payload.encode()).hexdigest()
    except Exception:
        return ""


# ─── Constants ────────────────────────────────────────────────────────────────
RISK_FREE_RATE      = 4.25  # % — 3-month T-bill yield (March 2026) — matches tokenized T-bill products yielding 4.3-4.5%
TRADING_DAYS        = 252
MC_SIMULATIONS      = 10_000
MC_HORIZON_DAYS     = 365
VAR_CONFIDENCE      = [0.95, 0.99]

# ─── Chain ecosystem maturity → extra annualized vol premium (%) ──────────────
# Newer/smaller chains = harder to exit = higher effective volatility
CHAIN_VOL_PREMIUM: dict = {
    "Ethereum":     0.0,    # most liquid, deepest DeFi
    "Polygon":      0.5,    # established L2/sidechain
    "Solana":       1.0,    # high-perf; no major outages in 2024 — downgraded from 1.5%
    "Arbitrum":     0.5,    # mature Ethereum L2
    "Optimism":     0.5,    # mature Ethereum L2
    "Base":         0.5,    # Coinbase L2 — deeply integrated 2024-2025, institutional RWA deployment
    "Avalanche":    1.0,    # institutional traction but smaller DeFi
    "Gnosis":       0.5,    # stable sidechain
    "Hedera":       2.0,    # institutional focus, limited DeFi liquidity
    "XRP Ledger":   2.0,    # deep for XRP, shallow for RWA tokens
    "Tezos":        2.5,    # EU-regulated but small DeFi ecosystem
    "Provenance":   3.5,    # niche fintech chain, minimal secondary market
    "Aptos":        3.0,    # new Move VM ecosystem
    "Cardano":      2.5,    # maturing but limited DeFi
    "Sui":          3.5,    # newest ecosystem, highest uncertainty
    "Stellar":      2.0,    # payments-focused, smaller DeFi
    "Algorand":     2.5,    # underused relative to capability
    "Tron":         1.5,    # large stablecoin flows but regulatory risk
    "BNB":          1.0,    # large ecosystem
    "Multiple":     1.0,    # multi-chain: use mid estimate
    "Off-chain / Reg A+": 4.0,  # no on-chain exit, fully illiquid
    # New chains added 2025-2026
    "Plume":        4.0,    # purpose-built RWA chain, very new, thin secondary markets
    "Mantra":       3.5,    # RWA-focused appchain, Dubai-licensed but young ecosystem
    "Noble":        2.0,    # Cosmos T-bill infrastructure, mature bridging but limited DeFi
    "TON":          3.0,    # Telegram ecosystem, growing rapidly but new DeFi layer
    "ZKsync Era":   1.5,    # established L2 with growing RWA activity
    "Starknet":     2.0,    # ZK-rollup, growing but smaller ecosystem than Arbitrum/Optimism
    "Linea":        2.0,    # Consensys L2, institutional backing but smaller DeFi
    "Mantle":       2.0,    # BYBIT/BitDAO backed L2, growing
    "Centrifuge Chain": 3.0, # purpose-built for Centrifuge pools, limited secondary liquidity
    "Kinexys":      0.0,    # JPMorgan private EVM, institutional grade — effectively zero market risk
    "Canton Network": 0.0,  # Goldman Sachs / Digital Asset private chain — institutional grade
    "Polymesh":     2.0,    # Purpose-built regulated securities chain, permissioned validators
    "SDX":          0.0,    # SIX Digital Exchange — Swiss DLT Act regulated, institutional-only CSD
    "Berachain":    3.5,    # Proof of Liquidity EVM, very new (2024 mainnet), thin RWA secondary markets
}

# ─── Category-pair correlation matrix ────────────────────────────────────────
# Captures how different RWA categories move together.
# T-bill tokens are highly correlated (same rate driver).
# Stocks and real estate have moderate positive correlation.
# Treasuries and equities have slight negative correlation (flight to quality).
# If a pair is not listed, default = 0.15 (low cross-category correlation).
CATEGORY_CORRELATIONS: dict = {
    ("Government Bonds",     "Government Bonds"):     0.92,
    ("Government Bonds",     "Private Credit"):       0.25,
    ("Government Bonds",     "Real Estate"):          0.10,
    ("Government Bonds",     "Equities"):            -0.10,
    ("Government Bonds",     "Commodities"):          0.05,
    ("Government Bonds",     "Carbon Credits"):      -0.05,
    ("Government Bonds",     "Trade Finance"):        0.30,
    ("Government Bonds",     "Infrastructure"):       0.20,
    ("Government Bonds",     "Private Equity"):       0.10,
    ("Government Bonds",     "Insurance"):            0.15,
    ("Government Bonds",     "Intellectual Property"):0.05,
    ("Government Bonds",     "Art & Collectibles"):   0.02,
    ("Private Credit",       "Private Credit"):       0.65,
    ("Private Credit",       "Real Estate"):          0.45,
    ("Private Credit",       "Equities"):             0.40,
    ("Private Credit",       "Trade Finance"):        0.55,
    ("Private Credit",       "Infrastructure"):       0.35,
    ("Private Credit",       "Private Equity"):       0.50,
    ("Private Credit",       "Insurance"):            0.30,
    ("Real Estate",          "Real Estate"):          0.65,
    ("Real Estate",          "Equities"):             0.35,
    ("Real Estate",          "Commodities"):          0.20,
    ("Real Estate",          "Infrastructure"):       0.40,
    ("Real Estate",          "Private Equity"):       0.30,
    ("Equities",             "Equities"):             0.82,
    ("Equities",             "Private Equity"):       0.60,
    ("Equities",             "Infrastructure"):       0.35,
    ("Equities",             "Carbon Credits"):       0.25,
    ("Commodities",          "Commodities"):          0.55,
    ("Commodities",          "Infrastructure"):       0.30,
    ("Carbon Credits",       "Carbon Credits"):       0.65,
    ("Carbon Credits",       "Infrastructure"):       0.20,
    ("Intellectual Property","Intellectual Property"):0.45,
    ("Art & Collectibles",   "Art & Collectibles"):   0.35,
    ("Private Equity",       "Private Equity"):       0.65,
    ("Private Equity",       "Infrastructure"):       0.40,
    ("Insurance",            "Insurance"):            0.55,
    ("Trade Finance",        "Trade Finance"):        0.50,
    ("Infrastructure",       "Infrastructure"):       0.60,
    ("Tokenized Equities",   "Tokenized Equities"):   0.88,  # high: same underlying stocks
    ("Tokenized Equities",   "Equities"):             0.82,  # near-perfect tracker; slight basis risk from oracle/settlement lag
    ("Tokenized Equities",   "Private Equity"):       0.50,
    ("Tokenized Equities",   "Government Bonds"):    -0.08,  # mild flight-to-quality negative
    ("Tokenized Equities",   "Private Credit"):       0.35,
    ("Tokenized Equities",   "Real Estate"):          0.40,  # both risk-on assets
    ("Tokenized Equities",   "Commodities"):          0.20,
    ("Tokenized Equities",   "Infrastructure"):       0.30,
    ("Tokenized Equities",   "Carbon Credits"):       0.25,
    ("Tokenized Equities",   "Trade Finance"):        0.30,
    ("Tokenized Equities",   "Insurance"):            0.20,
    ("Tokenized Equities",   "Art & Collectibles"):   0.15,
    ("Tokenized Equities",   "Intellectual Property"):0.25,
}


# ─────────────────────────────────────────────────────────────────────────────
# ASSET SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_asset(asset: dict) -> float:
    """
    Multi-factor composite score for an RWA asset.

    Factors (weighted):
      30% Yield attractiveness (vs risk-free rate)
      25% Liquidity (ability to exit)
      30% Regulatory safety
      15% Risk-adjusted yield (yield / risk)

    Adjustments applied post-score:
      - Chain maturity discount: illiquid/new chains penalised up to 15%
      - Synthetic/DEX basis risk penalty: oracle-dependent assets penalised 10%
      - Future-readiness bonus: multi-chain or institutional-grade assets +5%

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

    # Base composite (weights calibrated vs. Moody's, S&P, Franklin Templeton institutional frameworks)
    # Regulatory/legal structure is the institutional GATING factor post-MiCA + GENIUS Act 2025
    # Yield still important but without regulatory clarity it's irrelevant (Moody's digital asset framework)
    # Matches Arca/WisdomTree/Franklin approx: Regulatory 35%, Liquidity 25%, Yield 25%, Risk 15%
    score = (
        yield_score    * 0.30 +
        (liquidity/10) * 0.25 +
        (regulatory/10)* 0.30 +
        risk_adj_score * 0.15
    ) * 100

    # ── Institutional backing bonus ────────────────────────────────────────────
    # Major TradFi backing → tighter regulatory oversight, deeper liquidity, lower tail risk
    tags = asset.get("tags") or []
    if isinstance(tags, str):
        import json as _json
        try: tags = _json.loads(tags)
        except (ValueError, TypeError): tags = []
    institutional_tags = {"blackrock", "kkr", "apollo", "hamilton-lane", "franklin-templeton",
                          "wisdomtree", "axa", "societe-generale", "jpmorgan", "hsbc", "ubs",
                          "citi", "state-street", "bny-mellon", "deutsche-bank", "securitize"}
    if any(t.lower() in institutional_tags for t in tags):
        score = min(score * 1.05, 100)  # +5% bonus for major TradFi backing

    # ── Chain maturity discount (new/illiquid chains = harder to exit) ────────
    primary_chain = (asset.get("chain") or "Ethereum").split(" / ")[0].strip()
    chain_premium = CHAIN_VOL_PREMIUM.get(primary_chain, 2.0)
    chain_discount = 1.0 - min(chain_premium / 50.0, 0.15)  # max 15% discount
    score *= chain_discount

    # ── Synthetic / DEX basis risk penalty ────────────────────────────────────
    subcat = (asset.get("subcategory") or "").lower()
    if "synthetic" in subcat or ("dex" in subcat and "equit" in subcat):
        score *= 0.90   # 10% penalty: oracle risk + basis divergence possible

    # ── Future-readiness bonus ─────────────────────────────────────────────────
    # Multi-chain deployment = broader liquidity + more adoption surface
    chain_str = asset.get("chain", "")
    if " / " in chain_str:  # multi-chain asset
        score = min(score * 1.05, 100)
    # Institutional backing (Securitize, BlackRock, etc.) already in regulatory score

    return round(score, 2)


def score_assets_batch(assets_df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized batch version of score_asset() for 200+ assets (UPGRADE 20).
    Applies all scoring logic as pandas operations on the full DataFrame at once.
    Returns the input DataFrame with an added 'score' column.

    The individual score_asset() function is preserved for single-asset use cases.
    """
    df = assets_df.copy()

    # Extract base numeric fields
    yield_pct   = df.get("current_yield_pct", pd.Series(0.0, index=df.index)).fillna(
                       df.get("expected_yield_pct", pd.Series(0.0, index=df.index))
                  ).fillna(0.0)
    risk        = df.get("risk_score", pd.Series(5, index=df.index)).fillna(5).clip(1, 10)
    liquidity   = df.get("liquidity_score", pd.Series(5, index=df.index)).fillna(5).clip(1, 10)
    regulatory  = df.get("regulatory_score", pd.Series(5, index=df.index)).fillna(5).clip(1, 10)

    # Yield attractiveness
    yield_spread = (yield_pct - RISK_FREE_RATE).clip(lower=0)
    yield_score  = (yield_spread / 15).clip(upper=1.0)

    # Risk-adjusted yield
    risk_adj       = yield_pct / risk.clip(lower=1)
    risk_adj_score = (risk_adj / 5).clip(upper=1.0)

    # Base composite
    score = (
        yield_score    * 0.30
        + (liquidity / 10) * 0.25
        + (regulatory / 10) * 0.30
        + risk_adj_score  * 0.15
    ) * 100

    # Institutional backing bonus (+5%)
    _institutional_tags = {"blackrock", "kkr", "apollo", "hamilton-lane", "franklin-templeton",
                            "wisdomtree", "axa", "societe-generale", "jpmorgan", "hsbc", "ubs",
                            "citi", "state-street", "bny-mellon", "deutsche-bank", "securitize"}

    def _has_institutional(tags_val):
        if not tags_val:
            return False
        if isinstance(tags_val, str):
            try:
                import json as _json
                tags_val = _json.loads(tags_val)
            except Exception:
                return False
        if isinstance(tags_val, list):
            return any(str(t).lower() in _institutional_tags for t in tags_val)
        return False

    _inst_mask = df.get("tags", pd.Series("", index=df.index)).apply(_has_institutional)
    score = (score * _inst_mask.map({True: 1.05, False: 1.0})).clip(upper=100)

    # Chain maturity discount (max 15%)
    def _chain_discount(chain_val):
        primary = str(chain_val or "Ethereum").split(" / ")[0].strip()
        premium = CHAIN_VOL_PREMIUM.get(primary, 2.0)
        return 1.0 - min(premium / 50.0, 0.15)

    chain_disc = df.get("chain", pd.Series("Ethereum", index=df.index)).apply(_chain_discount)
    score = score * chain_disc

    # Synthetic / DEX basis risk penalty (-10%)
    subcat = df.get("subcategory", pd.Series("", index=df.index)).fillna("").str.lower()
    _synth_mask = subcat.str.contains("synthetic", na=False) | (
        subcat.str.contains("dex", na=False) & subcat.str.contains("equit", na=False)
    )
    score = score * _synth_mask.map({True: 0.90, False: 1.0})

    # Multi-chain future-readiness bonus (+5%)
    _multichain_mask = df.get("chain", pd.Series("", index=df.index)).fillna("").str.contains(" / ", na=False)
    score = (score * _multichain_mask.map({True: 1.05, False: 1.0})).clip(upper=100)

    df["score"] = score.round(2)
    return df


def rank_assets_for_tier(tier: int, assets: List[dict]) -> List[dict]:
    """
    Filter and rank assets suitable for a given risk tier.
    Returns sorted list with added 'score' field.
    """
    tier        = max(1, min(5, int(tier)))
    tier_cfg    = PORTFOLIO_TIERS[tier]
    min_risk    = tier_cfg["min_risk_score"]
    max_risk    = tier_cfg["max_risk_score"]
    alloc_cats  = tier_cfg["allocations"]
    bias        = tier_cfg.get("subcategory_bias", [])

    # Minimum liquidity floors per tier (institutional fiduciary duty requirement)
    # Tier 1-2: min=5 (must be exitable within ~30 days), Tier 3: min=4, Tier 4+: min=3
    min_liquidity = {1: 5, 2: 5, 3: 4, 4: 3, 5: 3}.get(tier, 3)

    # UPGRADE 20: use vectorized batch scoring for large asset lists
    if len(assets) >= 10:
        # Filter eligible assets first, then score in batch
        pre_eligible = []
        for asset in assets:
            risk = asset.get("risk_score", 5)
            if not (min_risk <= risk <= max_risk):
                continue
            cat = asset.get("category", "")
            if cat not in alloc_cats:
                continue
            if asset.get("liquidity_score", 5) < min_liquidity:
                continue
            pre_eligible.append(asset)

        if not pre_eligible:
            return []

        scored_df = score_assets_batch(pd.DataFrame(pre_eligible))
        eligible = []
        for _, row in scored_df.iterrows():
            asset_copy = row.to_dict()
            score = asset_copy.get("score", 0)
            # Bias bonus for preferred subcategories
            subcat = str(asset_copy.get("subcategory", "") or "")
            if bias and any(b.lower() in subcat.lower() for b in bias):
                score = min(score * 1.15, 100)
            asset_copy["score"] = score
            eligible.append(asset_copy)
    else:
        # Small lists: use original per-asset scoring
        eligible = []
        for asset in assets:
            risk = asset.get("risk_score", 5)
            if not (min_risk <= risk <= max_risk):
                continue
            cat = asset.get("category", "")
            if cat not in alloc_cats:
                continue
            if asset.get("liquidity_score", 5) < min_liquidity:
                continue
            score = score_asset(asset)
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

    tier        = max(1, min(5, int(tier)))
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
                                 "yield_pct": 0, "_yield_weighted_sum": 0,
                                 "count": 0,
                                 "color": CATEGORY_COLORS.get(cat, "#888888")}
        cat_summary[cat]["weight_pct"]          += h["weight_pct"]
        cat_summary[cat]["usd_value"]           += h["usd_value"]
        cat_summary[cat]["_yield_weighted_sum"] += h["current_yield_pct"] * h["weight_pct"]
        cat_summary[cat]["count"]               += 1
    # Compute weighted-average yield per category (yield_pct = weighted avg, not contribution)
    for cat_data in cat_summary.values():
        total_w = cat_data["weight_pct"]
        cat_data["yield_pct"] = round(
            cat_data["_yield_weighted_sum"] / total_w if total_w > 0 else 0, 4
        )
        del cat_data["_yield_weighted_sum"]

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
    yields    = np.array([h.get("current_yield_pct") or 0 for h in holdings], dtype=float)
    risks     = np.array([h.get("risk_score") or 5 for h in holdings], dtype=float)
    liq       = np.array([h.get("liquidity_score") or 5 for h in holdings], dtype=float)
    cats      = [h.get("category", "") for h in holdings]
    n         = len(holdings)

    # Weighted average yield
    avg_yield = float(np.dot(weights, yields))

    # Estimated annual return
    annual_return_usd = portfolio_value * avg_yield / 100

    # ── Per-asset volatility with chain + asset-type adjustments ─────────────
    vol_per_asset = np.array([_risk_to_vol(risks[i], holdings[i]) for i in range(n)])

    # ── Category-aware covariance matrix ─────────────────────────────────────
    # Replaces the old flat 0.3 correlation assumption.
    # Same category pairs use CATEGORY_CORRELATIONS; cross-category defaults 0.15.
    cov_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                cov_matrix[i, j] = vol_per_asset[i] ** 2
            else:
                pair     = (cats[i], cats[j])
                pair_rev = (cats[j], cats[i])
                corr = CATEGORY_CORRELATIONS.get(pair,
                       CATEGORY_CORRELATIONS.get(pair_rev, 0.15))
                cov_matrix[i, j] = corr * vol_per_asset[i] * vol_per_asset[j]

    portfolio_var = float(weights @ cov_matrix @ weights)
    portfolio_vol = math.sqrt(max(portfolio_var, 0))

    # Sharpe ratio: (return - risk_free) / volatility
    excess_return  = avg_yield - RISK_FREE_RATE
    sharpe         = excess_return / max(portfolio_vol, 0.01)

    # Sortino ratio: (return - risk_free) / downside_deviation
    # For positively-skewed RWA yields (mostly positive returns with occasional large drops):
    # downside std ≈ 56% of total vol (empirically observed for fixed-income-heavy portfolios)
    # This is better calibrated than the naive 60% approximation for yield-bearing assets
    downside_vol   = portfolio_vol * 0.56  # downside std ≈ 56% of total vol for RWA
    sortino        = excess_return / max(downside_vol, 0.01)

    # Max drawdown estimation — Magdon-Ismail & Atiya (2004) approximation
    # E[MDD] ≈ σ * sqrt(T) * f(μ/σ) where for annual horizon T=1 and f≈3.0 for RWA
    # The 3.0 multiplier (up from 2.5) accounts for illiquidity drag + jump risk
    # which cause drawdowns to persist longer than in liquid markets
    tier_cfg       = PORTFOLIO_TIERS[tier]
    max_drawdown   = min(portfolio_vol * 3.0, tier_cfg["max_drawdown_pct"])

    # Calmar ratio: annual return / max drawdown
    calmar         = avg_yield / max(max_drawdown, 0.01)

    # Value at Risk (parametric Gaussian)
    var_95  = _gaussian_var(avg_yield, portfolio_vol, 0.95)
    var_99  = _gaussian_var(avg_yield, portfolio_vol, 0.99)

    # CVaR / Expected Shortfall — Student-t(5) calibrated multipliers
    # Student-t with nu=5 df is academically supported for fat-tailed RWA distributions:
    #   nu=5: 95% CVaR/VaR ≈ 1.40, 99% CVaR/VaR ≈ 1.48
    # Gaussian (1.24/1.16) significantly understates tail risk for illiquid RWA
    # Moody's and S&P tokenized fund evaluations use t-distribution for tail risk
    cvar_95 = var_95 * 1.40
    cvar_99 = var_99 * 1.48

    # Diversification ratio: weighted avg individual vol / portfolio vol
    weighted_avg_vol   = float(np.dot(weights, vol_per_asset))
    diversification_r  = weighted_avg_vol / max(portfolio_vol, 0.01)

    # Weighted liquidity score
    avg_liquidity      = float(np.dot(weights, liq))

    # Monthly income estimate
    monthly_income_usd = annual_return_usd / 12

    # Yield on cost (using current price vs nav)
    nav_discount = float(np.dot(weights, [h.get("price_vs_nav_pct") or 0 for h in holdings]))

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


def _risk_to_vol(risk_score: float, asset: dict = None) -> float:
    """
    Convert 1-10 risk score to annualized volatility % with asset-aware adjustments.

    Base mapping (exponential): risk 1 → 0.5%, risk 10 → 40%
    Then applies:
      - Chain ecosystem maturity premium (new chains = harder to exit)
      - Synthetic/DEX basis risk multiplier (oracle-dependent assets)
      - Carbon credit regulatory uncertainty multiplier
    """
    # Steeper curve at high end (0.50 vs 0.46); floor at 0.15% for NAV-pegged score-1 assets
    # max(0.15, ...) prevents over-stating vol for BUIDL/BENJI which effectively have zero price vol
    base_vol = max(0.15, 0.35 * math.exp(0.50 * (risk_score - 1)))

    if asset is None:
        return base_vol

    # Synthetic/DEX stocks: oracle and basis risk add extra volatility
    subcat = (asset.get("subcategory") or "").lower()
    if "synthetic" in subcat or ("dex" in subcat and "equit" in subcat):
        base_vol *= 1.35   # 35% extra for oracle divergence + liquidation cascades

    # Carbon credits: regulatory risk multiplier (policy can crater value overnight)
    if asset.get("category") == "Carbon Credits":
        base_vol *= 1.20

    # Art & Collectibles: very thin market, high bid-ask spread risk
    if asset.get("category") == "Art & Collectibles":
        base_vol *= 1.15

    # Chain maturity premium: first-listed chain drives primary liquidity
    primary_chain = (asset.get("chain") or "Ethereum").split(" / ")[0].strip()
    chain_premium = CHAIN_VOL_PREMIUM.get(primary_chain, 2.0)

    return min(base_vol + chain_premium, 80.0)  # cap at 80% annualised vol


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
    Results are cached for 10 minutes (UPGRADE 13) to avoid re-running 10K
    scenarios on every Streamlit rerun.
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return {}

    # UPGRADE 13: check module-level cache before running expensive simulation
    _ck = _mc_cache_key(portfolio)
    if _ck:
        _cached = _mc_cache.get(_ck)
        if _cached and (time.time() - _cached.get("_ts", 0)) < _MC_CACHE_TTL:
            return {k: v for k, v in _cached.items() if k != "_ts"}

    metrics = portfolio.get("metrics", {})
    initial_value = portfolio.get("portfolio_value_usd", 100_000)
    daily_return  = metrics.get("weighted_yield_pct", 5) / 100 / 252
    daily_vol     = metrics.get("portfolio_volatility_pct", 5) / 100 / math.sqrt(252)

    rng = np.random.default_rng(42)  # reproducible

    # ── Jump-Diffusion GBM (Merton 1976) ─────────────────────────────────────
    # RWA assets face "jump" tail risks that pure GBM underestimates:
    #   - Protocol/bridge hacks (DeFi specific)
    #   - Regulatory shutdown orders (tokenized securities)
    #   - Oracle failures (synthetic stocks, DEX instruments)
    #   - Chain outages or hard forks
    # We model these as a Poisson jump process layered on top of the GBM.
    dt           = 1             # daily steps
    mu_gbm       = daily_return - 0.5 * daily_vol**2
    sigma        = daily_vol

    # Jump process parameters — re-calibrated for 2025-2026 RWA ecosystem maturity
    # DeFi exploit frequency has declined significantly since 2022 peak:
    #   2022: ~$3.8B stolen, ~0.8 significant events/protocol/year
    #   2023: ~$1.8B stolen, ~0.5 events/protocol/year
    #   2024-2025: ~$0.8-1.2B, ~0.35 events (better auditing, formal verification)
    # For a DIVERSIFIED RWA portfolio (20+ protocols), portfolio-level jump rate is lower
    # Mean jump = -4% (unchanged: mostly negative but occasionally +3-4% from price recovery)
    # Std = 9% (increased slightly: tail events are fatter when they do occur)
    base_jump_intensity = 0.50 / 252   # ~0.5 jump events per year (base rate)

    # #44 — Audit Score Adjustment: incorporate weighted-average audit score from holdings
    # adjusted_jump_intensity = base * (1.0 + (70 - audit_score) / 100.0)
    # Score 70 = no adjustment, score 40 = +30% intensity, score 95 = -25% intensity
    try:
        from config import RWA_UNIVERSE as _rwa_uni
        _audit_map = {a["id"]: a.get("audit_score", 70) for a in _rwa_uni}
        _scores = [
            _audit_map.get(h.get("id", ""), 70)
            for h in holdings
            if h.get("id")
        ]
        _avg_audit = sum(_scores) / len(_scores) if _scores else 70
        _jump_adj  = 1.0 + (70 - _avg_audit) / 100.0
        _jump_adj  = max(0.5, min(2.0, _jump_adj))   # clamp to [0.5, 2.0]
    except Exception:
        _avg_audit = 70
        _jump_adj  = 1.0

    jump_intensity = base_jump_intensity * _jump_adj
    jump_mean      = -0.04         # average jump = -4% (unchanged, negatively skewed)
    jump_std       = 0.09          # jump std dev = 9% (slightly wider tails for rare big events)

    # Diffusion component
    z              = rng.standard_normal((n_simulations, horizon_days))
    # Jump component: Poisson arrivals × Normal jump size
    jump_counts    = rng.poisson(jump_intensity, (n_simulations, horizon_days))
    jump_sizes     = rng.normal(jump_mean, jump_std, (n_simulations, horizon_days))

    # Combined log-return: GBM drift + diffusion + jumps
    log_returns    = mu_gbm * dt + sigma * math.sqrt(dt) * z + jump_counts * jump_sizes
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

    _result = {
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
    # UPGRADE 13: store in module-level cache with timestamp
    if _ck:
        _mc_cache[_ck] = {**_result, "_ts": time.time()}
    return _result


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
    capped  = valid[:20]  # cap at 20 assets
    yields  = np.array([a.get("current_yield_pct") or a.get("expected_yield_pct", 0)
                        for a in capped])
    vols    = np.array([_risk_to_vol(a.get("risk_score", 5), a) for a in capped])
    n       = len(yields)

    # Build category-aware covariance matrix for the capped asset universe
    cats_ef = [a.get("category", "") for a in capped]
    cov_ef  = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                cov_ef[i, j] = vols[i] ** 2
            else:
                pair     = (cats_ef[i], cats_ef[j])
                pair_rev = (cats_ef[j], cats_ef[i])
                corr = CATEGORY_CORRELATIONS.get(pair,
                       CATEGORY_CORRELATIONS.get(pair_rev, 0.15))
                cov_ef[i, j] = corr * vols[i] * vols[j]

    portfolios = []
    for _ in range(n_portfolios):
        w = rng.dirichlet(np.ones(n))  # random weights summing to 1
        ret  = float(np.dot(w, yields))
        # Use category-aware covariance instead of flat 0.3 correlation assumption
        port_var = float(w @ cov_ef @ w)
        vol  = float(math.sqrt(max(port_var, 0)))
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
    tier     = max(1, min(5, int(portfolio.get("tier", 3))))
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
    """Build all 5 portfolio tiers in parallel and return comparison dict (UPGRADE 14)."""
    df = _db.get_all_rwa_latest()
    assets = df.to_dict("records") if not df.empty else list(RWA_UNIVERSE)

    def _build_tier(tier: int) -> tuple:
        try:
            return tier, build_portfolio(tier, portfolio_value_usd, assets)
        except Exception as e:
            logger.error("[Portfolio] build_portfolio tier %d failed: %s", tier, e)
            return tier, {"tier": tier, "error": str(e)}

    portfolios: Dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=5) as _ex:
        _tier_futs = {_ex.submit(_build_tier, t): t for t in range(1, 6)}
        for _fut in _tier_futs:
            try:
                _tier, _port = _fut.result(timeout=60)
                portfolios[_tier] = _port
            except Exception as _e:
                _t = _tier_futs[_fut]
                logger.error("[Portfolio] tier %d parallel build failed: %s", _t, _e)
                portfolios[_t] = {"tier": _t, "error": str(_e)}
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


# ─────────────────────────────────────────────────────────────────────────────
# CORRELATION STRESS TESTING
# ─────────────────────────────────────────────────────────────────────────────

def stress_test_correlations(portfolio: dict, scenario: str = "crisis") -> dict:
    """
    Re-compute portfolio risk metrics under stressed correlation assumptions.

    Scenarios:
      "crisis"   — correlations → 1.0 (full contagion, 2008/2020 style)
      "moderate" — correlations capped at 0.70 (elevated but not full contagion)
      "normal"   — uses baseline CATEGORY_CORRELATIONS (current model default)

    Returns dict with stressed metrics, delta vs baseline, and scenario label.

    Why this matters:
      In systemic risk events (March 2020, crypto winter 2022), correlations between
      normally uncorrelated asset classes spike toward 1.0. A portfolio that looks
      diversified under normal correlations can suffer far larger drawdowns when all
      assets fall together. This function quantifies that hidden tail risk.
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return {}

    baseline_metrics = portfolio.get("metrics", {})
    portfolio_value  = portfolio.get("portfolio_value_usd", 100_000)
    tier             = portfolio.get("tier", 3)

    weights      = np.array([h["weight_pct"] / 100 for h in holdings])
    yields       = np.array([h.get("current_yield_pct") or 0 for h in holdings], dtype=float)
    risks        = np.array([h.get("risk_score") or 5 for h in holdings], dtype=float)
    n            = len(holdings)

    vol_per_asset = np.array([_risk_to_vol(risks[i], holdings[i]) for i in range(n)])

    # Scenario correlation override
    if scenario == "crisis":
        corr_value  = 1.0
        label       = "Full Crisis (ρ=1.0)"
        description = "Systemic contagion — all assets fall together (2008 / March 2020 style)"
    elif scenario == "moderate":
        corr_value  = 0.70
        label       = "Moderate Stress (ρ=0.70)"
        description = "Elevated correlation — risk-off environment, partial flight to quality"
    else:
        # Normal — just return baseline
        return {
            "scenario":     "normal",
            "label":        "Normal (Baseline)",
            "description":  "Current CATEGORY_CORRELATIONS model",
            "metrics":      baseline_metrics,
            "delta":        {k: 0.0 for k in baseline_metrics},
        }

    # Build stressed covariance matrix
    stressed_cov = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                stressed_cov[i, j] = vol_per_asset[i] ** 2
            else:
                stressed_cov[i, j] = corr_value * vol_per_asset[i] * vol_per_asset[j]

    stressed_var = float(weights @ stressed_cov @ weights)
    stressed_vol = math.sqrt(max(stressed_var, 0))

    avg_yield     = float(np.dot(weights, yields))
    excess_return = avg_yield - RISK_FREE_RATE
    sharpe        = excess_return / max(stressed_vol, 0.01)
    downside_vol  = stressed_vol * 0.56
    sortino       = excess_return / max(downside_vol, 0.01)

    tier_cfg     = PORTFOLIO_TIERS[tier]
    max_drawdown = min(stressed_vol * 3.0, tier_cfg["max_drawdown_pct"])
    calmar       = avg_yield / max(max_drawdown, 0.01)

    var_95  = _gaussian_var(avg_yield, stressed_vol, 0.95)
    var_99  = _gaussian_var(avg_yield, stressed_vol, 0.99)
    cvar_95 = var_95 * 1.40
    cvar_99 = var_99 * 1.48

    weighted_avg_vol  = float(np.dot(weights, vol_per_asset))
    diversification_r = weighted_avg_vol / max(stressed_vol, 0.01)

    liq       = np.array([h.get("liquidity_score") or 5 for h in holdings], dtype=float)
    avg_liquidity = float(np.dot(weights, liq))
    nav_discount  = float(np.dot(weights, [h.get("price_vs_nav_pct") or 0 for h in holdings]))

    stressed_metrics = {
        "weighted_yield_pct":       round(avg_yield, 3),
        "annual_return_usd":        round(portfolio_value * avg_yield / 100, 2),
        "monthly_income_usd":       round(portfolio_value * avg_yield / 100 / 12, 2),
        "portfolio_volatility_pct": round(stressed_vol, 3),
        "sharpe_ratio":             round(sharpe, 3),
        "sortino_ratio":            round(sortino, 3),
        "calmar_ratio":             round(calmar, 3),
        "max_drawdown_pct":         round(max_drawdown, 3),
        "var_95_pct":               round(var_95, 3),
        "var_99_pct":               round(var_99, 3),
        "cvar_95_pct":              round(cvar_95, 3),
        "cvar_99_pct":              round(cvar_99, 3),
        "diversification_ratio":    round(diversification_r, 3),
        "avg_liquidity_score":      round(avg_liquidity, 2),
        "nav_discount_pct":         round(nav_discount, 4),
        "n_holdings":               n,
        "excess_return_pct":        round(excess_return, 3),
    }

    # Delta vs baseline (positive = worse, negative = better)
    delta = {}
    for key in stressed_metrics:
        base_val = baseline_metrics.get(key, 0) or 0
        stress_val = stressed_metrics[key]
        delta[key] = round(stress_val - base_val, 3)

    return {
        "scenario":     scenario,
        "label":        label,
        "description":  description,
        "metrics":      stressed_metrics,
        "delta":        delta,
        "correlation":  corr_value,
    }


# ─────────────────────────────────────────────────────────────────────────────
# UPGRADE: DURATION / INTEREST RATE RISK MODULE
# Calculates portfolio duration, DV01, and rate scenario P&L.
# DV01 = dollar value of a 1 basis point move in rates (per $1M invested).
# ─────────────────────────────────────────────────────────────────────────────

_RATE_SCENARIOS_BPS = [-200, -100, -50, 0, 50, 100, 200]


def calculate_portfolio_duration(holdings: list, portfolio_value_usd: float = 100_000) -> dict:
    """
    Compute interest rate risk metrics for a portfolio of RWA holdings.

    Args:
        holdings: List of holding dicts with keys: id, category, weight_pct
        portfolio_value_usd: Total portfolio value in USD

    Returns dict:
        {
          "weighted_avg_duration":  float,  # years
          "dv01_usd":               float,  # $ loss per 1bp rate rise
          "dv01_per_million":        float,  # DV01 scaled to $1M
          "rate_exposure_label":    str,    # "Ultra-Short" | "Short" | "Medium" | "Long"
          "zero_duration_pct":      float,  # % of portfolio with zero rate sensitivity
          "scenarios": [
            {"shift_bps": int, "pnl_usd": float, "pnl_pct": float, "label": str},
            ...
          ],
          "holdings_duration": [
            {"id": str, "category": str, "weight_pct": float, "duration_years": float,
             "contribution_years": float},
            ...
          ],
        }
    """
    if not holdings:
        return {}

    holdings_dur = []
    total_weight = sum(h.get("weight_pct", 0) for h in holdings)

    for h in holdings:
        asset_id   = h.get("id", "")
        category   = h.get("category", "")
        weight_pct = h.get("weight_pct", 0)
        weight_frac = weight_pct / max(total_weight, 1.0)
        duration   = get_asset_duration(asset_id, category)
        holdings_dur.append({
            "id":               asset_id,
            "category":         category,
            "weight_pct":       round(weight_pct, 2),
            "duration_years":   duration,
            "contribution_years": round(weight_frac * duration, 4),
        })

    # Weighted average duration
    wav_duration = sum(h["contribution_years"] for h in holdings_dur)

    # DV01: for a 1bp (0.0001) rate change, bond price moves by ~ -Duration × 0.0001 × Value
    dv01 = portfolio_value_usd * wav_duration * 0.0001   # $ loss per 1bp rate RISE

    # % of portfolio with zero duration (commodities, art, equity-like)
    zero_dur_pct = sum(
        h["weight_pct"] for h in holdings_dur if h["duration_years"] == 0.0
    )

    # Duration label
    if wav_duration < 0.25:
        dur_label = "Ultra-Short (<3 months)"
    elif wav_duration < 1.0:
        dur_label = "Short (3-12 months)"
    elif wav_duration < 3.0:
        dur_label = "Medium (1-3 years)"
    elif wav_duration < 7.0:
        dur_label = "Long (3-7 years)"
    else:
        dur_label = "Ultra-Long (>7 years)"

    # Rate scenarios: P&L impact of parallel yield curve shifts
    scenarios = []
    for shift_bps in _RATE_SCENARIOS_BPS:
        # Price impact ≈ -ModDuration × ΔRate  (convexity adjustment skipped for simplicity)
        pnl_pct = -wav_duration * (shift_bps / 10000) * 100   # as % of portfolio
        pnl_usd = portfolio_value_usd * pnl_pct / 100
        label = (
            f"+{shift_bps}bp" if shift_bps > 0
            else f"{shift_bps}bp" if shift_bps < 0
            else "Unchanged"
        )
        scenarios.append({
            "shift_bps": shift_bps,
            "label":     label,
            "pnl_usd":   round(pnl_usd, 2),
            "pnl_pct":   round(pnl_pct, 3),
        })

    return {
        "weighted_avg_duration": round(wav_duration, 4),
        "dv01_usd":              round(dv01, 2),
        "dv01_per_million":      round(dv01 * (1_000_000 / portfolio_value_usd), 2) if portfolio_value_usd > 0 else 0.0,
        "rate_exposure_label":   dur_label,
        "zero_duration_pct":     round(zero_dur_pct, 2),
        "scenarios":             scenarios,
        "holdings_duration":     sorted(holdings_dur, key=lambda x: -x["contribution_years"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# UPGRADE: SECONDARY MARKET LIQUIDITY SCORING
# Composite liquidity score (0–100) per asset incorporating:
#   - Redemption speed (primary driver)
#   - Secondary market existence and depth
#   - Protocol liquidity_score from config (1-10)
# ─────────────────────────────────────────────────────────────────────────────

def _redemption_speed_score(days: int) -> float:
    """Convert redemption window (days) to a speed score 0-100."""
    if days == 0:    return 100.0   # instant DEX
    if days <= 1:    return 90.0    # T+1
    if days <= 3:    return 80.0    # T+3
    if days <= 7:    return 65.0    # weekly
    if days <= 14:   return 50.0    # bi-weekly
    if days <= 30:   return 35.0    # monthly
    if days <= 90:   return 20.0    # quarterly
    if days <= 180:  return 10.0    # semi-annual
    if days <= 365:  return 5.0     # annual
    return 1.0                      # locked / 999


def calculate_asset_liquidity_score(asset_id: str, category: str,
                                    protocol_liquidity_score: int = 5) -> float:
    """
    Compute composite liquidity score (0–100) for a single asset.

    Weights:
      60% redemption speed
      25% secondary market depth
      15% protocol liquidity score from config
    """
    meta       = get_asset_liquidity_meta(asset_id, category)
    speed      = _redemption_speed_score(meta["redemption_days"])
    depth_map  = {0: 0.0, 1: 40.0, 2: 70.0, 3: 100.0}
    depth      = depth_map.get(meta.get("secondary_depth", 0), 0.0)
    proto_norm = (protocol_liquidity_score / 10.0) * 100.0   # 1-10 → 0-100
    score = 0.60 * speed + 0.25 * depth + 0.15 * proto_norm
    return round(min(score, 100.0), 1)


def calculate_portfolio_liquidity(holdings: list, portfolio_value_usd: float = 100_000) -> dict:
    """
    Compute portfolio-level liquidity analytics from a list of holdings.

    Returns:
        {
          "portfolio_liquidity_score": float,    # 0-100 weighted average
          "liquid_pct":                float,    # % redeemable within 3 days
          "semi_liquid_pct":           float,    # % redeemable within 30 days
          "illiquid_pct":              float,    # % locked > 30 days
          "instant_exit_usd":          float,    # $ redeemable immediately
          "30d_exit_usd":              float,    # $ redeemable within 30 days
          "liquidity_label":           str,
          "holdings_liquidity": [
            {"id": str, "category": str, "weight_pct": float,
             "liquidity_score": float, "redemption_days": int,
             "has_secondary": bool},
            ...
          ],
        }
    """
    if not holdings:
        return {}

    holdings_liq = []
    total_weight = sum(h.get("weight_pct", 0) for h in holdings)

    for h in holdings:
        asset_id    = h.get("id", "")
        category    = h.get("category", "")
        weight_pct  = h.get("weight_pct", 0)
        proto_liq   = h.get("liquidity_score", 5)
        meta        = get_asset_liquidity_meta(asset_id, category)
        liq_score   = calculate_asset_liquidity_score(asset_id, category, proto_liq)
        holdings_liq.append({
            "id":               asset_id,
            "category":         category,
            "weight_pct":       round(weight_pct, 2),
            "liquidity_score":  liq_score,
            "redemption_days":  meta["redemption_days"],
            "has_secondary":    meta["has_secondary"],
        })

    # Portfolio-level weighted score
    port_liq_score = sum(
        h["liquidity_score"] * h["weight_pct"] / max(total_weight, 1.0)
        for h in holdings_liq
    )

    # Bucket by redemption speed
    liquid_pct     = sum(h["weight_pct"] for h in holdings_liq if h["redemption_days"] <= 3)
    semi_liq_pct   = sum(h["weight_pct"] for h in holdings_liq if 3 < h["redemption_days"] <= 30)
    illiquid_pct   = sum(h["weight_pct"] for h in holdings_liq if h["redemption_days"] > 30)

    # $ exit capacity
    instant_usd = portfolio_value_usd * sum(
        h["weight_pct"] / 100 for h in holdings_liq if h["redemption_days"] == 0
    )
    d30_usd = portfolio_value_usd * sum(
        h["weight_pct"] / 100 for h in holdings_liq if h["redemption_days"] <= 30
    )

    # Label
    if port_liq_score >= 80:
        liq_label = "Highly Liquid"
    elif port_liq_score >= 60:
        liq_label = "Moderately Liquid"
    elif port_liq_score >= 40:
        liq_label = "Semi-Liquid"
    elif port_liq_score >= 20:
        liq_label = "Illiquid"
    else:
        liq_label = "Locked"

    return {
        "portfolio_liquidity_score": round(port_liq_score, 1),
        "liquid_pct":                round(liquid_pct, 1),
        "semi_liquid_pct":           round(semi_liq_pct, 1),
        "illiquid_pct":              round(illiquid_pct, 1),
        "instant_exit_usd":          round(instant_usd, 2),
        "30d_exit_usd":              round(d30_usd, 2),
        "liquidity_label":           liq_label,
        "holdings_liquidity":        sorted(holdings_liq, key=lambda x: x["liquidity_score"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FACTOR-BASED PORTFOLIO OPTIMIZATION  (#114)
# Integrates macro factor signals into expected returns and covariance matrix.
# Factor model: 4 macro factors (VIX regime, yield curve, DXY, sentiment)
# produce tilted expected returns + stressed correlation adjustments.
# ─────────────────────────────────────────────────────────────────────────────

def compute_factor_tilted_portfolio(
    holdings: list,
    macro_factors: dict,
    value_usd: float = 100_000,
) -> dict:
    """
    Run mean-variance optimization with factor-tilted expected returns.

    Takes the macro factor bias (from get_macro_factor_allocation_bias) and:
      1. Adjusts per-asset expected returns by their category's factor tilt
      2. Scales correlations up during high-stress regimes (VIX > 25)
      3. Finds the max-Sharpe portfolio using random sampling

    Args:
        holdings:      list of holding dicts (same format as build_portfolio output)
        macro_factors: output of get_macro_factor_allocation_bias()
        value_usd:     portfolio notional for USD calculations

    Returns:
        max_sharpe_weights, expected_return, expected_vol, sharpe,
        factor_adjustments, regime, correlation_scalar
    """
    if not holdings:
        return {"error": "No holdings", "weights": {}}

    adj         = macro_factors.get("adjustments", {})
    factors     = macro_factors.get("factors", {})
    regime      = factors.get("regime", macro_factors.get("regime", "NEUTRAL"))
    vix         = float(factors.get("vix", 18.0))
    rationale   = macro_factors.get("rationale", "")

    # Stress correlation scalar — correlations spike during market stress
    # Research (Longin & Solnik 2001): avg pairwise correlation rises ~0.25 during VIX>30
    if vix > 35:
        corr_scalar = 1.45    # extreme stress: +45% correlation
    elif vix > 25:
        corr_scalar = 1.20    # elevated stress: +20%
    elif vix < 13:
        corr_scalar = 0.85    # low-vol regime: correlations slightly lower
    else:
        corr_scalar = 1.00    # normal regime

    n = min(len(holdings), 20)
    if n < 2:
        return {"error": "Need at least 2 holdings", "weights": {}}

    h       = holdings[:n]
    cats    = [x.get("category", "") for x in h]
    ids     = [x.get("id", f"asset_{i}") for i, x in enumerate(h)]

    # Base yields
    base_yields = np.array([
        float(x.get("current_yield_pct") or x.get("expected_yield_pct", 0))
        for x in h
    ])

    # Factor-tilted expected returns: add category adjustment (converted to %)
    # adj values are in percentage-point deltas — convert to additive return adj
    tilted_yields = base_yields.copy()
    cat_adj_map: dict = {}
    for i, cat in enumerate(cats):
        cat_delta = adj.get(cat, 0.0) / 10.0  # scale: 10pp bias → 1% yield adj
        tilted_yields[i] = base_yields[i] + cat_delta
        cat_adj_map[cat] = round(cat_delta, 3)

    tilted_yields = np.clip(tilted_yields, 0.1, 40.0)

    # Per-asset volatilities
    vols = np.array([_risk_to_vol(x.get("risk_score", 5), x) for x in h])

    # Factor-adjusted covariance matrix
    cov = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                cov[i, j] = vols[i] ** 2
            else:
                pair = (cats[i], cats[j])
                pair_rev = (cats[j], cats[i])
                base_corr = CATEGORY_CORRELATIONS.get(pair,
                            CATEGORY_CORRELATIONS.get(pair_rev, 0.15))
                # Apply stress scalar, clamp to [0.05, 0.95]
                adj_corr = min(0.95, max(0.05, base_corr * corr_scalar))
                cov[i, j] = adj_corr * vols[i] * vols[j]

    # Random-sampling mean-variance (no scipy required)
    rng = np.random.default_rng(42)
    best_sharpe = -999.0
    best_weights = np.ones(n) / n  # equal weight fallback

    for _ in range(3_000):
        w = rng.dirichlet(np.ones(n))
        ret = float(np.dot(w, tilted_yields))
        var = float(w @ cov @ w)
        vol = math.sqrt(max(var, 1e-8))
        sr  = (ret - RISK_FREE_RATE) / vol
        if sr > best_sharpe:
            best_sharpe = sr
            best_weights = w

    # Map weights to holding IDs
    weight_map = {ids[i]: round(float(best_weights[i]) * 100, 2) for i in range(n)}

    best_ret = float(np.dot(best_weights, tilted_yields))
    best_var = float(best_weights @ cov @ best_weights)
    best_vol = math.sqrt(max(best_var, 1e-8))

    return {
        "weights":             weight_map,
        "expected_return_pct": round(best_ret, 3),
        "expected_vol_pct":    round(best_vol, 3),
        "sharpe":              round(best_sharpe, 3),
        "factor_adjustments":  cat_adj_map,
        "correlation_scalar":  round(corr_scalar, 2),
        "regime":              regime,
        "vix":                 round(vix, 1),
        "rationale":           rationale,
        "n_assets":            n,
    }
