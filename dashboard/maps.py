"""World map with monitored climate regions and labeled reference locations.

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
SELECTED_COLOR = "#8DDCF0"
DIM_COLOR = "#5C6B80"
LOCATION_COLOR = "#94A3B8"


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
        fillcolor="rgba(141,220,240,0.20)",
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
        scope="world", projection_type="natural earth", center={"lat": 0, "lon": 0},
        lataxis_range=[-90, 90], lonaxis_range=[-180, 180],
        showland=True, landcolor="#263746", showocean=True, oceancolor="#0C2434",
        showcountries=True, countrycolor="#526779", showcoastlines=True,
        coastlinecolor="#7C92A3", showlakes=False, showframe=True, framecolor="#526779",
        bgcolor="rgba(0,0,0,0)",
    )
    figure.update_layout(
        title="Worldwide climate observations", showlegend=True, height=520,
        legend={"orientation": "h", "y": -0.05},
    )
    return apply_dark_layout(figure)
