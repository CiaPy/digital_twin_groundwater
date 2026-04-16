"""
pdf_report.py
─────────────
Groundwater Digital Twin — PDF Report Generator
Report is built around the live stop point (or end of live if no stop occurred).
Tables are rendered in landscape orientation.
"""

import io
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from reportlab.lib.pagesizes import A4, landscape, A3
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    HRFlowable, PageBreak, NextPageTemplate, PageTemplate, Frame,
    KeepTogether
)
from reportlab.platypus.doctemplate import BaseDocTemplate


# ── COLORS ─────────────────────────────────────────────────────────────────
DARK    = colors.HexColor("#1a2233")
BLUE    = colors.HexColor("#1a56db")
MUTED   = colors.HexColor("#64748b")
BORDER  = colors.HexColor("#d0d9e8")
GREEN   = colors.HexColor("#16a34a")
RED     = colors.HexColor("#dc2626")
ORANGE  = colors.HexColor("#e8572a")
BG_LIGHT = colors.HexColor("#f4f7fb")
BG_WHITE = colors.white
HEADER_BG = colors.HexColor("#1a2233")

SC_COLORS = {"dry": "#94a3b8", "medium": "#f59e0b", "wet": "#34d399"}

PLOT_LAYOUT = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#f8fafd",
    font=dict(family="Arial", color="#1a2233", size=12),
    xaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    yaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    margin=dict(l=50, r=30, t=55, b=45),
    legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#d0d9e8", borderwidth=1)
)


# ── STYLES ──────────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle("cover_title", parent=base["Title"],
            fontSize=30, textColor=DARK, leading=36, alignment=TA_CENTER, spaceAfter=8),
        "cover_sub": ParagraphStyle("cover_sub", parent=base["Normal"],
            fontSize=14, textColor=MUTED, alignment=TA_CENTER, spaceAfter=6),
        "cover_date": ParagraphStyle("cover_date", parent=base["Normal"],
            fontSize=11, textColor=BLUE, alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", parent=base["Heading1"],
            fontSize=15, textColor=DARK, leading=20, spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"],
            fontSize=12, textColor=BLUE, leading=15, spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("body", parent=base["Normal"],
            fontSize=10, textColor=DARK, leading=15, spaceAfter=6),
        "caption": ParagraphStyle("caption", parent=base["Normal"],
            fontSize=9, textColor=MUTED, alignment=TA_CENTER, spaceAfter=10, spaceBefore=3),
        "kpi_label": ParagraphStyle("kpi_label", parent=base["Normal"],
            fontSize=9, textColor=MUTED, alignment=TA_CENTER, spaceAfter=2),
        "kpi_value": ParagraphStyle("kpi_value", parent=base["Normal"],
            fontSize=15, textColor=DARK, alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "kpi_value_green": ParagraphStyle("kpi_value_green", parent=base["Normal"],
            fontSize=15, textColor=GREEN, alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "kpi_value_red": ParagraphStyle("kpi_value_red", parent=base["Normal"],
            fontSize=15, textColor=RED, alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "alert_ok": ParagraphStyle("alert_ok", parent=base["Normal"],
            fontSize=10, textColor=GREEN),
        "alert_warn": ParagraphStyle("alert_warn", parent=base["Normal"],
            fontSize=10, textColor=RED),
        "th": ParagraphStyle("th", parent=base["Normal"],
            fontSize=9, textColor=BG_WHITE, alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "td": ParagraphStyle("td", parent=base["Normal"],
            fontSize=9, textColor=DARK, alignment=TA_CENTER),
        "td_left": ParagraphStyle("td_left", parent=base["Normal"],
            fontSize=9, textColor=DARK, alignment=TA_LEFT),
    }


# ── HELPERS ─────────────────────────────────────────────────────────────────
def _fig_png(fig, width=720, height=340):
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    buf = io.BytesIO(img_bytes)
    ratio = height / width
    img_w = 17 * cm
    return Image(buf, width=img_w, height=img_w * ratio)


def _fig_png_wide(fig, width=1000, height=360):
    """Wider figure for landscape pages."""
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    buf = io.BytesIO(img_bytes)
    ratio = height / width
    img_w = 25 * cm
    return Image(buf, width=img_w, height=img_w * ratio)


def _apply(fig):
    fig.update_layout(**PLOT_LAYOUT)
    return fig


def _threshold_line(fig, thr, row=None, col=None):
    kwargs = dict(y=thr, line_dash="dash", line_color="#ef4444", line_width=1.5,
                  annotation_text=f"Threshold {thr:.1f} m",
                  annotation_font=dict(color="#ef4444", size=10),
                  annotation_position="top left")
    if row:
        kwargs.update(row=row, col=col)
    fig.add_hline(**kwargs)
    return fig


def _kpi_row(data: dict, styles, page_width=17*cm):
    n = len(data)
    col_w = page_width / n
    headers = [Paragraph(k, styles["kpi_label"]) for k in data]
    values  = []
    for k, (v, color_key) in data.items():
        style_key = {"green": "kpi_value_green", "red": "kpi_value_red"}.get(color_key, "kpi_value")
        values.append(Paragraph(v, styles[style_key]))
    t = Table([headers, values], colWidths=[col_w]*n)
    t.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",  (0,0), (-1,-1), 0.5, BORDER),
        ("BACKGROUND", (0,0), (-1,0),  BG_LIGHT),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    return t


def _data_table_landscape(df_in: pd.DataFrame, styles, rows_per_page=35):
    """Split dataframe into chunks, each rendered as a full-width landscape table."""
    col_names = list(df_in.columns)
    n_cols = len(col_names)
    # Landscape A4 usable width
    page_w = 27.7 * cm
    col_w  = page_w / n_cols

    chunks = [df_in.iloc[i:i+rows_per_page] for i in range(0, len(df_in), rows_per_page)]
    tables = []
    for chunk in chunks:
        header_row = [Paragraph(str(c), styles["th"]) for c in col_names]
        data_rows  = []
        for _, row in chunk.iterrows():
            data_rows.append([Paragraph(str(v), styles["td"]) for v in row])
        t = Table([header_row] + data_rows, colWidths=[col_w]*n_cols, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  HEADER_BG),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [BG_WHITE, BG_LIGHT]),
            ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ]))
        tables.append(t)
    return tables


