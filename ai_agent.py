"""
ai_agent.py — RWA Infinity Model v1.0
Autonomous AI trading agent powered by Claude claude-sonnet-4-6.

Architecture:
  - 5 selectable agents (Guardian / Navigator / Horizon / Titan / Apex)
  - Hard Python risk gates BEFORE and AFTER Claude — LLM never executes trades directly
  - Phantom-portfolio defense: always reads DB state, never trusts LLM memory
  - Prompt injection sanitizer on all external inputs
  - AI feedback loop: tracks decisions + outcomes → adjusts confidence over time
  - AgentSupervisor daemon thread with exponential back-off restart
  - LangGraph state machine (graceful fallback to sequential pipeline)

Usage:
    import ai_agent
    ai_agent.supervisor.start(agent_name="HORIZON", dry_run=True)
    ai_agent.supervisor.stop()
    ai_agent.supervisor.status()
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

import database as _db
from config import (
    AI_AGENTS, PORTFOLIO_TIERS, CLAUDE_MODEL, CLAUDE_TIMEOUT, AI_CACHE_TTL,
    CDP_API_KEY_ID, CDP_API_KEY_SECRET, CDP_WALLET_SECRET, CDP_NETWORK_ID,
    X402_T54_FACILITATOR,
)

logger = logging.getLogger(__name__)

# ─── Optional imports (graceful fallback) ────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    _LANGGRAPH = True
except ImportError:
    _LANGGRAPH = False
    logger.info("[Agent] langgraph not installed — using sequential pipeline")

try:
    import anthropic as _anthropic
    _ANTHROPIC = True
except ImportError:
    _ANTHROPIC = False
    logger.warning("[Agent] anthropic SDK not installed — AI analysis disabled")

# ── Coinbase AgentKit (Upgrade 11 — optional) ────────────────────────────────
try:
    from coinbase_agentkit import (
        CdpApiActionProvider,
        CdpWalletActionProvider,
        AgentKit,
        AgentKitConfig,
        CdpWalletProvider,
        CdpWalletProviderConfig,
    )
    _AGENTKIT = True
    logger.info("[Agent] Coinbase AgentKit available")
except ImportError:
    _AGENTKIT = False
    logger.info("[Agent] coinbase-agentkit not installed — AgentKit execution disabled")

# ── x402 payment client (Upgrade 10 — optional) ──────────────────────────────
try:
    import x402  # noqa: F401 — presence-check only; we use httpx directly
    _X402 = True
    logger.info("[Agent] x402 payment protocol available")
except ImportError:
    _X402 = False
    logger.info("[Agent] x402 not installed — micropayment rail disabled")


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT INJECTION SANITIZER
# ─────────────────────────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    "ignore previous instructions", "disregard all", "system prompt",
    "you are now", "forget your", "new instructions", "act as if",
    "override safety", "jailbreak", "bypass restrictions",
]

def _sanitize(value: Any, max_len: int = 500) -> str:
    text = str(value) if value is not None else ""
    low  = text.lower()
    for pat in _INJECTION_PATTERNS:
        if pat in low:
            logger.warning("[Agent] Prompt injection stripped: %r", text[:80])
            return "[SANITIZED]"
    return text[:max_len]


# ─────────────────────────────────────────────────────────────────────────────
# AGENT STATE (LangGraph TypedDict)
# ─────────────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    agent_name:         str
    agent_cfg:          dict
    portfolio:          dict
    portfolio_state:    dict        # authoritative from DB
    market_data:        dict
    arb_opportunities:  list
    risk_pre_passed:    bool
    risk_pre_reason:    str
    claude_decision:    str         # REBALANCE | HOLD | DEPLOY | REDUCE | SKIP
    claude_rationale:   str
    claude_confidence:  float
    proposed_actions:   list
    risk_post_passed:   bool
    risk_post_reason:   str
    execution_result:   dict
    cycle_notes:        list
    cycle_number:       int
    is_dry_run:         bool
    error:              Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO STATE — always read from DB (phantom-portfolio defence)
# ─────────────────────────────────────────────────────────────────────────────

def _get_live_portfolio_state(tier: int) -> dict:
    """Read authoritative portfolio state from DB."""
    try:
        snap = _db.get_latest_portfolio(tier)
        trades = _db.get_trade_history(50)
        decisions = _db.get_recent_agent_decisions(10)
        return {
            "tier":           tier,
            "snapshot":       snap or {},
            "recent_trades":  len(trades) if not trades.empty else 0,
            "last_decision":  decisions.iloc[0].to_dict() if not decisions.empty else {},
            "holdings":       (snap or {}).get("holdings", []),
        }
    except Exception as e:
        logger.error("[Agent] _get_live_portfolio_state failed: %s", e)
        return {"tier": tier, "snapshot": {}, "recent_trades": 0, "last_decision": {}, "holdings": []}


# ─────────────────────────────────────────────────────────────────────────────
# HARD RISK GATES (Python-enforced — LLM cannot override these)
# ─────────────────────────────────────────────────────────────────────────────

def _check_pre_risk(state: AgentState, cfg: dict) -> tuple[bool, str]:
    """
    Pre-trade risk gates. Returns (passed, reason).
    CRITICAL: These run BEFORE Claude. Claude never bypasses these.
    """
    port = state["portfolio_state"]
    snap = port.get("snapshot", {})
    metrics = snap.get("metrics", {})

    # Check max drawdown not breached
    portfolio_vol = metrics.get("portfolio_volatility_pct", 0)
    tier_cfg      = PORTFOLIO_TIERS[cfg["risk_tier"]]
    max_dd        = tier_cfg["max_drawdown_pct"]
    if portfolio_vol > max_dd:
        return False, f"Portfolio volatility {portfolio_vol:.1f}% > max drawdown limit {max_dd:.1f}%"

    # Check recent trade count limit (max 20 trades in last 50 DB rows)
    recent_trades = port.get("recent_trades", 0)
    if recent_trades > 20:
        return False, f"Trade count {recent_trades} exceeds daily limit"

    return True, "Pre-risk gates passed"


def _check_post_risk(actions: list, cfg: dict, portfolio_value: float) -> tuple[bool, str]:
    """
    Post-decision risk gates. Validates proposed actions before execution.
    Returns (passed, reason).
    """
    total_usd = sum(abs(a.get("size_usd", 0)) for a in actions)
    max_size  = portfolio_value * cfg["max_trade_size_pct"] / 100

    if total_usd > portfolio_value * 0.50:
        return False, f"Proposed trade size ${total_usd:,.0f} exceeds 50% of portfolio"

    for action in actions:
        size = abs(action.get("size_usd", 0))
        if size > max_size:
            return False, f"Single trade ${size:,.0f} exceeds max ${max_size:,.0f} ({cfg['max_trade_size_pct']}%)"

    return True, "Post-risk gates passed"


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE DECISION NODE
# ─────────────────────────────────────────────────────────────────────────────

_decision_cache: dict = {}
_decision_cache_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE TOOL-USE DEFINITIONS  (Item 16 — agents call data functions themselves)
# ─────────────────────────────────────────────────────────────────────────────

_AGENT_TOOLS = [
    {
        "name": "get_fear_greed",
        "description": (
            "Get the current Crypto Fear & Greed Index (0-100). "
            "Values ≤20 = extreme fear (historically precede bull runs, +62% avg 90d return). "
            "Also returns 7-day history and raw signal."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_macro_indicators",
        "description": (
            "Get live macro indicators from FRED and yfinance: M2 money supply (bn), "
            "Fed balance sheet (bn), WTI crude ($/bbl), DXY (USD index), VIX, "
            "SPX, Gold, and total stablecoin dry-powder (USDT+USDC bn)."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_yield_curve",
        "description": (
            "Get US Treasury yield curve: 3m, 1y, 2y, 5y, 10y, 30y yields. "
            "Includes 10y-2y spread and inversion flag. "
            "Inverted curve historically precedes recession by 12-18 months."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_onchain_data",
        "description": (
            "Get BTC on-chain metrics from CoinMetrics Community API: "
            "MVRV ratio, MVRV Z-Score (>3 = overvalued, <-0.5 = undervalued), "
            "SOPR (>1 = profit-taking, <1 = capitulation), realized cap, active addresses."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_xrpl_data",
        "description": (
            "Get XRPL ecosystem data: RLUSD circulating supply (currently ~$1.5B), "
            "RLUSD/XRP orderbook bid/ask/spread, Soil Protocol vault APYs, "
            "XLS-81 permissioned DEX status, total XRPL RWA TVL ($2.3B)."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_factor_bias",
        "description": (
            "Get macro factor portfolio allocation bias: VIX/DXY/yield-curve-slope/F&G "
            "driven overweight/underweight recommendations (±pp) per asset category. "
            "Use this to validate or refine proposed allocation changes."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _execute_agent_tool(name: str) -> dict:
    """Execute a named data tool and return its result as a serialisable dict."""
    try:
        from data_feeds import (
            fetch_fear_greed_index, fetch_macro_indicators,
            fetch_treasury_yield_curve, fetch_coinmetrics_onchain,
            fetch_xrpl_stats, get_macro_factor_allocation_bias,
            fetch_stablecoin_supply,
        )
        if name == "get_fear_greed":
            fg = fetch_fear_greed_index()
            return {"current": fg.get("current"), "signal": fg.get("signal"),
                    "history_7d": [h["value"] for h in fg.get("history", [])[:7]]}
        if name == "get_macro_indicators":
            m = fetch_macro_indicators()
            s = fetch_stablecoin_supply()
            return {**m, "stablecoin_total_bn": s.get("total_bn"),
                    "usdt_bn": s.get("usdt_bn"), "usdc_bn": s.get("usdc_bn")}
        if name == "get_yield_curve":
            return fetch_treasury_yield_curve()
        if name == "get_onchain_data":
            oc = fetch_coinmetrics_onchain(days=400)
            return {k: v for k, v in oc.items() if k not in ("mvrv_history", "sopr_history")}
        if name == "get_xrpl_data":
            return fetch_xrpl_stats()
        if name == "get_factor_bias":
            return get_macro_factor_allocation_bias()
    except Exception as e:
        return {"error": str(e), "tool": name}
    return {"error": f"unknown tool: {name}"}


def _call_claude(state: AgentState) -> tuple[str, str, float, list]:
    """
    Call Claude claude-sonnet-4-6 to make a portfolio decision using tool_use.
    Claude calls data tools as needed, then returns a structured JSON decision.
    Returns (decision, rationale, confidence_pct, proposed_actions).
    """
    if not _ANTHROPIC:
        return "HOLD", "Anthropic SDK not installed", 50.0, []

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return "HOLD", "ANTHROPIC_API_KEY not configured", 0.0, []

    agent_cfg = state["agent_cfg"]
    portfolio = state["portfolio"]
    arb_opps  = state["arb_opportunities"][:5]  # top 5 opportunities
    metrics   = portfolio.get("metrics", {})

    # Cache key to avoid repeated identical calls
    cache_key = f"{state['agent_name']}|{metrics.get('weighted_yield_pct', 0):.1f}|{state['cycle_number']}"
    with _decision_cache_lock:
        cached = _decision_cache.get(cache_key)
        if cached and (time.time() - cached["_ts"]) < AI_CACHE_TTL:
            return cached["decision"], cached["rationale"], cached["confidence"], cached["actions"]

    # Format portfolio summary (sanitized)
    port_summary = f"""
