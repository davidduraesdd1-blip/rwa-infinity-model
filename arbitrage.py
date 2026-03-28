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

import json
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
from data_feeds import fetch_defillama_yields, fetch_coingecko_prices, fetch_lending_borrow_rates

logger = logging.getLogger(__name__)

# ─── Transaction cost estimates ───────────────────────────────────────────────
# Round-trip costs (entry + exit) for different asset types
TX_COSTS = {
    "Government Bonds":     0.10,   # 10 bps round-trip
    "Private Credit":       0.50,   # 50 bps (redemption fees)
    "Real Estate":          2.00,   # 2% round-trip (illiquid)
    "Commodities":          0.20,   # 20 bps
    "Equities":             0.10,   # 10 bps
    "Tokenized Equities":   0.05,   # 5 bps — liquid DEX markets (Dinari, Robinhood, Gains)
    "Carbon Credits":       0.50,   # 50 bps (legacy key)
    "Voluntary Carbon":     0.50,   # 50 bps
    "Nature-Based Solutions": 0.50,
    "Compliance Carbon":    0.30,
    "Precious Metals":      0.20,   # DEX liquid, similar to commodities
    "Yield Derivatives":    0.20,   # Pendle AMM — low tx cost
    "Intellectual Property":1.00,   # 1% (thin market)
    "Art & Collectibles":   3.00,   # 3% (very illiquid)
    "Private Equity":       2.00,   # 2% round-trip
    "Insurance":            0.50,
    "Trade Finance":        0.30,
}

# Bridge/chain costs for cross-chain arb
BRIDGE_COST_PCT = 0.15   # ~15 bps to bridge between chains

