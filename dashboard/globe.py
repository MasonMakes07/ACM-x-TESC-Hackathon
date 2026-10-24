"""Interactive 3D globe (globe.gl) of the whole world with the monitored regions on it.

Owner: Person 3 (Product & Dashboard). Markers come only from real AnomalyRecords and
dashboard/maps.py coordinates - nothing on the globe is invented or randomly generated.
Clicking a region marker tells Python which anomaly was picked (a CCv2 trigger value).
"""

from collections.abc import Callable
from html import escape

import streamlit as st

from dashboard.maps import PERU_LOCATIONS, REGION_BOXES
from schemas.anomaly import AnomalyRecord

GLOBE_SCRIPT = "https://cdn.jsdelivr.net/npm/globe.gl@2.46.2/dist/globe.gl.min.js"
TEXTURE_BASE = "https://unpkg.com/three-globe@2.31.0/example/img"
GLOBE_HEIGHT = 700
STATUS_COLORS = {
    "detected": "#ff6b6b",
    "monitoring": "#ffd180",
    "inconclusive": "#cbd5e1",
}
LOCATION_COLOR = "#70e1bb"
QUIET_COLOR = "#5c6b80"

GLOBE_HTML = """
<div class="stage">
  <div id="globeViz"></div>
  <div id="fallback">The 3D globe could not load (no internet connection?). The dashboard still works.</div>
  <div id="legend">
    <div><i style="background:#ff6b6b"></i>Signal detected</div>
    <div><i style="background:#ffd180"></i>Monitoring</div>
    <div><i style="background:#70e1bb"></i>Monitoring location</div>
    <div class="hint">Drag to rotate · scroll to zoom · click a red or yellow marker to open that event</div>
  </div>
</div>
"""

GLOBE_CSS = """
.stage { position: relative; width: 100%; height: __HEIGHT__px; background: #05080f;
  border-radius: 8px; overflow: hidden; font-family: sans-serif; }
#globeViz { width: 100%; height: 100%; }
#legend { position: absolute; left: 14px; bottom: 14px; background: rgba(10,16,28,.85);
  color: #e6edf3; padding: 10px 12px; border: 1px solid #1e2b3c; border-radius: 8px;
  font-size: 12px; line-height: 1.6; pointer-events: none; }
#legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
#legend .hint { color: #8fa3b8; }
#fallback { position: absolute; inset: 0; display: none; align-items: center;
  justify-content: center; color: #cbd5e1; text-align: center; padding: 24px; }
""".replace("__HEIGHT__", str(GLOBE_HEIGHT))

GLOBE_JS = """
const SCRIPT_URL = "__SCRIPT__";
const TEXTURES = "__TEXTURES__";
const instances = new WeakMap();

// Loads globe.gl once per page and resolves with the Globe constructor.
function loadGlobeLibrary() {
  if (window.Globe) return Promise.resolve(window.Globe);
  if (!window.__earthwatchGlobeLoad) {
    window.__earthwatchGlobeLoad = new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = SCRIPT_URL;
      tag.onload = () => resolve(window.Globe);
      tag.onerror = reject;
      document.head.appendChild(tag);
    });
  }
  return window.__earthwatchGlobeLoad;
}

// Creates the globe once for this component instance.
function createGlobe(Globe, container, setTriggerValue) {
  const pick = (item) => {
    if (item && item.anomaly_id) setTriggerValue("selected", item.anomaly_id);
  };
  const globe = Globe()(container)
    .width(container.clientWidth).height(container.clientHeight)
    .globeImageUrl(TEXTURES + "/earth-night.jpg")
    .bumpImageUrl(TEXTURES + "/earth-topology.png")
    .backgroundImageUrl(TEXTURES + "/night-sky.png")
    .showAtmosphere(true).atmosphereColor("#0ea5e9").atmosphereAltitude(0.2)
    .pointLat("lat").pointLng("lng").pointColor("color").pointAltitude(0.02)
    .pointRadius("radius").pointLabel("tooltip").onPointClick(pick)
    .labelLat("lat").labelLng("lng").labelText("label").labelColor("color")
    .labelSize(1.3).labelDotRadius(0).labelAltitude(0.03).onLabelClick(pick)
    .pathPoints("coords").pathPointLat((p) => p[0]).pathPointLng((p) => p[1])
    .pathColor("color").pathStroke(1.6).pathLabel("name")
    .ringLat("lat").ringLng("lng").ringColor((d) => () => d.color)
    .ringMaxRadius("maxRadius").ringPropagationSpeed(2).ringRepeatPeriod(1800);
  globe.controls().autoRotate = true;
  globe.controls().autoRotateSpeed = 0.6;
  container.addEventListener("pointerdown", () => { globe.controls().autoRotate = false; });
  return globe;
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const container = parentElement.querySelector("#globeViz");
  const fallback = parentElement.querySelector("#fallback");
  if (!container) return;

  loadGlobeLibrary().then((Globe) => {
    let state = instances.get(parentElement);
    if (!state) {
      state = { globe: createGlobe(Globe, container, setTriggerValue), view: null };
      instances.set(parentElement, state);
    }
    const { globe } = state;
    globe.pointsData(data.points).labelsData(data.points.filter((p) => p.region))
      .pathsData(data.outlines).ringsData(data.rings);
    if (state.view !== data.view_key) {
      const first = state.view === null;
      state.view = data.view_key;
      globe.pointOfView(data.view, first ? 0 : 1200);
    }
  }).catch(() => { fallback.style.display = "flex"; });

  return () => {
    const state = instances.get(parentElement);
    if (state && state.globe._destructor) state.globe._destructor();
    instances.delete(parentElement);
  };
}
""".replace("__SCRIPT__", GLOBE_SCRIPT).replace("__TEXTURES__", TEXTURE_BASE)

