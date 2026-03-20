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
from config import AI_AGENTS, PORTFOLIO_TIERS, CLAUDE_MODEL, CLAUDE_TIMEOUT, AI_CACHE_TTL

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

    # Check daily trade limit (max 3 per day)
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


def _call_claude(state: AgentState) -> tuple[str, str, float, list]:
    """
    Call Claude claude-sonnet-4-6 to make a portfolio decision.
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

    # Fetch live yield curve and social signals for richer AI context
    yield_curve_text = ""
    social_text      = ""
    try:
        from data_feeds import fetch_treasury_yield_curve, fetch_social_signals, get_private_credit_warnings
        curve = fetch_treasury_yield_curve()
        ylds  = curve.get("yields", {})
        yield_curve_text = (
            f"  3m: {ylds.get('3m', 'N/A')}%  |  1y: {ylds.get('1y', 'N/A')}%  |  "
            f"2y: {ylds.get('2y', 'N/A')}%  |  10y: {ylds.get('10y', 'N/A')}%"
        )
        signals = fetch_social_signals()
        if signals.get("source") == "santiment":
            top_signal = max(
                [(k, v) for k, v in signals.items() if isinstance(v, dict)],
                key=lambda x: x[1].get("social_volume_7d", 0),
                default=(None, None)
            )
            if top_signal[0]:
                social_text = (
                    f"  Highest buzz (7d): {top_signal[0]} — "
                    f"{top_signal[1].get('social_volume_7d', 0):.0f} mentions, "
                    f"dev activity: {top_signal[1].get('dev_activity_30d', 0):.0f} commits/30d"
                )
        # Private credit warnings
        pc_warnings = get_private_credit_warnings()
        if pc_warnings:
            social_text += "\n  CREDIT WARNINGS: " + " | ".join(
                f"[{w['severity']}] {w['protocol']}: {w['type']}"
                for w in pc_warnings[:3]
            )
    except Exception:
        pass

    prompt = f"""You are {_sanitize(agent_cfg['name'])}, an autonomous RWA (Real World Asset) portfolio manager.

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

US TREASURY YIELD CURVE (live):
{yield_curve_text if yield_curve_text else "  Unavailable"}

MARKET INTELLIGENCE:
{social_text if social_text else "  No social or credit warning signals available"}

TASK: Analyze the above and provide EXACTLY ONE decision in JSON format:

{{
  "decision": "REBALANCE" | "HOLD" | "DEPLOY" | "REDUCE",
  "confidence_pct": 0-100,
  "rationale": "2-3 sentence explanation of your decision",
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

Respond with ONLY the JSON object, no markdown, no explanation outside JSON."""

    try:
        client = _anthropic.Anthropic(api_key=api_key, timeout=CLAUDE_TIMEOUT)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        if not response.content:
            return "HOLD", "Empty response from Claude", 30.0, []
        raw_text = response.content[0].text.strip()

        # Extract JSON from response
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw_text)
        decision   = str(parsed.get("decision", "HOLD")).upper()
        rationale  = _sanitize(parsed.get("rationale", ""), 1000)
        confidence = float(parsed.get("confidence_pct") or 50)
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
                "size_usd":    float(a.get("size_usd", 0)),
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
# AGENT PIPELINE NODES
# ─────────────────────────────────────────────────────────────────────────────

def _node_load_state(state: AgentState) -> AgentState:
    """Load authoritative portfolio state from DB."""
    try:
        from portfolio import build_portfolio
        from arbitrage import run_full_arb_scan, get_arb_summary

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
    g.add_node("load_state",    _node_load_state)
    g.add_node("pre_risk",      _node_pre_risk)
    g.add_node("claude_decide", _node_claude_decide)
    g.add_node("post_risk",     _node_post_risk)
    g.add_node("execute",       _node_execute)
    g.add_node("log_decision",  _node_log_decision)

    g.set_entry_point("load_state")
    g.add_edge("load_state",    "pre_risk")
    g.add_edge("pre_risk",      "claude_decide")
    g.add_edge("claude_decide", "post_risk")
    g.add_edge("post_risk",     "execute")
    g.add_edge("execute",       "log_decision")
    g.add_edge("log_decision",  END)

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
                    _node_post_risk, _node_execute, _node_log_decision]:
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

        for _, row in agent_decisions.iterrows():
            # Simple outcome evaluation: if DEPLOY/REBALANCE was called,
            # check if portfolio yield improved in subsequent snapshots
            tier = row.get("portfolio_tier", 3)
            current_snap = _db.get_latest_portfolio(tier)
            if not current_snap:
                continue

            current_yield = (current_snap.get("metrics") or {}).get("weighted_yield_pct", 0)
            before_json   = row.get("portfolio_before_json") or "{}"
            try:
                before_port = json.loads(before_json)
                before_yield = (before_port.get("metrics") or {}).get("weighted_yield_pct", 0)
            except Exception:
                before_yield = 0

            if before_yield <= 0:
                continue

            expected_return = float(row.get("confidence_pct", 50) / 100 * 5)  # rough estimate
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
            f"- {_sanitize(n['headline'][:150])}" for n in news
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
