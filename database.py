"""
database.py — RWA Infinity Model v1.0
SQLite backend with WAL mode, thread-local connection pooling, and full schema.
"""

import sqlite3
import threading
import json
import os
import logging
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from config import DB_FILE

_write_lock = threading.Lock()
_thread_local = threading.local()


# ─── Connection Pool ───────────────────────────────────────────────────────────

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    return conn


class _PooledConn:
    """Proxy — close() rolls back instead of destroying the pooled connection."""
    def __init__(self, conn: sqlite3.Connection):
        self.__dict__["_c"] = conn

    def close(self):
        try:
            self.__dict__["_c"].execute("PRAGMA optimize")
            self.__dict__["_c"].rollback()
        except Exception:
            pass

    def __enter__(self):      return self.__dict__["_c"].__enter__()
    def __exit__(self, *a):   return self.__dict__["_c"].__exit__(*a)
    def __getattr__(self, n): return getattr(self.__dict__["_c"], n)
    def __setattr__(self, n, v): setattr(self.__dict__["_c"], n, v)


def _get_conn() -> _PooledConn:
    w = getattr(_thread_local, "conn", None)
    if w is None:
        w = _PooledConn(_make_conn())
        _thread_local.conn = w
    else:
        try:
            w.execute("SELECT 1")
        except (sqlite3.DatabaseError, sqlite3.ProgrammingError):
            w = _PooledConn(_make_conn())
            _thread_local.conn = w
    return w