# ── FOOTER / HEADER ─────────────────────────────────────────────────────────
def _make_footer(canvas, doc):
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(1.5*cm, 1.4*cm, w - 1.5*cm, 1.4*cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(1.5*cm, 1.0*cm, "Groundwater Digital Twin — Automated Report — Confidential")
    canvas.drawRightString(w - 1.5*cm, 1.0*cm, f"Page {doc.page}")
    canvas.restoreState()


# ── COVER ───────────────────────────────────────────────────────────────────
def _cover(story, styles, meta):
    story.append(Spacer(1, 2.5*cm))
    story.append(HRFlowable(width="100%", thickness=6, color=ORANGE, spaceAfter=20))
    story.append(Paragraph("Groundwater Digital Twin", styles["cover_title"]))
    story.append(Paragraph("Automated Monitoring &amp; Forecast Report", styles["cover_sub"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Generated on {meta['generated_at']}", styles["cover_date"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Report based on live simulation — "
        f"{'stop point: <b>' + meta['ref_date'] + '</b>' if meta['was_stopped'] else 'end of simulation: <b>' + meta['ref_date'] + '</b>'}",
        styles["cover_date"]
    ))
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=20))

    level_color = "green" if meta['ref_level'] > meta['threshold'] else "red"
    story.append(_kpi_row({
        "Reference Date":     (meta['ref_date'],  None),
        "Water Level":        (f"{meta['ref_level']:.2f} m", level_color),
        "Critical Threshold": (f"{meta['threshold']:.1f} m", None),
        "Pump 1":             (meta['pump1'], "green" if meta['pump1'] == "ON" else "red"),
        "Pump 2":             (meta['pump2'], "green" if meta['pump2'] == "ON" else "red"),
        "Mode":               (meta['mode'],  None),
    }, styles))
    story.append(Spacer(1, 0.5*cm))

    if meta['ref_level'] > meta['threshold']:
        story.append(Paragraph(
            "&#10003;  System status: <b>NORMAL</b> — water level is above the critical threshold at the reference date.",
            styles["alert_ok"]))
    else:
        story.append(Paragraph(
            "&#9888;  System status: <b>WARNING</b> — water level is below the critical threshold at the reference date.",
            styles["alert_warn"]))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "This report was automatically generated by the Groundwater Digital Twin platform. "
        "It includes the live simulation chart up to the reference point, forecast scenarios "
        "projected from that point, the complete historical record, and the full operator action log.",
        styles["body"]
    ))
    story.append(PageBreak())


