"""Plotly charts for observation and anomaly series.

Owner: Person 3 (Product & Dashboard).
"""

from datetime import date
from html import escape

import pandas as pd
import plotly.graph_objects as go

from schemas.anomaly import AnomalyRecord

LINE_COLOR = "#5CC8FF"
ANOMALY_COLOR = "#B8C8D9"
THRESHOLD_COLOR = "#FFD180"
EMPTY_MESSAGE = "No observations in this period"


# Applies the shared dark, transparent styling used by every EarthWatch figure.
def apply_dark_layout(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    return figure


# Returns only the rows on or before the replay date, or every row when it is None.
def _replay_rows(series: pd.DataFrame, replay_until: date | None) -> pd.DataFrame:
    tidy = series.copy()
    tidy["date"] = pd.to_datetime(tidy["date"], errors="coerce", utc=True).dt.tz_convert(None)
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce")
    tidy = tidy.dropna(subset=["date"]).sort_values("date")
    if replay_until is None:
        return tidy
    return tidy[tidy["date"].dt.date <= replay_until]


# Builds a figure with a centered message for when there is nothing to plot.
def _empty_chart(title: str, unit: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=EMPTY_MESSAGE, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font={"size": 16},
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    figure.update_layout(title=title, yaxis_title=unit)
    return apply_dark_layout(figure)


# Adds labelled dashed lines at +threshold and -threshold.
def _add_threshold(figure: go.Figure, threshold: float, unit: str) -> None:
    for level in (threshold, -threshold):
        figure.add_hline(
            y=level, line_dash="dash", line_color=THRESHOLD_COLOR,
            annotation_text=f"Threshold {level:+g} {unit}",
            annotation_position="top left",
        )


# Highlights the anomaly's observation when it falls inside the plotted dates.
def _add_anomaly_marker(
    figure: go.Figure, plotted: pd.DataFrame, anomaly: AnomalyRecord
) -> None:
    observed_at = pd.Timestamp(anomaly.observation_date)
    if plotted.loc[plotted["date"].dt.date == anomaly.observation_date, "value"].dropna().empty:
        return
    figure.add_trace(
        go.Scatter(
            x=[observed_at], y=[anomaly.value], mode="markers", name="Detected anomaly",
            marker={"size": 16, "color": ANOMALY_COLOR, "line": {"width": 2, "color": "white"}},
            hovertemplate=(
                f"%{{x|%Y-%m-%d}}<br>%{{y:.2f}} {escape(anomaly.unit)}"
                f"<br>Source: {escape(anomaly.source)}<extra>Anomaly</extra>"
            ),
        )
    )
    figure.add_annotation(
        x=observed_at, y=anomaly.value, text=f"{anomaly.value:+g} {escape(anomaly.unit)}",
        showarrow=True, arrowhead=2, ay=-40, font={"color": ANOMALY_COLOR},
    )


# Builds a line chart of an observation series with optional replay, threshold and anomaly.
def observation_chart(
    series: pd.DataFrame,
    title: str,
    unit: str,
    anomaly: AnomalyRecord | None = None,
    threshold: float | None = None,
    replay_until: date | None = None,
) -> go.Figure:
    if series.empty:
        return _empty_chart(title, unit)
    plotted = _replay_rows(series, replay_until)
    if plotted.empty or not plotted["value"].notna().any():
        return _empty_chart(title, unit)
    source_line = f"<br>Source: {escape(anomaly.source)}" if anomaly else ""
    figure = go.Figure(
        go.Scatter(
            x=plotted["date"], y=plotted["value"], mode="lines+markers",
            name="Observed", line={"color": LINE_COLOR},
            hovertemplate=(
                f"%{{x|%Y-%m-%d}}<br>%{{y:.2f}} {escape(unit)}{source_line}"
                "<extra></extra>"
            ),
        )
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#8b9bb0")
    if threshold is not None:
        _add_threshold(figure, threshold, unit)
    if anomaly is not None and anomaly.unit == unit:
        _add_anomaly_marker(figure, plotted, anomaly)
    figure.update_layout(title=title, yaxis_title=unit, hovermode="closest")
    return apply_dark_layout(figure)


# Compares anomalies only within the same variable and unit, never across incompatible scales.
def anomaly_comparison_chart(anomalies: list[AnomalyRecord], selected_id: str | None = None) -> go.Figure:
    from plotly.subplots import make_subplots

    if not anomalies:
        return _empty_chart("No anomalies to compare", "")
    groups: dict[tuple[str, str], list[AnomalyRecord]] = {}
    for item in anomalies:
        groups.setdefault((item.variable, item.unit), []).append(item)
    figure = make_subplots(rows=len(groups), cols=1, subplot_titles=[f"{variable.replace('_', ' ')} ({unit})" for variable, unit in groups])
    for row, ((variable, unit), records) in enumerate(groups.items(), 1):
        figure.add_trace(go.Bar(
            x=[f"{item.region} · {item.observation_date}" for item in records], y=[item.value for item in records],
            name=variable.replace("_", " "), marker_color=["#8DDCF0" if item.anomaly_id == selected_id else "#94A3B8" for item in records],
            customdata=[[str(item.observation_date), escape(item.source)] for item in records],
            hovertemplate=f"%{{x}}<br>%{{y:g}} {escape(unit)}<br>Source: %{{customdata[1]}}<extra></extra>",
        ), row=row, col=1)
        figure.update_yaxes(title_text=unit, row=row, col=1)
    figure.update_layout(height=max(280, 260 * len(groups)), showlegend=False)
    return apply_dark_layout(figure)