# ─── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables. Idempotent — safe to call every startup."""
    with _write_lock:
        conn = _get_conn()
        conn.executescript("""
            -- Asset universe snapshots (updated every hour)
            CREATE TABLE IF NOT EXISTS rwa_assets (
                id              TEXT NOT NULL,
                name            TEXT NOT NULL,
                category        TEXT,
                subcategory     TEXT,
                chain           TEXT,
                protocol        TEXT,
                token_symbol    TEXT,
                current_price   REAL,
                nav_price       REAL,
                price_vs_nav_pct REAL,
                current_yield_pct REAL,
                tvl_usd         REAL,
                market_cap_usd  REAL,
                volume_24h_usd  REAL,
                risk_score      INTEGER,
                liquidity_score INTEGER,
                regulatory_score INTEGER,
                composite_score REAL,
                last_updated    TEXT NOT NULL,
                PRIMARY KEY (id, last_updated)
            );

            -- Latest snapshot view (one row per asset)
            CREATE TABLE IF NOT EXISTS rwa_latest (
                id              TEXT PRIMARY KEY,
                name            TEXT,
                category        TEXT,
                subcategory     TEXT,
                chain           TEXT,
                protocol        TEXT,
                token_symbol    TEXT,
                current_price   REAL,
                nav_price       REAL,
                price_vs_nav_pct REAL,
                current_yield_pct REAL,
                tvl_usd         REAL,
                market_cap_usd  REAL,
                volume_24h_usd  REAL,
                risk_score      INTEGER,
                liquidity_score INTEGER,
                regulatory_score INTEGER,
                composite_score REAL,
                expected_yield_pct REAL,
                description     TEXT,
                tags            TEXT,
                min_investment_usd REAL,
                last_updated    TEXT
            );

            -- Portfolio snapshots for each risk tier
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tier            INTEGER NOT NULL,
                tier_name       TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                total_value_usd REAL,
                expected_yield_pct REAL,
                sharpe_ratio    REAL,
                sortino_ratio   REAL,
                max_drawdown_pct REAL,
                var_95_pct      REAL,
                cvar_95_pct     REAL,
                volatility_pct  REAL,
                allocations_json TEXT,
                holdings_json   TEXT
            );

            -- Arbitrage opportunities log
            CREATE TABLE IF NOT EXISTS arb_opportunities (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                type            TEXT NOT NULL,  -- 'yield_spread' | 'price_vs_nav' | 'cross_chain' | 'carry'
                asset_a_id      TEXT,
                asset_b_id      TEXT,
                protocol_a      TEXT,
                protocol_b      TEXT,
                yield_a_pct     REAL,
                yield_b_pct     REAL,
                spread_pct      REAL,
                net_spread_pct  REAL,
                estimated_apy   REAL,
                signal          TEXT,  -- 'STRONG_ARB' | 'ARB' | 'MARGINAL'
                action          TEXT,
                notes           TEXT,
                is_active       INTEGER DEFAULT 1
            );

            -- AI agent decisions
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                agent_name      TEXT NOT NULL,
                cycle_number    INTEGER,
                portfolio_tier  INTEGER,
                decision        TEXT,  -- 'REBALANCE' | 'HOLD' | 'DEPLOY' | 'REDUCE'
                rationale       TEXT,
                confidence_pct  REAL,
                actions_json    TEXT,
                portfolio_before_json TEXT,
                portfolio_after_json  TEXT,
                is_dry_run      INTEGER DEFAULT 1
            );

            -- Trade execution log
            CREATE TABLE IF NOT EXISTS trade_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                agent_name      TEXT,
                asset_id        TEXT NOT NULL,
                action          TEXT NOT NULL,  -- 'BUY' | 'SELL' | 'REBALANCE'
                size_usd        REAL,
                price_usd       REAL,
                protocol        TEXT,
                chain           TEXT,
                status          TEXT,  -- 'PENDING' | 'FILLED' | 'FAILED' | 'DRY_RUN'
                tx_hash         TEXT,
                notes           TEXT
            );

            -- News and sentiment
            CREATE TABLE IF NOT EXISTS news_feed (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                source          TEXT,
                headline        TEXT NOT NULL,
                url             TEXT,
                sentiment       TEXT,  -- 'BULLISH' | 'BEARISH' | 'NEUTRAL'
                sentiment_score REAL,
                categories      TEXT,  -- JSON array of categories
                relevance_score REAL,
                is_read         INTEGER DEFAULT 0
            );

            -- AI feedback loop / learning log
            CREATE TABLE IF NOT EXISTS ai_feedback (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                agent_name      TEXT,
                decision_id     INTEGER REFERENCES agent_decisions(id),
                outcome         TEXT,  -- 'WIN' | 'LOSS' | 'NEUTRAL'
                expected_return_pct REAL,
                actual_return_pct   REAL,
                notes           TEXT
            );

            -- Protocol TVL history
            CREATE TABLE IF NOT EXISTS protocol_tvl (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                protocol        TEXT NOT NULL,
                tvl_usd         REAL,
                change_24h_pct  REAL,
                chain           TEXT
            );

            -- Yield history per asset
            CREATE TABLE IF NOT EXISTS yield_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                asset_id        TEXT NOT NULL,
                yield_pct       REAL,
                tvl_usd         REAL,
                pool_id         TEXT
            );

            -- Scan status
            CREATE TABLE IF NOT EXISTS scan_status (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                running         INTEGER DEFAULT 0,
                timestamp       TEXT,
                error           TEXT,
                progress_pct    INTEGER DEFAULT 0,
                current_task    TEXT
            );

            INSERT OR IGNORE INTO scan_status (id, running, progress_pct) VALUES (1, 0, 0);

            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_rwa_assets_category ON rwa_assets(category);
            CREATE INDEX IF NOT EXISTS idx_rwa_assets_updated  ON rwa_assets(last_updated);
            CREATE INDEX IF NOT EXISTS idx_arb_opp_timestamp   ON arb_opportunities(timestamp);
            CREATE INDEX IF NOT EXISTS idx_arb_opp_active      ON arb_opportunities(is_active);
            CREATE INDEX IF NOT EXISTS idx_agent_decisions_ts  ON agent_decisions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_yield_history_asset ON yield_history(asset_id);
            CREATE INDEX IF NOT EXISTS idx_news_feed_ts        ON news_feed(timestamp);
        """)
        conn.commit()
        logger.info("[DB] Schema initialized")


# ─── Asset Operations ──────────────────────────────────────────────────────────