# ── SECTION 1 : LIVE ────────────────────────────────────────────────────────
def _section_live(story, styles, df, threshold, ref_ts, ref_level, any_pump, was_stopped):
    story.append(Paragraph("1. Live Simulation — Water Level", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8))

    sim_start = pd.Timestamp("2025-01-01")
    sim_end   = sim_start + pd.Timedelta(days=365)
    sim_df    = df[(df["date"] >= sim_start) & (df["date"] <= sim_end)].copy()

    label = f"{'Stop point' if was_stopped else 'End of simulation'}: {ref_ts.strftime('%Y-%m-%d')} — {ref_level:.2f} m"
    story.append(Paragraph(
        f"The chart shows the simulated water level throughout 2025 up to the reference point "
        f"(<b>{label}</b>). Green = pump running above threshold; Red = pump stopped below threshold.",
        styles["body"]
    ))

    sub = sim_df[sim_df["date"] <= ref_ts]
    color_line = "#22c55e" if (ref_level > threshold and any_pump) else "#ef4444"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sim_df["date"], y=sim_df["niveau_nappe"],
        mode="lines", name="Full year (background)",
        line=dict(color="#c0c8d8", width=1.5), opacity=0.4
    ))
    fig.add_trace(go.Scatter(
        x=sub["date"], y=sub["niveau_nappe"],
        mode="lines", name="Simulation",
        line=dict(color=color_line, width=2.5)
    ))
    fig.add_trace(go.Scatter(
        x=[ref_ts], y=[ref_level],
        mode="markers+text",
        marker=dict(size=12, color="#f43f5e", symbol="star"),
        text=[f"  {ref_level:.2f} m"], textposition="top right",
        textfont=dict(color="#f43f5e", size=10),
        name="Stop point" if was_stopped else "End of simulation"
    ))
    _threshold_line(fig, threshold)
    _apply(fig)
    fig.update_layout(
        title=f"Simulated Water Level 2025 — up to {ref_ts.strftime('%Y-%m-%d')}",
        height=340,
        xaxis=dict(range=[sim_df["date"].min(), sim_df["date"].max()])
    )
    story.append(_fig_png(fig))
    story.append(Paragraph(
        f"Figure 1 — Live simulation up to {'stop point' if was_stopped else 'end of simulation'} "
        f"({ref_ts.strftime('%Y-%m-%d')}, level = {ref_level:.2f} m).",
        styles["caption"]
    ))


