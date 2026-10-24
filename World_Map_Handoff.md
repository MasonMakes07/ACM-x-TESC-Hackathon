# EarthWatch world map handoff

Copy this file to the Codex working on the other branch.

## Request

Make `dashboard.maps.region_map()` show the **entire world** for every selection. Keep the existing Niño 1+2 and Niño 3.4 region boxes and the labelled northern Peru locations. The selected box should remain highlighted. This changes the map viewport; it does not add worldwide climate observations.

## Existing commit

The tested change is on branch `p3-charts` in `MasonMakes07/ACM-x-TESC-Hackathon`:

```text
d85e0bb0aa7364e1418dee069bc4ce6352be98e0
Dashboard: show monitored regions on a world map
```

If your branch already contains the earlier chart and map implementation, apply this commit with `git cherry-pick d85e0bb0aa7364e1418dee069bc4ce6352be98e0`. If it does not, apply the changes below to your branch's map implementation instead. Do not replace unrelated work.

## Exact map change

In `dashboard/maps.py`, retain the existing `REGION_BOXES`, `PERU_LOCATIONS`, box traces and location markers. Replace the cropped `figure.update_geos(...)` settings inside `region_map()` with:

```python
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
```

Add `height=520` to the existing `figure.update_layout(...)` call so the global map has enough room.

## Test to add

In `tests/test_dashboad_charts.py`, with `pytest` and `region_map` imported:

```python
# Keeps a global viewport even when a Pacific region is selected.
@pytest.mark.parametrize("region", [None, "Nino 1+2", "Nino 3.4"])
def test_region_map_shows_the_whole_world(region: str | None) -> None:
    geo = region_map(region).layout.geo
    assert geo.scope == "world"
    assert geo.projection.type == "natural earth"
    assert tuple(geo.lataxis.range) == (-90, 90)
    assert tuple(geo.lonaxis.range) == (-180, 180)
    assert geo.showcountries
```

Run the full suite with `pytest -q`. It passed on `p3-charts` after this change: `59 passed in 1.12s`. Check the rendered map as well; all continents should be visible and selecting a Pacific region should highlight its box without zooming in.
