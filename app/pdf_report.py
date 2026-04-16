"""
pdf_report.py
─────────────
Groundwater Digital Twin — PDF Report Generator
Usage: call generate_pdf_report(...) and get back raw bytes to pass to st.download_button.
"""

import io
import tempfile
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)


# ── THEME ──────────────────────────────────────────────────────────────────
BLUE       = colors.HexColor("#1a56db")
DARK       = colors.HexColor("#1a2233")
MUTED      = colors.HexColor("#64748b")
BORDER     = colors.HexColor("#d0d9e8")
GREEN      = colors.HexColor("#0f7a35")
RED        = colors.HexColor("#dc2626")
AMBER      = colors.HexColor("#d97706")
BG_LIGHT   = colors.HexColor("#f4f7fb")
BG_WHITE   = colors.white
ORANGE     = colors.HexColor("#e8572a")

PLOT_LAYOUT = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#f8fafd",
    font=dict(family="Arial", color="#1a2233", size=11),
    xaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    yaxis=dict(gridcolor="#e2e8f0", zeroline=False, showline=True, linecolor="#cbd5e1"),
    margin=dict(l=40, r=30, t=50, b=40),
    legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#d0d9e8", borderwidth=1)
)

SC_COLORS = {"dry": "#94a3b8", "medium": "#f59e0b", "wet": "#34d399"}


# ── HELPERS ────────────────────────────────────────────────────────────────
def _fig_to_image(fig, width=700, height=320):
    """Render a Plotly figure to a ReportLab Image flowable."""
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    buf = io.BytesIO(img_bytes)
    return Image(buf, width=17*cm, height=17*cm * height/width)


def _add_threshold(fig, thr):
    fig.add_hline(
        y=thr, line_dash="dash", line_color="#ef4444", line_width=1.5,
        annotation_text=f"Threshold {thr:.1f} m",
        annotation_font=dict(color="#ef4444", size=10),
        annotation_position="top left"
    )
    return fig


def _apply_theme(fig):
    fig.update_layout(**PLOT_LAYOUT)
    return fig


def _styles():
    base = getSampleStyleSheet()
    custom = {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"],
            fontSize=28, textColor=DARK, leading=34,
            alignment=TA_CENTER, spaceAfter=6
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"],
            fontSize=13, textColor=MUTED, alignment=TA_CENTER, spaceAfter=4
        ),
        "cover_date": ParagraphStyle(
            "cover_date", parent=base["Normal"],
            fontSize=11, textColor=BLUE, alignment=TA_CENTER
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontSize=16, textColor=DARK, leading=20,
            spaceBefore=18, spaceAfter=8,
            borderPad=0
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontSize=13, textColor=BLUE, leading=16,
            spaceBefore=12, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=10, textColor=DARK, leading=15, spaceAfter=6
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"],
            fontSize=9, textColor=MUTED, alignment=TA_CENTER,
            spaceAfter=10, spaceBefore=4
        ),
        "table_header": ParagraphStyle(
            "table_header", parent=base["Normal"],
            fontSize=9, textColor=BG_WHITE, alignment=TA_CENTER
        ),
        "table_cell": ParagraphStyle(
            "table_cell", parent=base["Normal"],
            fontSize=9, textColor=DARK, alignment=TA_CENTER
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"],
            fontSize=9, textColor=MUTED, alignment=TA_CENTER, spaceAfter=2
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", parent=base["Normal"],
            fontSize=16, textColor=DARK, alignment=TA_CENTER,
            fontName="Helvetica-Bold"
        ),
        "alert_ok": ParagraphStyle(
            "alert_ok", parent=base["Normal"],
            fontSize=10, textColor=GREEN, leading=14
        ),
        "alert_warn": ParagraphStyle(
            "alert_warn", parent=base["Normal"],
            fontSize=10, textColor=RED, leading=14
        ),
    }
    return {**{k: base[k] for k in base.byName}, **custom}


