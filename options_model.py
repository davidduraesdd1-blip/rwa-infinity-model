"""
options_model.py — Black-Scholes pricing + Greeks (RWA Model)

Prices options and computes all 5 Greeks using the classic Black-Scholes formula.
Used for:
- Rate cap/floor pricing on RWA interest rate exposure
- IV surface context from Deribit to inform carry trade timing
- Enriching agent prompts with options-market volatility context

Primary source:    Black & Scholes (1973), Merton (1973)
Theta convention:  Daily theta (divided by 365). Negative = time decay.
Vega convention:   Per 1% (0.01) move in implied volatility.

Ported from DeFi Model models/options_model.py.
scipy-optional: falls back to erf-based normal CDF if scipy not installed.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Normal distribution helpers (scipy-optional) ────────────────────────────

try:
    from scipy.stats import norm as _scipy_norm
    def _norm_cdf(x: float) -> float: return float(_scipy_norm.cdf(x))
    def _norm_pdf(x: float) -> float: return float(_scipy_norm.pdf(x))
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False
    def _norm_cdf(x: float) -> float:
        """Cumulative normal using math.erf — accurate to 7+ decimal places."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    def _norm_pdf(x: float) -> float:
        """Standard normal PDF."""
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ─── Data class ──────────────────────────────────────────────────────────────

@dataclass
class OptionPrice:
    token:          str
    option_type:    str     # "call" or "put"
    spot:           float
    strike:         float
    expiry_days:    int
    volatility:     float   # annualised decimal (e.g. 0.80 = 80%)
    risk_free:      float   # annualised decimal (e.g. 0.045 = 4.5%)
    price:          float   # option premium in USD
    delta:          float   # ∂price/∂spot
    gamma:          float   # ∂²price/∂spot²
    theta:          float   # daily time decay in USD (negative)
    vega:           float   # price change per +1% vol move
    moneyness:      str     # "ITM" / "ATM" / "OTM"
    intrinsic:      float
    time_value:     float
    calculated_at:  Optional[str] = None

    def __post_init__(self):
        if self.calculated_at is None:
            self.calculated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "token": self.token, "option_type": self.option_type,
            "spot": self.spot, "strike": self.strike,
            "expiry_days": self.expiry_days,
            "volatility_pct": round(self.volatility * 100, 2),
            "risk_free_pct": round(self.risk_free * 100, 2),
            "price": self.price,
            "delta": self.delta, "gamma": self.gamma,
            "theta": self.theta, "vega": self.vega,
            "moneyness": self.moneyness,
            "intrinsic": self.intrinsic, "time_value": self.time_value,
            "calculated_at": self.calculated_at,
        }


# ─── Core formula ─────────────────────────────────────────────────────────────

def black_scholes(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
) -> tuple[float, float, float, float, float]:
    """
    Black-Scholes formula for European options.

    Args:
        S     : Current spot price
        K     : Strike price
        T     : Time to expiry in years
        r     : Risk-free rate (annualised decimal)
        sigma : Implied volatility (annualised decimal)
        option_type: "call" or "put"

    Returns:
        (price, delta, gamma, theta_daily, vega_per_1pct)
    """
    if T <= 0 or S <= 0 or K <= 0:
        return (0.0, 0.0, 0.0, 0.0, 0.0)

    if sigma <= 0 or not math.isfinite(sigma):
        # Zero-vol: price = intrinsic, no time value, delta is step function
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        delta = (1.0 if S > K else 0.0) if option_type == "call" else (-1.0 if S < K else 0.0)
        return (round(intrinsic, 6), round(delta, 4), 0.0, 0.0, 0.0)

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type == "call":
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0

    pdf_d1 = _norm_pdf(d1)
    gamma  = pdf_d1 / (S * sigma * sqrt_T)

    # Theta: daily decay (/ 365)
    if option_type == "call":
        theta = (-(S * pdf_d1 * sigma) / (2.0 * sqrt_T)
                 - r * K * math.exp(-r * T) * _norm_cdf(d2)) / 365.0
    else:
        theta = (-(S * pdf_d1 * sigma) / (2.0 * sqrt_T)
                 + r * K * math.exp(-r * T) * _norm_cdf(-d2)) / 365.0

    vega = S * pdf_d1 * sqrt_T / 100.0   # per 1% vol move

    return (
        round(float(price), 6),
        round(float(delta), 4),
        round(float(gamma), 6),
        round(float(theta), 6),
        round(float(vega),  6),
    )


