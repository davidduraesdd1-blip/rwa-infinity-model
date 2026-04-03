"""
news_sentiment.py — RWA Infinity Model v1.0
Claude Haiku-powered sentiment classification for Real World Asset news.

Aggregates sentiment across RWA headlines (tokenized treasuries, real estate,
stablecoins, equities, etc.) and produces a portfolio-level market sentiment
indicator used by the AI agent and portfolio builder.

Cache: 30-minute TTL aligned with news refresh cycle.
Fallback: keyword rule-based when ANTHROPIC_API_KEY not set.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import List, Optional

import requests

from config import CLAUDE_MODEL

logger = logging.getLogger(__name__)

# ─── Anthropic client (singleton) ──────────────────────────────────────────────
_anthropic_client = None
_anthropic_lock   = threading.Lock()


def _get_anthropic_client():
    """Return or create the module-level Anthropic client (thread-safe)."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    with _anthropic_lock:
        if _anthropic_client is None:
            try:
                import anthropic
                _anthropic_client = anthropic.Anthropic(api_key=api_key, timeout=15.0)
            except Exception as _ae:
                logger.warning("[NewsSentiment] Anthropic client init failed: %s", _ae)
    return _anthropic_client


# ─── Cache ──────────────────────────────────────────────────────────────────────
_cache: dict = {}
_cache_lock   = threading.Lock()
_CACHE_TTL    = 1800   # 30 minutes — aligned with news refresh cycle


# ─── RWA-specific keyword sets ──────────────────────────────────────────────────
_RWA_BULLISH_WORDS = {
    "tokenize", "tokenized", "tokenization", "launch", "approval", "approved",
    "adoption", "institutional", "milestone", "partnership", "integration",
    "expansion", "record", "surge", "breakout", "growth", "billion", "trillion",
    "upgrade", "bullish", "positive", "increase", "first", "leading", "major",
    "breakthrough", "compliance", "regulated", "backed", "verified", "legal",
    "etf", "fund", "attract", "demand", "yield", "stablecoin", "rwa", "pilot",
}
_RWA_BEARISH_WORDS = {
    "hack", "exploit", "fraud", "scam", "ban", "restrict", "regulation", "warning",
    "collapse", "liquidation", "default", "breach", "investigation", "suspend",
    "delay", "fail", "risk", "concern", "volatile", "drop", "slump", "decline",
    "crackdown", "lawsuit", "sec", "fine", "penalty", "delist", "halt",
    "devalue", "unstable", "depeg", "rug", "exit",
}


# ─── Rule-based fallback ────────────────────────────────────────────────────────

def _rule_based_classify(headlines: List[str]) -> dict:
    """Keyword-based sentiment fallback (no API key needed)."""
    bullish = bearish = neutral = 0
    for h in headlines:
        lower = h.lower()
        b_hits  = sum(1 for w in _RWA_BULLISH_WORDS if w in lower)
        br_hits = sum(1 for w in _RWA_BEARISH_WORDS if w in lower)
        if b_hits > br_hits:
            bullish += 1
        elif br_hits > b_hits:
            bearish += 1
        else:
            neutral += 1
    total = bullish + bearish + neutral or 1
    score = (bullish - bearish) / total
    if score > 0.15:
        sentiment = "BULLISH"
    elif score < -0.15:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"
    return {
        "sentiment":         sentiment,
        "score":             round(score, 3),
        "bullish":           bullish,
        "bearish":           bearish,
        "neutral":           neutral,
        "key_theme":         "",
        "confidence":        round(min(abs(score) * 2, 1.0), 3),
        "articles_analyzed": len(headlines),
        "source":            "rule_based",
        "error":             None,
    }


# ─── Claude Haiku classification ────────────────────────────────────────────────