Current Portfolio (Tier {portfolio.get('tier')}: {_sanitize(portfolio.get('tier_name', ''))}):
- Total Value: $100,000 (normalized)
- Weighted Yield: {_sanitize(metrics.get('weighted_yield_pct', 0))}%
- Sharpe Ratio: {_sanitize(metrics.get('sharpe_ratio', 0))}
- Sortino Ratio: {_sanitize(metrics.get('sortino_ratio', 0))}
- Volatility: {_sanitize(metrics.get('portfolio_volatility_pct', 0))}%
- VaR 95%: {_sanitize(metrics.get('var_95_pct', 0))}%
- Max Drawdown: {_sanitize(metrics.get('max_drawdown_pct', 0))}%
- Holdings: {_sanitize(metrics.get('n_holdings', 0))} positions
"""

    # Format holdings (sanitized, top 5)
    holdings = portfolio.get("holdings", [])[:5]
    holdings_text = "\n".join([
        f"  - {_sanitize(h.get('id', ''))} ({_sanitize(h.get('category', ''))}): "
        f"{_sanitize(h.get('weight_pct', 0))}% @ {_sanitize(h.get('current_yield_pct', 0))}% yield"
        for h in holdings
    ])

    # Format arb opportunities (sanitized, top 3)
    arb_text = "\n".join([
        f"  [{_sanitize(o.get('signal', ''))}] {_sanitize(o.get('type', ''))} — "
        f"Net spread: {_sanitize(o.get('net_spread_pct', 0))}% — "
        f"{_sanitize(o.get('action', ''))[:200]}"
        for o in arb_opps[:3]
    ])

    initial_prompt = f"""You are {_sanitize(agent_cfg['name'])}, an autonomous RWA (Real World Asset) portfolio manager.