def upsert_rwa_latest(asset: dict):
    """Upsert a single asset into rwa_latest table."""
    with _write_lock:
        conn = _get_conn()
        try:
            tags = asset.get("tags", [])
            if isinstance(tags, list):
                tags = json.dumps(tags)
            conn.execute("""
                INSERT OR REPLACE INTO rwa_latest
                (id, name, category, subcategory, chain, protocol, token_symbol,
                 current_price, nav_price, price_vs_nav_pct, current_yield_pct,
                 tvl_usd, market_cap_usd, volume_24h_usd, risk_score, liquidity_score,
                 regulatory_score, composite_score, expected_yield_pct, description,
                 tags, min_investment_usd, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                asset.get("id"), asset.get("name"), asset.get("category"),
                asset.get("subcategory"), asset.get("chain"), asset.get("protocol"),
                asset.get("token_symbol"), asset.get("current_price"),
                asset.get("nav_price"), asset.get("price_vs_nav_pct"),
                asset.get("current_yield_pct"), asset.get("tvl_usd"),
                asset.get("market_cap_usd"), asset.get("volume_24h_usd"),
                asset.get("risk_score"), asset.get("liquidity_score"),
                asset.get("regulatory_score"), asset.get("composite_score"),
                asset.get("expected_yield_pct"), asset.get("description"),
                tags, asset.get("min_investment_usd"),
                asset.get("last_updated", datetime.now(timezone.utc).isoformat()),
            ))
            conn.commit()
        except Exception as e:
            logger.error("[DB] upsert_rwa_latest failed: %s", e)
        finally:
            conn.close()


def get_all_rwa_latest() -> pd.DataFrame:
    """Return all assets from rwa_latest as DataFrame."""
    conn = _get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM rwa_latest ORDER BY composite_score DESC NULLS LAST", conn)
        return df
    except Exception as e:
        logger.error("[DB] get_all_rwa_latest failed: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


def get_rwa_by_category(category: str) -> pd.DataFrame:
    conn = _get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM rwa_latest WHERE category = ? ORDER BY composite_score DESC NULLS LAST",
            conn, params=(category,)
        )
        return df
    except Exception as e:
        logger.error("[DB] get_rwa_by_category failed: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


# ─── Arbitrage Operations ──────────────────────────────────────────────────────

def log_arb_opportunity(opp: dict):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO arb_opportunities
                (timestamp, type, asset_a_id, asset_b_id, protocol_a, protocol_b,
                 yield_a_pct, yield_b_pct, spread_pct, net_spread_pct, estimated_apy,
                 signal, action, notes, is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """, (
                opp.get("timestamp", datetime.now(timezone.utc).isoformat()),
                opp.get("type"), opp.get("asset_a_id"), opp.get("asset_b_id"),
                opp.get("protocol_a"), opp.get("protocol_b"),
                opp.get("yield_a_pct"), opp.get("yield_b_pct"),
                opp.get("spread_pct"), opp.get("net_spread_pct"),
                opp.get("estimated_apy"), opp.get("signal"),
                opp.get("action"), opp.get("notes"),
            ))
            conn.commit()
        except Exception as e:
            logger.error("[DB] log_arb_opportunity failed: %s", e)
        finally:
            conn.close()


def get_active_arb_opportunities(limit: int = 50) -> pd.DataFrame:
    conn = _get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM arb_opportunities WHERE is_active=1 ORDER BY estimated_apy DESC LIMIT ?",
            conn, params=(limit,)
        )
        return df
    except Exception as e:
        logger.error("[DB] get_active_arb_opportunities: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


def clear_active_arb_opportunities():
    """Mark all active arb opportunities as inactive (called before a fresh scan)."""
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("UPDATE arb_opportunities SET is_active=0 WHERE is_active=1")
            conn.commit()
        except Exception as e:
            logger.error("[DB] clear_active_arb_opportunities: %s", e)
        finally:
            conn.close()


# ─── Portfolio Operations ──────────────────────────────────────────────────────

def save_portfolio_snapshot(snap: dict):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO portfolio_snapshots
                (tier, tier_name, timestamp, total_value_usd, expected_yield_pct,
                 sharpe_ratio, sortino_ratio, max_drawdown_pct, var_95_pct,
                 cvar_95_pct, volatility_pct, allocations_json, holdings_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                snap.get("tier"), snap.get("tier_name"),
                snap.get("timestamp", datetime.now(timezone.utc).isoformat()),
                snap.get("total_value_usd"), snap.get("expected_yield_pct"),
                snap.get("sharpe_ratio"), snap.get("sortino_ratio"),
                snap.get("max_drawdown_pct"), snap.get("var_95_pct"),
                snap.get("cvar_95_pct"), snap.get("volatility_pct"),
                json.dumps(snap.get("allocations", {})),
                json.dumps(snap.get("holdings", [])),
            ))
            conn.commit()
        except Exception as e:
            logger.error("[DB] save_portfolio_snapshot: %s", e)
        finally:
            conn.close()


