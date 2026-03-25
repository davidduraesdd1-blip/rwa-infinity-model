"""
ai_feedback.py — RWA Infinity Model v1.0
Enhanced AI feedback loop: A-F grading, health score (0-100),
exponential time-weighting, directional accuracy, and model weight adjustment.

Reads from the ai_feedback SQLite table (populated by ai_agent.evaluate_past_decisions).
Provides a dashboard-ready summary for the AI tab in app.py.
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import database as _db

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
_LOOKBACK_DAYS   = 30       # rolling accuracy window
_MIN_SAMPLES     = 3        # minimum records before grading activates
_EXP_HALF_LIFE   = 14.0    # exponential time-weight half-life in days
_RETURN_THRESHOLD = 0.5     # within 0.5% of expected return = "accurate"

# Per-agent confidence multipliers (adjusted by update_model_weights)
_agent_weights: dict = {}
_agent_weights_lock = __import__("threading").Lock()


# ─── Core Accuracy Computation ────────────────────────────────────────────────

def compute_accuracy(agent_name: str) -> dict:
    """
    Compute rolling accuracy metrics for a given AI agent.

    Returns:
        accuracy_pct:       % of decisions where actual return was positive
        avg_return_pct:     mean actual return over the window
        win_rate:           % of WIN outcomes
        directional_pct:    % where actual_return_pct > 0 (directional accuracy)
        sample_count:       number of evaluated decisions
        grade:              A / B / C / D / F
        health_score:       0–100 composite for UI display
        message:            human-readable status string
    """
    conn = _db._get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).isoformat()
    try:
        rows = conn.execute(
            """
            SELECT outcome, expected_return_pct, actual_return_pct, timestamp
            FROM ai_feedback
            WHERE agent_name = ?
              AND timestamp  >= ?
            ORDER BY timestamp DESC
            LIMIT 500
            """,
            (agent_name, cutoff),
        ).fetchall()
    except Exception as e:
        logger.error("compute_accuracy DB read failed: %s", e)
        return _empty_result(agent_name)
    finally:
        conn.close()

    if len(rows) < _MIN_SAMPLES:
        return {
            "agent_name":      agent_name,
            "accuracy_pct":    None,
            "avg_return_pct":  None,
            "win_rate":        None,
            "directional_pct": None,
            "sample_count":    len(rows),
            "grade":           "N/A",
            "health_score":    50,
            "message":         f"Building history ({len(rows)}/{_MIN_SAMPLES} samples). Keep running scans.",
        }

    now_ts = datetime.now(timezone.utc)
    w_win        = 0.0
    w_directional = 0.0
    w_accurate   = 0.0
    w_total      = 0.0
    weighted_returns: list = []

    for row in rows:
        outcome     = row[0] or "NEUTRAL"
        expected    = row[1] or 0.0
        actual      = row[2] or 0.0
        ts_str      = row[3] or now_ts.isoformat()

        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now_ts - ts).total_seconds() / 86400)
        except Exception:
            age_days = 0.0

        weight = math.exp(-age_days / _EXP_HALF_LIFE)
        w_total += weight

        if outcome == "WIN":
            w_win += weight
        if actual > 0:
            w_directional += weight
        if expected != 0 and abs(actual - expected) / max(abs(expected), 0.01) < _RETURN_THRESHOLD:
            w_accurate += weight
        weighted_returns.append((actual, weight))

    if w_total == 0:
        return _empty_result(agent_name)

    win_rate        = w_win        / w_total * 100
    directional_pct = w_directional / w_total * 100
    accuracy_pct    = w_accurate   / w_total * 100

    # Weighted average return
    avg_return = (
        sum(r * w for r, w in weighted_returns) / w_total
        if weighted_returns else 0.0
    )

    # Grade (based on win_rate — most meaningful for agent decisions)
    if win_rate >= 70:
        grade = "A"
    elif win_rate >= 55:
        grade = "B"
    elif win_rate >= 40:
        grade = "C"
    elif win_rate >= 25:
        grade = "D"
    else:
        grade = "F"

    # Health score 0-100 composite
    health_score = min(100, int(
        win_rate        * 0.50
        + directional_pct * 0.30
        + accuracy_pct    * 0.20
    ))

    return {
        "agent_name":      agent_name,
        "accuracy_pct":    round(accuracy_pct, 1),
        "avg_return_pct":  round(avg_return, 2),
        "win_rate":        round(win_rate, 1),
        "directional_pct": round(directional_pct, 1),
        "sample_count":    len(rows),
        "grade":           grade,
        "health_score":    health_score,
        "message":         _health_message(health_score, grade),
    }


def _empty_result(agent_name: str) -> dict:
    return {
        "agent_name":      agent_name,
        "accuracy_pct":    None,
        "avg_return_pct":  None,
        "win_rate":        None,
        "directional_pct": None,
        "sample_count":    0,
        "grade":           "N/A",
        "health_score":    50,
        "message":         "No feedback data yet — start the agent to begin tracking.",
    }


def _health_message(score: int, grade: str) -> str:
    if score >= 80:
        return f"Agent is performing excellently (Grade {grade}). Decisions are highly reliable."
    elif score >= 60:
        return f"Agent is performing well (Grade {grade}). Most decisions are profitable."
    elif score >= 40:
        return f"Agent accuracy is fair (Grade {grade}). Markets have been volatile."
    else:
        return f"Agent needs more history to calibrate (Grade {grade}). Keep running cycles."


# ─── Full Dashboard ────────────────────────────────────────────────────────────

def get_feedback_dashboard() -> dict:
    """
    Single call for the Streamlit AI tab to get all feedback data across all agents.

    Returns:
        overall_health:    0-100 average across all active agents
        total_decisions:   total logged feedback records
        win_decisions:     total WIN outcomes
        per_agent:         {agent_name: compute_accuracy() result}
        model_weights:     {agent_name: confidence multiplier}
        trend:             'improving' | 'stable' | 'declining' | 'building'
        last_updated:      ISO timestamp
    """
    from config import AI_AGENTS

    # Per-agent accuracy
    per_agent = {}
    health_scores = []
    for agent_name in AI_AGENTS:
        acc = compute_accuracy(agent_name)
        per_agent[agent_name] = acc
        if acc["health_score"] is not None:
            health_scores.append(acc["health_score"])

    overall_health = int(sum(health_scores) / len(health_scores)) if health_scores else 50

    # Overall counts from DB
    conn = _db._get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) FROM ai_feedback"
        ).fetchone()
        total_decisions = row[0] or 0
        win_decisions   = int(row[1] or 0)
    except Exception:
        total_decisions = 0
        win_decisions   = 0
    finally:
        conn.close()

    # Load model weights
    with _agent_weights_lock:
        weights = dict(_agent_weights)

    return {
        "overall_health":   overall_health,
        "total_decisions":  total_decisions,
        "win_decisions":    win_decisions,
        "per_agent":        per_agent,
        "model_weights":    weights,
        "trend":            _compute_trend(),
        "last_updated":     datetime.now(timezone.utc).isoformat(),
    }


def _compute_trend() -> str:
    """Returns 'improving', 'stable', 'declining', or 'building' based on recent vs prior win rates."""
    conn = _db._get_conn()
    now_ts  = datetime.now(timezone.utc)
    recent_cut  = (now_ts - timedelta(days=7)).isoformat()
    previous_cut = (now_ts - timedelta(days=14)).isoformat()
    try:
        def _win_rate(after, before=None):
            q = "SELECT COUNT(*), SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) FROM ai_feedback WHERE timestamp >= ?"
            args = [after]
            if before:
                q += " AND timestamp < ?"
                args.append(before)
            r = conn.execute(q, args).fetchone()
            total = r[0] or 0
            wins  = r[1] or 0
            return wins / total if total >= 3 else None

        recent_wr   = _win_rate(recent_cut)
        previous_wr = _win_rate(previous_cut, recent_cut)

        if recent_wr is None or previous_wr is None:
            return "building"
        if recent_wr > previous_wr * 1.05:
            return "improving"
        elif recent_wr < previous_wr * 0.95:
            return "declining"
        return "stable"
    except Exception:
        return "building"
    finally:
        conn.close()


# ─── Model Weight Adjustment ──────────────────────────────────────────────────

def update_model_weights() -> dict:
    """
    Adjust per-agent confidence multipliers based on recent win rates.
    Higher win rate → higher weight (used by ai_agent to scale confidence).
    Returns updated weights dict.
    """
    from config import AI_AGENTS

    with _agent_weights_lock:
        for agent_name in AI_AGENTS:
            acc = compute_accuracy(agent_name)
            if acc["win_rate"] is not None:
                # Normalise: 50% win_rate → 0.70, 70% → 1.0, 90% → 1.20
                new_weight = 0.20 + (acc["win_rate"] / 100) * 1.0
                old_weight = _agent_weights.get(agent_name, 1.0)
                # 80/20 smoothing
                _agent_weights[agent_name] = round(0.80 * old_weight + 0.20 * new_weight, 4)
            else:
                _agent_weights.setdefault(agent_name, 1.0)

        weights = dict(_agent_weights)

    logger.info("[AI Feedback] Model weights updated: %s", weights)
    return weights


def get_agent_weight(agent_name: str) -> float:
    """Return the current confidence multiplier for an agent (default 1.0)."""
    with _agent_weights_lock:
        return _agent_weights.get(agent_name, 1.0)


# ─── Win Rate Export for Kelly Criterion ──────────────────────────────────────

def get_agent_win_rates() -> dict:
    """
    Return empirical win rates as decimals {agent_name: win_rate_decimal}.
    Used by portfolio.py to set data-driven Kelly win probabilities.
    Returns {} if insufficient data.
    """
    from config import AI_AGENTS
    rates = {}
    for agent_name in AI_AGENTS:
        acc = compute_accuracy(agent_name)
        if acc["win_rate"] is not None:
            rates[agent_name] = round(acc["win_rate"] / 100, 4)
    return rates
