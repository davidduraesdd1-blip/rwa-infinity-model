"""
pdf_export.py — RWA Infinity Model v1.0
Portfolio and arbitrage PDF report generation using ReportLab.
Returns raw PDF bytes for Streamlit st.download_button().
"""

import io
from datetime import datetime, timezone

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    _REPORTLAB = True
except ImportError:
    _REPORTLAB = False


# ── Color palette ──────────────────────────────────────────────────────────────
if _REPORTLAB:
    CYAN   = colors.HexColor("#00D4FF")   # RWA Infinity brand cyan
    DARK   = colors.HexColor("#0e1117")
    MID    = colors.HexColor("#1a1d23")
    GREEN  = colors.HexColor("#00cc96")
    RED    = colors.HexColor("#ff4b4b")
    ORANGE = colors.HexColor("#ffa500")
    GREY   = colors.HexColor("#888888")
    WHITE  = colors.white
    BLACK  = colors.black


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "rwa_title", parent=base["Title"],
            fontSize=18, textColor=CYAN, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "rwa_subtitle", parent=base["Normal"],
            fontSize=10, textColor=GREY, spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "rwa_section", parent=base["Heading2"],
            fontSize=13, textColor=CYAN, spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "rwa_body", parent=base["Normal"],
            fontSize=9, textColor=BLACK, spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "rwa_footer", parent=base["Normal"],
            fontSize=7, textColor=GREY,
        ),
    }


def _table_style(num_rows: int) -> "TableStyle":
    return TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), CYAN),
        ("TEXTCOLOR",     (0, 0), (-1, 0), BLACK),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTSIZE",      (0, 1), (-1, -1), 7.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f5f5f5"), WHITE]),
        ("ALIGN",         (1, 1), (-1, -1), "CENTER"),
        ("ALIGN",         (0, 1), (0, -1), "LEFT"),
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ])


def _fmt(val, prefix="", suffix="", decimals=2, fallback="N/A"):
    """Safe number formatter."""
    try:
        v = float(val)
        return f"{prefix}{v:,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return fallback


# ─── Portfolio Report ──────────────────────────────────────────────────────────

