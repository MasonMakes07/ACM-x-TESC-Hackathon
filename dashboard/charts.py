"""Plotly charts for observation and anomaly series.

Owner: Person 3 (Product & Dashboard).
"""

from datetime import date
from html import escape
from math import isfinite

import pandas as pd
import plotly.graph_objects as go

from schemas.anomaly import AnomalyRecord

LINE_COLOR = "#67D8E7"
ANOMALY_COLOR = "#FFC46B"
THRESHOLD_COLOR = "#F5A76E"
EMPTY_MESSAGE = "No observations in this period"


# Applies dark, transparent styling to a Plotly figure.
def apply_dark_layout(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 48, "r": 24, "t": 56, "b": 48},
    )
    return figure


# Applies the shared dark styling to an observation figure.
def _styled_figure(title: str, unit: str) -> go.Figure:
    figure = apply_dark_layout(go.Figure())
    figure.update_layout(
        title=title,
        xaxis_title="Observation date",
        yaxis_title=unit,
        hovermode="x unified",
    )
    return figure


# Returns only dated observations visible at the replay date.
def _visible_series(series: pd.DataFrame, replay_until: date | None) -> pd.DataFrame:
    if series.empty:
        return pd.DataFrame(columns=["date", "value"])
    visible = series.loc[:, ["date", "value"]].copy()
    visible["date"] = pd.to_datetime(visible["date"], errors="coerce")
    visible["value"] = pd.to_numeric(visible["value"], errors="coerce")
    visible = visible.dropna(subset=["date"])
    if replay_until is not None:
        visible = visible.loc[visible["date"].dt.date <= replay_until]
    return visible.sort_values("date")


# Builds an SST chart with optional replay, thresholds and anomaly context.
def observation_chart(
    series: pd.DataFrame,
    title: str,
    unit: str,
    anomaly: AnomalyRecord | None = None,
    threshold: float | None = None,
    replay_until: date | None = None,
) -> go.Figure:
    figure = _styled_figure(title, unit)
    visible = _visible_series(series, replay_until)
    if visible["value"].notna().sum() == 0:
        figure.add_annotation(
            text=EMPTY_MESSAGE,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 16, "color": "#CBD5E1"},
        )
        return figure

    safe_unit = escape(unit)
    source = f"<br>Source: {escape(anomaly.source)}" if anomaly else ""
    hover = f"Date: %{{x|%Y-%m-%d}}<br>Value: %{{y:.2f}} {safe_unit}{source}<extra></extra>"
    figure.add_trace(
        go.Scatter(
            x=visible["date"],
            y=visible["value"],
            mode="lines+markers",
            name="Observations",
            line={"color": LINE_COLOR, "width": 2.5},
            marker={"color": LINE_COLOR, "size": 6},
            hovertemplate=hover,
            connectgaps=False,
        )
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#64748B")

    if threshold is not None and isfinite(threshold):
        magnitude = abs(threshold)
        for level, label in ((magnitude, "+"), (-magnitude, "−")):
            figure.add_hline(
                y=level,
                line_dash="dash",
                line_color=THRESHOLD_COLOR,
                annotation_text=f"{label}{magnitude:g} {safe_unit} threshold",
                annotation_position="top right",
            )

    if anomaly is not None:
        matching = visible.loc[
            (visible["date"].dt.date == anomaly.observation_date)
            & visible["value"].notna()
        ]
        if not matching.empty:
            observed_date = matching.iloc[-1]["date"]
            figure.add_trace(
                go.Scatter(
                    x=[observed_date],
                    y=[anomaly.value],
                    mode="markers",
                    name="Detected anomaly",
                    marker={
                        "color": ANOMALY_COLOR,
                        "size": 16,
                        "line": {"color": "#FFFFFF", "width": 2},
                    },
                    hovertemplate=hover,
                )
            )
            figure.add_annotation(
                x=observed_date,
                y=anomaly.value,
                text=f"{anomaly.value:.2f} {escape(anomaly.unit)}",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-42,
                bgcolor="rgba(15,23,42,0.9)",
                bordercolor=ANOMALY_COLOR,
                borderpad=5,
            )
    return figure