# ── SECTION 2 : FORECAST ────────────────────────────────────────────────────
def _section_forecast(story, styles, threshold, ref_ts, ref_level):
    story.append(PageBreak())
    story.append(Paragraph("2. Forecast Scenarios from Reference Point", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8))
    story.append(Paragraph(
        f"Three 12-month probabilistic scenarios projected from "
        f"<b>{ref_ts.strftime('%Y-%m-%d')}</b> (level = {ref_level:.2f} m): "
        "<b>Dry</b> (+0.8 m drift, reduced recharge), "
        "<b>Medium</b> (baseline conditions), "
        "<b>Wet</b> (-0.6 m drift, high recharge). "
        "Shaded bands represent the uncertainty envelope widening over time.",
        styles["body"]
    ))

    recompute_dates = pd.date_range(start=ref_ts, periods=365, freq="D")
    n_pts = len(recompute_dates)
    rng   = np.random.default_rng(seed=42)

    fig = go.Figure()
    summary_rows = []

    for sc, annual_drift in [("dry", +0.8), ("medium", 0.0), ("wet", -0.6)]:
        t    = np.linspace(0, 1, n_pts)
        vals = ref_level + annual_drift*t + 0.8*np.sin(2*np.pi*t) + np.cumsum(rng.normal(0,0.08,n_pts))*0.015
        bw   = 0.05 + 0.7*t
        dl   = list(recompute_dates)

        fig.add_trace(go.Scatter(
            x=dl + dl[::-1], y=list(vals+bw) + list((vals-bw)[::-1]),
            fill="toself", fillcolor=SC_COLORS[sc],
            opacity=0.15, line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=recompute_dates, y=vals,
            mode="lines", name=sc.capitalize(),
            line=dict(color=SC_COLORS[sc], width=2.5)
        ))
        days_below = int((vals < threshold).sum())
        summary_rows.append({
            "Scenario":            sc.capitalize(),
            "Start Level (m)":     f"{ref_level:.2f}",
            "End Level (m)":       f"{vals[-1]:.2f}",
            "Delta (m)":           f"{vals[-1]-ref_level:+.2f}",
            "Min (m)":             f"{vals.min():.2f}",
            "Max (m)":             f"{vals.max():.2f}",
            "Days below threshold":str(days_below),
            "% Critical":          f"{days_below/n_pts*100:.1f}%",
        })

    fig.add_trace(go.Scatter(
        x=[ref_ts], y=[ref_level], mode="markers+text",
        marker=dict(size=14, color="#f43f5e", symbol="star"),
        text=[f"  {ref_level:.2f} m"], textposition="middle right",
        textfont=dict(color="#f43f5e", size=11), name="Reference point"
    ))
    fig.add_shape(type="line",
        x0=str(ref_ts.date()), x1=str(ref_ts.date()), y0=0, y1=1,
        xref="x", yref="paper", line=dict(color="#f43f5e", width=1.5, dash="dot"))
    _threshold_line(fig, threshold)
    _apply(fig)
    fig.update_layout(
        title=f"12-month Forecast from {ref_ts.strftime('%Y-%m-%d')}",
        height=340,
        xaxis=dict(range=[str(ref_ts.date()), str(recompute_dates[-1].date())])
    )
    story.append(_fig_png(fig))
    story.append(Paragraph(
        f"Figure 2 — 12-month forecast scenarios from reference point ({ref_ts.strftime('%Y-%m-%d')}).",
        styles["caption"]
    ))

    # Scenario summary table (compact, portrait is fine here)
    story.append(Paragraph("Scenario Summary", styles["h2"]))
    sc_df = pd.DataFrame(summary_rows)
    n_cols = len(sc_df.columns)
    col_w  = 17*cm / n_cols
    header_row = [Paragraph(c, styles["th"]) for c in sc_df.columns]
    data_rows  = []
    for _, row in sc_df.iterrows():
        data_rows.append([Paragraph(str(v), styles["td"]) for v in row])
    t = Table([header_row]+data_rows, colWidths=[col_w]*n_cols)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  HEADER_BG),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [BG_WHITE, BG_LIGHT]),
        ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 5), ("RIGHTPADDING",  (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Paragraph("Table 1 — End-of-period statistics for each forecast scenario.", styles["caption"]))


# ── SECTION 3 : HISTORY (LANDSCAPE) ────────────────────────────────────────
def _section_history_portrait(story, styles, df, threshold, ref_ts):
    story.append(PageBreak())
    story.append(Paragraph("3. Historical Record up to Reference Point", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8))

    filtered = df[df["date"] <= ref_ts].copy()
    story.append(Paragraph(
        f"Historical data from <b>{filtered['date'].min().strftime('%Y-%m-%d')}</b> to "
        f"<b>{ref_ts.strftime('%Y-%m-%d')}</b> — "
        f"<b>{len(filtered):,} daily records</b>. "
        "Upper panel: piezometric water level with critical threshold. "
        "Lower panel: daily rainfall (mm).",
        styles["body"]
    ))

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.68, 0.32],
                        subplot_titles=["Water Level (m)", "Rainfall (mm)"],
                        vertical_spacing=0.08)
    fig.add_trace(go.Scatter(
        x=filtered["date"], y=filtered["niveau_nappe"],
        mode="lines", name="Water Level", line=dict(color="#388bfd", width=1.5)
    ), row=1, col=1)
    fig.add_hline(y=threshold, line_dash="dash", line_color="#ef4444",
                  annotation_text="Threshold", annotation_position="top left", row=1, col=1)
    fig.add_trace(go.Scatter(
        x=[ref_ts], y=[float(filtered["niveau_nappe"].iloc[-1])],
        mode="markers", marker=dict(size=10, color="#f43f5e", symbol="star"),
        name="Reference point"
    ), row=1, col=1)
    if "pluie_mm" in filtered.columns:
        fig.add_trace(go.Bar(
            x=filtered["date"], y=filtered["pluie_mm"],
            name="Rainfall", marker_color="#34d399", opacity=0.6
        ), row=2, col=1)
    layout_kw = {k: v for k, v in PLOT_LAYOUT.items() if k not in ("xaxis","yaxis")}
    fig.update_layout(height=400, **layout_kw)
    fig.update_xaxes(gridcolor="#e2e8f0", linecolor="#cbd5e1")
    fig.update_yaxes(gridcolor="#e2e8f0", linecolor="#cbd5e1")

    story.append(_fig_png(fig, width=720, height=400))
    story.append(Paragraph(
        "Figure 3 — Full historical water level and daily rainfall up to reference point.",
        styles["caption"]
    ))

    # Stats KPIs
    days_below = int((filtered["niveau_nappe"] < threshold).sum())
    pct = days_below / len(filtered) * 100 if len(filtered) > 0 else 0
    story.append(_kpi_row({
        "Min Level":            (f"{filtered['niveau_nappe'].min():.2f} m", None),
        "Max Level":            (f"{filtered['niveau_nappe'].max():.2f} m", None),
        "Mean Level":           (f"{filtered['niveau_nappe'].mean():.2f} m", None),
        "Days below threshold": (str(days_below), "red" if days_below > 0 else "green"),
        "% Critical time":      (f"{pct:.1f}%", "red" if pct > 5 else "green"),
    }, styles))