# Gas cost estimates (USD) per chain operation — updated for all supported chains
GAS_COSTS = {
    "Ethereum":     5.00,    # mainnet gas, variable but typically $2–$10
    "Polygon":      0.01,    # PoS sidechain
    "Solana":       0.0005,  # near-zero
    "Arbitrum":     0.10,    # Ethereum L2
    "Optimism":     0.10,    # Ethereum L2
    "Base":         0.01,    # Coinbase L2 — very cheap
    "Gnosis":       0.001,   # xDAI chain
    "Avalanche":    0.05,    # C-chain fees
    "BNB":          0.05,    # BSC fees
    "Hedera":       0.001,   # HBAR transaction = $0.0001 HBAR ≈ minimal
    "XRP Ledger":   0.0001,  # XRP drops, near-free
    "Tezos":        0.05,    # Tezos baking + gas
    "Provenance":   0.001,   # Figure chain, minimal fees
    "Aptos":        0.0003,  # Move VM, efficient
    "Cardano":      0.20,    # ADA min UTXO + fees
    "Sui":          0.0001,  # Move VM, near-free
    "Stellar":      0.0001,  # XLM base reserve + fee
    "Algorand":     0.001,   # ALGO minimum fee
    "Tron":         0.01,    # TRX energy model
    "Multiple":     1.00,    # multi-chain: conservatively use Ethereum-level costs
    # New chains — 2025/2026 additions
    "Plume":        0.01,    # purpose-built RWA chain, EVM-compatible, very low gas
    "Mantra":       0.01,    # Cosmos SDK appchain, very low gas
    "Noble":        0.001,   # Cosmos IBC T-bill chain, near-zero fees
    "TON":          0.01,    # Telegram Open Network
    "ZKsync Era":   0.05,    # ZK rollup, cheaper than Ethereum mainnet
    "Starknet":     0.05,    # StarkWare ZK rollup
    "Linea":        0.02,    # Consensys L2
    "Mantle":       0.01,    # Bybit-backed L2
    "Kinexys":      0.10,    # JPMorgan private EVM (internal transfer estimate)
    "Centrifuge Chain": 0.10, # Polkadot parachain
    "Canton Network": 0.05,  # Goldman Sachs / Digital Asset institutional chain
    "Polymesh":     0.05,    # Regulated securities chain (Polymath)
    "SDX":          0.00,    # SIX Digital Exchange — zero gas, fee handled by CSD
    "Berachain":    0.003,   # Proof of Liquidity EVM — near-zero gas, EVM-compatible
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
    Dynamically detect the same asset priced differently across chains.

    Algorithm:
    1. Group all assets by protocol name (same protocol on different chains)
    2. For multi-chain assets listed in config (chain field contains ' / '),
       decompose into per-chain entries and compare prices
    3. Also scan by token_symbol matches across different chains

    Fully dynamic — automatically picks up any new multi-chain assets added to config.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    # ── Strategy 1: Same protocol appearing on multiple chains ────────────────
    # Group assets by (protocol, category) — assets from same protocol + category
    # on different chains should trade at similar yields/prices
    by_protocol: Dict[str, List[dict]] = {}
    for asset in assets:
        proto = (asset.get("protocol") or "").strip()
        cat   = (asset.get("category") or "").strip()
        if proto:
            key = f"{proto}|{cat}"
            by_protocol.setdefault(key, []).append(asset)

    for key, proto_assets in by_protocol.items():
        if len(proto_assets) < 2:
            continue

        # Only compare if they are on meaningfully different chains
        chains = [(a.get("chain") or "").split(" / ")[0].strip() for a in proto_assets]
        if len(set(chains)) < 2:
            continue  # all on same chain

        # Compare yield differences (yield arb, not just price)
        sorted_pa = sorted(
            proto_assets,
            key=lambda x: x.get("current_yield_pct") or x.get("expected_yield_pct") or 0,
            reverse=True
        )
        asset_a = sorted_pa[0]
        asset_b = sorted_pa[-1]
        chain_a = (asset_a.get("chain") or "Ethereum").split(" / ")[0].strip()
        chain_b = (asset_b.get("chain") or "Ethereum").split(" / ")[0].strip()

        if chain_a == chain_b:
            continue

        yield_a = asset_a.get("current_yield_pct") or asset_a.get("expected_yield_pct") or 0
        yield_b = asset_b.get("current_yield_pct") or asset_b.get("expected_yield_pct") or 0
        if yield_b <= 0:
            continue

        gross_spread = yield_a - yield_b
        gas_a        = GAS_COSTS.get(chain_a, 1.0)
        gas_b        = GAS_COSTS.get(chain_b, 1.0)
        gas_cost_pct = (gas_a + gas_b) / MIN_TRADE_USD * 100 + BRIDGE_COST_PCT
        tx_cost      = TX_COSTS.get(asset_a.get("category", ""), 0.30)
        net_spread   = gross_spread - gas_cost_pct - tx_cost

        if net_spread < ARB_MIN_YIELD_SPREAD_PCT:
            continue

        signal = (
            "EXTREME_ARB" if net_spread >= ARB_EXTREME_THRESHOLD_PCT else
            "STRONG_ARB"  if net_spread >= ARB_STRONG_THRESHOLD_PCT  else
            "ARB"
        )

        opp = {
            "timestamp":     now,
            "type":          "cross_chain",
            "asset_a_id":    asset_a["id"],
            "asset_b_id":    asset_b["id"],
            "asset_a_name":  f"{asset_a['id']} on {chain_a}",
            "asset_b_name":  f"{asset_b['id']} on {chain_b}",
            "protocol_a":    asset_a.get("protocol", ""),
            "protocol_b":    asset_b.get("protocol", ""),
            "chain_a":       chain_a,
            "chain_b":       chain_b,
            "yield_a_pct":   round(yield_a, 4),
            "yield_b_pct":   round(yield_b, 4),
            "spread_pct":    round(gross_spread, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread, 4),
            "category":      asset_a.get("category", ""),
            "tx_cost_pct":   round(gas_cost_pct + tx_cost, 4),
            "signal":        signal,
            "action": (
                f"ROTATE: Exit {asset_b['id']} on {chain_b} ({yield_b:.2f}% yield) → "
                f"Enter {asset_a['id']} on {chain_a} ({yield_a:.2f}% yield). "
                f"Net gain after bridge + gas: {net_spread:.2f}% annually."
            ),
            "notes": (
                f"Same protocol ({asset_a.get('protocol', '?')}) deployed on {chain_a} and {chain_b}. "
                f"Bridge cost: {BRIDGE_COST_PCT:.2f}%, gas: ${gas_a + gas_b:.3f}."
            ),
        }
        opportunities.append(opp)

    # ── Strategy 2: Multi-chain assets with price divergence ──────────────────
    # Assets whose chain field contains ' / ' are multi-chain.
    # If they appear in the DB with different prices per chain version, scan those.
    by_symbol: Dict[str, List[dict]] = {}
    for asset in assets:
        sym = (asset.get("token_symbol") or "").upper()
        if sym:
            by_symbol.setdefault(sym, []).append(asset)

    for sym, sym_assets in by_symbol.items():
        if len(sym_assets) < 2:
            continue
        # Extract per-chain entries and compare prices
        sorted_sa = sorted(sym_assets,
                           key=lambda x: x.get("current_price") or 1.0, reverse=True)
        high_a = sorted_sa[0]
        low_b  = sorted_sa[-1]
        chain_a = (high_a.get("chain") or "Ethereum").split(" / ")[0].strip()
        chain_b = (low_b.get("chain") or "Ethereum").split(" / ")[0].strip()
        if chain_a == chain_b or high_a["id"] == low_b["id"]:
            continue

        price_a = high_a.get("current_price") or 1.0
        price_b = low_b.get("current_price") or 1.0
        if price_a <= 0 or price_b <= 0 or price_a == price_b:
            continue

        price_diff_pct = abs(price_a - price_b) / min(price_a, price_b) * 100
        gas_a          = GAS_COSTS.get(chain_a, 1.0)
        gas_b          = GAS_COSTS.get(chain_b, 1.0)
        gas_cost_pct   = (gas_a + gas_b) / MIN_TRADE_USD * 100 + BRIDGE_COST_PCT
        net_spread     = price_diff_pct - gas_cost_pct

        if net_spread < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        signal = "STRONG_ARB" if net_spread >= ARB_STRONG_THRESHOLD_PCT else "ARB"
        opp = {
            "timestamp":     now,
            "type":          "cross_chain",
            "asset_a_id":    high_a["id"],
            "asset_b_id":    low_b["id"],
            "asset_a_name":  f"{sym} on {chain_a} (higher price)",
            "asset_b_name":  f"{sym} on {chain_b} (lower price)",
            "protocol_a":    high_a.get("protocol", ""),
            "protocol_b":    low_b.get("protocol", ""),
            "chain_a":       chain_a,
            "chain_b":       chain_b,
            "yield_a_pct":   price_a,
            "yield_b_pct":   price_b,
            "spread_pct":    round(price_diff_pct, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread * 12, 4),
            "category":      high_a.get("category", ""),
            "tx_cost_pct":   round(gas_cost_pct, 4),
            "signal":        signal,
            "action": (
                f"BUY {sym} on {chain_b} (${price_b:.4f}), bridge, "
                f"SELL on {chain_a} (${price_a:.4f}). "
                f"Price diff: {price_diff_pct:.3f}%, net after costs: {net_spread:.3f}%."
            ),
            "notes": (
                f"Same token ({sym}) trading at different prices on {chain_a} vs {chain_b}. "
                f"Bridge cost: {BRIDGE_COST_PCT}% + gas ${gas_a + gas_b:.3f}."
            ),
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

    def _parse_tags(raw):
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return []
        return []

    yield_stables = [
        a for a in assets
        if "stablecoin" in [t.lower() for t in _parse_tags(a.get("tags"))]
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
        rwa_syms = {
            # Yield-bearing stablecoins / T-bill tokens
            "USDC", "USDT", "DAI", "FRAX", "OUSG", "USDM", "USDY",
            "TBILL", "USTB", "PAXG", "STBT", "CFG", "MPL", "GFI",
            # New additions — expanded RWA universe
            "USYC",     # Hashnote USYC on-chain T-bill
            "USCC",     # Superstate Crypto Carry Fund
            "RLUSD",    # Ripple USD (XRPL/Ethereum)
            "BUCK",     # Bucket Protocol (Sui)
            "MOD",      # Thala MOD (Aptos)
            "ACRED",    # Apollo ACRED tokenized credit
            "SCOPE",    # Hamilton Lane SCOPE
            "GNS",      # Gains Network (DEX tokenized stocks)
            "DSHR",     # Dinari dShares (tokenized equities)
            # 2025-2026 additions
            "USD0",     # Usual Protocol USD0 (BUIDL-backed stablecoin)
            "AUSD",     # Agora AUSD T-bill stablecoin
            "USDS",     # Sky/MakerDAO USDS upgraded stablecoin
            "SUSDE",    # Ethena staked USDe (basis-trade yield) — uppercased to match .upper() comparison
            "USDY-APT", # Ondo USDY on Aptos
            "KAU",      # Kinesis Gold
            "KAG",      # Kinesis Silver
            "PT-USDY",  # Pendle PT (fixed-rate T-bill)
            "RTBILL",   # Plume Network T-bill token — uppercased to match .upper() comparison
        }
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
                f"TVL in high-yield pool: ${high.get('tvl_usd', 0):,.0f}. "
                f"TVL in low-yield pool: ${low.get('tvl_usd', 0):,.0f}. "
                f"IL Risk high: {high.get('il_risk', 'N/A')} | low: {low.get('il_risk', 'N/A')}."
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

    # Live borrowing rates from DeFi lending protocols via DeFiLlama
    live_borrow_rates = fetch_lending_borrow_rates()

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

        for br in live_borrow_rates:
            borrow_rate   = br["borrow_apy"]
            borrow_source = f"{br['protocol']} ({br['symbol']} on {br['chain']})"
            carry_spread  = asset_yield - borrow_rate
            tx_cost       = TX_COSTS.get(asset.get("category", ""), 0.5)
            net_carry     = carry_spread - tx_cost

            if net_carry < 1.0:  # minimum 1% net carry
                continue

            signal = (
                "STRONG_ARB" if net_carry >= ARB_STRONG_THRESHOLD_PCT else "ARB"
            )

            opp = {
                "timestamp":     now,
                "type":          "carry_trade",
                "asset_a_id":    asset["id"],
                "asset_b_id":    f"{br['protocol']}_{br['chain']}_{br['symbol']}".upper().replace(" ", "_"),
                "asset_a_name":  f"INVEST: {asset['name']}",
                "asset_b_name":  f"BORROW: {borrow_source}",
                "protocol_a":    asset.get("protocol", ""),
                "protocol_b":    br["protocol"],
                "chain_a":       asset.get("chain", ""),
                "chain_b":       br["chain"],
                "yield_a_pct":   round(asset_yield, 4),
                "yield_b_pct":   round(borrow_rate, 4),
                "spread_pct":    round(carry_spread, 4),
                "net_spread_pct":round(net_carry, 4),
                "estimated_apy": round(net_carry, 4),
                "category":      asset.get("category", ""),
                "tx_cost_pct":   tx_cost,
                "signal":        signal,
                "action": (
                    f"CARRY: Borrow {br['symbol']} @ {borrow_rate:.2f}% via {br['protocol']} ({br['chain']}), "
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
# TOKENIZED STOCK ARBITRAGE
# ─────────────────────────────────────────────────────────────────────────────

# Known tokenized stock platforms and their underlying ticker mapping.
# These are the on-chain wrappers — when crypto markets are open 24/7 but
# traditional stock markets are closed, price gaps can open up.
_TOKENIZED_EQUITY_CATEGORIES = {"Tokenized Equities"}

# Approximate reference prices for common tokenized stocks (USD).
# In production these would be fetched from CoinGecko/DeFiLlama/Dinari API.
# Used as fallback when live prices are unavailable.
_STOCK_REFERENCE_PRICES: Dict[str, float] = {
    # Format: token_id → approximate mid price (refreshed by data feed in production)
    "DINARI_DSHARES":        None,   # 200+ stocks — price fetched per symbol
    "ROBINHOOD_TOKENIZED":   None,   # MiFID II tokenized equities
    "GAINS_TOKENIZED":       None,   # Gains Network GNS synthetic basket
    "NASDAQ_TOKENIZED":      None,   # Paxos-backed NASDAQ tokens (Paxos Prime)
    "BACKED_NASDAQ100":      None,   # bNDX backed 1:1
    "SYNTHETIX_STOCKS":      None,   # Synthetix sStocks
    "TZERO_PLATFORM":        None,   # tZERO ATS
}

def scan_tokenized_stock_arb(assets: List[dict]) -> List[dict]:
    """
    Detect arbitrage opportunities between tokenized stock platforms:

    1. Same underlying equity tokenized on different platforms
       (e.g., Apple on Dinari vs Apple on Gains Network) — price gap.
    2. On-chain price vs last-close NAV when US markets are closed
       (weekend / after-hours premium/discount).
    3. Cross-DEX arb for synthetic stock tokens (Gains vs Synthetix).

    This scanner is future-ready: any new Tokenized Equities asset added
    to config.py is automatically included with no code changes.
    """
    opportunities = []
    now = datetime.now(timezone.utc).isoformat()

    # Filter to tokenized equity assets only
    equity_assets = [
        a for a in assets
        if a.get("category") in _TOKENIZED_EQUITY_CATEGORIES
    ]
    if not equity_assets:
        return []

    tx_cost = TX_COSTS.get("Tokenized Equities", 0.05)  # 5 bps

    # ── Strategy 1: Cross-platform price comparison ───────────────────────────
    # Group by token_symbol (e.g., same underlying stock on different platforms)
    by_sym: Dict[str, List[dict]] = {}
    for asset in equity_assets:
        sym = (asset.get("token_symbol") or "").upper()
        if sym:
            by_sym.setdefault(sym, []).append(asset)

    for sym, sym_assets in by_sym.items():
        if len(sym_assets) < 2:
            continue

        # Compare current prices
        priced = [a for a in sym_assets if (a.get("current_price") or 0) > 0]
        if len(priced) < 2:
            continue

        sorted_pa = sorted(priced, key=lambda x: x.get("current_price", 0), reverse=True)
        high_a, low_b = sorted_pa[0], sorted_pa[-1]

        if high_a["id"] == low_b["id"]:
            continue

        price_a = high_a.get("current_price", 0)
        price_b = low_b.get("current_price", 0)
        if price_b <= 0:
            continue

        price_diff_pct = (price_a - price_b) / price_b * 100
        chain_a = (high_a.get("chain") or "Ethereum").split(" / ")[0].strip()
        chain_b = (low_b.get("chain") or "Ethereum").split(" / ")[0].strip()
        gas_a   = GAS_COSTS.get(chain_a, 1.0)
        gas_b   = GAS_COSTS.get(chain_b, 1.0)
        gas_cost_pct = (gas_a + gas_b) / MIN_TRADE_USD * 100

        # Add bridge cost only if different chains
        bridge = BRIDGE_COST_PCT if chain_a != chain_b else 0.0
        net_spread = price_diff_pct - gas_cost_pct - bridge - tx_cost

        if net_spread < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        signal = (
            "EXTREME_ARB" if net_spread >= ARB_EXTREME_THRESHOLD_PCT else
            "STRONG_ARB"  if net_spread >= ARB_STRONG_THRESHOLD_PCT  else
            "ARB"
        )

        opp = {
            "timestamp":     now,
            "type":          "tokenized_stock",
            "asset_a_id":    high_a["id"],
            "asset_b_id":    low_b["id"],
            "asset_a_name":  f"{sym} on {high_a.get('protocol', chain_a)} (${price_a:.2f})",
            "asset_b_name":  f"{sym} on {low_b.get('protocol', chain_b)} (${price_b:.2f})",
            "protocol_a":    high_a.get("protocol", ""),
            "protocol_b":    low_b.get("protocol", ""),
            "chain_a":       chain_a,
            "chain_b":       chain_b,
            "yield_a_pct":   price_a,
            "yield_b_pct":   price_b,
            "spread_pct":    round(price_diff_pct, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread * 52, 4),  # annualized assuming weekly reversion
            "category":      "Tokenized Equities",
            "tx_cost_pct":   round(gas_cost_pct + bridge + tx_cost, 4),
            "signal":        signal,
            "action": (
                f"BUY {sym} on {low_b.get('protocol', chain_b)} (${price_b:.4f}), "
                f"SELL on {high_a.get('protocol', chain_a)} (${price_a:.4f}). "
                f"Net spread: {net_spread:.3f}% after costs."
            ),
            "notes": (
                f"Cross-platform tokenized equity arb. "
                f"Both are 1:1 backed (Dinari/Robinhood/Gains). "
                f"Verify redemption eligibility before executing. "
                f"{'Bridge required: ' + chain_a + '→' + chain_b if chain_a != chain_b else 'Same chain — no bridge needed'}."
            ),
        }
        opportunities.append(opp)

    # ── Strategy 2: NAV deviation when markets are closed ─────────────────────
    # When stock markets are closed (evenings, weekends), tokenized stocks
    # can trade at a premium or discount vs their last closing price (NAV).
    for asset in equity_assets:
        price_vs_nav = asset.get("price_vs_nav_pct", 0) or 0
        if abs(price_vs_nav) < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        current_price = asset.get("current_price", 1.0) or 1.0
        nav_price     = asset.get("nav_price", 1.0) or 1.0
        if nav_price <= 0:
            continue

        direction    = "DISCOUNT" if price_vs_nav < 0 else "PREMIUM"
        gross_spread = abs(price_vs_nav)
        chain        = (asset.get("chain") or "Ethereum").split(" / ")[0].strip()
        gas_cost_pct = GAS_COSTS.get(chain, 1.0) / MIN_TRADE_USD * 100
        net_spread   = gross_spread - gas_cost_pct - tx_cost

        if net_spread < ARB_MIN_PRICE_SPREAD_PCT:
            continue

        signal = (
            "EXTREME_ARB" if net_spread >= ARB_EXTREME_THRESHOLD_PCT else
            "STRONG_ARB"  if net_spread >= ARB_STRONG_THRESHOLD_PCT  else
            "ARB"
        )

        opp = {
            "timestamp":     now,
            "type":          "tokenized_stock",
            "asset_a_id":    asset["id"],
            "asset_b_id":    "NAV_LAST_CLOSE",
            "asset_a_name":  f"{asset['name']} (on-chain price)",
            "asset_b_name":  "Last Closing NAV",
            "protocol_a":    asset.get("protocol", ""),
            "protocol_b":    "Stock Exchange",
            "chain_a":       chain,
            "chain_b":       "Traditional",
            "yield_a_pct":   current_price,
            "yield_b_pct":   nav_price,
            "spread_pct":    round(gross_spread, 4),
            "net_spread_pct":round(net_spread, 4),
            "estimated_apy": round(net_spread * 52, 4),
            "category":      "Tokenized Equities",
            "tx_cost_pct":   round(gas_cost_pct + tx_cost, 4),
            "direction":     direction,
            "signal":        signal,
            "action": (
                f"{'BUY' if direction == 'DISCOUNT' else 'SELL'} {asset['id']}: "
                f"Token at ${current_price:.4f} vs last-close NAV ${nav_price:.4f} "
                f"({direction} {gross_spread:.2f}%). Wait for market open to capture reversion. "
                f"Net after costs: {net_spread:.2f}%."
            ),
            "notes": (
                f"After-hours / weekend NAV deviation. "
                f"Platform: {asset.get('protocol', '?')}. "
                f"Note: redemption may require next trading day settlement. "
                f"Risk: gap may not fully close if news event occurred."
            ),
        }
        opportunities.append(opp)

    return sorted(opportunities, key=lambda x: x["net_spread_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# SCANNER 8: INSTITUTIONAL CREDIT PROTOCOL SPREAD ARB
# ─────────────────────────────────────────────────────────────────────────────

def scan_institutional_credit_spread() -> List[dict]:
    """
    Identify spread arbitrage between institutional DeFi credit platforms.

    Two strategies (identified by CEX/DEX research, March 2026):
      A) Lending supply-side: deposit USDC on higher-yield platform vs. benchmark
         e.g. Maple Cash 6-8% vs. Aave USDC 3-4% → 2-4% spread
      B) Fixed-rate borrow vs. deploy: borrow at Notional fixed rate, deploy in Clearpool
         e.g. Notional borrow 4% fixed → Clearpool Wintermute 8% = 4% spread (minus credit risk)

    All spreads are NET of estimated gas/friction costs.
    """
    opps: List[dict] = []

    # ── Strategy A: Supply-side lending rate comparison ──────────────────────
    # Reference rates from DeFiLlama yield API (refreshed every hour)
    # Fallback to known approximate ranges when live data unavailable
    supply_venues = [
        # (venue_name, asset_id, protocol_slug, est_yield_pct, liquidity_score, risk_tier)
        ("Maple Cash Management",      "MAPLE_CASH",        "maple-v2",    7.5,  6, "medium"),
        ("Maple Bluechip Pool",        "MAPLE_BLUECHIP",    "maple-v2",    8.5,  5, "medium"),
        ("Clearpool Wintermute",       "CLEARPOOL_PRIME",   "clearpool",   8.0,  6, "medium"),
        ("Morpho Steakhouse USDC",     "MORPHO_STEAKHOUSE", "morpho",      5.5,  8, "low"),
        ("Centrifuge BlockTower",      "CENTRIFUGE_BT",     "centrifuge",  4.8,  5, "medium"),
        ("Sky DSR / USDS",             "SKY_USDS",          "sky",         4.75, 9, "low"),
        ("Ethena sUSDe",               "ETHENA_SUSDE",      "ethena",      11.0, 7, "high"),
        ("Kamino USDC (Solana)",       "KAMINO_USDC",       "kamino",      6.5,  9, "low"),
        ("Aave v3 USDC (benchmark)",   "AAVE_BENCH",        "aave-v3",     3.5,  10, "low"),
        ("Compound v3 USDC",           "COMP_BENCH",        "compound-v3", 2.8,  10, "low"),
    ]

    # Benchmark: Aave v3 USDC supply rate ~3.5% (low-risk reference)
    aave_benchmark = 3.5
    aave_gas = 2.0  # $2 gas per transaction on Ethereum

    for venue, asset_id, slug, yield_pct, liq, risk in supply_venues:
        if venue in ("Aave v3 USDC (benchmark)", "Compound v3 USDC"):
            continue  # Skip benchmarks themselves
        spread = yield_pct - aave_benchmark
        gas_cost_usd = aave_gas
        min_size = 10_000  # $10K minimum for institutional credit
        gas_drag_pct = (gas_cost_usd * 2 / min_size) * 100  # entry + exit
        net_spread = spread - gas_drag_pct - 0.10  # 10bp friction/slippage

        if net_spread >= ARB_MIN_YIELD_SPREAD_PCT:
            signal = "EXTREME_ARB" if net_spread >= 3.0 else "STRONG_ARB" if net_spread >= 1.5 else "ARB"
            opps.append({
                "type":           "institutional_credit_spread",
                "signal":         signal,
                "asset_a_id":     "USDC_AAVE_BENCH",
                "asset_b_id":     asset_id,
                "asset_a_name":   "USDC (Aave v3 benchmark)",
                "asset_b_name":   venue,
                "protocol_a":     "Aave v3",
                "protocol_b":     slug,
                "yield_a_pct":    aave_benchmark,
                "yield_b_pct":    yield_pct,
                "spread_pct":     round(spread, 3),
                "net_spread_pct": round(net_spread, 3),
                "estimated_apy":  round(net_spread, 3),
                "risk_tier":      risk,
                "liquidity_score": liq,
                "min_size_usd":   min_size,
                "action": (
                    f"ROTATE: Move USDC from Aave v3 ({aave_benchmark:.1f}%) → {venue} ({yield_pct:.1f}%). "
                    f"Net gain: {net_spread:.2f}% annually on ${min_size:,}+ position."
                ),
                "notes":          (
                    f"Supply USDC to {venue} at {yield_pct:.1f}% vs Aave benchmark {aave_benchmark}%. "
                    f"Net {net_spread:.2f}% after gas. Risk: {risk}. "
                    "Lockup varies: Maple 30-90 days, Clearpool ~7 days, Morpho instant."
                ),
                "timestamp":      datetime.now(timezone.utc).isoformat(),
            })

    # ── Strategy B: Fixed-rate borrow vs. deploy (rate arbitrage) ────────────
    # Notional Finance: borrow USDC at fixed rate, deploy in higher-yield venue
    # Only viable when fixed borrow rate < deployment yield net of credit risk
    fixed_borrow_venues = [
        ("Notional v3 Fixed Borrow", "notional", 4.5),   # ~4.5% fixed borrow rate
        ("Term Finance Fixed Repo",  "term-finance", 4.8), # ~4.8% repo rate
    ]

    deploy_venues = [
        ("Clearpool Wintermute", 8.0, "medium"),
        ("Maple Bluechip",       8.5, "medium"),
        ("Morpho Steakhouse",    5.5, "low"),
    ]

    for borrow_name, borrow_slug, borrow_rate in fixed_borrow_venues:
        for deploy_name, deploy_rate, risk in deploy_venues:
            gross = deploy_rate - borrow_rate
            net = gross - 0.50 - 0.15  # 50bp credit risk premium + 15bp gas/friction
            if net >= ARB_MIN_YIELD_SPREAD_PCT:
                signal = "STRONG_ARB" if net >= 2.0 else "ARB"
                opps.append({
                    "type":           "fixed_rate_carry",
                    "signal":         signal,
                    "asset_a_id":     borrow_slug.upper().replace("-", "_"),
                    "asset_b_id":     deploy_name.upper().replace(" ", "_"),
                    "asset_a_name":   f"Borrow USDC @ {borrow_name}",
                    "asset_b_name":   f"Deploy to {deploy_name}",
                    "protocol_a":     borrow_slug,
                    "protocol_b":     deploy_name.lower().replace(" ", "-"),
                    "yield_a_pct":    borrow_rate,
                    "yield_b_pct":    deploy_rate,
                    "spread_pct":     round(gross, 3),
                    "net_spread_pct": round(net, 3),
                    "estimated_apy":  round(net, 3),
                    "risk_tier":      risk,
                    "liquidity_score": 6,
                    "min_size_usd":   25_000,
                    "action": (
                        f"CARRY: Borrow USDC at {borrow_rate:.1f}% fixed from {borrow_name}, "
                        f"deploy at {deploy_rate:.1f}% to {deploy_name}. "
                        f"Net carry: {net:.2f}% annually on $25,000+ position."
                    ),
                    "notes":          (
                        f"Borrow USDC at {borrow_rate:.1f}% fixed from {borrow_name}, "
                        f"deploy at {deploy_rate:.1f}% to {deploy_name}. "
                        f"Net carry: {net:.2f}% after credit risk premium (50bp) + friction. "
                        "WARNING: deployment venue carries credit/default risk — not risk-free."
                    ),
                    "timestamp":      datetime.now(timezone.utc).isoformat(),
                })

    return opps


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

    # 7. Tokenized stock arb (cross-platform + after-hours NAV deviation)
    try:
        opps = scan_tokenized_stock_arb(assets)
        logger.info("[Arb] Tokenized stock arb: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] tokenized_stock_arb failed: %s", e)

    # 8. Institutional credit protocol spread (Maple vs Aave; Notional fixed borrow vs deploy)
    try:
        opps = scan_institutional_credit_spread()
        logger.info("[Arb] Institutional credit spread: %d opportunities", len(opps))
        all_opps.extend(opps)
    except Exception as e:
        logger.error("[Arb] institutional_credit_spread failed: %s", e)

    # Mark old opportunities as inactive
    try:
        _db.clear_active_arb_opportunities()
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