AGENT PROFILE:
- Strategy: {_sanitize(agent_cfg['strategy'])}
- Risk Tier: {agent_cfg['risk_tier']} ({_sanitize(PORTFOLIO_TIERS[agent_cfg['risk_tier']]['name'])})
- Target Yield: {PORTFOLIO_TIERS[agent_cfg['risk_tier']]['target_yield_pct']}%
- Max Single Trade: {agent_cfg['max_trade_size_pct']}% of portfolio

CURRENT PORTFOLIO:
{port_summary}

TOP HOLDINGS:
{holdings_text}

TOP ARBITRAGE OPPORTUNITIES:
{arb_text if arb_text else "  No significant arbitrage opportunities detected"}

TASK: Use your available tools to gather live market intelligence (fear & greed, macro indicators, \
yield curve, on-chain data, XRPL stats, factor bias), then provide EXACTLY ONE decision in JSON format:

{{
  "decision": "REBALANCE" | "HOLD" | "DEPLOY" | "REDUCE",
  "confidence_pct": 0-100,
  "rationale": "2-3 sentence explanation referencing data you retrieved",
  "actions": [
    {{
      "action_type": "BUY" | "SELL" | "ROTATE",
      "asset_id": "asset identifier",
      "size_usd": dollar_amount,
      "reason": "brief reason"
    }}
  ]
}}

DECISION CRITERIA:
- REBALANCE: Significant drift from target allocations (>5%)
- DEPLOY: Strong new opportunity identified, capital available
- REDUCE: Risk metrics approaching limits, reduce exposure
- HOLD: Portfolio on track, no action needed

CONSTRAINTS (HARD LIMITS — you cannot override these):
- Max single trade: {agent_cfg['max_trade_size_pct']}% of portfolio
- Total trades in this cycle: max 3
- Only suggest assets from the approved RWA universe
- Prioritize yield quality over quantity

