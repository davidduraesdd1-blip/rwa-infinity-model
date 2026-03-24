"""
alerts.py — RWA Infinity Model v1.0
Email, Telegram, Discord, and webhook notifications for portfolio and arb events.
Called by the scheduler after each scan completes.

Credentials are read from environment variables (config.py) as defaults,
and can be overridden via alerts_config.json for persistent settings.

NOTE: alerts_config.json may contain SMTP credentials — add it to .gitignore.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import smtplib
import ssl
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

ALERTS_CONFIG_FILE = Path(__file__).parent / "alerts_config.json"

# Alert signal levels that trigger notifications
_ALERT_LEVELS = {"ARB", "STRONG_ARB", "EXTREME_ARB"}
_HIGH_PRIORITY_LEVELS = {"STRONG_ARB", "EXTREME_ARB"}

# Calibration bounds
_MIN_YIELD_FLOOR   = 5.0    # never alert below 5% yield
_MIN_YIELD_CEILING = 50.0   # never auto-set above 50%
_SMOOTH_FACTOR     = 0.20   # 80/20 smoothing on calibration
_MIN_CALIBRATION_SAMPLES = 6


# ─── Input Validation ──────────────────────────────────────────────────────────

def _is_valid_email(addr: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr.strip()))


def _is_valid_telegram_token(token: str) -> bool:
    return bool(re.match(r"^\d+:[A-Za-z0-9_-]{35,}$", token.strip()))


# ─── Atomic Write ──────────────────────────────────────────────────────────────

def _atomic_json_write(path: Path, data: dict) -> bool:
    """Write JSON atomically: write to temp file then rename."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            suffix=".tmp", delete=False
        ) as tf:
            json.dump(data, tf, indent=2)
            tmp_path = tf.name
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.warning(f"Could not write {path}: {e}")
        return False


# ─── Config I/O ────────────────────────────────────────────────────────────────

def _env_defaults() -> dict:
    """Pull notification credentials from environment variables (config.py)."""
    from config import (
        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
        DISCORD_WEBHOOK_URL,
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL,
    )
    return {
        "email": {
            "enabled":     bool(SMTP_USER and SMTP_PASSWORD and ALERT_EMAIL),
            "address":     ALERT_EMAIL or "",
            "smtp_server": SMTP_HOST or "smtp.gmail.com",
            "smtp_port":   SMTP_PORT or 587,
            "username":    SMTP_USER or "",
            "password":    SMTP_PASSWORD or "",
        },
        "telegram": {
            "enabled":   bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
            "bot_token": TELEGRAM_BOT_TOKEN or "",
            "chat_id":   TELEGRAM_CHAT_ID or "",
        },
        "discord": {
            "enabled":     bool(DISCORD_WEBHOOK_URL),
            "webhook_url": DISCORD_WEBHOOK_URL or "",
        },
        "webhook": {
            "enabled": False,
            "url":     "",
            "secret":  "",
        },
        "thresholds": {
            "min_yield_alert":  10.0,   # alert when top asset yield >= this %
            "arb_alert":        True,   # alert on any STRONG_ARB / EXTREME_ARB
            "extreme_arb_only": False,  # if True, only alert on EXTREME_ARB
        },
    }