# ── KPI TABLE ──────────────────────────────────────────────────────────────
def _kpi_table(data: dict, styles):
    """Build a horizontal KPI summary row."""
    headers = [Paragraph(k, styles["kpi_label"]) for k in data.keys()]
    values  = [Paragraph(v, styles["kpi_value"]) for v in data.values()]
    t = Table([headers, values], colWidths=[17*cm / len(data)] * len(data))
    t.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",  (0,0), (-1,-1), 0.5, BORDER),
        ("BACKGROUND", (0,0), (-1,0),  BG_LIGHT),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1), (-1,1), [BG_WHITE]),
    ]))
    return t


# ── DATA TABLE ─────────────────────────────────────────────────────────────
def _data_table(df_table: pd.DataFrame, styles, max_rows=30):
    """Convert a DataFrame to a styled ReportLab Table."""
    df_table = df_table.head(max_rows).copy()
    col_names = list(df_table.columns)
    n_cols = len(col_names)
    col_w  = 17*cm / n_cols

    header_row = [Paragraph(str(c), styles["table_header"]) for c in col_names]
    data_rows  = []
    for _, row in df_table.iterrows():
        data_rows.append([Paragraph(str(v), styles["table_cell"]) for v in row])

    table_data = [header_row] + data_rows
    t = Table(table_data, colWidths=[col_w]*n_cols, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#1a2233")),
        ("TEXTCOLOR",     (0,0), (-1,0),  BG_WHITE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [BG_WHITE, BG_LIGHT]),
        ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ]))
    return t


# ── COVER PAGE ─────────────────────────────────────────────────────────────
def _cover(story, styles, meta: dict):
    story.append(Spacer(1, 3*cm))

    # Orange accent bar
    story.append(HRFlowable(width="100%", thickness=6, color=ORANGE, spaceAfter=24))

    story.append(Paragraph("Groundwater Digital Twin", styles["cover_title"]))
    story.append(Paragraph("Automated Monitoring &amp; Forecast Report", styles["cover_sub"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"Generated on {meta['generated_at']}", styles["cover_date"]
    ))
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=24))

    # Summary KPIs
    story.append(_kpi_table({
        "Current Level": f"{meta['current_level']:.2f} m",
        "Critical Threshold": f"{meta['threshold']:.1f} m",
        "Pump 1": meta['pump1'],
        "Pump 2": meta['pump2'],
        "Mode": meta['mode'],
    }, styles))
    story.append(Spacer(1, 0.5*cm))

    # Status line
    if meta['current_level'] > meta['threshold']:
        status_txt = "&#10003; System status: <b>NORMAL</b> — water level is above the critical threshold."
        story.append(Paragraph(status_txt, styles["alert_ok"]))
    else:
        status_txt = "&#9888; System status: <b>WARNING</b> — water level is below the critical threshold."
        story.append(Paragraph(status_txt, styles["alert_warn"]))

    story.append(PageBreak())


# ── SECTION 1 : LIVE SIMULATION ────────────────────────────────────────────
def _section_live(story, styles, df, threshold, stopped_at, stopped_level, any_pump_active):
    story.append(Paragraph("1. Live Simulation — Water Level (2025)", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=10))

    sim_start = pd.Timestamp("2025-01-01")
    sim_end   = sim_start + pd.Timedelta(days=365)
    sim_df    = df[(df["date"] >= sim_start) & (df["date"] <= sim_end)].copy()

    story.append(Paragraph(
        "The chart below shows the simulated water level throughout 2025. "
        "The green segment indicates periods when the pump was running (level above threshold); "
        "red indicates pump-stopped periods. The amber marker shows the last recorded position.",
        styles["body"]
    ))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sim_df["date"], y=sim_df["niveau_nappe"],
        mode="lines", name="Full year",
        line=dict(color="#c0c8d8", width=1.5), opacity=0.5
    ))

    if stopped_at:
        stopped_ts = pd.Timestamp(stopped_at)
        sub = sim_df[sim_df["date"] <= stopped_ts]
        color_line = "#22c55e" if (stopped_level > threshold and any_pump_active) else "#ef4444"
        fig.add_trace(go.Scatter(
            x=sub["date"], y=sub["niveau_nappe"],
            mode="lines", name="Simulation",
            line=dict(color=color_line, width=2.5)
        ))
        fig.add_trace(go.Scatter(
            x=[stopped_ts], y=[stopped_level],
            mode="markers+text",
            marker=dict(size=10, color="#f59e0b", symbol="circle"),
            text=[f"{stopped_level:.2f} m"], textposition="top center",
            textfont=dict(color="#d97706", size=10), name="Stop point"
        ))

    _add_threshold(fig, threshold)
    _apply_theme(fig)
    fig.update_layout(title="Simulated Water Level — 2025", height=320)

    story.append(_fig_to_image(fig, width=700, height=320))
    story.append(Paragraph("Figure 1 — Live simulation of piezometric water level for 2025.", styles["caption"]))

    if stopped_at:
        story.append(Paragraph(
            f"Simulation stopped at <b>{pd.Timestamp(stopped_at).strftime('%Y-%m-%d')}</b> "
            f"with a recorded level of <b>{stopped_level:.2f} m</b>.",
            styles["body"]
        ))