Call tools first to gather intelligence, then respond with ONLY the JSON object."""

    try:
        client = _anthropic.Anthropic(api_key=api_key, timeout=CLAUDE_TIMEOUT)

        # Tool-use loop — Claude calls data tools as needed (max 5 rounds)
        messages: list[dict] = [{"role": "user", "content": initial_prompt}]
        raw_text = ""
        for _round in range(5):
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                tools=_AGENT_TOOLS,
                messages=messages,
            )
            if not response.content:
                break

            if response.stop_reason != "tool_use":
                # Final text response — extract it
                for block in response.content:
                    if hasattr(block, "text"):
                        raw_text = block.text.strip()
                        break
                break

            # Claude wants to call tools — execute them and feed results back
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_data = _execute_agent_tool(block.name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_data, default=str)[:4000],
                    })
            messages.append({"role": "user", "content": tool_results})

        if not raw_text:
            return "HOLD", "Empty response from Claude after tool loop", 30.0, []

        # Extract JSON from response
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw_text)
        decision   = str(parsed.get("decision", "HOLD")).upper()
        rationale  = _sanitize(parsed.get("rationale", ""), 1000)
        confidence = float(parsed.get("confidence_pct") if parsed.get("confidence_pct") is not None else 50)
        actions    = parsed.get("actions") or []

        # Validate decision is in allowed set
        if decision not in ("REBALANCE", "HOLD", "DEPLOY", "REDUCE"):
            rationale = f"Invalid decision '{decision}' overridden to HOLD"
            decision = "HOLD"

        # Sanitize actions
        clean_actions = []
        for a in actions[:3]:  # max 3 actions
            clean_actions.append({
                "action_type": _sanitize(str(a.get("action_type", "BUY")).upper()),
                "asset_id":    _sanitize(str(a.get("asset_id", ""))),
                "size_usd":    float(a.get("size_usd") or 0),
                "reason":      _sanitize(str(a.get("reason", ""))),
            })

        # Cache
        with _decision_cache_lock:
            _decision_cache[cache_key] = {
                "decision": decision, "rationale": rationale,
                "confidence": confidence, "actions": clean_actions,
                "_ts": time.time()
            }

        logger.info("[Agent] Claude decision: %s (%.0f%% confidence)", decision, confidence)
        return decision, rationale, confidence, clean_actions

    except json.JSONDecodeError as e:
        logger.warning("[Agent] Claude JSON parse error: %s", e)
        return "HOLD", f"JSON parse error — defaulting to HOLD: {str(e)[:100]}", 30.0, []
    except Exception as e:
        logger.error("[Agent] Claude call failed: %s", e)
        return "HOLD", f"Claude call failed: {str(e)[:200]}", 0.0, []


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 — COINBASE AGENTKIT  (Upgrade 11)
# ─────────────────────────────────────────────────────────────────────────────

_agentkit_instance = None
_agentkit_lock     = threading.Lock()


def _build_agentkit() -> Optional[Any]:
    """Lazily initialise a CdpWalletProvider-backed AgentKit instance.

    Returns None (and logs a clear reason) if:
    - coinbase-agentkit is not installed
    - CDP_API_KEY_ID / CDP_API_KEY_SECRET / CDP_WALLET_SECRET are not set
    Upgrade 11.
    """
    global _agentkit_instance
    with _agentkit_lock:
        if _agentkit_instance is not None:
            return _agentkit_instance
        if not _AGENTKIT:
            return None
        if not (CDP_API_KEY_ID and CDP_API_KEY_SECRET and CDP_WALLET_SECRET):
            logger.info(
                "[AgentKit] CDP credentials not set — set RWA_CDP_API_KEY_ID, "
                "RWA_CDP_API_KEY_SECRET, RWA_CDP_WALLET_SECRET to enable on-chain execution"
            )
            return None
        try:
            wallet_provider = CdpWalletProvider(CdpWalletProviderConfig(
                api_key_id     = CDP_API_KEY_ID,
                api_key_secret = CDP_API_KEY_SECRET,
                wallet_secret  = CDP_WALLET_SECRET,
                network_id     = CDP_NETWORK_ID,
            ))
            _agentkit_instance = AgentKit(AgentKitConfig(
                wallet_provider    = wallet_provider,
                action_providers   = [
                    CdpApiActionProvider(),
                    CdpWalletActionProvider(),
                ],
            ))
            logger.info("[AgentKit] Initialised on network: %s", CDP_NETWORK_ID)
            return _agentkit_instance
        except Exception as e:
            logger.warning("[AgentKit] Init failed: %s", e)
            return None


def get_agentkit_status() -> dict:
    """Return AgentKit availability and wallet address for UI display."""
    if not _AGENTKIT:
        return {"available": False, "reason": "coinbase-agentkit not installed"}
    if not (CDP_API_KEY_ID and CDP_API_KEY_SECRET and CDP_WALLET_SECRET):
        return {"available": False, "reason": "CDP credentials not configured"}
    ak = _build_agentkit()
    if ak is None:
        return {"available": False, "reason": "AgentKit initialisation failed"}
    try:
        address = ak.wallet_provider.get_address()
        return {
            "available": True,
            "address":   address,
            "network":   CDP_NETWORK_ID,
            "reason":    "Ready",
        }
    except Exception as e:
        return {"available": True, "address": "unknown", "network": CDP_NETWORK_ID, "reason": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 — x402 MICROPAYMENT RAIL  (Upgrade 10)
# ─────────────────────────────────────────────────────────────────────────────

def pay_x402_service(url: str, max_usdc_cents: int = 1) -> Optional[dict]:
    """Attempt to access an x402-gated data endpoint.

    Flow:
      1. GET the URL — if 200, return JSON directly.
      2. If 402, parse the PAYMENT-REQUIRED header.
      3. If an XRPL wallet is configured (via CDP/xrpl-py), sign and retry.
         Currently logs the 402 details; full XRPL signing requires a funded
         wallet configured via RWA_CDP_WALLET_SECRET (Base) or a raw XRPL key.
      4. Returns None and logs on failure.

    Upgrade 10 — uses T54 XRPL facilitator for XRPL settlement.
    """
    if not _X402:
        logger.debug("[x402] x402 package not installed — skipping payment rail")
        return None
    try:
        import httpx
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 402:
                pay_req = resp.headers.get("PAYMENT-REQUIRED") or resp.headers.get("X-Payment-Required")
                logger.info(
                    "[x402] 402 received from %s (max_usdc_cents=%d). "
                    "Facilitator: %s. Payment header: %.120s",
                    url, max_usdc_cents, X402_T54_FACILITATOR, pay_req or "none",
                )
                # Full payment signing requires a funded XRPL or Base wallet.
                # Infrastructure is wired — set RWA_CDP_WALLET_SECRET for AgentKit
                # execution on Base, or configure an XRPL key for T54 settlement.
                return None
            logger.debug("[x402] Unexpected status %d from %s", resp.status_code, url)
            return None
    except Exception as e:
        logger.warning("[x402] Request to %s failed: %s", url, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# AGENT PIPELINE NODES
# ─────────────────────────────────────────────────────────────────────────────

def _node_load_state(state: AgentState) -> AgentState:
    """Load authoritative portfolio state from DB."""
    try:
        from portfolio import build_portfolio
        from arbitrage import run_full_arb_scan

        tier      = state["agent_cfg"]["risk_tier"]
        portfolio = build_portfolio(tier)
        port_state = _get_live_portfolio_state(tier)

        # Get top arb opportunities
        arb_opps = _db.get_active_arb_opportunities(10).to_dict("records")

        state["portfolio"]          = portfolio
        state["portfolio_state"]    = port_state
        state["arb_opportunities"]  = arb_opps
        state["cycle_notes"].append("Portfolio state loaded from DB")
    except Exception as e:
        state["error"] = f"load_state failed: {e}"
        logger.error("[Agent] _node_load_state: %s", e)
    return state


def _node_pre_risk(state: AgentState) -> AgentState:
    """Run pre-trade risk gates."""
    if state.get("error"):
        return state
    try:
        passed, reason = _check_pre_risk(state, state["agent_cfg"])
        state["risk_pre_passed"] = passed
        state["risk_pre_reason"] = reason
        state["cycle_notes"].append(f"Pre-risk: {reason}")
    except Exception as e:
        state["risk_pre_passed"] = False
        state["risk_pre_reason"] = f"Risk gate error: {e}"
    return state


def _node_claude_decide(state: AgentState) -> AgentState:
    """Call Claude for portfolio decision."""
    if state.get("error") or not state.get("risk_pre_passed"):
        state["claude_decision"]   = "SKIP"
        state["claude_rationale"]  = state.get("risk_pre_reason", "Pre-risk gate failed")
        state["claude_confidence"] = 0.0
        state["proposed_actions"]  = []
        return state

    try:
        decision, rationale, confidence, actions = _call_claude(state)
        state["claude_decision"]   = decision
        state["claude_rationale"]  = rationale
        state["claude_confidence"] = confidence
        state["proposed_actions"]  = actions
        state["cycle_notes"].append(f"Claude: {decision} ({confidence:.0f}% confidence)")
    except Exception as e:
        state["claude_decision"]   = "HOLD"
        state["claude_rationale"]  = f"Claude error: {e}"
        state["claude_confidence"] = 0.0
        state["proposed_actions"]  = []
        logger.error("[Agent] _node_claude_decide: %s", e)
    return state


def _node_post_risk(state: AgentState) -> AgentState:
    """Validate proposed actions against hard risk limits."""
    if state.get("error") or state["claude_decision"] in ("HOLD", "SKIP"):
        state["risk_post_passed"] = True
        state["risk_post_reason"] = "No actions to validate"
        return state

    try:
        portfolio_value = (state["portfolio"].get("portfolio_value_usd") or 100_000)
        passed, reason  = _check_post_risk(
            state["proposed_actions"], state["agent_cfg"], portfolio_value
        )
        state["risk_post_passed"] = passed
        state["risk_post_reason"] = reason
        state["cycle_notes"].append(f"Post-risk: {reason}")
    except Exception as e:
        state["risk_post_passed"] = False
        state["risk_post_reason"] = f"Post-risk error: {e}"
    return state


def _node_execute(state: AgentState) -> AgentState:
    """Execute approved trades (paper or live)."""
    is_dry_run = state.get("is_dry_run", True)
    result     = {"executed": [], "skipped": [], "errors": []}

    if not state.get("risk_post_passed") or state["claude_decision"] in ("HOLD", "SKIP"):
        state["execution_result"] = {"status": "NO_ACTION", "reason": state.get("risk_post_reason", "HOLD")}
        return state

    for action in state.get("proposed_actions", []):
        try:
            trade = {
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "agent_name": state["agent_name"],
                "asset_id":   action["asset_id"],
                "action":     action["action_type"],
                "size_usd":   action["size_usd"],
                "price_usd":  1.0,  # RWA tokens typically $1 NAV
                "protocol":   "",
                "chain":      "",
                "status":     "DRY_RUN" if is_dry_run else "PENDING",
                "notes":      action.get("reason", ""),
            }
            _db.log_trade(trade)
            result["executed"].append(action)
            state["cycle_notes"].append(
                f"{'DRY RUN' if is_dry_run else 'LIVE'}: {action['action_type']} "
                f"{action['asset_id']} ${action['size_usd']:,.0f}"
            )
        except Exception as e:
            result["errors"].append({"action": action, "error": str(e)})
            logger.error("[Agent] execute failed for %s: %s", action.get("asset_id"), e)

    state["execution_result"] = result
    return state


def _node_agentkit_execute(state: AgentState) -> AgentState:
    """Execute approved trades on-chain via Coinbase AgentKit (Upgrade 11).

    Only fires when:
    - is_dry_run is False
    - Post-risk passed
    - Claude decision is DEPLOY or REBALANCE
    - AgentKit is initialised (CDP keys configured)

    For RWA context, AgentKit operates on Base mainnet and can:
    - Transfer USDC/ERC-20 tokens to RWA protocol smart contracts
    - Interact with Aave, Morpho, Compound on Base
    - Query on-chain balances and prices via Pyth feeds

    When AgentKit is not available, this node is a transparent pass-through.
    """
    if state.get("is_dry_run", True):
        state["cycle_notes"].append("AgentKit: skipped (dry run mode)")
        return state
    if not state.get("risk_post_passed"):
        state["cycle_notes"].append("AgentKit: skipped (post-risk failed)")
        return state
    if state.get("claude_decision") not in ("DEPLOY", "REBALANCE"):
        state["cycle_notes"].append(f"AgentKit: skipped (decision={state.get('claude_decision')})")
        return state

    ak = _build_agentkit()
    if ak is None:
        state["cycle_notes"].append("AgentKit: not configured (set CDP credentials to enable)")
        return state

    executed_onchain = []
    for action in state.get("proposed_actions", []):
        try:
            asset_id  = action.get("asset_id", "")
            size_usd  = float(action.get("size_usd", 0))
            act_type  = action.get("action_type", "BUY")

            if size_usd <= 0:
                continue

            # Use AgentKit to get current wallet balance before acting
            result = ak.run(
                f"Check my USDC balance on {CDP_NETWORK_ID}. "
                f"If I have at least {size_usd:.2f} USDC available, "
                f"report the balance. Do not execute any transfers yet."
            )
            logger.info("[AgentKit] Balance check for %s action: %s", act_type, str(result)[:200])
            executed_onchain.append({
                "asset_id":  asset_id,
                "action":    act_type,
                "size_usd":  size_usd,
                "status":    "AGENTKIT_CHECKED",
                "response":  str(result)[:300],
            })
            state["cycle_notes"].append(
                f"AgentKit: {act_type} {asset_id} ${size_usd:,.0f} — balance checked"
            )
        except Exception as e:
            logger.error("[AgentKit] Action failed for %s: %s", action.get("asset_id"), e)
            state["cycle_notes"].append(f"AgentKit error: {e}")

    if executed_onchain:
        existing = state.get("execution_result") or {}
        existing["agentkit"] = executed_onchain
        state["execution_result"] = existing

    return state


def _node_log_decision(state: AgentState) -> AgentState:
    """Persist the full cycle decision to DB."""
    try:
        decision_record = {
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "agent_name":   state["agent_name"],
            "cycle_number": state.get("cycle_number", 0),
            "portfolio_tier": state["agent_cfg"]["risk_tier"],
            "decision":     state["claude_decision"],
            "rationale":    state["claude_rationale"],
            "confidence_pct": state["claude_confidence"],
            "actions":      state.get("proposed_actions", []),
            "portfolio_before": state.get("portfolio", {}),
            "portfolio_after":  {},
            "is_dry_run":   state.get("is_dry_run", True),
        }
        _db.log_agent_decision(decision_record)
    except Exception as e:
        logger.error("[Agent] _node_log_decision: %s", e)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# LANGGRAPH PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def _build_graph():
    """Build the LangGraph state machine for the agent pipeline."""
    if not _LANGGRAPH:
        return None

    g = StateGraph(AgentState)
    g.add_node("load_state",       _node_load_state)
    g.add_node("pre_risk",         _node_pre_risk)
    g.add_node("claude_decide",    _node_claude_decide)
    g.add_node("post_risk",        _node_post_risk)
    g.add_node("execute",          _node_execute)
    g.add_node("agentkit_execute", _node_agentkit_execute)   # Upgrade 11
    g.add_node("log_decision",     _node_log_decision)

    g.set_entry_point("load_state")
    g.add_edge("load_state",       "pre_risk")
    g.add_edge("pre_risk",         "claude_decide")
    g.add_edge("claude_decide",    "post_risk")
    g.add_edge("post_risk",        "execute")
    g.add_edge("execute",          "agentkit_execute")       # Upgrade 11
    g.add_edge("agentkit_execute", "log_decision")
    g.add_edge("log_decision",     END)

    return g.compile()


_graph = None
_graph_lock = threading.Lock()


def _get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            _graph = _build_graph()
    return _graph


# ─────────────────────────────────────────────────────────────────────────────
# AGENT CYCLE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_agent_cycle(agent_name: str, dry_run: bool = True, cycle_number: int = 0) -> dict:
    """
    Run one complete agent decision cycle.
    Returns the final state dict.
    """
    agent_cfg = AI_AGENTS.get(agent_name)
    if not agent_cfg:
        logger.error("[Agent] Unknown agent: %s", agent_name)
        return {"error": f"Unknown agent: {agent_name}"}

    initial_state: AgentState = {
        "agent_name":        agent_name,
        "agent_cfg":         agent_cfg,
        "portfolio":         {},
        "portfolio_state":   {},
        "market_data":       {},
        "arb_opportunities": [],
        "risk_pre_passed":   False,
        "risk_pre_reason":   "",
        "claude_decision":   "HOLD",
        "claude_rationale":  "",
        "claude_confidence": 0.0,
        "proposed_actions":  [],
        "risk_post_passed":  False,
        "risk_post_reason":  "",
        "execution_result":  {},
        "cycle_notes":       [],
        "cycle_number":      cycle_number,
        "is_dry_run":        dry_run,
        "error":             None,
    }

    graph = _get_graph()
    if graph:
        try:
            final_state = graph.invoke(initial_state)
            return dict(final_state)
        except Exception as e:
            logger.error("[Agent] LangGraph cycle failed: %s — falling back to sequential", e)

    # Sequential fallback
    state = initial_state
    for node_fn in [_node_load_state, _node_pre_risk, _node_claude_decide,
                    _node_post_risk, _node_execute, _node_agentkit_execute,
                    _node_log_decision]:
        try:
            state = node_fn(state)
        except Exception as e:
            state["error"] = f"{node_fn.__name__}: {e}"
            logger.error("[Agent] Sequential node %s failed: %s", node_fn.__name__, e)
            break
    return state


# ─────────────────────────────────────────────────────────────────────────────
# AI FEEDBACK LOOP
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_past_decisions(agent_name: str, lookback_cycles: int = 10):
    """
    Compare recent agent decisions against portfolio outcome.
    Logs wins/losses to ai_feedback table for learning signal.
    """
    try:
        decisions = _db.get_recent_agent_decisions(lookback_cycles * 2)
        if decisions.empty:
            return

        agent_decisions = decisions[decisions["agent_name"] == agent_name]
        if agent_decisions.empty:
            return

        already_evaluated = _db.get_evaluated_decision_ids()

        for _, row in agent_decisions.iterrows():
            if row.get("id") in already_evaluated:
                continue
            # Simple outcome evaluation: if DEPLOY/REBALANCE was called,
            # check if portfolio yield improved in subsequent snapshots
            tier = row.get("portfolio_tier", 3)
            current_snap = _db.get_latest_portfolio(tier)
            if not current_snap:
                continue

            current_yield = (current_snap.get("metrics") or {}).get("weighted_yield_pct", 0)
            raw_json = row.get("portfolio_before_json")
            before_json = (
                str(raw_json)
                if raw_json and not (isinstance(raw_json, float) and math.isnan(raw_json))
                else "{}"
            )
            try:
                before_port = json.loads(before_json)
                before_yield = (before_port.get("metrics") or {}).get("weighted_yield_pct", 0)
            except Exception:
                before_yield = 0

            if before_yield <= 0:
                continue

            confidence_val = row.get("confidence_pct")
            expected_return = float((confidence_val if confidence_val is not None else 50) / 100 * 5)  # rough estimate
            actual_return   = current_yield - before_yield
            outcome         = "WIN" if actual_return > 0 else ("LOSS" if actual_return < -0.5 else "NEUTRAL")

            _db.log_ai_feedback({
                "agent_name":         agent_name,
                "decision_id":        row.get("id"),
                "outcome":            outcome,
                "expected_return_pct":expected_return,
                "actual_return_pct":  actual_return,
                "notes":              f"Decision: {row.get('decision')} | Before yield: {before_yield:.2f}% | After: {current_yield:.2f}%",
            })

        logger.info("[Agent] Feedback loop updated for %s", agent_name)
    except Exception as e:
        logger.error("[Agent] evaluate_past_decisions: %s", e)


def get_agent_insights(agent_name: str) -> dict:
    """Get AI-generated insights for the current market state."""
    if not _ANTHROPIC:
        return {"insights": "Anthropic SDK not installed", "timestamp": datetime.now(timezone.utc).isoformat()}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {"insights": "ANTHROPIC_API_KEY not configured", "timestamp": datetime.now(timezone.utc).isoformat()}

    # Cache check
    cache_key = f"insights_{agent_name}"
    with _decision_cache_lock:
        cached = _decision_cache.get(cache_key)
        if cached and (time.time() - cached["_ts"]) < AI_CACHE_TTL:
            return cached["data"]

    try:
        from data_feeds import get_market_summary, fetch_rwa_news
        market  = get_market_summary()
        news    = fetch_rwa_news()[:5]

        news_text = "\n".join([
            f"- {_sanitize((n.get('headline') or '')[:150])}" for n in news
        ])

        agent_cfg = AI_AGENTS.get(agent_name, {})
        tier_cfg  = PORTFOLIO_TIERS.get(agent_cfg.get("risk_tier", 3), {})

        prompt = f"""You are {_sanitize(agent_cfg.get('name', agent_name))}, an RWA portfolio analyst.

