"""Plotly charts for observation and anomaly series.

Owner: Person 3 (Product & Dashboard).
"""

import pandas as pd
import plotly.graph_objects as go


# Builds a line chart of an observation series with a zero-anomaly reference line.
def observation_chart(series: pd.DataFrame, title: str, unit: str) -> go.Figure:
    figure = go.Figure(
        go.Scatter(x=series["date"], y=series["value"], mode="lines+markers")
    )
    figure.add_hline(y=0, line_dash="dot")
    figure.update_layout(
        title=title,
        yaxis_title=unit,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    return figure