def _classify_with_claude(headlines: List[str]) -> dict:
    """
    Classify RWA news sentiment with Claude Haiku.
    Falls back to rule-based if no API key or call fails.
    """
    if not headlines:
        return {
            "sentiment": "NEUTRAL", "score": 0.0,
            "bullish": 0, "bearish": 0, "neutral": 0,
            "key_theme": "", "confidence": 0.0,
            "articles_analyzed": 0, "source": "no_headlines", "error": None,
        }

    client = _get_anthropic_client()
    if client is None:
        return _rule_based_classify(headlines)

    try:
        import anthropic
        headlines_text = "\n".join(f"- {h}" for h in headlines[:25])
        prompt = (
            "You are an RWA (Real World Assets) market analyst specializing in tokenized "
            "treasuries, tokenized equities, stablecoins, tokenized real estate, and "
            "institutional DeFi. Analyze these recent RWA news headlines and classify "
            "the overall market sentiment.\n\n"
            f"Headlines:\n{headlines_text}\n\n"
            "Respond in exactly this JSON format (no extra text):\n"
            '{"bullish": <count>, "bearish": <count>, "neutral": <count>, '
            '"overall": "<BULLISH|BEARISH|NEUTRAL>", "confidence": <0.0-1.0>, '
            '"key_theme": "<one short phrase summarizing the dominant RWA story>"}'
        )
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        if not msg.content:
            raise ValueError("Claude returned empty content list")
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)

        bullish = result.get("bullish", 0) or 0
        bearish = result.get("bearish", 0) or 0
        neutral = result.get("neutral", 0) or 0
        total   = bullish + bearish + neutral or 1
        score   = (bullish - bearish) / total

        return {
            "sentiment":         result.get("overall", "NEUTRAL"),
            "score":             round(score, 3),
            "bullish":           bullish,
            "bearish":           bearish,
            "neutral":           neutral,
            "key_theme":         result.get("key_theme", ""),
            "confidence":        float(result.get("confidence", 0.5)),
            "articles_analyzed": len(headlines),
            "source":            "claude_ai",
            "error":             None,
        }
    except Exception as e:
        logger.warning("[NewsSentiment] Claude classification failed: %s", e)
        return _rule_based_classify(headlines)


# ─── Public API ─────────────────────────────────────────────────────────────────

def get_rwa_sentiment(headlines: List[str]) -> dict:
    """
    Classify sentiment of a list of RWA headlines.

    Args:
        headlines: list of headline strings to classify

    Returns:
        dict with:
          sentiment  : 'BULLISH' | 'BEARISH' | 'NEUTRAL'
          score      : float [-1, +1] (positive = bullish)
          bullish    : count of bullish-classified headlines
          bearish    : count of bearish-classified headlines
          key_theme  : dominant story phrase (from Claude)
          confidence : float [0, 1]
          source     : 'claude_ai' | 'rule_based' | 'no_headlines'
    """
    cache_key = "rwa_sentiment"
    now = time.time()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached.get("_ts", 0) < _CACHE_TTL:
            return {k: v for k, v in cached.items() if k != "_ts"}

    result = _classify_with_claude(headlines)

    with _cache_lock:
        _cache[cache_key] = {**result, "_ts": now}

    return result


def get_sentiment_summary() -> dict:
    """
    Build an aggregate RWA sentiment summary from recently stored news_feed rows.

    Reads the last 50 news articles from SQLite, extracts their existing
    sentiment labels, and also produces a Claude-powered re-classification
    from all recent headlines together.

    Returns:
        dict with sentiment, score, bullish, bearish, neutral, key_theme,
        confidence, articles_analyzed, breakdown (BULLISH/BEARISH/NEUTRAL counts
        from stored labels), source
    """
    cache_key = "rwa_sentiment_summary"
    now = time.time()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached.get("_ts", 0) < _CACHE_TTL:
            return {k: v for k, v in cached.items() if k != "_ts"}

    headlines    = []
    stored_bull  = 0
    stored_bear  = 0
    stored_neut  = 0

    try:
        import database as _db
        df = _db.get_recent_news(limit=50)
        if df is not None and not df.empty:
            if "headline" in df.columns:
                headlines = df["headline"].dropna().tolist()
            if "sentiment" in df.columns:
                counts = df["sentiment"].value_counts()
                stored_bull = int(counts.get("BULLISH", 0))
                stored_bear = int(counts.get("BEARISH", 0))
                stored_neut = int(counts.get("NEUTRAL", 0))
    except Exception as e:
        logger.warning("[NewsSentiment] DB read failed: %s", e)

    classification = _classify_with_claude(headlines)

    result = {
        **classification,
        "breakdown": {
            "stored_bullish": stored_bull,
            "stored_bearish": stored_bear,
            "stored_neutral": stored_neut,
        },
    }

    with _cache_lock:
        _cache[cache_key] = {**result, "_ts": now}

    return result


def score_rwa_sentiment_bias() -> float:
    """
    Return a numeric sentiment bias for portfolio/yield scoring adjustments.

    Positive = bullish market (favor higher-risk RWA assets),
    Negative = bearish market (rotate toward safe havens like tokenized treasuries).

    Returns:
        float in range [-10.0, +10.0]
    """
    try:
        summary    = get_sentiment_summary()
        score      = summary.get("score", 0.0)
        confidence = summary.get("confidence", 0.0)
        return round(score * confidence * 10.0, 1)
    except Exception:
        return 0.0


def invalidate_cache():
    """Clear the sentiment cache (call after a news refresh to force re-scoring)."""
    with _cache_lock:
        _cache.clear()
