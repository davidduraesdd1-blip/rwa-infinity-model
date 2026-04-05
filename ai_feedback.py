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
_LOOKBACK_DAYS   = 30       # primary rolling accuracy window (30-day)
_LOOKBACK_7D     = 7        # G3: secondary short-window (7-day, matches DeFi Model)
_MIN_SAMPLES     = 3        # minimum records before grading activates
_EXP_HALF_LIFE   = 14.0    # exponential time-weight half-life in days
_RETURN_THRESHOLD = 0.5     # within 0.5% of expected return = "accurate"

# Per-agent confidence multipliers (adjusted by update_model_weights)
_agent_weights: dict = {}
_agent_weights_lock = __import__("threading").Lock()


# ─── Core Accuracy Computation ────────────────────────────────────────────────

def compute_accuracy(agent_name: str, window_days: int = None) -> dict:
    """
    Compute rolling accuracy metrics for a given AI agent.

    Args:
        agent_name:   agent identifier (e.g. "GUARDIAN")
        window_days:  lookback window in days (default: _LOOKBACK_DAYS=30).
                      Pass 7 for short-window comparison (G3 — matches DeFi Model dual-window).

    Returns:
        accuracy_pct:       % of decisions where actual return was positive
        avg_return_pct:     mean actual return over the window
        win_rate:           % of WIN outcomes
        directional_pct:    % where actual_return_pct > 0 (directional accuracy)
        sample_count:       number of evaluated decisions
        grade:              A / B / C / D / F
        health_score:       0–100 composite for UI display
        message:            human-readable status string
        window_days:        which window was used (added for G3 dual-window display)
    """
    days = window_days if window_days is not None else _LOOKBACK_DAYS
    conn = _db._get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
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
        "window_days":     days,   # G3: expose window for dual-window UI display
    }


# ─── G3: Dual-window accuracy summary (30-day vs 7-day) ──────────────────────

def get_dual_window_accuracy(agent_name: str) -> dict:
    """
    G3: Return both 30-day and 7-day accuracy metrics for an agent.
    Matches DeFi Model's dual-window evaluation pattern.

    Returns:
        acc_30d:  compute_accuracy result over 30-day window
        acc_7d:   compute_accuracy result over 7-day window
        trend:    'improving' if 7d win_rate > 30d win_rate by >5pp,
                  'declining' if 7d < 30d by >5pp, else 'stable' or 'building'
    """
    acc_30d = compute_accuracy(agent_name, window_days=30)
    acc_7d  = compute_accuracy(agent_name, window_days=7)

    wr_30 = acc_30d.get("win_rate")
    wr_7  = acc_7d.get("win_rate")

    if wr_30 is None or wr_7 is None:
        trend = "building"
    elif wr_7 > wr_30 + 5:
        trend = "improving"
    elif wr_7 < wr_30 - 5:
        trend = "declining"
    else:
        trend = "stable"

    return {"acc_30d": acc_30d, "acc_7d": acc_7d, "trend": trend}


def get_rolling_win_rate_history(agent_name: str, window_days: int = 30,
                                  rolling_window: int = 7) -> list:
    """
    F1: Return daily rolling win-rate history for the agent over the past
    *window_days* days, computed using a *rolling_window*-day rolling window.

    Returns list of dicts: [{date: str, win_rate: float, total: int}, ...]
    sorted by date ascending. Empty list if no data.
    """
    if window_days <= 0 or rolling_window <= 0:
        logger.debug("[ai_feedback] get_rolling_win_rate_history: invalid params "
                     "window_days=%d rolling_window=%d", window_days, rolling_window)
        return []

    conn = _db._get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days + rolling_window)).isoformat()
    try:
        rows = conn.execute(
            """
            SELECT DATE(timestamp) AS day, outcome
            FROM ai_feedback
            WHERE agent_name = ? AND timestamp >= ? AND outcome IS NOT NULL
            ORDER BY day ASC
            """,
            (agent_name, cutoff),
        ).fetchall()
    except Exception as e:
        logger.debug("[ai_feedback] rolling win rate query failed: %s", e)
        return []
    finally:
        conn.close()

    if not rows:
        return []

    import collections
    from datetime import date, timedelta as _td

    # Group outcomes by day
    daily: dict[str, list] = collections.defaultdict(list)
    for row in rows:
        daily[row[0]].append(str(row[1]).upper())

    # Build list of all days in range
    all_days = sorted(daily.keys())
    if not all_days:
        return []

    start_day = datetime.now(timezone.utc).date() - timedelta(days=window_days)
    results = []
    today = datetime.now(timezone.utc).date()
    d = start_day
    while d <= today:
        ds = d.isoformat()
        # Collect rolling_window days of data ending on d
        window_days_list = [
            (d - _td(days=i)).isoformat()
            for i in range(rolling_window)
        ]
        outcomes = []
        for wd in window_days_list:
            outcomes.extend(daily.get(wd, []))
        if outcomes:
            wins = sum(1 for o in outcomes if o == "WIN")
            results.append({
                "date": ds,
                "win_rate": round(wins / len(outcomes) * 100, 1),
                "total": len(outcomes),
            })
        d += _td(days=1)

    return results


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


