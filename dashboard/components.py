"""Accessible dashboard components. Owner: Person 3 / Codex B."""

from html import escape
from urllib.parse import urlsplit

import streamlit as st

from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, EvidenceItem, ProgressEvent

CONFIDENCE_COLORS = {
    "high": "#70E1BB",
    "moderate": "#FFD180",
    "low": "#FFABAB",
    "inconclusive": "#CBD5E1",
}
EVIDENCE_BADGES = {
    "measured": "📏 Measured",
    "reported": "📰 Reported",
    "inferred": "🔎 Inferred",
    "uncertain": "❓ Uncertain",
}
STATUS_LABELS = {
    "detected": "Signal detected",
    "monitoring": "Monitoring",
    "inconclusive": "Inconclusive",
}


# Returns an accessible foreground color without treating unknown levels as certainty.
def confidence_color(level: str) -> str:
    return CONFIDENCE_COLORS.get(level, "#CBD5E1")


# Pairs each evidence category with text so meaning never depends on its icon.
def evidence_badge(evidence_type: str) -> str:
    return EVIDENCE_BADGES.get(evidence_type, "❔ Unclassified")


# Makes schema field names readable without changing the underlying scientific meaning.
def _readable(value: str) -> str:
    return value.replace("_", " ").capitalize()


# Formats a measurement with its supplied units.
def _measurement(anomaly: AnomalyRecord) -> str:
    unit = "°C" if anomaly.unit == "degC" else anomaly.unit
    return f"{anomaly.value:g} {unit}"


# Displays supplied findings as text, keeping external content out of HTML.
def _findings(items: list[str], empty_message: str) -> None:
    if not items:
        st.caption(empty_message)
    for item in items:
        st.write("• " + item)


# Summarizes regional signal status and explicitly dates the displayed observations.
def status_strip(anomalies: list[AnomalyRecord], is_sample: bool) -> None:
    st.subheader("Monitoring status")
    if not anomalies:
        st.info("No observations available. Monitoring status cannot be determined.")
        if is_sample:
            st.caption("(sample data)")
        return
    latest = max(item.observation_date for item in anomalies)
    st.caption(f"Data as of {latest:%Y-%m-%d}" + (" (sample data)" if is_sample else ""))
    regions = sorted({item.region for item in anomalies})
    for offset in range(0, len(regions), 3):
        batch = regions[offset:offset + 3]
        for column, region in zip(st.columns(len(batch)), batch):
            records = [item for item in anomalies if item.region == region]
            region_date = max(item.observation_date for item in records)
            latest_records = [item for item in records if item.observation_date == region_date]
            status = next(
                (state for state in ("detected", "monitoring", "inconclusive")
                 if any(item.status == state for item in latest_records)),
                None,
            )
            with column:
                st.metric(region, STATUS_LABELS.get(status, "Unknown status"))
                st.caption(f"Observed {region_date:%Y-%m-%d}")