def _section_history_landscape(story, styles, control_log):
    """Control Action Log in landscape orientation."""
    if not control_log:
        return

    story.append(NextPageTemplate("landscape"))
    story.append(PageBreak())

    story.append(Paragraph("Historical Data Table — Control Action Log", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8))
    story.append(Paragraph(
        "Complete record of all operator actions during the session, "
        "including simulation starts/stops, pump commands, and mode changes. "
        "Sorted most recent first.",
        styles["body"]
    ))

    log_df = pd.DataFrame(control_log[::-1]).reset_index(drop=True)
    if "level" in log_df.columns:
        log_df["level"] = log_df["level"].apply(
            lambda x: f"{float(x):.2f} m" if x is not None else "—"
        )
    log_df.columns = [c.replace("_", " ").title() for c in log_df.columns]

    tables = _data_table_landscape(log_df, styles, rows_per_page=40)
    for i, t in enumerate(tables):
        story.append(t)
        story.append(Paragraph(
            f"Table 2.{i+1} — Control action log (page {i+1} of {len(tables)}).",
            styles["caption"]
        ))
        if i < len(tables) - 1:
            story.append(PageBreak())

    story.append(NextPageTemplate("portrait"))
    story.append(PageBreak())


# ── SECTION 4 : ACTION LOG (LANDSCAPE) ─────────────────────────────────────
def _section_log(story, styles, control_log):
    if not control_log:
        return

    story.append(NextPageTemplate("landscape"))
    story.append(PageBreak())

    story.append(Paragraph("4. Operator Action Log", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8))
    story.append(Paragraph(
        "All actions recorded during the session: simulation starts/stops, "
        "pump commands, and mode changes. Sorted most recent first.",
        styles["body"]
    ))

    log_df = pd.DataFrame(control_log[::-1]).reset_index(drop=True)
    if "level" in log_df.columns:
        log_df["level"] = log_df["level"].apply(
            lambda x: f"{float(x):.2f} m" if x is not None else "—"
        )
    log_df.columns = [c.replace("_", " ").title() for c in log_df.columns]

    tables = _data_table_landscape(log_df, styles, rows_per_page=45)
    for i, t in enumerate(tables):
        story.append(t)
        story.append(Paragraph(
            f"Table 3.{i+1} — Operator action log (page {i+1} of {len(tables)}).",
            styles["caption"]
        ))
        if i < len(tables) - 1:
            story.append(PageBreak())

    story.append(NextPageTemplate("portrait"))


