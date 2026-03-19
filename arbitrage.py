"""
arbitrage.py — RWA Infinity Model v1.0
Multi-dimensional RWA arbitrage scanner:
  1. Yield Spread Arb     — same asset category, different protocols
  2. Price vs NAV Arb     — token price deviates from net asset value
  3. Cross-Chain Arb      — same asset priced differently on different chains
  4. Carry Trade / Basis  — borrow low, invest in higher-yield RWA
  5. Liquidity Premium    — illiquid RWA vs liquid equivalent yield gap
  6. Stablecoin Yield     — yield-bearing stablecoin vs vanilla stablecoin
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional

import database as _db
from config import (
    RWA_UNIVERSE, ARB_MIN_YIELD_SPREAD_PCT,
    ARB_STRONG_THRESHOLD_PCT, ARB_EXTREME_THRESHOLD_PCT,
    ARB_MIN_PRICE_SPREAD_PCT
)
from data_feeds import fetch_defillama_yields, fetch_coingecko_prices

logger = logging.getLogger(__name__)

# ─── Transaction cost estimates ───────────────────────────────────────────────
# Round-trip costs (entry + exit) for different asset types
TX_COSTS = {
    "Government Bonds":     0.10,   # 10 bps round-trip
    "Private Credit":       0.50,   # 50 bps (redemption fees)
    "Real Estate":          2.00,   # 2% round-trip (illiquid)
    "Commodities":          0.20,   # 20 bps
    "Equities":             0.10,   # 10 bps
    "Carbon Credits":       0.50,   # 50 bps
    "Intellectual Property":1.00,   # 1% (thin market)
    "Art & Collectibles":   3.00,   # 3% (very illiquid)
    "Private Equity":       2.00,   # 2% round-trip
    "Insurance":            0.50,
    "Trade Finance":        0.30,
}

# Bridge/chain costs for cross-chain arb
BRIDGE_COST_PCT = 0.15   # ~15 bps to bridge between chains

# Gas cost estimates (USD) per chain operation
GAS_COSTS = {
    "Ethereum":  5.0,
    "Polygon":   0.01,
    "Solana":    0.0005,
    "Arbitrum":  0.10,
    "Optimism":  0.10,
    "Gnosis":    0.001,
    "Avalanche": 0.05,
    "BNB":       0.05,
}

# Minimum trade size to make arb worthwhile
MIN_TRADE_USD = 10_000


# ─────────────────────────────────────────────────────────────────────────────
# YIELD SPREAD ARBITRAGE
# ─────────────────────────────────────────────────────────────────────────────

def scan_yield_spread_arb(assets: List[dict]) -> List[dict]:
    """
    Find yield spread arbitrage opportunities within the same asset category.
    e.g.: TBILL yields 5.12% while BENJI yields 5.05% → 7bps spread.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    # Group assets by category
    by_category: Dict[str, List[dict]] = {}
    for asset in assets:
        cat = asset.get("category", "Unknown")
        by_category.setdefault(cat, []).append(asset)

    for cat, cat_assets in by_category.items():
        # Need at least 2 assets in same category
        if len(cat_assets) < 2:
            continue

        # Sort by yield descending
        sorted_assets = sorted(
            cat_assets,
            key=lambda x: x.get("current_yield_pct") or x.get("expected_yield_pct") or 0,
            reverse=True
        )

        tx_cost = TX_COSTS.get(cat, 0.50)

        for i, high_yield_asset in enumerate(sorted_assets[:-1]):
            for low_yield_asset in sorted_assets[i+1:]:
                high_yield = high_yield_asset.get("current_yield_pct") or \
                             high_yield_asset.get("expected_yield_pct") or 0
                low_yield  = low_yield_asset.get("current_yield_pct") or \
                             low_yield_asset.get("expected_yield_pct") or 0

                if low_yield <= 0:
                    continue

                gross_spread = high_yield - low_yield
                net_spread   = gross_spread - tx_cost

                if net_spread < ARB_MIN_YIELD_SPREAD_PCT:
                    continue

                # Liquidity check — both must be liquid enough to trade
                min_liquidity = min(
                    high_yield_asset.get("liquidity_score", 5),
                    low_yield_asset.get("liquidity_score", 5)
                )
                if min_liquidity < 3:
                    continue

                signal = (
                    "EXTREME_ARB" if net_spread >= ARB_EXTREME_THRESHOLD_PCT else
                    "STRONG_ARB"  if net_spread >= ARB_STRONG_THRESHOLD_PCT  else
                    "ARB"
                )

                opp = {
                    "timestamp":     now,
                    "type":          "yield_spread",
                    "asset_a_id":    high_yield_asset["id"],
                    "asset_b_id":    low_yield_asset["id"],
                    "asset_a_name":  high_yield_asset["name"],
                    "asset_b_name":  low_yield_asset["name"],
                    "protocol_a":    high_yield_asset.get("protocol", ""),
                    "protocol_b":    low_yield_asset.get("protocol", ""),
                    "chain_a":       high_yield_asset.get("chain", ""),
                    "chain_b":       low_yield_asset.get("chain", ""),
                    "yield_a_pct":   round(high_yield, 4),
                    "yield_b_pct":   round(low_yield, 4),
                    "spread_pct":    round(gross_spread, 4),
                    "net_spread_pct":round(net_spread, 4),
                    "estimated_apy": round(net_spread, 4),
                    "category":      cat,
                    "tx_cost_pct":   tx_cost,
                    "min_liquidity": min_liquidity,
                    "signal":        signal,
                    "action": (
                        f"ROTATE: Exit {low_yield_asset['id']} ({low_yield:.2f}% yield) → "
                        f"Enter {high_yield_asset['id']} ({high_yield:.2f}% yield). "
                        f"Net gain: {net_spread:.2f}% annually on {_fmt_usd(MIN_TRADE_USD)}"
                    ),
                    "notes": (
                        f"Same category ({cat}), similar risk profiles. "
                        f"Gross spread {gross_spread:.2f}% minus {tx_cost}% tx costs = {net_spread:.2f}% net."
                    ),
                }
                opportunities.append(opp)

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# PRICE vs NAV ARBITRAGE
# ─────────────────────────────────────────────────────────────────────────────