def load_alerts_config() -> dict:
    """
    Load alerts config from JSON file, falling back to env var defaults.
    JSON file values override env defaults for credentials that were
    manually set in the UI.
    """
    defaults = _env_defaults()
    if ALERTS_CONFIG_FILE.exists():
        try:
            with open(ALERTS_CONFIG_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            # Deep merge: saved values override defaults
            for section, vals in saved.items():
                if isinstance(vals, dict) and section in defaults:
                    defaults[section].update(vals)
                else:
                    defaults[section] = vals
        except Exception as e:
            logger.warning(f"Could not load alerts config: {e}")
    return defaults


def save_alerts_config(config: dict) -> None:
    """Persist alerts config atomically."""
    if _atomic_json_write(ALERTS_CONFIG_FILE, config):
        logger.info("Alerts config saved.")


# ─── Delivery Functions ────────────────────────────────────────────────────────

def send_email_alert(subject: str, body: str, config: dict) -> bool:
    """Send an email alert via SMTP/TLS. Returns True on success."""
    cfg = config.get("email", {})
    if not cfg.get("enabled") or not cfg.get("address"):
        return False
    if not _is_valid_email(cfg["address"]):
        logger.warning(f"Email alert skipped — invalid address: {cfg['address']!r}")
        return False
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart()
        msg["From"]    = cfg.get("username") or cfg["address"]
        msg["To"]      = cfg["address"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        tls_context = ssl.create_default_context()
        with smtplib.SMTP(
            cfg.get("smtp_server", "smtp.gmail.com"),
            int(cfg.get("smtp_port", 587)),
            timeout=30,
        ) as server:
            server.ehlo()
            server.starttls(context=tls_context)
            if cfg.get("username") and cfg.get("password"):
                server.login(cfg["username"], cfg["password"])
            server.sendmail(msg["From"], msg["To"], msg.as_string())
        logger.info(f"Email alert sent: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Email alert failed: {e}")
        return False


def send_telegram_alert(message: str, config: dict) -> bool:
    """Send a Telegram message via bot API. Returns True on success."""
    cfg = config.get("telegram", {})
    if not cfg.get("enabled") or not cfg.get("bot_token") or not cfg.get("chat_id"):
        return False
    if not _is_valid_telegram_token(cfg["bot_token"]):
        logger.warning("Telegram alert skipped — bot_token format invalid")
        return False
    try:
        url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
        r = requests.post(
            url,
            json={"chat_id": cfg["chat_id"], "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.ok:
            logger.info("Telegram alert sent.")
            return True
        logger.warning(f"Telegram alert failed: {r.status_code} — {r.text[:200]}")
        return False
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")
        return False


def send_discord_alert(message: str, config: dict) -> bool:
    """Send an alert to Discord via incoming webhook. Returns True on success."""
    cfg = config.get("discord", {})
    if not cfg.get("enabled") or not cfg.get("webhook_url"):
        return False
    url = cfg["webhook_url"].strip()
    if not url.startswith("https://discord.com/api/webhooks/"):
        logger.warning("Discord alert skipped — webhook URL format invalid.")
        return False
    try:
        payload = {"content": f"```\n{message[:1990]}\n```"}
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code in (200, 204):
            logger.info("Discord alert sent.")
            return True
        logger.warning(f"Discord alert failed: {r.status_code} — {r.text[:200]}")
        return False
    except Exception as e:
        logger.warning(f"Discord alert failed: {e}")
        return False


def send_webhook_alert(subject: str, message: str, config: dict) -> bool:
    """
    Send a signed JSON webhook (Zapier, Make, n8n, Slack, etc.).
    Signs with HMAC-SHA256 if a secret is configured.
    Returns True on success.
    """
    cfg = config.get("webhook", {})
    if not cfg.get("enabled") or not cfg.get("url"):
        return False
    url = cfg["url"].strip()
    if not url.startswith("https://"):
        logger.warning("Webhook alert skipped — URL must use HTTPS.")
        return False
    try:
        payload = {
            "source":    "rwa_infinity_model",
            "subject":   subject,
            "message":   message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        headers = {"Content-Type": "application/json"}
        body = json.dumps(payload, separators=(",", ":")).encode()
        secret = cfg.get("secret", "").strip()
        if secret:
            sig  = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-RWA-Signature"] = sig
        r = requests.post(url, data=body, headers=headers, timeout=10)
        if r.ok:
            logger.info("Webhook alert sent.")
            return True
        logger.warning(f"Webhook alert failed: {r.status_code} — {r.text[:200]}")
        return False
    except Exception as e:
        logger.warning(f"Webhook alert failed: {e}")
        return False


def _broadcast(subject: str, message: str, config: dict) -> None:
    """Send to all enabled channels."""
    send_email_alert(subject, message, config)
    send_telegram_alert(message, config)
    send_discord_alert(message, config)
    send_webhook_alert(subject, message, config)


# ─── Test Functions ────────────────────────────────────────────────────────────

def test_email(config: dict) -> tuple:
    ok = send_email_alert(
        "RWA Infinity Model — Test Alert",
        f"Test alert sent at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.\n"
        f"Email alerts are configured correctly.",
        config,
    )
    return (ok, "Test email sent!" if ok else "Email failed — check SMTP settings and logs.")


def test_telegram(config: dict) -> tuple:
    ok = send_telegram_alert(
        f"<b>RWA Infinity Model — Test Alert</b>\n"
        f"Sent at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.\n"
        f"Telegram alerts are working correctly.",
        config,
    )
    return (ok, "Test message sent!" if ok else "Telegram failed — check bot token and chat ID.")


def test_discord(config: dict) -> tuple:
    ok = send_discord_alert(
        f"RWA Infinity Model — Test Alert\n"
        f"Sent at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.\n"
        f"Discord alerts are working correctly.",
        config,
    )
    return (ok, "Test Discord message sent!" if ok else "Discord failed — check webhook URL.")


def test_webhook(config: dict) -> tuple:
    ok = send_webhook_alert(
        "RWA Infinity Model — Test Alert",
        f"Test sent at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Webhook is working.",
        config,
    )
    return (ok, "Test webhook sent!" if ok else "Webhook failed — check URL and logs.")


# ─── Main Alert Checker ────────────────────────────────────────────────────────

def check_and_send_alerts(
    arb_opportunities: list = None,
    portfolio_results: dict = None,
    ai_decisions: list = None,
) -> None:
    """
    Called by the scheduler after each scan.
    Checks arb opportunities, portfolio yields, and AI agent decisions
    against user thresholds and sends notifications on all enabled channels.

    Args:
        arb_opportunities: list of arb dicts from run_full_arb_scan()
        portfolio_results:  dict of tier -> portfolio from build_all_portfolios()
        ai_decisions:       list of recent agent decision dicts
    """
    config     = load_alerts_config()
    thresholds = config.get("thresholds", {})

    try:
        min_yield = float(thresholds.get("min_yield_alert", 10.0))
    except (TypeError, ValueError):
        min_yield = 10.0

    arb_alert       = thresholds.get("arb_alert", True)
    extreme_only    = thresholds.get("extreme_arb_only", False)
    ts              = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [f"RWA Infinity Model Scan — {ts}", ""]
    triggered = False

    # ── Arbitrage Alerts ──────────────────────────────────────────────────────
    if arb_alert and arb_opportunities:
        for opp in arb_opportunities:
            signal = opp.get("signal") or opp.get("signal_level", "")
            if extreme_only and signal != "EXTREME_ARB":
                continue
            if signal in _HIGH_PRIORITY_LEVELS:
                triggered = True
                net_yield = opp.get("net_spread_pct") or opp.get("net_profit_pct") or 0
                lines.append(
                    f"[{signal}] {opp.get('type') or opp.get('arb_type', 'ARB')} — "
                    f"{opp.get('asset_a_name') or opp.get('asset_a', '')} / "
                    f"{opp.get('asset_b_name') or opp.get('asset_b', '')}: "
                    f"+{net_yield:.2f}% net"
                )

    # ── Portfolio Yield Alerts ────────────────────────────────────────────────
    if portfolio_results:
        for tier, port in portfolio_results.items():
            if "error" in port:
                continue
            yield_pct = port.get("metrics", {}).get("weighted_yield_pct", 0)
            if yield_pct >= min_yield:
                triggered = True
                tier_name = port.get("tier_name", tier)
                lines.append(
                    f"[PORTFOLIO] {tier_name}: {yield_pct:.2f}% weighted yield "
                    f"(Sharpe {port.get('metrics', {}).get('sharpe_ratio', 0):.2f})"
                )

    # ── AI Agent Decision Alerts ──────────────────────────────────────────────
    if ai_decisions:
        for decision in ai_decisions[:3]:   # cap at 3 to keep alert concise
            action = decision.get("action", "")
            if action in ("BUY", "SELL", "REBALANCE"):
                triggered = True
                lines.append(
                    f"[AI AGENT] {decision.get('agent_name', 'Agent')} — "
                    f"{action}: {decision.get('asset', '')} "
                    f"(confidence {decision.get('confidence', 0):.0f}%)"
                )

    if not triggered:
        logger.debug("No alert thresholds met — skipping notifications.")
        return

    lines.append("\nView full details in your RWA Infinity dashboard.")
    message = "\n".join(lines)
    subject = "RWA Infinity Alert — Action Required"

    _broadcast(subject, message, config)


# ─── Smart Alert Calibration ──────────────────────────────────────────────────

def calibrate_alert_thresholds() -> dict:
    """
    Auto-calibrate the min_yield_alert threshold based on historical AI agent
    decision accuracy from the SQLite agent_decisions table.

    Strategy:
      - Collect all WIN decisions and their associated yield expectations.
      - Set min_yield_alert to the 75th percentile of those yields.
      - Apply 80/20 smoothing to avoid sudden jumps.
      - Save back to alerts_config.json.
    """
    import database as db

    conn = None
    try:
        conn = db._get_conn()
        rows = conn.execute(
            """
            SELECT outcome, notes FROM ai_feedback
            WHERE outcome IN ('WIN', 'NEUTRAL')
            AND notes IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 200
            """,
        ).fetchall()
    except Exception as e:
        logger.warning(f"Calibration DB read failed: {e}")
        return {"calibrated": False, "reason": str(e), "samples": 0}
    finally:
        if conn is not None:
            conn.close()

    # Extract yield expectations from notes JSON or numeric fields
    accurate_yields = []
    for row in rows:
        notes = row[1] or "{}"
        try:
            data = json.loads(notes) if isinstance(notes, str) else {}
            y = float(data.get("expected_yield_pct") or data.get("yield_pct") or 0)
            if y > 0:
                accurate_yields.append(y)
        except (TypeError, ValueError):
            pass

    if len(accurate_yields) < _MIN_CALIBRATION_SAMPLES:
        return {
            "calibrated": False,
            "reason":     f"Need {_MIN_CALIBRATION_SAMPLES} samples, have {len(accurate_yields)}.",
            "samples":    len(accurate_yields),
            "new_threshold": None,
        }

    accurate_yields.sort()
    p75_idx   = int(0.75 * (len(accurate_yields) - 1))
    p75_yield = accurate_yields[p75_idx]
    p75_yield = max(_MIN_YIELD_FLOOR, min(_MIN_YIELD_CEILING, p75_yield))

    config     = load_alerts_config()
    thresholds = config.setdefault("thresholds", {})
    old_thresh = float(thresholds.get("min_yield_alert", 10.0))

    new_thresh = round(old_thresh * (1 - _SMOOTH_FACTOR) + p75_yield * _SMOOTH_FACTOR, 1)
    new_thresh = max(_MIN_YIELD_FLOOR, min(_MIN_YIELD_CEILING, new_thresh))

    thresholds["min_yield_alert"]        = new_thresh
    thresholds["_calibrated_at"]         = datetime.now(timezone.utc).isoformat()
    thresholds["_calibration_samples"]   = len(accurate_yields)
    thresholds["_raw_p75_yield"]         = round(p75_yield, 1)
    save_alerts_config(config)

    delta     = new_thresh - old_thresh
    direction = "raised" if delta > 0.5 else ("lowered" if delta < -0.5 else "unchanged")
    logger.info(
        f"Alert calibration: threshold {direction} {old_thresh:.1f}% → {new_thresh:.1f}% "
        f"(p75={p75_yield:.1f}%, n={len(accurate_yields)})"
    )
    return {
        "calibrated":    True,
        "old_threshold": old_thresh,
        "new_threshold": new_thresh,
        "p75_yield":     round(p75_yield, 1),
        "direction":     direction,
        "samples":       len(accurate_yields),
        "reason":        f"75th-percentile of {len(accurate_yields)} winning yields = {p75_yield:.1f}%",
    }


def get_calibration_report() -> dict:
    """Return latest calibration metadata for UI display."""
    config     = load_alerts_config()
    thresholds = config.get("thresholds", {})
    return {
        "min_yield_alert":       thresholds.get("min_yield_alert", 10.0),
        "calibrated_at":         thresholds.get("_calibrated_at"),
        "calibration_samples":   thresholds.get("_calibration_samples"),
        "raw_p75_yield":         thresholds.get("_raw_p75_yield"),
        "arb_alert":             thresholds.get("arb_alert", True),
        "extreme_arb_only":      thresholds.get("extreme_arb_only", False),
    }