def get_latest_portfolio(tier: int) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE tier=? ORDER BY timestamp DESC LIMIT 1",
            (tier,)
        ).fetchone()
        if row:
            d = dict(row)
            d["allocations"] = json.loads(d.get("allocations_json") or "{}")
            d["holdings"]    = json.loads(d.get("holdings_json")    or "[]")
            return d
        return None
    except Exception as e:
        logger.error("[DB] get_latest_portfolio: %s", e)
        return None
    finally:
        conn.close()


# ─── Agent Operations ──────────────────────────────────────────────────────────

def log_agent_decision(decision: dict) -> int:
    with _write_lock:
        conn = _get_conn()
        try:
            cur = conn.execute("""
                INSERT INTO agent_decisions
                (timestamp, agent_name, cycle_number, portfolio_tier, decision,
                 rationale, confidence_pct, actions_json, portfolio_before_json,
                 portfolio_after_json, is_dry_run)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                decision.get("timestamp", datetime.now(timezone.utc).isoformat()),
                decision.get("agent_name"), decision.get("cycle_number"),
                decision.get("portfolio_tier"), decision.get("decision"),
                decision.get("rationale"), decision.get("confidence_pct"),
                json.dumps(decision.get("actions", [])),
                json.dumps(decision.get("portfolio_before", {})),
                json.dumps(decision.get("portfolio_after",  {})),
                int(decision.get("is_dry_run", True)),
            ))
            conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.error("[DB] log_agent_decision: %s", e)
            return -1
        finally:
            conn.close()


def get_recent_agent_decisions(limit: int = 20) -> pd.DataFrame:
    conn = _get_conn()
    try:
        return pd.read_sql_query(
            "SELECT * FROM agent_decisions ORDER BY timestamp DESC LIMIT ?",
            conn, params=(limit,)
        )
    except Exception as e:
        logger.error("[DB] get_recent_agent_decisions: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


# ─── Trade Log ────────────────────────────────────────────────────────────────

def log_trade(trade: dict):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO trade_log
                (timestamp, agent_name, asset_id, action, size_usd, price_usd,
                 protocol, chain, status, tx_hash, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trade.get("timestamp", datetime.now(timezone.utc).isoformat()),
                trade.get("agent_name"), trade.get("asset_id"),
                trade.get("action"), trade.get("size_usd"), trade.get("price_usd"),
                trade.get("protocol"), trade.get("chain"),
                trade.get("status", "DRY_RUN"), trade.get("tx_hash"),
                trade.get("notes"),
            ))
            conn.commit()
        except Exception as e:
            logger.error("[DB] log_trade: %s", e)
        finally:
            conn.close()


def get_trade_history(limit: int = 100) -> pd.DataFrame:
    conn = _get_conn()
    try:
        return pd.read_sql_query(
            "SELECT * FROM trade_log ORDER BY timestamp DESC LIMIT ?",
            conn, params=(limit,)
        )
    except Exception as e:
        logger.error("[DB] get_trade_history: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


# ─── News Feed ────────────────────────────────────────────────────────────────

def save_news(items: List[dict]):
    if not items:
        return
    with _write_lock:
        conn = _get_conn()
        try:
            for item in items:
                headline = item.get("headline")
                if not headline:
                    continue
                # Deduplicate by headline — no UNIQUE constraint on table so check manually
                exists = conn.execute(
                    "SELECT 1 FROM news_feed WHERE headline = ? LIMIT 1", (headline,)
                ).fetchone()
                if exists:
                    continue
                cats = item.get("categories", [])
                if isinstance(cats, list):
                    cats = json.dumps(cats)
                conn.execute("""
                    INSERT INTO news_feed
                    (timestamp, source, headline, url, sentiment, sentiment_score,
                     categories, relevance_score)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    item.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    item.get("source"), headline, item.get("url"),
                    item.get("sentiment", "NEUTRAL"), item.get("sentiment_score", 0.0),
                    cats, item.get("relevance_score", 0.5),
                ))
            conn.commit()
        except Exception as e:
            logger.error("[DB] save_news: %s", e)
        finally:
            conn.close()


