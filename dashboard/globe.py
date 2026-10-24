"""Interactive 3D globe (globe.gl) of the whole world with the monitored regions on it.

Owner: Person 3 (Product & Dashboard). Markers come only from real AnomalyRecords and
dashboard/maps.py coordinates - nothing on the globe is invented or randomly generated.
Clicking a region marker tells Python which anomaly was picked (a CCv2 trigger value).
"""

from collections.abc import Callable
from html import escape

import streamlit as st

from dashboard.maps import PERU_LOCATIONS, REGION_BOXES
from dashboard.components import SEVERITY_STYLES, _globe_regions, _severity_mapping, severity_color
from schemas.anomaly import AnomalyRecord

GLOBE_SCRIPT = "https://cdn.jsdelivr.net/npm/globe.gl@2.46.2/dist/globe.gl.min.js"
TEXTURE_BASE = "https://unpkg.com/three-globe@2.31.0/example/img"
GLOBE_HEIGHT = 700
STATUS_COLORS = {
    "detected": "#ff6b6b",
    "monitoring": "#ffd180",
    "inconclusive": "#65705f",
}
LOCATION_COLOR = "#94a3b8"
QUIET_COLOR = "#5c6b80"

GLOBE_HTML = """
<div class="stage">
  <div id="globeViz" role="img" aria-label="Worldwide climate event globe. Select an event from the sidebar for keyboard access."></div>
  <div id="fallback" role="status">The 3D view could not load. Event details and sources remain available in the dashboard.</div>
  <div id="legend">
    <div><i style="background:#FF767C"></i>Red · critical danger</div>
    <div><i style="background:#FFB16A"></i>Orange · high concern</div>
    <div><i style="background:#F6DB72"></i>Yellow · moderate concern</div>
    <div><i style="background:#79DFB5"></i>Green · beneficial event</div>
    <div><i style="background:#B8C8D9"></i>Gray · severity not assessed</div>
    <div class="hint">Drag to rotate · scroll to zoom · click an event for evidence</div>
    <div class="hint">Green does not mean hazard-free. App alerts are distinct from official warnings.</div>
  </div>
</div>
"""

GLOBE_CSS = """
.stage { position: relative; width: 100%; height: __HEIGHT__px; background: #e6eadf;
  border-radius: 12px; overflow: hidden; font-family: sans-serif; }
#globeViz { width: 100%; height: 100%; }
#legend { position: absolute; left: 14px; bottom: 14px; background: rgba(255,253,247,.95);
  color: #29392d; padding: 10px 12px; border: 1px solid #c2ccb5; border-radius: 8px;
  font-size: 11px; line-height: 1.6; pointer-events: none; max-width: calc(100% - 28px); }
#legend i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
#legend .hint { color: #65705f; }
#fallback { position: absolute; inset: 0; display: none; align-items: center;
  justify-content: center; color: #65705f; text-align: center; padding: 24px; }
@media(max-width:640px){.stage{height:540px}#legend{font-size:10px;padding:8px}.hint{max-width:280px}}
""".replace("__HEIGHT__", str(GLOBE_HEIGHT))

