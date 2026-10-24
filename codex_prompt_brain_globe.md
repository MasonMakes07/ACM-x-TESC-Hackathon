# Codex prompt: make the EarthWatch globe look and behave like the portfolio brain

Not committed. Paste everything inside the code block below into Codex. It can run on any device.

```
You are a coding agent on the EarthWatch hackathon repo (Python + Streamlit). Another agent is
changing OTHER files right now, so follow the file rules exactly.

== SETUP ==
git clone git@github.com:MasonMakes07/ACM-x-TESC-Hackathon.git earthwatch-globe
  (if SSH fails: gh repo clone MasonMakes07/ACM-x-TESC-Hackathon earthwatch-globe)
cd earthwatch-globe && git checkout main && git pull && git checkout -b p3-brain-globe
python3 -m venv .venv && source .venv/bin/activate    (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
pytest -q          # must pass before you start

== FILE RULES ==
Edit ONLY: dashboard/globe.py and tests/test_dashboard_globe.py.
Do NOT edit app.py, translator.py, dashboard/components.py, schemas/, agents/, data/, analysis/.
Do not add Python dependencies. Load three.js only from
https://cdn.jsdelivr.net/npm/three@0.150.1/build/three.min.js (or keep globe.gl@2.46.2 if you build
on it). Pin exact versions. Keep the one-comment-line-above-every-function style.

== THE REFERENCE ==
Study the 3D brain at https://alexgilbreath11.github.io . Its code is
https://alexgilbreath11.github.io/brain/brain-stage.js (custom element <brain-stage>, three.js 0.150.1).
Reproduce its LOOK and FEEL for a planet Earth. What makes the brain feel the way it does:
1. X-ray / holographic material: ShaderMaterial with a fresnel rim. Base #5980a6, accent #9dc2e0,
   rim/edge #cfe4f5. Transparent canvas (alpha: true, setClearAlpha(0)), no photo texture needed.
   For Earth: draw continents as glowing outlines or a dense field of land dots on that x-ray sphere.
2. Sparkle particles: THREE.Points with an additive-blending ShaderMaterial scattered over the
   surface (on land for Earth), twinkling with uTime. Particles near the active event burn brighter
   (the brain uses uActive + a hot color #ffffff).
3. Hover + select: a Raycaster picks event markers every frame from the pointer. The hovered or
   selected event glows (uniform eases toward 1 with dt*5.5); everything else dims (uDim eases with
   dt*4). Cursor becomes a pointer over an event.
4. Leader-line labels (SVG overlay, pointer-events:none): a dot on the 3D anchor, a line out ~96px
   from the globe centre, a short horizontal tick, then a text plate. Labels fade out when their
   anchor faces away from the camera (normal·toCamera < 0.10), ease their y position (dt*6), stay
   inside the frame, and the active label is full opacity while others drop to 0.30.
5. Motion: slow idle spin (~0.12 rad/s) eased with velocity smoothing; gentle float drift
   (sin-based position/rotation wobble, amplitude ~0.035); drag rotates Y and tilts X clamped to
   ±0.65; a click only counts if the pointer moved < 5px (so drags never select). Stop rendering while
   scrolled out of view (IntersectionObserver) but keep the rAF loop alive. Respect
   prefers-reduced-motion (no spin, no drift, no twinkle).
6. Controls: a small nav row of buttons, one per event (label = region name) plus "Pause rotation".
   Buttons select the event too, so keyboard users can do everything without the canvas.

== THE CONTRACT (do not break) ==
dashboard/globe.py is a Streamlit Custom Component v2 (st.components.v2.component). Keep:
- render_globe(anomalies, selected_region, on_select, *, region_locations=None,
               severity_by_anomaly=None) -> None   (same signature, same key="globe")
- globe_data(...) -> dict and unplotted_regions(...) stay pure Python, return JSON-safe data, and
  only ever contain values derived from the AnomalyRecords passed in. Never invent events.
- Clicking an event (canvas OR nav button) must call setTriggerValue("selected", anomaly_id) so the
  existing on_select callback keeps working. Selecting must NOT start an investigation by itself.
- Escape every text value that reaches HTML/SVG (region, source, labels).
- Events can be ANYWHERE on Earth: region strings may carry coordinates as
  "Place name (lat, lon)" and region_locations maps names to (lat, lon). Coastal tide-gauge events
  (variable "Coastal water level above predicted tide", e.g. San Diego, Miami, New York) and Pacific
  El Nino indices must both appear. Do not centre or label the view on Peru/Pacific only.
- Labels and nav buttons show the place name WITHOUT the "(lat, lon)" suffix (e.g. "San Diego, CA"),
  plus the value and unit (e.g. "+0.47 m above predicted tide"). Every event marker must be clickable.
- Keep the existing severity colors/legend and the "click an event" hint, restyled to match.
- If WebGL or the CDN fails, show the existing readable fallback message; the dashboard must still work.

== TESTS ==
Update tests/test_dashboard_globe.py: keep every existing contract test passing (adjust only tests
of markup you replaced), and add tests that: globe_data includes a coastal record placed from its
"(lat, lon)" region; nav buttons exist for each event in the generated HTML/JS payload; hostile
text is escaped; the pinned three.js URL is used.

== FINISH ==
pytest -q                                 # whole repo must pass
streamlit run app.py                      # click an event on the globe and in the nav row; check it selects
git add dashboard/globe.py tests/test_dashboard_globe.py
git commit -m "Globe: x-ray holographic Earth styled after the portfolio brain"
git push -u origin p3-brain-globe
Do NOT merge, open a PR, or push to main. Reply with the branch name, the pytest result line, a
screenshot description, and at most 5 bullets of decisions.
```

## After Codex replies
Tell Claude **"brain globe pushed"**. Claude fetches `p3-brain-globe`, tests it together with the coastal
events and tutorial work, and merges it.
