"""Map of the monitored Pacific region and Peru locations (Tier 2 feature).

Owner: Person 3 (Product & Dashboard).
"""

import plotly.graph_objects as go

from dashboard.charts import apply_dark_layout

# Region name -> (lat_min, lat_max, lon_min, lon_max), using NOAA's index boxes.
REGION_BOXES: dict[str, tuple[float, float, float, float]] = {
    "Nino 1+2": (-10, 0, -90, -80),
    "Nino 3.4": (-5, 5, -170, -120),
}
# Northern Peru locations -> (lat, lon).
PERU_LOCATIONS: dict[str, tuple[float, float]] = {
    "Tumbes": (-3.57, -80.45),
    "Piura": (-5.19, -80.63),
    "Chiclayo": (-6.77, -79.84),
    "Trujillo": (-8.11, -79.03),
}
SELECTED_COLOR = "#FF6B6B"
DIM_COLOR = "#5C6B80"
LOCATION_COLOR = "#70E1BB"


# Draws one region box as a closed outline, filled and bright when selected.
def _region_trace(name: str, box: tuple[float, float, float, float], selected: bool) -> go.Scattergeo:
    lat_min, lat_max, lon_min, lon_max = box
    color = SELECTED_COLOR if selected else DIM_COLOR
    return go.Scattergeo(
        lat=[lat_min, lat_min, lat_max, lat_max, lat_min],
        lon=[lon_min, lon_max, lon_max, lon_min, lon_min],
        mode="lines", name=name,
        line={"color": color, "width": 3 if selected else 1.5},
        fill="toself" if selected else "none",
        fillcolor="rgba(255,107,107,0.25)",
        hoverinfo="name",
    )


# Draws the northern Peru locations as labelled markers.
def _locations_trace() -> go.Scattergeo:
    names = list(PERU_LOCATIONS)
    return go.Scattergeo(
        lat=[PERU_LOCATIONS[name][0] for name in names],
        lon=[PERU_LOCATIONS[name][1] for name in names],
        text=names, mode="markers+text", textposition="middle right",
        name="Northern Peru", marker={"size": 8, "color": LOCATION_COLOR},
        textfont={"color": LOCATION_COLOR},
    )


# Builds a map of the monitored Pacific boxes with the selected region highlighted.
def region_map(selected_region: str | None = None) -> go.Figure:
    figure = go.Figure(
        [_region_trace(name, box, name == selected_region) for name, box in REGION_BOXES.items()]
    )
    figure.add_trace(_locations_trace())
    figure.update_geos(
        projection_type="natural earth",
        lataxis_range=[-20, 15], lonaxis_range=[-180, -65],
        showland=True, landcolor="#1E2B3C",
        showocean=True, oceancolor="#0E1A2A",
        showcountries=True, countrycolor="#3A4A60",
        showcoastlines=True, coastlinecolor="#4A5C74",
        bgcolor="rgba(0,0,0,0)",
    )
    figure.update_layout(
        title="Monitored regions", showlegend=True,
        legend={"orientation": "h", "y": -0.05},
    )
    return apply_dark_layout(figure)