GLOBE_JS = """
const SCRIPT_URL = "__SCRIPT__";
const TEXTURES = "__TEXTURES__";
const instances = new WeakMap();

// Loads the pinned library once and permits a retry after a failed network request.
function loadGlobeLibrary() {
  if (window.Globe) return Promise.resolve(window.Globe);
  if (!window.__earthwatchGlobeLoad) {
    window.__earthwatchGlobeLoad = new Promise((resolve, reject) => {
      const tag = document.createElement("script"); tag.src = SCRIPT_URL;
      tag.onload = () => resolve(window.Globe);
      tag.onerror = () => { window.__earthwatchGlobeLoad = null; tag.remove(); reject(new Error("Globe library unavailable")); };
      document.head.appendChild(tag);
    });
  }
  return window.__earthwatchGlobeLoad;
}

// Creates one interactive instance, keeping event selection wired back to Python.
function createGlobe(Globe, container, setTriggerValue) {
  const pick = (item, event) => {
    if (!item?.anomaly_id) return;
    event?.stopPropagation?.();
    globe.controls().autoRotate = false;
    container.style.cursor = "pointer";
    setTriggerValue("selected", item.anomaly_id);
  };
  const hover = item => { container.style.cursor = item?.anomaly_id ? "pointer" : "grab"; };
  const globe = Globe()(container)
    .width(container.clientWidth).height(container.clientHeight)
    .globeImageUrl("https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg")
    .bumpImageUrl(TEXTURES + "/earth-topology.png")
    .backgroundColor("#e6eadf")
    .showAtmosphere(true).atmosphereColor("#72b5ef").atmosphereAltitude(0.12)
    .pointLat("lat").pointLng("lng").pointColor("color").pointAltitude(0.022)
    .pointRadius("radius").pointLabel("tooltip").onPointClick(pick).onPointHover(hover)
    .labelLat("lat").labelLng("lng").labelText("label").labelColor("color")
    .labelSize(1.1).labelDotRadius(0).labelAltitude(0.025).onLabelClick(pick).onLabelHover(hover)
    .pathPoints("coords").pathPointLat((p) => p[0]).pathPointLng((p) => p[1])
    .pathColor("color").pathStroke(1.6).pathLabel("name")
    .polygonGeoJsonGeometry("geometry").polygonCapColor("fill").polygonStrokeColor("color")
    .polygonSideColor(() => "rgba(0,0,0,0)").polygonAltitude(d => d.selected ? 0.012 : 0.006)
    .polygonLabel("tooltip").onPolygonClick(pick).onPolygonHover(hover).polygonsTransitionDuration(0)
    .ringLat("lat").ringLng("lng").ringColor((d) => () => d.color)
    .ringMaxRadius("maxRadius").ringPropagationSpeed(1).ringRepeatPeriod(2000);
  const state = { globe, view: null, timer: null, rotate: true, pulses: true, rings: [], interacting: false,
    motion: matchMedia("(prefers-reduced-motion: reduce)") };
  // Applies user preferences while honoring reduced motion and active dragging.
  state.sync = () => {
    globe.controls().autoRotate = state.rotate && !state.interacting && !state.motion.matches;
    globe.controls().autoRotateSpeed = 0.35;
    globe.ringsData(state.pulses && !state.motion.matches ? state.rings : []);
  };
  state.start = () => { clearTimeout(state.timer); state.interacting = true; state.sync(); };
  state.end = () => { clearTimeout(state.timer); state.timer = setTimeout(() => { state.interacting = false; state.sync(); }, 3000); };
  globe.controls().addEventListener("start", state.start);
  globe.controls().addEventListener("end", state.end);
  state.motion.addEventListener("change", state.sync);
  state.resize = new ResizeObserver(() => globe.width(container.clientWidth).height(container.clientHeight));
  state.resize.observe(container);
  return state;
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const container = parentElement.querySelector("#globeViz"), fallback = parentElement.querySelector("#fallback");
  if (!container) return;
  let active = true;
  loadGlobeLibrary().then((Globe) => {
    if (!active || !container.isConnected) return;
    let state = instances.get(parentElement);
    if (!state) { state = createGlobe(Globe, container, setTriggerValue); instances.set(parentElement, state); }
    const { globe } = state;
    state.rotate = data.rotate; state.pulses = data.pulses; state.rings = data.rings;
    // Polling changes review text, not source geometry. Avoid triangulating every
    // polygon again on each timer tick, which can block pointer input.
    const polygons = data.polygons || [];
    const polygonKey = polygons.map(p => p.anomaly_id + ':' + Boolean(p.selected)).join('|');
    if (state.polygonKey !== polygonKey) {
      globe.polygonsData(polygons);
      state.polygonKey = polygonKey;
    }
    globe.pointsData(data.points).labelsData(data.points.filter((p) => p.region)).pathsData(data.outlines);
    state.sync(); fallback.style.display = "none";
    if (state.view !== data.view_key) {
      const first = state.view === null; state.view = data.view_key;
      globe.pointOfView(data.view, first || state.motion.matches ? 0 : 1200);
    }
  }).catch(() => { if(active) fallback.style.display = "flex"; });
  return () => {
    active = false; const state = instances.get(parentElement);
    if (state) {
      clearTimeout(state.timer); state.resize.disconnect(); state.motion.removeEventListener("change", state.sync);
      state.globe.controls().removeEventListener("start", state.start);state.globe.controls().removeEventListener("end", state.end);
      if (state.globe._destructor) state.globe._destructor();
    }
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


# Resolves registered coordinates without assigning a location to unknown feed regions.
def _coordinates(anomalies: list[AnomalyRecord], region_locations: dict[str, tuple[float, float]] | None) -> dict[str, tuple[float, float]]:
    return {str(item["name"]): (float(item["latitude"]), float(item["longitude"]))
            for item in _globe_regions(anomalies, region_locations) if item["latitude"] is not None}


# Preserves distinct event types at the same location and colors only explicit severity.
def _region_points(
    anomalies: list[AnomalyRecord], locations: dict[str, tuple[float, float]], levels: dict[str, str],
) -> list[dict]:
    latest: dict[tuple[str, str], AnomalyRecord] = {}
    for anomaly in sorted(anomalies, key=lambda item: item.observation_date):
        latest[(anomaly.region, anomaly.variable)] = anomaly
    points = []
    for (region, _), anomaly in latest.items():
        if region not in locations:
            continue
        lat, lng = locations[region]
        level = levels.get(anomaly.anomaly_id, "unknown")
        points.append({
            "lat": lat, "lng": lng, "radius": 0.8, "color": severity_color(level), "severity": level,
            "label": f"{region}  {anomaly.value:+g} {anomaly.unit}",
            "tooltip": _tooltip(region, [anomaly.variable.replace("_", " ").capitalize(),
                f"{anomaly.value:+g} {anomaly.unit} on {anomaly.observation_date}",
                SEVERITY_STYLES[level][1], f"Status: {anomaly.status}", f"Source: {anomaly.source}", "Click to open this event"]),
            "region": region, "anomaly_id": anomaly.anomaly_id,
        })
    return points


# Reports feed regions missing a supplied or registered geographic location.
def unplotted_regions(
    anomalies: list[AnomalyRecord], region_locations: dict[str, tuple[float, float]] | None = None,
) -> list[str]:
    locations = _coordinates(anomalies, region_locations)
    return sorted({item.region for item in anomalies if item.region not in locations})


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
            "color": "#8ddcf0" if selected else QUIET_COLOR,
            "coords": [
                [lat_min, lon_min], [lat_min, lon_max], [lat_max, lon_max],
                [lat_max, lon_min], [lat_min, lon_min],
            ],
        })
    return outlines


# Adds pulses only to explicitly classified events, independently of selection.
def _rings(points: list[dict]) -> list[dict]:
    return [{"lat": point["lat"], "lng": point["lng"], "color": point["color"], "maxRadius": 5}
            for point in points if point["severity"] != "unknown"]


# Builds worldwide event data, retaining source IDs used by the existing app callback.
def globe_data(
    anomalies: list[AnomalyRecord], selected_region: str | None, *,
    region_locations: dict[str, tuple[float, float]] | None = None,
    severity_by_anomaly: dict[str, str] | None = None,
) -> dict:
    levels = _severity_mapping(anomalies, severity_by_anomaly)
    locations = _coordinates(anomalies, region_locations)
    region_points = _region_points(anomalies, locations, levels)
    lat, lng = locations.get(selected_region, (20.0, -20.0))
    return {
        "points": region_points + _location_points(), "outlines": _outlines(selected_region),
        "rings": _rings(region_points), "view": {"lat": lat, "lng": lng, "altitude": 2.8},
        "view_key": selected_region or "", "rotate": True, "pulses": True,
    }


# Renders the whole-world globe; on_select(anomaly_id) runs when a marker is clicked.
def render_globe(
    anomalies: list[AnomalyRecord],
    selected_region: str | None,
    on_select: Callable[[str], None], *,
    region_locations: dict[str, tuple[float, float]] | None = None,
    severity_by_anomaly: dict[str, str] | None = None,
) -> None:
    # Runs before the script body on a click, reading the id the globe sent back.
    def handle_click() -> None:
        anomaly_id = st.session_state["globe"].get("selected")
        if anomaly_id:
            on_select(anomaly_id)

    data = globe_data(anomalies, selected_region, region_locations=region_locations, severity_by_anomaly=severity_by_anomaly)
    rotation, alerts = st.columns(2)
    with rotation:
        data["rotate"] = st.toggle("Automatic rotation", value=True, key="globe_rotation")
    with alerts:
        data["pulses"] = st.toggle("Alert pulses", value=True, key="globe_alert_pulses")
    st.caption("Worldwide climate events · drag freely; rotation resumes after 3 seconds. Reduced motion is respected.")
    _GLOBE_COMPONENT(
        key="globe",
        data=data,
        height=GLOBE_HEIGHT,
        on_selected_change=handle_click,
    )
    missing = unplotted_regions(anomalies, region_locations)
    if missing:
        st.caption(
            "Listed in the dashboard, awaiting geographic coordinates: "
            + ", ".join(missing)
        )