# ─── High-level wrapper ───────────────────────────────────────────────────────

def price_option(
    token: str,
    spot: float,
    strike: float,
    expiry_days: int,
    vol: float,
    option_type: str = "call",
    risk_free: float = 0.045,
) -> OptionPrice:
    """
    Price a single option and compute all Greeks.

    Args:
        token      : Symbol (e.g. "BTC")
        spot       : Current spot price (USD)
        strike     : Strike price (USD)
        expiry_days: Days to expiry
        vol        : Implied volatility (annualised decimal, e.g. 0.80)
        option_type: "call" or "put"
        risk_free  : Risk-free rate (default: 4.5% = 0.045)
    """
    T = expiry_days / 365.0
    price, delta, gamma, theta, vega = black_scholes(spot, strike, T, risk_free, vol, option_type)

    intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
    time_value = max(0.0, price - intrinsic)

    # Moneyness: within ±3% of ATM
    if option_type == "call":
        moneyness = "ITM" if strike < spot * 0.97 else ("OTM" if strike > spot * 1.03 else "ATM")
    else:
        moneyness = "ITM" if strike > spot * 1.03 else ("OTM" if strike < spot * 0.97 else "ATM")

    return OptionPrice(
        token=token, option_type=option_type,
        spot=round(spot, 4), strike=round(strike, 4),
        expiry_days=expiry_days, volatility=round(vol, 4),
        risk_free=risk_free, price=price,
        delta=delta, gamma=gamma, theta=theta, vega=vega,
        moneyness=moneyness, intrinsic=round(intrinsic, 4),
        time_value=round(time_value, 4),
    )


def atm_greeks(
    token: str,
    spot: float,
    vol: float,
    expiry_days: int = 30,
    risk_free: float = 0.045,
) -> dict:
    """
    Compute ATM call and put Greeks for a quick market-wide Greeks summary.
    Useful for including options context in agent prompts.

    Returns a flat dict with call_delta, put_delta, gamma, theta, vega,
    vega_usd (vega × portfolio_notional proxy), and a risk_summary string.
    """
    try:
        atm_call = price_option(token, spot, spot, expiry_days, vol, "call", risk_free)
        atm_put  = price_option(token, spot, spot, expiry_days, vol, "put",  risk_free)

        risk_label = (
            "HIGH" if vol > 0.8 else
            "ELEVATED" if vol > 0.5 else
            "MODERATE" if vol > 0.3 else
            "LOW"
        )

        return {
            "token":         token,
            "spot":          spot,
            "vol_pct":       round(vol * 100, 1),
            "expiry_days":   expiry_days,
            "call_price":    atm_call.price,
            "put_price":     atm_put.price,
            "call_delta":    atm_call.delta,
            "put_delta":     atm_put.delta,
            "gamma":         atm_call.gamma,
            "theta_daily":   atm_call.theta,
            "vega_per_1pct": atm_call.vega,
            "vol_risk":      risk_label,
            "risk_summary":  (
                f"{token} ATM 30D: call={atm_call.price:.2f} put={atm_put.price:.2f} "
                f"delta={atm_call.delta:.2f} gamma={atm_call.gamma:.4f} "
                f"theta={atm_call.theta:.4f}/day vega={atm_call.vega:.3f}/1pct "
                f"(IV={vol*100:.0f}% -- {risk_label})"
            ),
        }
    except Exception as exc:
        logger.debug("[OptionsModel] atm_greeks failed for %s: %s", token, exc)
        return {"token": token, "error": str(exc)}


def implied_vol_from_price(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    tol: float = 1e-6,
    max_iter: int = 100,
) -> Optional[float]:
    """
    Compute implied volatility via bisection search.
    Returns IV as a decimal (e.g. 0.80 = 80%), or None if no convergence.
    """
    if market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None

    intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    if market_price < intrinsic:
        return None

    lo, hi = 0.001, 20.0  # IV search bounds: 0.1% to 2000%
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        price, *_ = black_scholes(S, K, T, r, mid, option_type)
        diff = price - market_price
        if abs(diff) < tol:
            return round(mid, 6)
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2.0, 6)