# Presents a compact anomaly card with a textual selection indicator.
def anomaly_card(anomaly: AnomalyRecord, selected: bool = False) -> None:
    with st.container(border=True):
        if selected:
            st.caption("● Selected signal")
        st.text(anomaly.region)
        st.caption(_readable(anomaly.variable))
        st.metric("Recorded value", _measurement(anomaly))
        label = escape(STATUS_LABELS.get(anomaly.status, "Unknown status"))
        st.markdown(
            f'<span style="display:inline-block;border:1px solid #b8c8d9;'
            f'border-radius:999px;padding:.2rem .65rem;color:#edf3fa">{label}</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Observed {anomaly.observation_date:%Y-%m-%d}")


# Explains the selected record and offers a short optional walkthrough.
def anomaly_detail(anomaly: AnomalyRecord) -> None:
    st.subheader("Signal details")
    st.text(f"{anomaly.region} · {_readable(anomaly.variable)}")
    left, right = st.columns(2)
    with left:
        st.metric("Recorded value", _measurement(anomaly))
        st.text(f"Observation date: {anomaly.observation_date:%Y-%m-%d}")
        st.text(f"Status: {STATUS_LABELS.get(anomaly.status, 'Unknown status')}")
    with right:
        st.text(f"Baseline period: {anomaly.baseline_period}")
        st.text(f"Detection method: {_readable(anomaly.detection_method)}")
        st.text(f"Source: {anomaly.source}")
    if "anomaly" in anomaly.variable.lower():
        st.caption(
            f"Anomaly magnitude: {_measurement(anomaly)} relative to the source's "
            "baseline. Positive means above the baseline; negative means below. "
            "The absolute temperature and baseline mean are not supplied in this record."
        )
    else:
        st.caption("Anomaly magnitude and baseline mean are not supplied in this record.")
    with st.expander("New here? How to use EarthWatch"):
        st.markdown(
            "1. **Choose a signal.** Select a region and an observation to inspect.\n"
            "2. **Explore the measurements.** Check the date, units, source, and baseline. "
            "An anomaly is a difference from a historical reference.\n"
            "3. **Run Investigation.** Click the button to ask the agents to examine "
            "the selected signal. Follow their actual progress in Investigation.\n"
            "4. **Read the briefing.** Compare measured observations with potential "
            "regional implications, then expand the evidence to check sources.\n"
            "5. **Check uncertainty.** Read confidence, conflicting findings, and "
            "limitations before using the assessment."
        )
        st.caption(
            "Measured = data observation; reported = a source's statement; "
            "inferred = an interpretation; uncertain = unresolved. "
            "Sample data is illustrative. Historical replay shows past observations. "
            "A detected anomaly alone does not establish a flood forecast."
        )


# Renders only actual progress events, preserving their supplied order.
def investigation_timeline(events: list[ProgressEvent]) -> None:
    if not events:
        st.info("No investigation run yet. Click Run Investigation.")
        return
    st.caption("Investigation progress · timestamps as supplied by the backend")
    for event in events:
        with st.expander(f"{event.timestamp:%H:%M:%S}  {event.agent}"):
            st.text(event.message)
            st.caption(f"Timestamp: {event.timestamp.isoformat()}")


# Orders evidence by provenance and exposes only HTTP or HTTPS source links.
def evidence_list(evidence: list[EvidenceItem]) -> None:
    if not evidence:
        st.info("No evidence supplied. The assessment cannot be independently checked here.")
        return
    order = {kind: index for index, kind in enumerate(EVIDENCE_BADGES)}
    for item in sorted(evidence, key=lambda record: order.get(record.evidence_type, 4)):
        with st.expander(f"{evidence_badge(item.evidence_type)} · {item.claim}"):
            st.text(f"Source: {item.source}")
            st.text(f"Source date: {item.source_date or 'undated'}")
            st.text(f"Evidence type: {item.evidence_type}")
            if item.limitations:
                st.text(f"Limitations: {item.limitations}")
            if item.url:
                try:
                    url = urlsplit(item.url)
                    valid = url.scheme.lower() in {"http", "https"} and bool(url.netloc)
                except ValueError:
                    valid = False
                if valid:
                    st.link_button("Open source", item.url)
                else:
                    st.caption("Source link unavailable: a valid HTTP or HTTPS URL is required.")


# Separates supplied observations, interpretations, provenance, and uncertainty.
def briefing(assessment: Assessment, anomaly: AnomalyRecord) -> None:
    if assessment.anomaly_id != anomaly.anomaly_id:
        st.error("This assessment belongs to a different signal. Run an investigation for the selected signal.")
        return
    st.caption("Regional briefing")
    st.subheader(assessment.summary)
    level = escape(assessment.confidence.capitalize())
    st.markdown(
        f'<span class="ew-confidence" style="color:{confidence_color(assessment.confidence)}">'
        f'Confidence: {level}</span>', unsafe_allow_html=True,
    )
    st.caption(
        "Confidence is the investigation's qualitative assessment, not a probability. "
        "Check the evidence and limitations below for its basis; no separate confidence "
        "rationale is supplied in this report."
    )
    st.markdown("### What we observed")
    st.text(
        f"{anomaly.region}: {_readable(anomaly.variable)} = {_measurement(anomaly)} "
        f"on {anomaly.observation_date:%Y-%m-%d}. Source: {anomaly.source}. "
        f"Baseline period: {anomaly.baseline_period}."
    )
    measured = [item.claim for item in assessment.evidence if item.evidence_type == "measured"]
    _findings(measured, "No additional measured evidence supplied.")
    st.markdown("### Why it matters")
    st.caption("Potential regional implications · these are not confirmed outcomes")
    _findings(assessment.regional_implications, "No regional implications established.")
    supporting, contradictory = st.columns(2)
    with supporting:
        st.markdown("### Supporting findings")
        _findings(assessment.supporting_findings, "No supporting findings supplied.")
    with contradictory:
        st.markdown("### Contradictory findings")
        _findings(assessment.contradictory_findings, "No contradictory findings supplied. This does not establish agreement.")
    st.markdown("### Evidence and sources")
    evidence_list(assessment.evidence)
    st.markdown("### Recommended next steps")
    _findings(assessment.recommended_next_steps, "No next steps supplied.")
    st.markdown("### Limitations")
    _findings(assessment.limitations, "No limitations supplied. This does not establish certainty.")
    st.caption("EarthWatch investigates unusual conditions. An ocean-temperature anomaly alone cannot establish a specific flood forecast.")


# Builds worldwide navigation and accepts precise locations from any backend feed.
def _globe_regions(
    anomalies: list[AnomalyRecord], region_locations: dict[str, tuple[float, float]] | None,
) -> list[dict[str, object]]:
    from math import isfinite

    centers: dict[str, tuple[float, float]] = {
        "North America": (40, -105), "South America": (-18, -60),
        "Europe": (50, 15), "Africa": (2, 22), "Asia": (35, 100),
        "Oceania": (-25, 135), "Antarctica": (-80, 0),
        "Arctic": (80, 0), "Pacific Ocean": (0, -150),
        "Atlantic Ocean": (5, -35), "Indian Ocean": (-15, 75),
    }
    known_indices = {"Nino 1+2": (-5, -85), "Nino 3.4": (0, -145)}
    for name, coordinates in (region_locations or {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Region names must be nonempty strings.")
        if not isinstance(coordinates, (tuple, list)) or len(coordinates) != 2:
            raise ValueError("Region locations must contain latitude and longitude.")
        lat, lon = coordinates
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not isfinite(value) for value in coordinates):
            raise ValueError("Region coordinates must be finite numbers.")
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Region coordinates are outside Earth's latitude or longitude range.")
        centers[name] = (lat, lon)
    for anomaly in anomalies:
        if anomaly.region not in centers and anomaly.region in known_indices:
            centers[anomaly.region] = known_indices[anomaly.region]
    names = dict.fromkeys([*centers, *(item.region for item in anomalies)])
    return [
        {"name": name, "latitude": centers[name][0] if name in centers else None,
         "longitude": centers[name][1] if name in centers else None}
        for name in names
    ]


# Serializes worldwide backend records safely for an isolated browser component.
def _globe_payload(
    anomalies: list[AnomalyRecord], assessments: list[Assessment], is_sample: bool,
    region_locations: dict[str, tuple[float, float]] | None = None,
) -> str:
    import json

    payload = {
        "anomalies": [item.model_dump(mode="json") for item in anomalies],
        "assessments": [item.model_dump(mode="json") for item in assessments],
        "regions": _globe_regions(anomalies, region_locations),
        "isSample": is_sample,
    }
    return json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")


# Builds the global globe document without executing report content as JavaScript.
def _globe_document(
    anomalies: list[AnomalyRecord], assessments: list[Assessment], is_sample: bool,
    region_locations: dict[str, tuple[float, float]] | None = None,
) -> str:
    return _GLOBE_HTML.replace(
        "__EARTHWATCH_PAYLOAD__", _globe_payload(anomalies, assessments, is_sample, region_locations),
    )


# Displays worldwide evidence; optional coordinates locate any new feed region precisely.
def climate_globe(
    anomalies: list[AnomalyRecord], assessments: list[Assessment] | None = None,
    is_sample: bool = False, *,
    region_locations: dict[str, tuple[float, float]] | None = None,
) -> None:
    document = _globe_document(anomalies, assessments or [], is_sample, region_locations)
    if hasattr(st, "iframe"):
        st.iframe(document, height="content", alt="Worldwide Earth explorer with climate observations and agent evidence")
    else:
        st.info("The interactive globe requires a Streamlit version with st.iframe. Regional observations remain available below.")
        status_strip(anomalies, is_sample)


_GLOBE_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EarthWatch · Earth explorer</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#080f18;color:#edf3f8;font:14px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
button,select{font:inherit}button,a,select{touch-action:manipulation}button{cursor:pointer}button:focus-visible,a:focus-visible,select:focus-visible,canvas:focus-visible{outline:3px solid #8be5c7;outline-offset:4px}button{min-height:44px;color:#c0d0df;border:1px solid #304252;border-radius:8px;background:#111e2c;padding:9px 14px}button:hover{background:#1d3040;color:#fff}button[aria-pressed=true]{color:#9debd1;border-color:#81c9af;background:#142e2c}a{color:#9debd1;text-underline-offset:3px}p{margin:0 0 12px}h1,h2,h3{line-height:1.25;margin:0}h1{font-size:32px;font-weight:500;letter-spacing:-1px}h2{font-size:24px;font-weight:500;letter-spacing:-.5px}h3{font-size:13px;font-weight:600;margin:24px 0 9px;color:#edf3f8}.eyebrow{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#a2b5c6;font-weight:650}.shell{border:1px solid #263746;border-radius:16px;overflow:hidden;background:radial-gradient(ellipse at 30% 35%,#152331 0%,#080f18 64%)}header{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:24px 28px;border-bottom:1px solid #263746}header .wordmark{display:flex;align-items:center;gap:12px}.icon{width:34px;height:34px;border:1px solid #89c9b6;border-radius:50%;display:grid;place-items:center;color:#9debd1;font-size:24px}.source-state{font-size:11px;border:1px solid #4c4c3b;border-radius:5px;color:#edcf92;padding:5px 9px}.main{display:grid;grid-template-columns:minmax(0,1fr) 330px;min-height:650px}.world{position:relative;min-height:650px;isolation:isolate;overflow:hidden}.world-top{position:absolute;left:28px;right:24px;top:26px;pointer-events:none;z-index:2}.world-top p{color:#b2c3d1;font-size:12px;margin-top:10px;max-width:330px}.view-label{position:absolute;left:28px;bottom:93px;color:#a2b5c6;font-size:10px;letter-spacing:1.6px;text-transform:uppercase;pointer-events:none}.view-label span{display:block;color:#dce9f0;letter-spacing:0;font-size:12px;margin-top:5px;text-transform:none}.tools{position:absolute;left:24px;bottom:24px;right:24px;z-index:2;display:flex;gap:8px;flex-wrap:wrap}.tools button{background:#101c29e8;font-size:12px}.tools button:first-child{color:#b8efd9}.legend{position:absolute;right:24px;bottom:100px;color:#a8bac9;font-size:11px;pointer-events:none}.dot{display:inline-block;width:6px;height:6px;background:#99efd4;border-radius:50%;margin-right:6px}.dot.amber{background:#eac284}.panel{background:#0d1722ee;border-left:1px solid #263746;padding:26px 24px;max-height:690px;overflow:auto;scrollbar-color:#405667 #0d1722}.panel label{display:block;margin:0 0 8px}select{width:100%;color:#e6eef4;background:#142331;border:1px solid #3a4d5b;border-radius:6px;padding:11px 9px;min-height:44px}#region-title{margin:22px 0 8px}.badge{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:1px;border:1px solid #637d74;color:#a8e9cf;padding:3px 7px;border-radius:4px;margin:4px 0 15px}.reading{font-size:38px;line-height:1.3;letter-spacing:-1px;color:#e9f6f1;font-variant-numeric:tabular-nums}.reading small{font-size:18px;color:#a6b8c9;letter-spacing:0}.muted{color:#a8bac9;font-size:12px}.rule{border-top:1px solid #263746;margin:20px 0}.meta{display:grid;grid-template-columns:76px minmax(0,1fr);gap:8px;font-size:12px}.meta dt{color:#a8bac9}.meta dd{margin:0;overflow-wrap:anywhere}.feed-state{display:flex;align-items:center;gap:8px;color:#a9bbca;font-size:11px}.feed-state::before{content:"";width:5px;height:5px;border-radius:50%;background:#eac284}.evidence{border-top:1px solid #263746;padding:12px 0}.evidence p{font-size:12px;margin:6px 0}.evidence a{font-size:12px}.evidence .eyebrow{font-size:9px;letter-spacing:1px}ul{padding-left:18px;font-size:12px;color:#c8d5e0}li{margin:6px 0}footer{border-top:1px solid #263746;padding:13px 24px;display:flex;justify-content:space-between;gap:12px;color:#9eafbf;font-size:10px;flex-wrap:wrap}#viewport{position:absolute;inset:0}canvas{display:block;touch-action:none}#loading{position:absolute;left:28px;top:130px;font-size:12px;color:#b9c9d8;max-width:330px;z-index:2}#tooltip{position:absolute;display:none;background:#142331f5;border:1px solid #506777;border-radius:6px;padding:7px 12px;color:#edf3f8;font-size:12px;pointer-events:none;z-index:3}#fallback{display:none;position:absolute;inset:170px 25px 170px;border:1px solid #304252;border-radius:10px;background:#10202c;padding:25px;color:#b8cad8;font-size:13px}#canvas-status{position:absolute;left:28px;bottom:155px;font-size:11px;color:#b8cad8;pointer-events:none}.help{margin-top:22px;border:1px solid #304252;border-radius:8px;padding:12px;font-size:12px;color:#aebfcd}.help summary{cursor:pointer;min-height:34px;display:flex;align-items:center;color:#d8e5ee}.help ol{padding-left:18px}.help li{margin:8px 0}.hidden{display:none!important}@media(max-width:760px){header{padding:18px}.main{grid-template-columns:1fr}.world{min-height:530px}.panel{border-left:0;border-top:1px solid #263746;max-height:none;padding:24px}.world-top{left:20px;top:20px}.world-top h1{font-size:28px}.world-top p{max-width:260px}.legend{display:none}.tools{left:16px;right:16px;bottom:16px;gap:5px}.tools button{padding:8px 11px}.view-label{bottom:125px;left:20px}#canvas-status{bottom:174px;left:20px}.source-state{font-size:9px}header .eyebrow{font-size:9px}.world-top .eyebrow{display:none}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/"}}</script>
</head><body><div class="shell">
<header><div class="wordmark"><span class="icon" aria-hidden="true">◎</span><div><strong style="letter-spacing:2px;font-size:13px">EARTHWATCH</strong><div class="eyebrow">Planetary intelligence</div></div></div><span class="source-state" id="data-mode"></span></header>
<div class="main"><section class="world" aria-label="Interactive Earth explorer">
<div class="world-top"><div class="eyebrow">01 / Earth explorer</div><h1>The Earth, in focus.</h1><p>Follow the signals. Explore the evidence.<br>Understand a changing planet.</p></div>
<div id="viewport"></div><div id="loading" role="status">Loading Earth imagery…</div><div id="fallback" role="status"></div><div id="tooltip"></div>
<div class="view-label">Worldwide climate watch<span>Drag to explore · Scroll or pinch to zoom</span></div><div id="canvas-status" role="status" aria-live="polite"></div>
<div class="legend"><div><span class="dot"></span>Observation supplied</div><div><span class="dot amber"></span>Awaiting coverage</div></div>
<div class="tools" aria-label="Globe controls"><button id="rotate" aria-pressed="true">Pause rotation</button><button id="reset">World view</button><button id="zoom-in" aria-label="Zoom in">＋</button><button id="zoom-out" aria-label="Zoom out">−</button></div>
</section><aside class="panel" aria-label="Selected region information"><label for="region" class="eyebrow">Explore a region</label><select id="region"><option value="__world__">Worldwide overview</option></select>
<div id="region-body" aria-live="polite"></div><details class="help"><summary>How to explore</summary><ol><li>Drag the Earth or use the region selector.</li><li>Click any regional marker or any point on Earth.</li><li>Read the dated observation and expand its evidence.</li><li>Use Pause rotation for a stationary view.</li></ol><p>The selector provides keyboard access to every monitored region. Regions without a feed show an empty state. Markers represent regional centers, not national boundaries.</p></details></aside></div>
<footer><span>Earth imagery: Three.js Earth texture collection · illustrative surface, not live satellite imagery</span><span id="coverage"></span></footer></div>
<script id="earthwatch-data" type="application/json">__EARTHWATCH_PAYLOAD__</script>
<script>
// Shows a useful fallback if the network, WebGL, or module loader is unavailable.
window.globeFallback = function(message) { document.getElementById('loading').hidden=true; const box=document.getElementById('fallback');box.style.display='block';box.textContent=message; };
window.globeTimer = setTimeout(()=>window.globeFallback('The 3D view could not load. Use the region selector to explore the same observations and evidence.'),20000);
</script>
<script>
const data=JSON.parse(document.getElementById('earthwatch-data').textContent);
const names=Object.create(null);names.__world__='Worldwide overview';
for(const region of data.regions)names[region.name]=region.name;
const available=new Set(data.anomalies.map(item=>item.region));
const select=document.getElementById('region');
document.getElementById('data-mode').textContent=data.isSample?'SAMPLE DATA / DEMONSTRATION':'SUPPLIED OBSERVATIONS';
document.getElementById('coverage').textContent=`Worldwide explorer · ${available.size} regions with supplied observations`;
for(const region of data.regions){const option=document.createElement('option');option.value=region.name;option.textContent=region.name+(available.has(region.name)?' · observation supplied':' · awaiting coverage');select.append(option);}
// Uses DOM text nodes for all backend content, including agent-authored findings.
function add(parent,tag,text,cls='') {const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;parent.append(el);return el;}
// Accepts only navigable HTTP or HTTPS evidence URLs.
function sourceLink(parent,item){if(!item.url)return;try{const url=new URL(item.url);if(!['https:','http:'].includes(url.protocol))return;const link=add(parent,'a','Open source ↗');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';}catch{}}
// Displays only records and assessment evidence supplied by the Python backend.
function regionPanel(region) {
 const parent=document.getElementById('region-body');parent.replaceChildren();
 add(parent,'h2',names[region]||region).id='region-title';add(parent,'p',region==='__world__'?'Climate observations and evidence from around the world.':'Regional climate observations and evidence.','muted');
 const records=data.anomalies.filter(item=>region==='__world__'||item.region===region).sort((a,b)=>b.observation_date.localeCompare(a.observation_date));
 const record=records[0];
 if(region==='__world__'){
  add(parent,'span',available.size+' regions with observations','badge');add(parent,'p','Worldwide navigation is available. Data coverage depends on the connected feeds.','muted');
  if(records.length)add(parent,'p','Latest supplied observation: '+records[0].observation_date,'muted');
  const latest=new Map();for(const item of records)if(!latest.has(item.region))latest.set(item.region,item);
  for(const item of latest.values()){add(parent,'h3',item.region);add(parent,'p',`${item.value} ${item.unit} · ${item.observation_date}`);add(parent,'p',item.variable.replaceAll('_',' ')+' · '+item.source,'muted');}
 }else if(record){
  add(parent,'span',record.status==='detected'?'Signal detected':record.status,'badge');
  const reading=add(parent,'div',Number(record.value).toLocaleString(undefined,{maximumFractionDigits:2}),'reading');add(reading,'small',' '+(record.unit==='degC'?'°C':record.unit));
  add(parent,'p',record.variable.replaceAll('_',' '),'muted');
  const meta=add(parent,'dl','','meta');for(const [key,value] of [['Observed',record.observation_date],['Baseline',record.baseline_period],['Source',record.source]]){add(meta,'dt',key);add(meta,'dd',value);}
 }else{add(parent,'span','Awaiting observations','badge');add(parent,'p','No measurements have been supplied for this location.','muted');}
 add(parent,'div','','rule');add(parent,'div',data.isSample?'Sample assessment feed':'Agent assessment feed','eyebrow');
 const ids=new Set(records.map(item=>item.anomaly_id));
 const reports=data.assessments.filter(item=>ids.has(item.anomaly_id));
 if(!reports.length){add(parent,'p','Awaiting agent feed','feed-state');add(parent,'p','No source-backed update has been supplied. New reports will appear when the dashboard receives refreshed backend data.','muted');}
 for(const report of reports){
  if(region==='__world__'){const observation=records.find(item=>item.anomaly_id===report.anomaly_id);add(parent,'h3',observation?.region||'Regional assessment');}
  add(parent,'p',report.summary);
  if(report.regional_implications.length){add(parent,'h3','Potential regional implications');const list=add(parent,'ul','');for(const text of report.regional_implications)add(list,'li',text);}
  add(parent,'p','Confidence: '+report.confidence,'muted');
  const order={measured:0,reported:1,inferred:2,uncertain:3};
  for(const item of [...report.evidence].sort((a,b)=>order[a.evidence_type]-order[b.evidence_type])){
   const entry=add(parent,'details','','evidence');add(entry,'summary',item.evidence_type+' · '+(item.source_date||'undated'));
   add(entry,'p',item.claim);add(entry,'p',item.source,'muted');if(item.limitations)add(entry,'p','Limitations: '+item.limitations,'muted');sourceLink(entry,item);
  }
  if(report.limitations.length){add(parent,'h3','Limitations');for(const text of report.limitations)add(parent,'p',text,'muted');}
 }
 const location=data.regions.find(item=>item.name===region);if(record&&location?.latitude===null)add(parent,'p','Map location not supplied. This report is listed without guessing its coordinates.','muted');
 add(parent,'p','An observed anomaly alone does not establish a specific disaster forecast.','muted');
}
select.addEventListener('change',()=>{regionPanel(select.value);window.dispatchEvent(new CustomEvent('earthwatch-focus',{detail:select.value}));});
regionPanel(select.value);
</script>
<script type="module">
try {
 const THREE=await import('three'); const {OrbitControls}=await import('three/addons/controls/OrbitControls.js');
 const viewport=document.getElementById('viewport');
 const scene=new THREE.Scene();const camera=new THREE.PerspectiveCamera(36,1,.1,100);camera.position.set(3.0,1.4,1.6);
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.setClearColor(0x000000,0);viewport.append(renderer.domElement);
 renderer.domElement.tabIndex=0;renderer.domElement.setAttribute('aria-label','Interactive Earth. Drag to rotate, scroll to zoom. Use region selector for keyboard navigation.');
 const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=2.2;controls.maxDistance=5.5;controls.autoRotate=!matchMedia('(prefers-reduced-motion: reduce)').matches;controls.autoRotateSpeed=.3;
 controls.listenToKeyEvents(renderer.domElement);
 const button=document.getElementById('rotate');
 // Keeps the motion control label synchronized with its actual state.
 function rotation(value){controls.autoRotate=value;button.textContent=value?'Pause rotation':'Resume rotation';button.setAttribute('aria-pressed',String(value));}
 rotation(controls.autoRotate);button.onclick=()=>rotation(!controls.autoRotate);
 scene.add(new THREE.AmbientLight(0xa6bedd,1.8));const sun=new THREE.DirectionalLight(0xfff1dc,2.5);scene.add(sun);
 const loader=new THREE.TextureLoader();const root='https://threejs.org/examples/textures/planets/';
 // Loads a real Earth surface image and preserves an explicit fallback on failure.
 const texture=await loader.loadAsync(root+'earth_atmos_2048.jpg');texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
 const earth=new THREE.Mesh(new THREE.SphereGeometry(1,96,64),new THREE.MeshPhongMaterial({map:texture,shininess:12,specular:0x556c7c}));scene.add(earth);
 loader.load(root+'earth_normal_2048.jpg',map=>{earth.material.normalMap=map;earth.material.normalScale.set(.45,.45);earth.material.needsUpdate=true;});
 loader.load(root+'earth_specular_2048.jpg',map=>{earth.material.specularMap=map;earth.material.needsUpdate=true;});
 const atmosphere=new THREE.Mesh(new THREE.SphereGeometry(1.035,64,48),new THREE.ShaderMaterial({vertexShader:'varying vec3 n; varying vec3 v; void main(){vec4 p=modelViewMatrix*vec4(position,1.0);n=normalize(normalMatrix*normal);v=normalize(-p.xyz);gl_Position=projectionMatrix*p;}',fragmentShader:'varying vec3 n; varying vec3 v; void main(){float rim=pow(1.0-abs(dot(normalize(n),normalize(v))),4.0);gl_FragColor=vec4(0.28,0.65,0.95,rim*0.45);}',transparent:true,depthWrite:false,blending:THREE.AdditiveBlending}));scene.add(atmosphere);
 // Converts geographic coordinates to the sphere's equirectangular texture coordinates.
 function xyz(lat,lon,r=1.008){const a=THREE.MathUtils.degToRad(lat),b=THREE.MathUtils.degToRad(lon);return new THREE.Vector3(r*Math.cos(a)*Math.cos(b),r*Math.sin(a),-r*Math.cos(a)*Math.sin(b));}
 const knownBoxes={'Nino 1+2':[-10,0,-90,-80],'Nino 3.4':[-5,5,-170,-120]};const boxes=Object.fromEntries(Object.entries(knownBoxes).filter(([name])=>available.has(name)));
 const centers=Object.create(null);for(const region of data.regions)if(region.latitude!==null)centers[region.name]=[region.latitude,region.longitude];
 const overlays={};
 // Draws geographic monitoring boundaries with enough vertices to follow Earth's curvature.
 for(const [region,[south,north,west,east]] of Object.entries(boxes)){
  const points=[];for(let i=0;i<=48;i++)points.push(xyz(south,west+(east-west)*i/48));for(let i=1;i<=24;i++)points.push(xyz(south+(north-south)*i/24,east));for(let i=1;i<=48;i++)points.push(xyz(north,east-(east-west)*i/48));for(let i=1;i<=24;i++)points.push(xyz(north-(north-south)*i/24,west));
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0x91ebd0,transparent:true,opacity:.85}));scene.add(line);overlays[region]=line;
 }
 const markers=[];
 // Marks every global navigation center and every geolocated backend region.
 for(const [name,coordinates] of Object.entries(centers)){
  const color=available.has(name)?0x99efd4:0xeac284;
  const marker=new THREE.Mesh(new THREE.SphereGeometry(.012,16,12),new THREE.MeshBasicMaterial({color}));marker.position.copy(xyz(...coordinates,1.016));marker.userData.region=name;scene.add(marker);markers.push(marker);
  const ring=new THREE.Mesh(new THREE.RingGeometry(.021,.026,32),new THREE.MeshBasicMaterial({color,side:THREE.DoubleSide,transparent:true,opacity:.65}));ring.position.copy(xyz(...coordinates,1.01));ring.lookAt(ring.position.clone().multiplyScalar(2));scene.add(ring);
 }
 let targetPosition=null;
 // Focuses a region and stops rotation so a selected area remains available to inspect.
 function focus(region){if(region==='__world__'){rotation(false);targetPosition=new THREE.Vector3(3.0,1.4,1.6);return;}const position=centers[region];if(!position){document.getElementById('canvas-status').textContent='Map location not supplied for '+region;return;}rotation(false);targetPosition=xyz(...position,3.6);for(const [key,line] of Object.entries(overlays)){line.material.color.set(key===region?0xffffff:0x91ebd0);line.material.opacity=key===region?1:.6;}document.getElementById('canvas-status').textContent='Viewing '+names[region];}
 window.addEventListener('earthwatch-focus',event=>focus(event.detail));
 document.getElementById('reset').onclick=()=>{select.value='__world__';regionPanel('__world__');focus('__world__');document.getElementById('canvas-status').textContent='Worldwide view';};
 document.getElementById('zoom-in').onclick=()=>{targetPosition=null;camera.position.multiplyScalar(Math.max(2.2/camera.position.length(),.85));controls.update();};document.getElementById('zoom-out').onclick=()=>{targetPosition=null;camera.position.multiplyScalar(Math.min(5.5/camera.position.length(),1.15));controls.update();};
 controls.addEventListener('start',()=>{targetPosition=null;rotation(false);});
 const ray=new THREE.Raycaster();const pointer=new THREE.Vector2();let down=null;
 // Picks the visible Earth surface, preventing clicks through to its far side.
 function pick(event){const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObject(earth)[0];if(!hit)return null;const p=hit.point.clone().normalize();const lat=THREE.MathUtils.radToDeg(Math.asin(p.y)),lon=-THREE.MathUtils.radToDeg(Math.atan2(p.z,p.x));let region=null;for(const [name,[s,n,w,e]]of Object.entries(boxes)){if(lat>=s&&lat<=n&&lon>=w&&lon<=e)region=name;}const markerHit=ray.intersectObjects(markers).find(item=>item.distance<=hit.distance+.055);if(markerHit)region=markerHit.object.userData.region;else{const nearby=markers.map(marker=>({name:marker.userData.region,distance:hit.point.distanceTo(marker.position)})).sort((a,b)=>a.distance-b.distance)[0];if(nearby?.distance<.055)region=nearby.name;}return {region,lat,lon};}
 renderer.domElement.addEventListener('pointerdown',event=>{down=[event.clientX,event.clientY];});
 renderer.domElement.addEventListener('pointerup',event=>{if(!down||Math.hypot(event.clientX-down[0],event.clientY-down[1])>6)return;down=null;const hit=pick(event);if(!hit)return;if(hit.region){select.value=hit.region;regionPanel(hit.region);focus(hit.region);}else{const location=`${hit.lat.toFixed(1)}°, ${hit.lon.toFixed(1)}°`;select.selectedIndex=-1;regionPanel(location);document.getElementById('canvas-status').textContent=location+' · No monitoring feed at this location';}});
 const tooltip=document.getElementById('tooltip');
 renderer.domElement.addEventListener('pointermove',event=>{const hit=pick(event);renderer.domElement.style.cursor=hit?.region?'pointer':'grab';if(hit?.region){const rect=viewport.getBoundingClientRect();tooltip.style.display='block';tooltip.style.left=Math.min(event.clientX-rect.left+12,rect.width-160)+'px';tooltip.style.top=(event.clientY-rect.top-38)+'px';tooltip.textContent=names[hit.region];}else tooltip.style.display='none';});renderer.domElement.addEventListener('pointerleave',()=>tooltip.style.display='none');
 // Resizes for mobile layouts and browser zoom without stretching the sphere.
 new ResizeObserver(()=>{const width=viewport.clientWidth,height=viewport.clientHeight;camera.aspect=width/height;camera.fov=THREE.MathUtils.radToDeg(2*Math.atan(Math.tan(THREE.MathUtils.degToRad(36)/2)/Math.min(1,camera.aspect)));camera.updateProjectionMatrix();renderer.setSize(width,height);}).observe(viewport);
 const clock=new THREE.Clock();let previous=0;
 // Keeps lighting tied to the viewing direction for a legible, naturally shaded surface.
 renderer.setAnimationLoop(()=>{const elapsed=clock.getElapsedTime(),delta=Math.min(elapsed-previous,.05);previous=elapsed;if(document.hidden)return;if(targetPosition){camera.position.lerp(targetPosition,1-Math.exp(-delta*5));if(camera.position.distanceTo(targetPosition)<.002)targetPosition=null;}controls.update(delta);sun.position.copy(camera.position).add(new THREE.Vector3(-2,2,1));renderer.render(scene,camera);});
 clearTimeout(window.globeTimer);document.getElementById('loading').hidden=true;document.getElementById('fallback').style.display='none';
 window.addEventListener('pagehide',()=>{renderer.setAnimationLoop(null);controls.dispose();renderer.dispose();});
} catch(error){clearTimeout(window.globeTimer);window.globeFallback('The 3D view is unavailable. Use the region selector to explore observations and evidence.');console.error('EarthWatch globe:',error);}
</script></body></html>'''
