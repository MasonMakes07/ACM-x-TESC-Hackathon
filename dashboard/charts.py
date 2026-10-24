"""Plotly charts for observation and anomaly series.

Owner: Person 3 (Product & Dashboard).
"""

from datetime import date
from html import escape

import pandas as pd
import plotly.graph_objects as go

from schemas.anomaly import AnomalyRecord

LINE_COLOR = "#5CC8FF"
ANOMALY_COLOR = "#FF6B6B"
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
    if replay_until is None:
        return series
    return series[series["date"] <= pd.Timestamp(replay_until)]


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
    if not plotted["date"].min() <= observed_at <= plotted["date"].max():
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
    plotted = _replay_rows(series, replay_until).dropna(subset=["date"])
    if plotted.empty:
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
    if anomaly is not None:
        _add_anomaly_marker(figure, plotted, anomaly)
    figure.update_layout(title=title, yaxis_title=unit, hovermode="closest")
    return apply_dark_layout(figure)