def generate_portfolio_pdf(
    portfolio: dict,
    tier_name: str = "Portfolio",
    macro_data: dict | None = None,
    stress_results: dict | None = None,
) -> bytes:
    """
    Generate a portfolio report PDF.

    Args:
        portfolio:      result from portfolio.build_portfolio() — includes holdings + metrics
        tier_name:      e.g. "Balanced Growth" for the title
        macro_data:     optional market summary dict — adds macro intelligence section
        stress_results: optional dict of {scenario: stress_test result} — adds risk scenarios section

    Returns:
        Raw PDF bytes.
    """
    if not _REPORTLAB:
        raise ImportError("reportlab is not installed — pip install reportlab")

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = _styles()
    story  = []
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Title ──
    story.append(Paragraph(f"RWA Infinity Model — {tier_name}", styles["title"]))
    story.append(Paragraph(f"Portfolio Report  |  Generated: {ts}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=CYAN, spaceAfter=10))

    metrics = portfolio.get("metrics", {})

    # ── Portfolio Metrics Summary ──
    story.append(Paragraph("Portfolio Metrics", styles["section"]))
    summary_data = [
        ["Metric", "Value"],
        ["Portfolio Value",    _fmt(portfolio.get("portfolio_value_usd", 0), "$", "", 0)],
        ["Weighted Yield",     _fmt(metrics.get("weighted_yield_pct"), suffix="%")],
        ["Sharpe Ratio",       _fmt(metrics.get("sharpe_ratio"), decimals=3)],
        ["Sortino Ratio",      _fmt(metrics.get("sortino_ratio"), decimals=3)],
        ["Calmar Ratio",       _fmt(metrics.get("calmar_ratio"), decimals=3)],
        ["Max Drawdown",       _fmt(metrics.get("max_drawdown_pct"), suffix="%")],
        ["VaR 95%",            _fmt(metrics.get("var_95_pct"), suffix="%")],
        ["CVaR 95%",           _fmt(metrics.get("cvar_95_pct"), suffix="%")],
        ["VaR 99%",            _fmt(metrics.get("var_99_pct"), suffix="%")],
        ["Portfolio Vol",      _fmt(metrics.get("portfolio_volatility_pct"), suffix="%")],
        ["Holdings",           str(metrics.get("n_holdings", 0))],
    ]
    tbl = Table(summary_data, colWidths=[6 * cm, 5 * cm])
    tbl.setStyle(_table_style(len(summary_data)))
    story.append(tbl)
    story.append(Spacer(1, 12))

    # ── Holdings Table ──
    holdings = portfolio.get("holdings", [])
    if holdings:
        story.append(Paragraph(f"Holdings ({len(holdings)} assets)", styles["section"]))
        headers = ["Asset", "Category", "Chain", "Yield%", "Weight%", "Risk", "TVL ($M)", "Score"]
        col_w   = [5.0, 3.5, 3.0, 2.0, 2.2, 1.8, 2.5, 2.0]
        col_w_cm = [w * cm for w in col_w]

        rows = [headers]
        for h in sorted(holdings, key=lambda x: x.get("weight_pct", 0), reverse=True):
            tvl_m = (h.get("tvl_usd") or 0) / 1_000_000
            rows.append([
                (h.get("name") or h.get("id") or "?")[:28],
                (h.get("category") or "?")[:16],
                (h.get("chain") or "?")[:12],
                _fmt(h.get("current_yield_pct"), suffix="%", decimals=1),
                _fmt(h.get("weight_pct"), suffix="%", decimals=1),
                str(h.get("risk_score") or "?"),
                _fmt(tvl_m, prefix="$", decimals=1) if tvl_m > 0 else "N/A",
                _fmt(h.get("composite_score"), decimals=1),
            ])

        tbl2 = Table(rows, colWidths=col_w_cm)
        style2 = _table_style(len(rows))
        # Color yield column by magnitude
        for i, h in enumerate(sorted(holdings, key=lambda x: x.get("weight_pct", 0), reverse=True), start=1):
            y = h.get("current_yield_pct") or 0
            bg = "#e6f9f3" if y >= 10 else ("#fff9e6" if y >= 5 else "#f5f5f5")
            style2.add("BACKGROUND", (3, i), (3, i), colors.HexColor(bg))
        tbl2.setStyle(style2)
        story.append(tbl2)
        story.append(Spacer(1, 10))

    # ── Category Allocation ──
    cat_summary = portfolio.get("category_summary", {})
    if cat_summary:
        story.append(Paragraph("Category Allocation", styles["section"]))
        cat_data = [["Category", "Weight%", "Avg Yield%", "Assets"]]
        for cat, data in sorted(cat_summary.items(), key=lambda x: x[1].get("weight_pct", 0), reverse=True):
            cat_data.append([
                cat[:30],
                _fmt(data.get("weight_pct"), suffix="%", decimals=1),
                _fmt(data.get("yield_pct"), suffix="%", decimals=1),
                str(data.get("count", 0)),
            ])
        tbl3 = Table(cat_data, colWidths=[7 * cm, 3 * cm, 4 * cm, 2.5 * cm])
        tbl3.setStyle(_table_style(len(cat_data)))
        story.append(tbl3)
        story.append(Spacer(1, 10))

    # ── Macro Intelligence (Phase 12 Enhancement) ────────────────────────────
    if macro_data:
        story.append(Paragraph("Macro Intelligence", styles["section"]))
        macro_rows = [["Macro Signal", "Value"]]
        _reg    = macro_data.get("macro_regime",       "N/A")
        _bias   = macro_data.get("macro_bias",         "")
        _fg_val = macro_data.get("fear_greed_value",   "N/A")
        _fg_lbl = macro_data.get("fear_greed_label",   "")
        _fg_sig = macro_data.get("fear_greed_signal",  "")
        _sc_tot = macro_data.get("stablecoin_total_bn", 0)
        macro_rows += [
            ["Macro Regime",            f"{_reg} — {_bias}" if _bias else _reg],
            ["Fear & Greed",            f"{_fg_val} / 100 — {_fg_lbl} ({_fg_sig})"],
            ["Stablecoin Supply",       f"${_sc_tot:.1f}B (dry powder indicator)"],
            ["Portfolio Value (USD)",   _fmt(portfolio.get("portfolio_value_usd", 0), "$", "", 0)],
        ]
        tbl_m = Table(macro_rows, colWidths=[6 * cm, 14 * cm])
        tbl_m.setStyle(_table_style(len(macro_rows)))
        story.append(tbl_m)
        story.append(Spacer(1, 10))

    # ── Risk Scenarios (Phase 12 Enhancement) ────────────────────────────────
    if stress_results:
        story.append(Paragraph("Risk Scenario Analysis", styles["section"]))
        stress_header = ["Scenario", "Portfolio Vol%", "VaR 95%", "CVaR 95%", "Max Drawdown%", "vs Baseline"]
        stress_data   = [stress_header]
        _base_vol = metrics.get("portfolio_volatility_pct", 0) or 0
        for _sc_name, _sc_res in stress_results.items():
            if not _sc_res or not isinstance(_sc_res, dict):
                continue
            _sc_metrics = _sc_res.get("metrics", {})
            _sc_vol     = _sc_metrics.get("portfolio_volatility_pct", 0) or 0
            _delta_vol  = round(_sc_vol - _base_vol, 2) if _base_vol else 0
            stress_data.append([
                _sc_res.get("label", _sc_name)[:30],
                _fmt(_sc_vol, suffix="%", decimals=2),
                _fmt(_sc_metrics.get("var_95_pct"), suffix="%", decimals=2),
                _fmt(_sc_metrics.get("cvar_95_pct"), suffix="%", decimals=2),
                _fmt(_sc_metrics.get("max_drawdown_pct"), suffix="%", decimals=1),
                f"+{_delta_vol:.2f}%" if _delta_vol >= 0 else f"{_delta_vol:.2f}%",
            ])
        if len(stress_data) > 1:
            tbl_s = Table(stress_data, colWidths=[5.5 * cm, 3 * cm, 3 * cm, 3 * cm, 3.5 * cm, 3 * cm])
            tbl_s.setStyle(_table_style(len(stress_data)))
            story.append(tbl_s)
            story.append(Paragraph(
                "Crisis: ρ=1.0 (full contagion).  Moderate: ρ=0.70 (risk-off elevated correlation).",
                styles["footer"],
            ))
            story.append(Spacer(1, 10))

    # ── Footer ──
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Paragraph(
        "RWA Infinity Model  |  For informational purposes only. Not financial advice.",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()


# ─── Arbitrage Report ─────────────────────────────────────────────────────────

def generate_arb_pdf(opportunities: list) -> bytes:
    """
    Generate an arbitrage opportunities report PDF.

    Args:
        opportunities: list of arb dicts from run_full_arb_scan()

    Returns:
        Raw PDF bytes.
    """
    if not _REPORTLAB:
        raise ImportError("reportlab is not installed — pip install reportlab")

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = _styles()
    story  = []
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story.append(Paragraph("RWA Infinity Model — Arbitrage Report", styles["title"]))
    story.append(Paragraph(
        f"Generated: {ts}  |  Opportunities found: {len(opportunities)}", styles["subtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=CYAN, spaceAfter=10))

    if not opportunities:
        story.append(Paragraph("No arbitrage opportunities detected in this scan.", styles["body"]))
        doc.build(story)
        return buf.getvalue()

    # Summary counts — arb dicts use "signal" key
    extreme = [o for o in opportunities if o.get("signal") == "EXTREME_ARB"]
    strong  = [o for o in opportunities if o.get("signal") == "STRONG_ARB"]
    regular = [o for o in opportunities if o.get("signal") == "ARB"]

    story.append(Paragraph("Signal Summary", styles["section"]))
    sum_data = [
        ["Signal Level", "Count"],
        ["EXTREME_ARB",  str(len(extreme))],
        ["STRONG_ARB",   str(len(strong))],
        ["ARB",          str(len(regular))],
        ["Total",        str(len(opportunities))],
    ]
    tbl = Table(sum_data, colWidths=[5 * cm, 3 * cm])
    tbl.setStyle(_table_style(len(sum_data)))
    story.append(tbl)
    story.append(Spacer(1, 12))

    # Main opportunities table
    story.append(Paragraph("Opportunities", styles["section"]))
    headers = ["Type", "Asset A", "Asset B", "Signal", "Net Spread%", "Min Capital", "Notes"]
    col_w   = [3.5, 4.0, 4.0, 2.5, 2.5, 3.0, 8.0]
    col_w_cm = [w * cm for w in col_w]

    rows = [headers]
    sorted_opps = sorted(
        opportunities,
        key=lambda o: (
            {"EXTREME_ARB": 3, "STRONG_ARB": 2, "ARB": 1}.get(o.get("signal", ""), 0),
            o.get("net_spread_pct") or o.get("net_profit_pct") or 0,
        ),
        reverse=True,
    )
    for o in sorted_opps:
        net = o.get("net_spread_pct") or o.get("net_profit_pct") or 0
        rows.append([
            (o.get("type") or o.get("arb_type") or "")[:16],
            (o.get("asset_a_name") or o.get("asset_a") or o.get("protocol_a") or "?")[:20],
            (o.get("asset_b_name") or o.get("asset_b") or o.get("protocol_b") or "?")[:20],
            o.get("signal", "ARB"),
            _fmt(net, suffix="%", decimals=2),
            _fmt(o.get("min_capital_usd") or o.get("min_size_usd"), prefix="$", decimals=0)
                if (o.get("min_capital_usd") or o.get("min_size_usd")) else "N/A",
            (o.get("notes") or o.get("rationale") or "")[:60],
        ])

    tbl2 = Table(rows, colWidths=col_w_cm)
    style2 = _table_style(len(rows))
    # Color signal level column
    _SIG_COLORS = {"EXTREME_ARB": "#ffd6d6", "STRONG_ARB": "#fff9e6", "ARB": "#e6f9f3"}
    for i, o in enumerate(sorted_opps, start=1):
        bg = _SIG_COLORS.get(o.get("signal", ""), "#f5f5f5")
        style2.add("BACKGROUND", (3, i), (3, i), colors.HexColor(bg))
    tbl2.setStyle(style2)
    story.append(tbl2)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Paragraph(
        "RWA Infinity Model  |  For informational purposes only. Not financial advice.",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()
