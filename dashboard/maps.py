"""World map with monitored Pacific SST regions and northern Peru locations.

Owner: Person 3 (Product & Dashboard).
"""

import plotly.graph_objects as go

REGION_BOXES: dict[str, tuple[float, float, float, float]] = {
    "Nino 1+2": (-10, 0, -90, -80),
    "Nino 3.4": (-5, 5, -170, -120),
}

PERU_LOCATIONS: dict[str, tuple[float, float]] = {
    "Piura": (-5.1945, -80.6328),
    "Tumbes": (-3.5669, -80.4515),
    "Chiclayo": (-6.7714, -79.8409),
    "Trujillo": (-8.1116, -79.0287),
}


# Returns a closed longitude-latitude outline for one monitored region.
def _box_outline(box: tuple[float, float, float, float]) -> tuple[list[float], list[float]]:
    lat_min, lat_max, lon_min, lon_max = box
    return (
        [lon_min, lon_max, lon_max, lon_min, lon_min],
        [lat_min, lat_min, lat_max, lat_max, lat_min],
    )


# Draws a global map with Pacific monitoring regions and Peru locations.
def region_map(selected_region: str | None = None) -> go.Figure:
    figure = go.Figure()
    for name, box in REGION_BOXES.items():
        lon, lat = _box_outline(box)
        selected = name == selected_region
        figure.add_trace(
            go.Scattergeo(
                lon=lon,
                lat=lat,
                mode="lines",
                name=name,
                fill="toself" if selected else "none",
                fillcolor="rgba(64,202,221,0.24)" if selected else "rgba(0,0,0,0)",
                line={
                    "color": "#55D8E9" if selected else "#526779",
                    "width": 3 if selected else 1.5,
                },
                hovertemplate=f"{name}<extra></extra>",
            )
        )

    figure.add_trace(
        go.Scattergeo(
            lon=[coordinate[1] for coordinate in PERU_LOCATIONS.values()],
            lat=[coordinate[0] for coordinate in PERU_LOCATIONS.values()],
            text=list(PERU_LOCATIONS),
            mode="markers+text",
            name="Northern Peru",
            textposition="middle right",
            textfont={"color": "#F8FAFC", "size": 11},
            marker={"color": "#FFC46B", "size": 8, "line": {"color": "#0F172A", "width": 1}},
            hovertemplate="%{text}<br>%{lat:.2f}°, %{lon:.2f}°<extra></extra>",
        )
    )
    figure.update_geos(
        scope="world",
        projection_type="natural earth",
        center={"lat": 0, "lon": 0},
        lataxis_range=[-90, 90],
        lonaxis_range=[-180, 180],
        showland=True,
        landcolor="#263746",
        showocean=True,
        oceancolor="#0C2434",
        showcountries=True,
        countrycolor="#526779",
        showcoastlines=True,
        coastlinecolor="#7C92A3",
        showlakes=False,
        showframe=True,
        framecolor="#526779",
        bgcolor="rgba(0,0,0,0)",
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=520,
        showlegend=True,
        legend={"orientation": "h", "y": 0, "x": 0},
    )
    return figure