# ── SECTION 2 : FORECASTING ────────────────────────────────────────────────
def _section_forecast(story, styles, df, fc, threshold, stopped_at, stopped_level):
    story.append(PageBreak())
    story.append(Paragraph("2. Forecast Scenarios", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=10))

    story.append(Paragraph(
        "Three probabilistic scenarios are projected over a 12-month horizon from the stop point: "
        "<b>Dry</b> (reduced recharge, rising trend), <b>Medium</b> (baseline conditions), "
        "and <b>Wet</b> (high recharge, falling trend). Shaded bands represent the uncertainty envelope.",
        styles["body"]
    ))

    fig_bot = go.Figure()

    if stopped_at:
        extra_ts = pd.Timestamp(stopped_at)
        extra_lv = float(stopped_level)
        recompute_dates = pd.date_range(start=extra_ts, periods=365, freq="D")
        n_pts = len(recompute_dates)
        rng   = np.random.default_rng(seed=42)

        for sc, annual_drift in [("dry", +0.8), ("medium", 0.0), ("wet", -0.6)]:
            t    = np.linspace(0, 1, n_pts)
            vals = extra_lv + annual_drift*t + 0.8*np.sin(2*np.pi*t) + np.cumsum(rng.normal(0,0.08,n_pts))*0.015
            bw   = 0.05 + 0.7*t
            dl   = list(recompute_dates)
            fig_bot.add_trace(go.Scatter(
                x=dl + dl[::-1], y=list(vals+bw) + list((vals-bw)[::-1]),
                fill="toself", fillcolor=SC_COLORS[sc],
                opacity=0.15, line=dict(width=0), showlegend=False, hoverinfo="skip"
            ))
            fig_bot.add_trace(go.Scatter(
                x=recompute_dates, y=vals,
                mode="lines", name=sc.capitalize(),
                line=dict(color=SC_COLORS[sc], width=2.5)
            ))

        fig_bot.add_trace(go.Scatter(
            x=[extra_ts], y=[extra_lv], mode="markers+text",
            marker=dict(size=14, color="#f43f5e", symbol="star"),
            text=[f"  {extra_lv:.2f} m"], textposition="middle right",
            textfont=dict(color="#f43f5e", size=11), name="Stop point"
        ))
        fig_bot.update_xaxes(range=[str(extra_ts.date()), str(recompute_dates[-1].date())])
        fig_bot.update_layout(title="Forecast from Stop Point — 12-month horizon", height=320)
    else:
        last_hist_date = df["date"].max()
        fc_future = fc[fc["date"] > last_hist_date].copy()
        for sc in ["dry", "medium", "wet"]:
            sc_data = fc_future[fc_future["scenario"] == sc].copy().sort_values("date")
            if not sc_data.empty:
                dl = list(sc_data["date"]); vl = list(sc_data["niveau_nappe"])
                fig_bot.add_trace(go.Scatter(
                    x=dl+dl[::-1], y=[v+0.4 for v in vl]+[v-0.4 for v in vl[::-1]],
                    fill="toself", fillcolor=SC_COLORS[sc],
                    opacity=0.12, line=dict(width=0), showlegend=False
                ))
                fig_bot.add_trace(go.Scatter(
                    x=sc_data["date"], y=sc_data["niveau_nappe"],
                    mode="lines", name=sc.capitalize(),
                    line=dict(color=SC_COLORS[sc], width=2)
                ))
        fig_bot.update_layout(title="Forecast Scenarios (from end of history)", height=320)

    _add_threshold(fig_bot, threshold)
    _apply_theme(fig_bot)

    story.append(_fig_to_image(fig_bot, width=700, height=320))
    story.append(Paragraph("Figure 2 — 12-month forecast scenarios from the simulation stop point.", styles["caption"]))

    # End-of-period summary table
    if stopped_at:
        extra_ts = pd.Timestamp(stopped_at)
        extra_lv = float(stopped_level)
        recompute_dates = pd.date_range(start=extra_ts, periods=365, freq="D")
        n_pts = len(recompute_dates)
        rng   = np.random.default_rng(seed=42)
        summary_rows = []
        for sc, annual_drift in [("dry", +0.8), ("medium", 0.0), ("wet", -0.6)]:
            t    = np.linspace(0, 1, n_pts)
            vals = extra_lv + annual_drift*t + 0.8*np.sin(2*np.pi*t) + np.cumsum(rng.normal(0,0.08,n_pts))*0.015
            end_val  = vals[-1]
            delta    = end_val - extra_lv
            min_val  = vals.min()
            max_val  = vals.max()
            days_below = int((vals < threshold).sum())
            summary_rows.append({
                "Scenario": sc.capitalize(),
                "End Level (m)": f"{end_val:.2f}",
                "Delta vs Start (m)": f"{delta:+.2f}",
                "Min (m)": f"{min_val:.2f}",
                "Max (m)": f"{max_val:.2f}",
                "Days below threshold": str(days_below),
            })
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Scenario Summary — End of 12-month period", styles["h2"]))
        story.append(_data_table(pd.DataFrame(summary_rows), styles, max_rows=10))
        story.append(Paragraph("Table 1 — End-of-period statistics for each forecast scenario.", styles["caption"]))