# Declared once at import time, as CCv2 requires.
_GLOBE_COMPONENT = st.components.v2.component(
    "earthwatch_globe", html=GLOBE_HTML, css=GLOBE_CSS, js=GLOBE_JS
)


# Returns the (lat, lng) center of a region's bounding box.
def _box_center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = box
    return (lat_min + lat_max) / 2, (lon_min + lon_max) / 2


# Builds the HTML tooltip text for a marker, escaping every value.
def _tooltip(title: str, lines: list[str]) -> str:
    body = "".join(f"<div>{escape(line)}</div>" for line in lines)
    return f"<b>{escape(title)}</b>{body}"


# Builds one clickable marker per monitored region from its newest anomaly record.
def _region_points(anomalies: list[AnomalyRecord]) -> list[dict]:
    latest: dict[str, AnomalyRecord] = {}
    for anomaly in sorted(anomalies, key=lambda item: item.observation_date):
        latest[anomaly.region] = anomaly
    points = []
    for region, anomaly in latest.items():
        if region not in REGION_BOXES:
            continue
        lat, lng = _box_center(REGION_BOXES[region])
        points.append({
            "lat": lat, "lng": lng, "radius": 1.2,
            "color": STATUS_COLORS.get(anomaly.status, QUIET_COLOR),
            "label": f"{region}  {anomaly.value:+g} {anomaly.unit}",
            "tooltip": _tooltip(region, [
                anomaly.variable.replace("_", " ").capitalize(),
                f"{anomaly.value:+g} {anomaly.unit} on {anomaly.observation_date}",
                f"Status: {anomaly.status}", f"Source: {anomaly.source}",
                "Click to open this event",
            ]),
            "region": region,
            "anomaly_id": anomaly.anomaly_id,
        })
    return points


# Returns the regions of anomalies that have no known coordinates, so none vanish silently.
def unplotted_regions(anomalies: list[AnomalyRecord]) -> list[str]:
    return sorted({item.region for item in anomalies if item.region not in REGION_BOXES})


# Builds a marker for each northern Peru monitoring location (hover only, not clickable).
def _location_points() -> list[dict]:
    return [
        {
            "lat": lat, "lng": lng, "radius": 0.35, "color": LOCATION_COLOR,
            "label": name, "tooltip": _tooltip(name, ["Monitoring location"]),
            "region": None, "anomaly_id": None,
        }
        for name, (lat, lng) in PERU_LOCATIONS.items()
    ]


# Builds a closed outline of each region box, bright when it is the selected region.
def _outlines(selected_region: str | None) -> list[dict]:
    outlines = []
    for name, (lat_min, lat_max, lon_min, lon_max) in REGION_BOXES.items():
        selected = name == selected_region
        outlines.append({
            "name": name,
            "color": "#ff6b6b" if selected else QUIET_COLOR,
            "coords": [
                [lat_min, lon_min], [lat_min, lon_max], [lat_max, lon_max],
                [lat_max, lon_min], [lat_min, lon_min],
            ],
        })
    return outlines


# Builds pulsing rings on the selected region, colored by that anomaly's status.
def _rings(points: list[dict], selected_region: str | None) -> list[dict]:
    return [
        {"lat": point["lat"], "lng": point["lng"], "color": point["color"], "maxRadius": 9}
        for point in points
        if point["region"] is not None and point["region"] == selected_region
    ]


# Builds everything the globe needs, centered on the selected region.
def globe_data(anomalies: list[AnomalyRecord], selected_region: str | None) -> dict:
    region_points = _region_points(anomalies)
    if selected_region in REGION_BOXES:
        lat, lng = 15.0, _box_center(REGION_BOXES[selected_region])[1]
    else:
        lat, lng = 15.0, -90.0
    return {
        "points": region_points + _location_points(),
        "outlines": _outlines(selected_region),
        "rings": _rings(region_points, selected_region),
        "view": {"lat": lat, "lng": lng, "altitude": 2.8},
        "view_key": selected_region or "",
    }


# Renders the whole-world globe; on_select(anomaly_id) runs when a marker is clicked.
def render_globe(
    anomalies: list[AnomalyRecord],
    selected_region: str | None,
    on_select: Callable[[str], None],
) -> None:
    # Runs before the script body on a click, reading the id the globe sent back.
    def handle_click() -> None:
        anomaly_id = st.session_state["globe"].get("selected")
        if anomaly_id:
            on_select(anomaly_id)

    _GLOBE_COMPONENT(
        key="globe",
        data=globe_data(anomalies, selected_region),
        height=GLOBE_HEIGHT,
        on_selected_change=handle_click,
    )
    missing = unplotted_regions(anomalies)
    if missing:
        st.caption(
            "Not shown on the globe (no coordinates registered in dashboard/maps.py): "
            + ", ".join(missing)
        )