def get_recent_news(limit: int = 30) -> pd.DataFrame:
    conn = _get_conn()
    try:
        return pd.read_sql_query(
            "SELECT * FROM news_feed ORDER BY timestamp DESC LIMIT ?",
            conn, params=(limit,)
        )
    except Exception as e:
        logger.error("[DB] get_recent_news: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


# ─── Yield History ────────────────────────────────────────────────────────────

def save_yield_history(asset_id: str, yield_pct: float, tvl_usd: Optional[float] = None):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO yield_history (timestamp, asset_id, yield_pct, tvl_usd)
                VALUES (?, ?, ?, ?)
            """, (datetime.now(timezone.utc).isoformat(), asset_id, yield_pct, tvl_usd))
            conn.commit()
        except Exception as e:
            logger.error("[DB] save_yield_history: %s", e)
        finally:
            conn.close()


def get_yield_history(asset_id: str, days: int = 30) -> pd.DataFrame:
    conn = _get_conn()
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return pd.read_sql_query(
            "SELECT * FROM yield_history WHERE asset_id=? AND timestamp >= ? ORDER BY timestamp",
            conn, params=(asset_id, since)
        )
    except Exception as e:
        logger.error("[DB] get_yield_history: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()


# ─── Scan Status ──────────────────────────────────────────────────────────────

def write_scan_status(running: bool, timestamp: str = None, error: str = None,
                      progress: int = 0, current_task: str = ""):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                UPDATE scan_status SET running=?, timestamp=?, error=?,
                progress_pct=?, current_task=? WHERE id=1
            """, (int(running), timestamp or datetime.now(timezone.utc).isoformat(),
                  error, progress, current_task))
            conn.commit()
        except Exception as e:
            logger.error("[DB] write_scan_status: %s", e)
        finally:
            conn.close()


def read_scan_status() -> dict:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM scan_status WHERE id=1").fetchone()
        if row:
            return dict(row)
        return {"running": 0, "timestamp": None, "error": None, "progress_pct": 0, "current_task": ""}
    except Exception as e:
        logger.error("[DB] read_scan_status: %s", e)
        return {"running": 0, "timestamp": None, "error": None, "progress_pct": 0, "current_task": ""}
    finally:
        conn.close()


# ─── Protocol TVL ─────────────────────────────────────────────────────────────

def save_protocol_tvl(protocol: str, tvl_usd: float, change_24h_pct: float = None, chain: str = None):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO protocol_tvl (timestamp, protocol, tvl_usd, change_24h_pct, chain)
                VALUES (?,?,?,?,?)
            """, (datetime.now(timezone.utc).isoformat(), protocol, tvl_usd, change_24h_pct, chain))
            conn.commit()
        except Exception as e:
            logger.error("[DB] save_protocol_tvl: %s", e)
        finally:
            conn.close()


# ─── Feedback Log ─────────────────────────────────────────────────────────────

def log_ai_feedback(feedback: dict):
    with _write_lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO ai_feedback
                (timestamp, agent_name, decision_id, outcome, expected_return_pct,
                 actual_return_pct, notes)
                VALUES (?,?,?,?,?,?,?)
            """, (
                feedback.get("timestamp", datetime.now(timezone.utc).isoformat()),
                feedback.get("agent_name"), feedback.get("decision_id"),
                feedback.get("outcome"), feedback.get("expected_return_pct"),
                feedback.get("actual_return_pct"), feedback.get("notes"),
            ))
            conn.commit()
        except Exception as e:
            logger.error("[DB] log_ai_feedback: %s", e)
        finally:
            conn.close()


def get_agent_performance() -> pd.DataFrame:
    """Aggregate win/loss stats per agent for the feedback loop."""
    conn = _get_conn()
    try:
        return pd.read_sql_query("""
            SELECT agent_name,
                   COUNT(*) as total_decisions,
                   SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN outcome='LOSS' THEN 1 ELSE 0 END) as losses,
                   AVG(actual_return_pct) as avg_return_pct,
                   AVG(expected_return_pct) as avg_expected_pct
            FROM ai_feedback
            GROUP BY agent_name
        """, conn)
    except Exception as e:
        logger.error("[DB] get_agent_performance: %s", e)
        return pd.DataFrame()
    finally:
        conn.close()