# ── SECTION 3 : HISTORY ────────────────────────────────────────────────────
def _section_history(story, styles, df, threshold, stopped_at):
    story.append(PageBreak())
    story.append(Paragraph("3. Full Historical Record", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=10))

    hist_max = (
        pd.Timestamp(stopped_at).date()
        if stopped_at else df["date"].max().date()
    )
    filtered = df[df["date"] <= pd.Timestamp(hist_max)].copy()

    story.append(Paragraph(
        f"Historical data spanning <b>{filtered['date'].min().strftime('%Y-%m-%d')}</b> to "
        f"<b>{hist_max}</b> — a total of <b>{len(filtered):,} daily records</b>. "
        "The upper panel shows the piezometric water level with the critical threshold; "
        "the lower panel shows daily rainfall.",
        styles["body"]
    ))

    # Historical chart
    fig_hist = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
        subplot_titles=["Water Level (m)", "Rainfall (mm)"]
    )
    fig_hist.add_trace(go.Scatter(
        x=filtered["date"], y=filtered["niveau_nappe"],
        mode="lines", name="Water Level", line=dict(color="#388bfd", width=1.5)
    ), row=1, col=1)
    fig_hist.add_hline(
        y=threshold, line_dash="dash", line_color="#ef4444",
        annotation_text="Threshold", annotation_position="top left",
        row=1, col=1
    )
    if stopped_at:
        stop_ts  = pd.Timestamp(stopped_at)
        stop_lvl = float(df[df["date"] <= stop_ts]["niveau_nappe"].iloc[-1]) if not df[df["date"] <= stop_ts].empty else threshold
        fig_hist.add_trace(go.Scatter(
            x=[stop_ts], y=[stop_lvl], mode="markers",
            marker=dict(size=10, color="#f43f5e", symbol="star"),
            name="Stop point"
        ), row=1, col=1)

    if "pluie_mm" in filtered.columns:
        fig_hist.add_trace(go.Bar(
            x=filtered["date"], y=filtered["pluie_mm"],
            name="Rainfall", marker_color="#34d399", opacity=0.6
        ), row=2, col=1)

    fig_hist.update_layout(
        height=380,
        **{k: v for k, v in PLOT_LAYOUT.items() if k not in ("xaxis","yaxis")}
    )
    fig_hist.update_xaxes(gridcolor="#e2e8f0", linecolor="#cbd5e1")
    fig_hist.update_yaxes(gridcolor="#e2e8f0", linecolor="#cbd5e1")

    story.append(_fig_to_image(fig_hist, width=700, height=380))
    story.append(Paragraph("Figure 3 — Full historical water level and rainfall record.", styles["caption"]))

    # Stats KPI
    days_below = int((filtered["niveau_nappe"] < threshold).sum())
    pct_crit   = days_below / len(filtered) * 100 if len(filtered) > 0 else 0
    story.append(Spacer(1, 0.3*cm))
    story.append(_kpi_table({
        "Min Level":           f"{filtered['niveau_nappe'].min():.2f} m",
        "Max Level":           f"{filtered['niveau_nappe'].max():.2f} m",
        "Mean Level":          f"{filtered['niveau_nappe'].mean():.2f} m",
        "Days below threshold": str(days_below),
        "% Critical":          f"{pct_crit:.1f}%",
    }, styles))

    # Recent data table (last 30 days)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Recent Data — Last 30 Records", styles["h2"]))
    story.append(Paragraph(
        "The table below shows the 30 most recent daily records including water level, "
        "precipitation, and evapotranspiration.",
        styles["body"]
    ))
    recent = filtered.sort_values("date", ascending=False).head(30).copy()
    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
    recent.columns = [c.replace("_", " ").title() for c in recent.columns]
    for col in recent.select_dtypes(include="float").columns:
        recent[col] = recent[col].round(2).astype(str)
    story.append(_data_table(recent, styles, max_rows=30))
    story.append(Paragraph("Table 2 — 30 most recent daily observations.", styles["caption"]))