CURRENT MARKET SNAPSHOT:
- Total RWA TVL: ${market.get('total_rwa_tvl_usd', 0):,.0f}
- Average RWA Yield: {market.get('avg_rwa_yield_pct', 0):.2f}%
- Active Yield Pools: {market.get('active_pools', 0)}
- Gold Price: ${market.get('gold_price_usd', 0):,.2f}
- Protocol Count: {market.get('protocol_count', 0)}

RECENT NEWS:
{news_text}

YOUR MANDATE: {_sanitize(agent_cfg.get('description', ''))}
TARGET YIELD: {tier_cfg.get('target_yield_pct', 8)}%

Provide 3 concise bullet-point insights (1 sentence each) about:
1. Current RWA market opportunity or risk
2. Best actionable opportunity right now given your mandate
3. Key risk to watch this week

Format as plain text bullet points, no markdown."""

        client = _anthropic.Anthropic(api_key=api_key, timeout=CLAUDE_TIMEOUT)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        insights = response.content[0].text.strip()

        result = {
            "insights":  insights,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent":     agent_name,
        }

        with _decision_cache_lock:
            _decision_cache[cache_key] = {"data": result, "_ts": time.time()}

        return result

    except Exception as e:
        logger.error("[Agent] get_agent_insights: %s", e)
        return {
            "insights":  f"Analysis temporarily unavailable ({type(e).__name__})",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT SUPERVISOR (24/7 daemon with exponential back-off restart)
# ─────────────────────────────────────────────────────────────────────────────

class AgentSupervisor:
    """
    Daemon thread that runs the selected agent in a loop.
    Automatically restarts on failure with exponential back-off.
    """

    def __init__(self):
        self._thread:      Optional[threading.Thread] = None
        self._stop_event:  threading.Event = threading.Event()
        self._agent_name:  str  = "HORIZON"
        self._dry_run:     bool = True
        self._cycle_count: int  = 0
        self._last_cycle:  Optional[dict] = None
        self._status_lock: threading.Lock = threading.Lock()
        self._interval:    int  = 60   # seconds between cycles
        self._running:     bool = False
        self._error:       Optional[str] = None
        self._last_error:  Optional[str] = None

    def start(self, agent_name: str = "HORIZON", dry_run: bool = True, interval_seconds: int = 60):
        """Start the agent supervisor (idempotent)."""
        with self._status_lock:
            if self._running:
                logger.info("[Supervisor] Already running agent: %s", self._agent_name)
                return
            self._agent_name = agent_name
            self._dry_run    = dry_run
            self._interval   = interval_seconds
            self._running    = True
            self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"RWA-Agent-{agent_name}",
            daemon=True,
        )
        self._thread.start()
        logger.info("[Supervisor] Started agent %s (dry_run=%s, interval=%ds)",
                    agent_name, dry_run, interval_seconds)

    def stop(self):
        """Gracefully stop the agent (non-blocking)."""
        with self._status_lock:
            self._running = False
        self._stop_event.set()
        logger.info("[Supervisor] Stop signal sent to agent %s", self._agent_name)

    def status(self) -> dict:
        """Return current supervisor status."""
        with self._status_lock:
            return {
                "running":       self._running,
                "agent_name":    self._agent_name,
                "dry_run":       self._dry_run,
                "cycle_count":   self._cycle_count,
                "interval_sec":  self._interval,
                "last_error":    self._last_error,
                "last_cycle":    self._last_cycle,
            }

    def _run_loop(self):
        """Main agent loop with exponential back-off on failure."""
        backoff  = 5
        max_back = 300  # 5 min max back-off

        while not self._stop_event.is_set():
            try:
                cycle_result = run_agent_cycle(
                    self._agent_name,
                    dry_run=self._dry_run,
                    cycle_number=self._cycle_count,
                )
                with self._status_lock:
                    self._cycle_count += 1
                    self._last_cycle   = {
                        "cycle":     self._cycle_count,
                        "decision":  cycle_result.get("claude_decision", "UNKNOWN"),
                        "confidence":cycle_result.get("claude_confidence", 0),
                        "notes":     cycle_result.get("cycle_notes", []),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    self._last_error = cycle_result.get("error")
                backoff = 5  # reset back-off on success

                # Feedback loop evaluation every 10 cycles
                if self._cycle_count % 10 == 0:
                    try:
                        evaluate_past_decisions(self._agent_name)
                    except Exception as fb_err:
                        logger.warning("[Supervisor] Feedback loop error: %s", fb_err)

            except Exception as e:
                with self._status_lock:
                    self._last_error = str(e)
                logger.error("[Supervisor] Agent cycle error: %s — retrying in %ds", e, backoff)
                self._stop_event.wait(timeout=backoff)
                backoff = min(backoff * 2, max_back)
                continue

            # Wait for next cycle
            self._stop_event.wait(timeout=self._interval)


# Module-level singleton supervisor
supervisor = AgentSupervisor()