# ── MAIN ────────────────────────────────────────────────────────────────────
def generate_pdf_report(
    df: pd.DataFrame,
    fc: pd.DataFrame,
    threshold: float,
    pump1: bool,
    pump2: bool,
    mode: str,
    control_log: list,
    live_stopped_at=None,
    live_stopped_level=None,
) -> bytes:
    buf = io.BytesIO()

    # ── Determine reference point ──
    # Use stop point if available, otherwise use last point of simulation data
    sim_start = pd.Timestamp("2025-01-01")
    sim_end   = sim_start + pd.Timedelta(days=365)
    sim_df    = df[(df["date"] >= sim_start) & (df["date"] <= sim_end)].copy()

    if live_stopped_at is not None and live_stopped_level is not None:
        ref_ts    = pd.Timestamp(live_stopped_at)
        ref_level = float(live_stopped_level)
        was_stopped = True
    else:
        # End of simulation
        ref_ts    = sim_df["date"].max() if not sim_df.empty else df["date"].max()
        ref_level = float(sim_df["niveau_nappe"].iloc[-1]) if not sim_df.empty else float(df["niveau_nappe"].iloc[-1])
        was_stopped = False

    any_pump = pump1 or pump2

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ref_date":     ref_ts.strftime("%Y-%m-%d"),
        "ref_level":    ref_level,
        "threshold":    threshold,
        "pump1":        "ON" if pump1 else "OFF",
        "pump2":        "ON" if pump2 else "OFF",
        "mode":         mode,
        "was_stopped":  was_stopped,
    }

    # ── Page templates ──
    portrait_frame  = Frame(1.5*cm, 2*cm, 18*cm, 25*cm, id="portrait_frame")
    landscape_frame = Frame(1.5*cm, 2*cm, 27.7*cm, 18*cm, id="landscape_frame")

    portrait_tpl  = PageTemplate(id="portrait",  frames=[portrait_frame],
                                  pagesize=A4, onPage=_make_footer)
    landscape_tpl = PageTemplate(id="landscape", frames=[landscape_frame],
                                  pagesize=landscape(A4), onPage=_make_footer)

    doc = BaseDocTemplate(
        buf,
        pageTemplates=[portrait_tpl, landscape_tpl],
        title="Groundwater Digital Twin Report",
        author="Digital Twin System",
    )

    story = []
    _cover(story, styles_obj := _styles(), meta)
    _section_live(story, styles_obj, df, threshold, ref_ts, ref_level, any_pump, was_stopped)
    _section_forecast(story, styles_obj, threshold, ref_ts, ref_level)
    _section_history_portrait(story, styles_obj, df, threshold, ref_ts)
    _section_history_landscape(story, styles_obj, df, threshold, ref_ts)

    doc.build(story)
    return buf.getvalue()