# ── SECTION 4 : ACTION LOG ─────────────────────────────────────────────────
def _section_log(story, styles, control_log):
    if not control_log:
        return
    story.append(PageBreak())
    story.append(Paragraph("4. Control Action Log", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=10))
    story.append(Paragraph(
        "All operator actions recorded during the current session, including pump activations, "
        "simulation starts/stops, and mode changes.",
        styles["body"]
    ))
    log_df = pd.DataFrame(control_log)
    log_df = log_df[::-1].reset_index(drop=True)
    if "level" in log_df.columns:
        log_df["level"] = log_df["level"].apply(lambda x: f"{float(x):.2f} m" if x else "—")
    log_df.columns = [c.replace("_", " ").title() for c in log_df.columns]
    story.append(_data_table(log_df, styles, max_rows=50))
    story.append(Paragraph("Table 3 — Full operator action log for this session.", styles["caption"]))


# ── FOOTER ─────────────────────────────────────────────────────────────────
def _footer_canvas(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(2*cm, 1.5*cm, w - 2*cm, 1.5*cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2*cm, 1.1*cm, "Groundwater Digital Twin — Confidential")
    canvas.drawRightString(w - 2*cm, 1.1*cm, f"Page {doc.page}")
    canvas.restoreState()


# ── MAIN ENTRY POINT ───────────────────────────────────────────────────────
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
    """
    Generate the full PDF report and return it as bytes.

    Parameters
    ----------
    df                 : historical daily dataframe (date, niveau_nappe, pluie_mm, etp_mm)
    fc                 : forecast dataframe (date, scenario, niveau_nappe)
    threshold          : critical level in metres
    pump1, pump2       : current pump states
    mode               : 'Automatic' or 'Manual'
    control_log        : list of action dicts
    live_stopped_at    : Timestamp or None
    live_stopped_level : float or None
    """
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2.5*cm,
        title="Groundwater Digital Twin Report",
        author="Digital Twin System"
    )

    styles  = _styles()
    story   = []
    current_level = float(df["niveau_nappe"].iloc[-1])
    any_pump      = pump1 or pump2

    meta = {
        "generated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_level": live_stopped_level if live_stopped_level else current_level,
        "threshold":     threshold,
        "pump1":         "ON" if pump1 else "OFF",
        "pump2":         "ON" if pump2 else "OFF",
        "mode":          mode,
    }

    _cover(story, styles, meta)
    _section_live(story, styles, df, threshold, live_stopped_at, live_stopped_level, any_pump)
    _section_forecast(story, styles, df, fc, threshold, live_stopped_at, live_stopped_level)
    _section_history(story, styles, df, threshold, live_stopped_at)
    _section_log(story, styles, control_log)

    doc.build(story, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    return buf.getvalue()
