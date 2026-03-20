"""
scheduler.py — RWA Infinity Model v1.0
Background job scheduler using APScheduler.
Jobs:
  - Full data refresh every 60 minutes
  - Price-only refresh every 5 minutes
  - News refresh every 30 minutes
  - Arbitrage scan after each data refresh
  - AI feedback loop every 6 hours
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    _APScheduler = True
except ImportError:
    _APScheduler = False
    logger.warning("[Scheduler] apscheduler not installed — pip install apscheduler")

import database as _db
from config import REFRESH_INTERVAL_MINUTES, PRICE_INTERVAL_SECONDS, NEWS_INTERVAL_MINUTES

# ─── Module state ─────────────────────────────────────────────────────────────
_scheduler: Optional[object] = None
_scheduler_lock = threading.Lock()
_last_refresh:  Optional[str] = None
_refresh_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# JOB FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def job_full_refresh():
    """Full RWA data refresh — runs every hour."""
    global _last_refresh, _refresh_count
    logger.info("[Scheduler] Starting full data refresh...")
    try:
        _db.write_scan_status(True, progress=0, current_task="Full refresh started")
        from data_feeds import refresh_all_assets

        def progress_cb(pct, task):
            _db.write_scan_status(True, progress=pct, current_task=task)

        assets = refresh_all_assets(progress_callback=progress_cb)
        _last_refresh  = datetime.now(timezone.utc).isoformat()
        _refresh_count += 1

        # Trigger arb scan immediately after refresh
        job_arb_scan()

        _db.write_scan_status(False, timestamp=_last_refresh, progress=100,
                              current_task=f"Complete — {len(assets)} assets updated")
        logger.info("[Scheduler] Full refresh complete — %d assets", len(assets))
    except Exception as e:
        logger.error("[Scheduler] Full refresh failed: %s", e)
        _db.write_scan_status(False, error=str(e), progress=0, current_task="Error")


def job_price_refresh():
    """Price-only refresh — runs every 5 minutes."""
    try:
        from data_feeds import fetch_coingecko_prices
        prices = fetch_coingecko_prices()
        logger.debug("[Scheduler] Price refresh — %d tokens", len(prices))
    except Exception as e:
        logger.debug("[Scheduler] Price refresh failed: %s", e)


def job_news_refresh():
    """News refresh — runs every 30 minutes."""
    try:
        from data_feeds import refresh_news
        news = refresh_news()
        logger.info("[Scheduler] News refresh — %d items", len(news))
    except Exception as e:
        logger.warning("[Scheduler] News refresh failed: %s", e)


def job_arb_scan():
    """Arbitrage scan — runs after each full refresh."""
    try:
        from arbitrage import run_full_arb_scan
        opps = run_full_arb_scan()
        logger.info("[Scheduler] Arb scan — %d opportunities", len(opps))
    except Exception as e:
        logger.warning("[Scheduler] Arb scan failed: %s", e)


def job_ai_feedback():
    """AI feedback loop — runs every 6 hours."""
    try:
        from ai_agent import evaluate_past_decisions
        from config import AI_AGENTS
        for agent_name in AI_AGENTS:
            evaluate_past_decisions(agent_name)
        logger.info("[Scheduler] AI feedback loop complete")
    except Exception as e:
        logger.warning("[Scheduler] AI feedback failed: %s", e)


def job_portfolio_snapshot():
    """Save portfolio snapshots for all tiers — runs every hour."""
    try:
        from portfolio import build_all_portfolios
        portfolios = build_all_portfolios()
        for tier, port in portfolios.items():
            if "error" not in port:
                metrics = port.get("metrics", {})
                _db.save_portfolio_snapshot({
                    "tier":              tier,
                    "tier_name":         port.get("tier_name", ""),
                    "total_value_usd":   port.get("portfolio_value_usd", 0),
                    "expected_yield_pct":metrics.get("weighted_yield_pct", 0),
                    "sharpe_ratio":      metrics.get("sharpe_ratio", 0),
                    "sortino_ratio":     metrics.get("sortino_ratio", 0),
                    "max_drawdown_pct":  metrics.get("max_drawdown_pct", 0),
                    "var_95_pct":        metrics.get("var_95_pct", 0),
                    "cvar_95_pct":       metrics.get("cvar_95_pct", 0),
                    "volatility_pct":    metrics.get("portfolio_volatility_pct", 0),
                    "allocations":       port.get("category_summary", {}),
                    "holdings":          port.get("holdings", []),
                })
        logger.info("[Scheduler] Portfolio snapshots saved for %d tiers", len(portfolios))
    except Exception as e:
        logger.warning("[Scheduler] Portfolio snapshot failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def start():
    """Initialize and start the background scheduler."""
    global _scheduler

    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            logger.info("[Scheduler] Already running")
            return

        if not _APScheduler:
            logger.warning("[Scheduler] APScheduler not available — background jobs disabled")
            return

        _scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce":   True,    # merge missed runs into one
                "max_instances": 1,    # only 1 instance per job at a time
                "misfire_grace_time": 300,  # 5 min grace for misfires
            },
            timezone="UTC",
        )

        # Add jobs
        _scheduler.add_job(
            job_full_refresh, "interval",
            minutes=REFRESH_INTERVAL_MINUTES,
            id="full_refresh",
            name="Full RWA Data Refresh",
        )
        _scheduler.add_job(
            job_price_refresh, "interval",
            seconds=PRICE_INTERVAL_SECONDS,
            id="price_refresh",
            name="Price Refresh",
        )
        _scheduler.add_job(
            job_news_refresh, "interval",
            minutes=NEWS_INTERVAL_MINUTES,
            id="news_refresh",
            name="News Refresh",
        )
        _scheduler.add_job(
            job_portfolio_snapshot, "interval",
            minutes=REFRESH_INTERVAL_MINUTES,
            id="portfolio_snapshot",
            name="Portfolio Snapshot",
            start_date=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        _scheduler.add_job(
            job_ai_feedback, "interval",
            hours=6,
            id="ai_feedback",
            name="AI Feedback Loop",
        )

        # Error listener
        def _on_job_error(event):
            logger.error("[Scheduler] Job %s failed: %s", event.job_id, event.exception)

        _scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

        _scheduler.start()
        logger.info("[Scheduler] Started — full refresh every %d min", REFRESH_INTERVAL_MINUTES)

        # Run initial refresh immediately in background thread
        t = threading.Thread(target=job_full_refresh, name="InitialRefresh", daemon=True)
        t.start()


def stop():
    """Stop the scheduler gracefully."""
    global _scheduler
    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("[Scheduler] Stopped")


def trigger_refresh():
    """Manually trigger an immediate full refresh."""
    t = threading.Thread(target=job_full_refresh, name="ManualRefresh", daemon=True)
    t.start()
    return "Refresh triggered"


def get_status() -> dict:
    """Return scheduler status."""
    jobs = []
    if _scheduler and _APScheduler:
        for job in _scheduler.get_jobs():
            next_run = getattr(job, "next_run_time", None)
            jobs.append({
                "id":       job.id,
                "name":     job.name,
                "next_run": str(next_run) if next_run else "N/A",
            })

    scan_status = _db.read_scan_status()
    return {
        "running":       bool(_scheduler and _scheduler.running) if _APScheduler else False,
        "last_refresh":  _last_refresh,
        "refresh_count": _refresh_count,
        "jobs":          jobs,
        "scan_status":   scan_status,
    }
