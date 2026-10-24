"""A bundled world overview that does not require third-party basemap tiles."""
from html import escape
import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st


@st.cache_data
def boundary_lines():
    data = json.loads((Path(__file__).resolve().parents[1] / 'data/world_boundaries.json').read_text())
    x, y = [], []
    for ring in data['rings']:
        previous = None
        for lon, lat in ring:
            if previous is not None and abs(lon - previous) > 180:
                x.append(None)
                y.append(None)
            x.append(lon)
            y.append(lat)
            previous = lon
        x.append(None)
        y.append(None)
    return x, y


def watch_map(points):
    x, y = boundary_lines()
    figure = go.Figure(go.Scatter(x=x, y=y, mode='lines', fill='toself',
        fillcolor='#DEE4D1', line=dict(color='#89977C', width=0.6),
        hoverinfo='skip', showlegend=False))
    figure.add_scatter(x=[point['longitude'] for point in points],
        y=[point['latitude'] for point in points], mode='markers',
        marker=dict(size=13, color=[point['color'] for point in points],
                    line=dict(color='#E1EDF5', width=1)),
        text=[f"{escape(point['label'])}<br>{escape(point['level'])}" for point in points],
        customdata=[point['key'] for point in points],
        hovertemplate='%{text}<extra></extra>', showlegend=False,
        selected=dict(marker=dict(size=18, opacity=1)),
        unselected=dict(marker=dict(opacity=0.7)))
    figure.update_layout(height=350, margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor='#F7F5ED', plot_bgcolor='#F7F5ED',
        xaxis=dict(range=[-180, 180], visible=False, fixedrange=True),
        yaxis=dict(range=[-90, 90], visible=False, fixedrange=True),
        clickmode='event+select', dragmode=False, uirevision='watchlist-world')
    return figure
