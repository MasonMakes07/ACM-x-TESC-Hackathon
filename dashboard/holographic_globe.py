"""Holographic Earth with accessible event selection, inspired by the portfolio brain."""
import json
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).parent
HTML = '''
<div class="earth-stage">
  <div class="eyebrow">EARTHWATCH / PLANETARY SIGNALS</div>
  <div class="viewport" role="img" aria-label="Interactive holographic Earth. Use event buttons below for keyboard selection."></div>
  <svg class="labels" aria-hidden="true"></svg>
  <div class="fallback" role="status">Loading holographic Earth…</div>
  <div class="hint">Drag to rotate · select a signal to inspect its history</div>
</div>
<div class="controls"><button class="motion" type="button">Pause rotation</button><div class="events" aria-label="Select an event"></div></div>
'''
CSS = '''
.earth-stage {height:560px;position:relative;overflow:hidden;border:1px solid #31495e;border-radius:20px;
background:radial-gradient(ellipse at 50% 45%,#172c3f,#0b111b 70%);font-family:var(--st-font,sans-serif);}
.earth-stage:before{content:'';position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(#5980a60b 1px,transparent 1px),linear-gradient(90deg,#5980a60b 1px,transparent 1px);background-size:48px 48px;}
.viewport,.labels{position:absolute;inset:0;width:100%;height:100%;touch-action:none;}
.labels{pointer-events:none;overflow:hidden}.eyebrow,.hint{position:absolute;z-index:2;left:22px;right:22px;color:#9dc2e0;font-size:11px;letter-spacing:.13em;pointer-events:none;}
.eyebrow{top:22px}.hint{bottom:18px;letter-spacing:.02em}.fallback{position:absolute;inset:0;display:grid;place-items:center;color:#cfe4f5;text-align:center;padding:35px;pointer-events:none;}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.events{display:flex;flex-wrap:wrap;gap:8px}
button{background:#101f2d;border:1px solid #38516a;border-radius:8px;color:#b9d4e8;padding:10px 13px;font:inherit;font-size:12px;cursor:pointer;min-height:44px}
button[aria-pressed=true]{background:#26465e;border-color:#9dc2e0;color:#fff;box-shadow:0 0 18px #5980a633}button:focus-visible{outline:3px solid #cfe4f5;outline-offset:2px}
@media(max-width:600px){.earth-stage{height:440px}.eyebrow{font-size:9px}}
'''
JS = (_ROOT / 'holographic_globe.js').read_text()
_COMPONENT = st.components.v2.component('earthwatch_holographic_earth', html=HTML, css=CSS, js=JS)


# Reuses bundled public-domain geography without remote texture dependencies.
@st.cache_data
def boundaries():
    return json.loads((_ROOT.parent / 'data/world_boundaries.json').read_text())['rings']


# Keeps the selection trigger identical for all event consumers.
def render_holographic_globe(points, selected, on_select, *, key='weather_globe', rotate=True):
    def picked():
        value = st.session_state[key].get('selected')
        if value in {p['anomaly_id'] for p in points}:
            on_select(value)
    _COMPONENT(key=key, data={'points':points, 'selected':selected, 'rings':boundaries(), 'rotate':rotate},
               height=730, on_selected_change=picked)