def scan_price_vs_nav_arb(assets: List[dict]) -> List[dict]:
    """
    Find tokens trading at a discount or premium to NAV.
    Discount → buy token, redeem at NAV = instant profit.
    Premium  → sell token, create new token at NAV = instant profit.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    for asset in assets:
        price_vs_nav = asset.get("price_vs_nav_pct", 0) or 0
        if abs(price_vs_nav) < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        current_price = asset.get("current_price", 1.0) or 1.0
        nav_price     = asset.get("nav_price", 1.0) or 1.0
        if nav_price <= 0:
            continue

        direction   = "DISCOUNT" if price_vs_nav < 0 else "PREMIUM"
        gross_spread = abs(price_vs_nav)
        tx_cost      = TX_COSTS.get(asset.get("category", ""), 0.5)
        net_spread   = gross_spread - tx_cost

        if net_spread < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        signal = (
            "EXTREME_ARB" if net_spread >= ARB_EXTREME_THRESHOLD_PCT else
            "STRONG_ARB"  if net_spread >= ARB_STRONG_THRESHOLD_PCT  else
            "ARB"
        )

        action = (
            f"{'BUY' if direction == 'DISCOUNT' else 'SHORT'} {asset['id']}: "
            f"Token at ${current_price:.4f} vs NAV ${nav_price:.4f} "
            f"({direction} of {gross_spread:.2f}%). "
            f"Net after costs: {net_spread:.2f}%."
        )

        opp = {
            "timestamp":     now,
            "type":          "price_vs_nav",
            "asset_a_id":    asset["id"],
            "asset_b_id":    "NAV",
            "asset_a_name":  asset["name"],
            "asset_b_name":  "Net Asset Value",
            "protocol_a":    asset.get("protocol", ""),
            "protocol_b":    "On-chain NAV",
            "chain_a":       asset.get("chain", ""),
            "chain_b":       "N/A",
            "yield_a_pct":   asset.get("current_yield_pct") or 0,
            "yield_b_pct":   0,
            "spread_pct":    round(gross_spread, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread * 4, 4),  # assume quarterly opportunity
            "category":      asset.get("category", ""),
            "tx_cost_pct":   tx_cost,
            "direction":     direction,
            "signal":        signal,
            "action":        action,
            "notes": (
                f"{asset['id']} currently trades at {abs(price_vs_nav):.2f}% "
                f"{'below' if direction == 'DISCOUNT' else 'above'} NAV. "
                f"Liquidity score: {asset.get('liquidity_score', 'N/A')}/10."
            ),
        }
        opportunities.append(opp)

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-CHAIN ARBITRAGE
# ─────────────────────────────────────────────────────────────────────────────

def scan_cross_chain_arb(assets: List[dict]) -> List[dict]:
    """
    Find the same asset (by ID pattern or yield similarity) priced differently
    on different chains.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    # Group by token symbol (multi-chain assets)
    by_symbol: Dict[str, List[dict]] = {}
    for asset in assets:
        sym = asset.get("token_symbol", "")
        if sym:
            by_symbol.setdefault(sym, []).append(asset)

    # Look for multi-chain RWA assets with yield differences
    # (e.g., OUSG on Ethereum vs Solana, USDY on Ethereum vs Mantle)
    cross_chain_pairs = [
        # (asset_id_a, chain_a, asset_id_b, chain_b, expected_spread_note)
        ("OUSG",  "Ethereum", "OUSG",  "Solana",  "Solana OUSG may lag Ethereum by 1-2 days"),
        ("USDM",  "Ethereum", "USDM",  "Polygon", "Polygon bridge premium"),
        ("USDY",  "Ethereum", "USDY",  "Solana",  "Cross-chain yield arbitrage"),
        ("TBILL", "Ethereum", "TBILL", "Polygon", "Gas cost arbitrage"),
    ]

    for sym_a, chain_a, sym_b, chain_b, note in cross_chain_pairs:
        assets_a = [a for a in assets if a.get("token_symbol") == sym_a
                    and chain_a.lower() in (a.get("chain") or "").lower()]
        assets_b = [a for a in assets if a.get("token_symbol") == sym_b
                    and chain_b.lower() in (a.get("chain") or "").lower()]

        if not assets_a or not assets_b:
            continue

        asset_a = assets_a[0]
        asset_b = assets_b[0]

        # Price difference
        price_a = asset_a.get("current_price", 1.0) or 1.0
        price_b = asset_b.get("current_price", 1.0) or 1.0

        if price_a <= 0 or price_b <= 0:
            continue

        price_diff_pct = abs(price_a - price_b) / min(price_a, price_b) * 100

        # Gas costs both chains
        gas_a = GAS_COSTS.get(chain_a, 1.0)
        gas_b = GAS_COSTS.get(chain_b, 1.0)
        gas_cost_pct = (gas_a + gas_b) / MIN_TRADE_USD * 100 + BRIDGE_COST_PCT

        net_spread = price_diff_pct - gas_cost_pct

        if net_spread < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        signal = "STRONG_ARB" if net_spread >= ARB_STRONG_THRESHOLD_PCT else "ARB"
        higher_price_chain = chain_a if price_a >= price_b else chain_b
        lower_price_chain  = chain_b if price_a >= price_b else chain_a

        opp = {
            "timestamp":     now,
            "type":          "cross_chain",
            "asset_a_id":    asset_a["id"],
            "asset_b_id":    asset_b["id"],
            "asset_a_name":  f"{sym_a} on {chain_a}",
            "asset_b_name":  f"{sym_b} on {chain_b}",
            "protocol_a":    asset_a.get("protocol", ""),
            "protocol_b":    asset_b.get("protocol", ""),
            "chain_a":       chain_a,
            "chain_b":       chain_b,
            "yield_a_pct":   price_a,
            "yield_b_pct":   price_b,
            "spread_pct":    round(price_diff_pct, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread * 12, 4),  # assume monthly cycle
            "category":      asset_a.get("category", ""),
            "tx_cost_pct":   round(gas_cost_pct, 4),
            "signal":        signal,
            "action": (
                f"BUY {sym_a} on {lower_price_chain}, BRIDGE, SELL on {higher_price_chain}. "
                f"Price diff: {price_diff_pct:.3f}%, Bridge + gas: {gas_cost_pct:.3f}%, "
                f"Net: {net_spread:.3f}%."
            ),
            "notes": note,
        }
        opportunities.append(opp)

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# STABLECOIN YIELD ARBITRAGE
# ─────────────────────────────────────────────────────────────────────────────