# ─── Batch accuracy (UPGRADE 19) ──────────────────────────────────────────────

def compute_accuracy_all_agents(agent_names: list) -> dict:
    """
    Batch version of compute_accuracy() — runs a single DB query for all agents
    instead of N separate queries (UPGRADE 19).

    Returns {agent_name: compute_accuracy_result_dict}.
    Falls back to individual queries per agent on error.
    """
    conn = _db._get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).isoformat()
    try:
        rows = conn.execute(
            """
            SELECT agent_name, outcome, expected_return_pct, actual_return_pct, timestamp
            FROM ai_feedback
            WHERE timestamp >= ?
              AND outcome IS NOT NULL
            ORDER BY agent_name, timestamp DESC
            LIMIT 2500
            """,
            (cutoff,),
        ).fetchall()
    except Exception as e:
        logger.error("compute_accuracy_all_agents DB read failed: %s", e)
        # Fallback to individual per-agent queries
        return {name: compute_accuracy(name) for name in agent_names}
    finally:
        conn.close()

    # Group rows by agent_name
    from collections import defaultdict
    grouped: dict = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)

    now_ts = datetime.now(timezone.utc)
    results: dict = {}
    for agent_name in agent_names:
        agent_rows = grouped.get(agent_name, [])
        if len(agent_rows) < _MIN_SAMPLES:
            results[agent_name] = {
                "agent_name":      agent_name,
                "accuracy_pct":    None,
                "avg_return_pct":  None,
                "win_rate":        None,
                "directional_pct": None,
                "sample_count":    len(agent_rows),
                "grade":           "N/A",
                "health_score":    50,
                "message":         f"Building history ({len(agent_rows)}/{_MIN_SAMPLES} samples). Keep running scans.",
            }
            continue

        w_win = w_directional = w_accurate = w_total = 0.0
        weighted_returns: list = []
        for row in agent_rows:
            outcome  = row[1] or "NEUTRAL"
            expected = row[2] or 0.0
            actual   = row[3] or 0.0
            ts_str   = row[4] or now_ts.isoformat()
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
            results[agent_name] = _empty_result(agent_name)
            continue

        win_rate        = w_win        / w_total * 100
        directional_pct = w_directional / w_total * 100
        accuracy_pct    = w_accurate   / w_total * 100
        avg_return = (
            sum(r * w for r, w in weighted_returns) / w_total
            if weighted_returns else 0.0
        )
        if win_rate >= 70:   grade = "A"
        elif win_rate >= 55: grade = "B"
        elif win_rate >= 40: grade = "C"
        elif win_rate >= 25: grade = "D"
        else:                grade = "F"

        health_score = min(100, int(
            win_rate        * 0.50
            + directional_pct * 0.30
            + accuracy_pct    * 0.20
        ))
        results[agent_name] = {
            "agent_name":      agent_name,
            "accuracy_pct":    round(accuracy_pct, 1),
            "avg_return_pct":  round(avg_return, 2),
            "win_rate":        round(win_rate, 1),
            "directional_pct": round(directional_pct, 1),
            "sample_count":    len(agent_rows),
            "grade":           grade,
            "health_score":    health_score,
            "message":         _health_message(health_score, grade),
        }
    return results


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

    # UPGRADE 19: use single-query batch version instead of N per-agent queries
    per_agent = compute_accuracy_all_agents(list(AI_AGENTS))
    health_scores = []
    for agent_name in AI_AGENTS:
        acc = per_agent.get(agent_name, _empty_result(agent_name))
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