def scan_stablecoin_yield_arb(assets: List[dict]) -> List[dict]:
    """
    Compare yield-bearing stablecoins (USDM, USDY, OUSG) vs
    vanilla stablecoins (USDC, USDT) earning 0%.
    This is a straightforward "rotate out of 0% yield into RWA yield" opportunity.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    yield_stables = [
        a for a in assets
        if "stablecoin" in [t.lower() for t in (a.get("tags") or [])]
        and (a.get("current_yield_pct") or 0) > 0
    ]

    for asset in yield_stables:
        yield_pct = asset.get("current_yield_pct") or asset.get("expected_yield_pct") or 0
        if yield_pct < 1.0:
            continue

        tx_cost    = 0.10   # minimal for stablecoins
        net_yield  = yield_pct - tx_cost

        signal = (
            "STRONG_ARB" if net_yield >= 4.0 else
            "ARB"        if net_yield >= 2.0 else
            "MARGINAL"
        )

        if signal == "MARGINAL":
            continue

        opp = {
            "timestamp":     now,
            "type":          "stablecoin_yield",
            "asset_a_id":    asset["id"],
            "asset_b_id":    "USDC",
            "asset_a_name":  asset["name"],
            "asset_b_name":  "USDC (0% yield)",
            "protocol_a":    asset.get("protocol", ""),
            "protocol_b":    "Circle",
            "chain_a":       asset.get("chain", ""),
            "chain_b":       "Ethereum",
            "yield_a_pct":   round(yield_pct, 4),
            "yield_b_pct":   0.0,
            "spread_pct":    round(yield_pct, 4),
            "net_spread_pct":round(net_yield, 4),
            "estimated_apy": round(net_yield, 4),
            "category":      "Government Bonds",
            "tx_cost_pct":   tx_cost,
            "signal":        signal,
            "action": (
                f"SWAP: USDC → {asset['id']}. Earn {yield_pct:.2f}% APY "
                f"(vs 0% on vanilla USDC). Min investment: ${asset.get('min_investment_usd', 0):,.0f}."
            ),
            "notes": (
                f"{asset['id']} is a yield-bearing stablecoin backed by US Treasuries. "
                f"Risk score: {asset.get('risk_score', 'N/A')}/10. "
                f"Regulatory: {asset.get('regulatory_score', 'N/A')}/10."
            ),
        }
        opportunities.append(opp)

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# DEFILLAMA YIELD POOL SPREAD ARB
# ─────────────────────────────────────────────────────────────────────────────

def scan_defi_pool_arb() -> List[dict]:
    """
    Scan DeFiLlama yield pools for the same underlying asset
    earning very different yields across protocols.
    e.g., USDC earning 3% on Compound vs 8% on Maple.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    pools = fetch_defillama_yields()
    if not pools:
        return []

    # Group pools by symbol
    by_sym: Dict[str, List[dict]] = {}
    for pool in pools:
        sym = (pool.get("symbol") or "").upper()
        # Focus on RWA-adjacent symbols
        rwa_syms = {"USDC", "USDT", "DAI", "FRAX", "OUSG", "USDM", "USDY",
                    "TBILL", "USTB", "PAXG", "STBT", "CFG", "MPL", "GFI"}
        if sym in rwa_syms and pool.get("apy", 0) > 0:
            by_sym.setdefault(sym, []).append(pool)

    for sym, sym_pools in by_sym.items():
        if len(sym_pools) < 2:
            continue

        sorted_pools = sorted(sym_pools, key=lambda x: x["apy"], reverse=True)
        high = sorted_pools[0]
        low  = sorted_pools[-1]

        if high["apy"] <= 0 or low["apy"] <= 0:
            continue

        gross_spread = high["apy"] - low["apy"]
        tx_cost      = 0.30   # swap + protocol fees
        net_spread   = gross_spread - tx_cost

        if net_spread < ARB_MIN_YIELD_SPREAD_PCT:
            continue

        signal = (
            "EXTREME_ARB" if net_spread >= ARB_EXTREME_THRESHOLD_PCT else
            "STRONG_ARB"  if net_spread >= ARB_STRONG_THRESHOLD_PCT  else
            "ARB"
        )

        opp = {
            "timestamp":     now,
            "type":          "defi_pool_spread",
            "asset_a_id":    f"{sym}_{high.get('project','').upper()}",
            "asset_b_id":    f"{sym}_{low.get('project','').upper()}",
            "asset_a_name":  f"{sym} @ {high.get('project','?')} ({high.get('chain','?')})",
            "asset_b_name":  f"{sym} @ {low.get('project','?')} ({low.get('chain','?')})",
            "protocol_a":    high.get("project", ""),
            "protocol_b":    low.get("project", ""),
            "chain_a":       high.get("chain", ""),
            "chain_b":       low.get("chain", ""),
            "yield_a_pct":   round(high["apy"], 4),
            "yield_b_pct":   round(low["apy"], 4),
            "spread_pct":    round(gross_spread, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread, 4),
            "category":      "Private Credit",
            "tx_cost_pct":   tx_cost,
            "signal":        signal,
            "action": (
                f"ROTATE: Move {sym} from {low.get('project')} ({low['apy']:.2f}% APY) "
                f"to {high.get('project')} ({high['apy']:.2f}% APY). "
                f"Net gain: {net_spread:.2f}% per year."
            ),
            "notes": (
                f"TVL in high-yield pool: ${high['tvl_usd']:,.0f}. "
                f"TVL in low-yield pool: ${low['tvl_usd']:,.0f}. "
                f"IL Risk high: {high['il_risk']} | low: {low['il_risk']}."
            ),
        }
        opportunities.append(opp)

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# CARRY TRADE (Borrow Low, Invest in RWA)
# ─────────────────────────────────────────────────────────────────────────────

def scan_carry_trades(assets: List[dict]) -> List[dict]:
    """
    Identify carry trade opportunities:
    Borrow USDC/ETH at low rate → Deploy into high-yield RWA.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    # Current borrowing rates on major DeFi platforms (approximate)
    borrow_rates = {
        "USDC on Aave":    5.20,
        "USDC on Compound":5.10,
        "USDT on Aave":    5.15,
        "DAI on MakerDAO": 5.00,
        "ETH on Aave":     2.80,
    }

    # Filter high-yield RWA assets
    high_yield_assets = sorted(
        [a for a in assets if (a.get("current_yield_pct") or 0) > 6.0
         and a.get("risk_score", 10) <= 6
         and a.get("liquidity_score", 0) >= 5],
        key=lambda x: x.get("current_yield_pct", 0),
        reverse=True
    )[:10]

    for asset in high_yield_assets:
        asset_yield = asset.get("current_yield_pct") or asset.get("expected_yield_pct") or 0

        for borrow_source, borrow_rate in borrow_rates.items():
            carry_spread = asset_yield - borrow_rate
            tx_cost      = TX_COSTS.get(asset.get("category", ""), 0.5)
            net_carry    = carry_spread - tx_cost

            if net_carry < 1.0:  # minimum 1% net carry
                continue

            signal = (
                "STRONG_ARB" if net_carry >= ARB_STRONG_THRESHOLD_PCT else "ARB"
            )

            opp = {
                "timestamp":     now,
                "type":          "carry_trade",
                "asset_a_id":    asset["id"],
                "asset_b_id":    borrow_source.replace(" ", "_").upper(),
                "asset_a_name":  f"INVEST: {asset['name']}",
                "asset_b_name":  f"BORROW: {borrow_source}",
                "protocol_a":    asset.get("protocol", ""),
                "protocol_b":    borrow_source,
                "chain_a":       asset.get("chain", ""),
                "chain_b":       "Ethereum",
                "yield_a_pct":   round(asset_yield, 4),
                "yield_b_pct":   round(borrow_rate, 4),
                "spread_pct":    round(carry_spread, 4),
                "net_spread_pct":round(net_carry, 4),
                "estimated_apy": round(net_carry, 4),
                "category":      asset.get("category", ""),
                "tx_cost_pct":   tx_cost,
                "signal":        signal,
                "action": (
                    f"CARRY: Borrow {borrow_source.split(' ')[0]} @ {borrow_rate:.2f}%, "
                    f"invest in {asset['id']} @ {asset_yield:.2f}%. "
                    f"Net carry: {net_carry:.2f}% per year."
                ),
                "notes": (
                    f"Risk: Rising borrow rates could compress carry. "
                    f"Asset risk score: {asset.get('risk_score')}/10. "
                    f"Max leverage: 1.5x recommended for risk management."
                ),
            }
            opportunities.append(opp)
            break  # only log the best borrow source per asset

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCANNER
# ─────────────────────────────────────────────────────────────────────────────

def run_full_arb_scan(assets: List[dict] = None) -> List[dict]:
    """
    Run all arbitrage scanners and return combined, deduplicated opportunities.
    Saves results to database.
    """
    logger.info("[Arb] Starting full arbitrage scan...")

    if assets is None:
        df = _db.get_all_rwa_latest()
        if df.empty:
            assets = list(RWA_UNIVERSE)
        else:
            assets = df.to_dict("records")

    all_opps = []

    # 1. Yield spread within categories
    try:
        opps = scan_yield_spread_arb(assets)
        logger.info("[Arb] Yield spread: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] yield_spread failed: %s", e)

    # 2. Price vs NAV
    try:
        opps = scan_price_vs_nav_arb(assets)
        logger.info("[Arb] Price vs NAV: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] price_vs_nav failed: %s", e)

    # 3. Cross-chain
    try:
        opps = scan_cross_chain_arb(assets)
        logger.info("[Arb] Cross-chain: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] cross_chain failed: %s", e)

    # 4. Stablecoin yield
    try:
        opps = scan_stablecoin_yield_arb(assets)
        logger.info("[Arb] Stablecoin yield: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] stablecoin_yield failed: %s", e)

    # 5. DeFi pool spreads
    try:
        opps = scan_defi_pool_arb()
        logger.info("[Arb] DeFi pool spread: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] defi_pool_arb failed: %s", e)

    # 6. Carry trades
    try:
        opps = scan_carry_trades(assets)
        logger.info("[Arb] Carry trades: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] carry_trades failed: %s", e)

    # Mark old opportunities as inactive
    try:
        conn = _db._get_conn()
        conn.execute("UPDATE arb_opportunities SET is_active=0 WHERE is_active=1")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("[Arb] Failed to clear old opportunities: %s", e)

    # Save new opportunities
    for opp in all_opps:
        try:
            _db.log_arb_opportunity(opp)
        except Exception as e:
            logger.warning("[Arb] Failed to log opportunity: %s", e)

    logger.info("[Arb] Scan complete — %d total opportunities found", len(all_opps))
    return sorted(all_opps, key=lambda x: x.get("net_spread_pct", 0), reverse=True)


def _fmt_usd(n: float) -> str:
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"${n/1_000:.0f}K"
    return f"${n:.0f}"


def get_arb_summary(opportunities: List[dict]) -> dict:
    """Return summary stats for arbitrage dashboard."""
    if not opportunities:
        return {
            "total": 0, "strong": 0, "extreme": 0,
            "avg_spread_pct": 0, "best_spread_pct": 0,
            "by_type": {}
        }

    strong  = [o for o in opportunities if o.get("signal") in ("STRONG_ARB", "EXTREME_ARB")]
    extreme = [o for o in opportunities if o.get("signal") == "EXTREME_ARB"]
    spreads = [o.get("net_spread_pct", 0) for o in opportunities]

    by_type: Dict[str, int] = {}
    for o in opportunities:
        t = o.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total":            len(opportunities),
        "strong":           len(strong),
        "extreme":          len(extreme),
        "avg_spread_pct":   round(sum(spreads) / len(spreads), 3) if spreads else 0,
        "best_spread_pct":  round(max(spreads), 3) if spreads else 0,
        "by_type":          by_type,
    }
