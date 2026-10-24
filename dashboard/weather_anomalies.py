"""Globe-first current weather comparison and Grok safety briefing."""
from datetime import datetime, timezone
from html import escape

import plotly.graph_objects as go
import streamlit as st

from analysis.current_anomalies import compare_current
from agents.weather_brief import ACTIONS, explain
from data import san_diego_heat as heat
from data.locations import Location, search_locations
from dashboard.globe import GLOBE_CSS, GLOBE_JS

_HTML = '''
<div class="stage"><div id="globeViz" role="img" aria-label="Weather comparisons globe; use the location selector for keyboard access"></div>
<div id="fallback" role="status">Globe unavailable. Use the location selector below.</div>
<div id="legend"><div>● Red · reported weather anomaly &nbsp; ● Coral · historical anomaly &nbsp; ● Mint · within screening range</div>
<div>● Gray · not scanned or insufficient history</div><div class="hint">Click a location to open its history · drag to explore</div></div></div>
'''
_GLOBE = st.components.v2.component('weather_anomaly_globe', html=_HTML, css=GLOBE_CSS, js=GLOBE_JS)
_SPEECH = st.components.v2.component(
    'weather_brief_announcement',
    html='<div><button id="speak" type="button">Read briefing aloud</button> <button id="stop" type="button">Stop</button><span id="message" role="status"></span></div>',
    css="""
    button { background: #426346; color: #edf3fa; border: 1px solid #8c9675;
             border-radius: 8px; padding: 12px; cursor: pointer; font: inherit; }
    button:focus-visible { outline: 3px solid #426346; }
    """,
    js="""
    export default function({parentElement, data}) {
      const speak=parentElement.querySelector('#speak'), stop=parentElement.querySelector('#stop');
      const message=parentElement.querySelector('#message');
      if (!('speechSynthesis' in window)) {
        speak.disabled=true; stop.disabled=true; message.textContent='Audio unavailable in this browser.';
        return;
      }
      speak.onclick=()=>{
        window.speechSynthesis.cancel();
        const utterance=new SpeechSynthesisUtterance(data.text);
        utterance.onerror=()=>{message.textContent='Audio unavailable. Read the briefing below.';};
        window.speechSynthesis.speak(utterance);
      };
      stop.onclick=()=>window.speechSynthesis.cancel();
      return ()=>window.speechSynthesis.cancel();
    }
    """,
)
DEFAULTS = [Location('San Diego',32.7157,-117.1611), Location('London',51.5074,-0.1278),
            Location('Mumbai',19.076,72.8777), Location('Tokyo',35.6762,139.6503),
            Location('Sydney',-33.8688,151.2093), Location('Cape Town',-33.9249,18.4241),
            Location('São Paulo',-23.5505,-46.6333)]


REPORTED_COLOR = '#e5322d'
REPORT_SECTIONS = ('What happened', 'Why it happened', 'El Niño connection')


def reported_event(place):
    """The documented anomaly report for a watched place, if one exists within ~25 km."""
    return heat if abs(place.latitude-heat.LATITUDE) < .25 and abs(place.longitude-heat.LONGITUDE) < .25 else None


def render_reported_anomaly(report):
    st.error('Daily heat records fell across San Diego County in early October 2026. '
             'This is a documented, source-linked event, separate from the live comparison below.',
             title='Reported weather anomaly · record heat', icon=':material/local_fire_department:')
    for section in REPORT_SECTIONS:
        st.markdown(f"**{'Why it was so hot' if section == 'Why it happened' else section}**")
        for finding in (f for f in report.FINDINGS if f['section'] == section):
            st.caption(finding['status'])
            st.markdown(finding['text'])
            st.markdown(' · '.join(f"[{report.SOURCES[ref]['title']}]({report.SOURCES[ref]['url']})" for ref in finding['refs']))
    with st.expander('Impacts and unknowns'):
        for finding in (f for f in report.FINDINGS if f['section'] not in REPORT_SECTIONS):
            st.markdown(f"**{finding['status']}** · {finding['text']}")
    st.caption(f'Sources checked {report.VERIFIED_ON:%d %B %Y}. Airport and station records, not readings for every neighborhood.')


def comparison_chart(metric, fahrenheit=False):
    convert = lambda value: value * 1.8 + 32 if fahrenheit and metric.variable == 'temperature' else value
    unit = '°F' if fahrenheit and metric.variable == 'temperature' else metric.unit
    fig = go.Figure()
    if metric.samples:
        fig.add_trace(go.Histogram(x=[convert(v) for v in metric.samples], name='1991–2020 history',
                                  marker_color='#6cd5c3', opacity=.65, nbinsx=35))
    if metric.p05 is not None:
        fig.add_vrect(x0=convert(metric.p05), x1=convert(metric.p95), fillcolor='#6cd5c3', opacity=.1,
                      line_width=0, annotation_text='Historical 5th–95th percentile')
        fig.add_vline(x=convert(metric.historical_mean), line_color='#6cd5c3', line_dash='dash', annotation_text='Historical mean')
    if metric.current is not None:
        fig.add_vline(x=convert(metric.current), line_color='#ff827a', line_width=3, annotation_text='Now')
    fig.update_layout(height=310, margin=dict(l=15,r=15,t=40,b=30), paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)', xaxis_title=unit, yaxis_title='Historical hours', showlegend=False)
    return fig


def fresh(snapshot):
    return -900 <= (datetime.now(timezone.utc)-snapshot.conditions_time).total_seconds() <= 5400 and (datetime.now(timezone.utc)-snapshot.retrieved_at).total_seconds() <= 600


def render_weather_anomalies():
    st.caption('WEATHER INTELLIGENCE / CURRENT CONDITIONS × HISTORICAL CONTEXT')
    st.header('See what’s unusual. Know what to do.')
    st.write('Explore weather departures around the world, compare them with local history, and ask Grok for possible causes and protective actions.')
    state = st.session_state
    state.setdefault('weather_places', {p.key:p for p in DEFAULTS})
    state.setdefault('weather_snapshots', {})
    state.setdefault('weather_briefs', {})
    places, snapshots = state.weather_places, state.weather_snapshots
    with st.sidebar.expander('Add a location'):
        with st.form('weather_search'):
            query = st.text_input('City or postal code')
            search = st.form_submit_button('Search')
        if search:
            try:
                state.weather_search_results = search_locations(query)
            except Exception:
                st.error('Location search unavailable. Try again shortly.')
        results = state.get('weather_search_results', [])
        if results:
            choice = st.selectbox('Matching places', results, format_func=lambda p:p.label)
            if st.button('Watch this place'):
                places[choice.key] = choice
                state.weather_selected = choice.key
        with st.form('weather_coordinates'):
            name = st.text_input('Location name', value='Custom location')
            lat = st.number_input('Latitude', -90.,90.,32.7157)
            lon = st.number_input('Longitude',-180.,180.,-117.1611)
            if st.form_submit_button('Add coordinates'):
                if name.strip():
                    place = Location(name,lat,lon)
                    places[place.key] = place
                    state.weather_selected = place.key
    state.setdefault('weather_selected', next(iter(places)))
    selected = places[state.weather_selected]
    units = st.sidebar.segmented_control('Temperature units', ['°F','°C'], default='°F')
    valid = {key:value for key,value in snapshots.items() if fresh(value)}
    a,b,c = st.columns(3)
    a.metric('Watched locations', len(places))
    b.metric('Fresh comparisons',len(valid))
    c.metric('Locations with anomalies',sum(any(m.unusual for m in s.metrics) for s in valid.values()))
    targets = st.multiselect('Locations to scan', list(places), default=[selected.key], format_func=lambda k:places[k].label)
    if st.button('Scan weather against history', type='primary', disabled=not targets):
        for key in targets:
            with st.spinner(f'Comparing {places[key].name} with 30 years of history…'):
                try:
                    snapshots[key] = compare_current(places[key],refresh=True)
                except Exception:
                    snapshots.pop(key,None)
                    st.error(f'{places[key].label}: weather unavailable. No anomaly was inferred.')
        st.rerun()
    st.caption('Scan selected locations on demand. First scans download historical data and may take a minute. This is a location watchlist, not continuous coverage of the entire world.')
    left,right = st.columns([1.25,1],gap='large')
    with left:
        points=[]
        for key,p in places.items():
            snap=valid.get(key)
            unusual=bool(snap and any(m.unusual for m in snap.metrics))
            adequate=bool(snap and all(m.historical_mean is not None and m.current is not None for m in snap.metrics))
            report=reported_event(p)
            color=REPORTED_COLOR if report else '#ff827a' if unusual else '#6cd5c3' if adequate else '#94a3b8'
            tooltip=(f'<b>{escape(p.name)} · reported heat anomaly</b><br>Record heat, early October 2026 · click to see why'
                     if report else escape(p.label))
            points.append(dict(lat=p.latitude,lng=p.longitude,label=p.name+(' · record heat' if report else ''),region=p.name,
                               anomaly_id=key,color=color,radius=1.1 if report else .65,tooltip=tooltip))
        def pick():
            key=state['weather_globe'].get('selected')
            if key in places:
                state.weather_selected=key
        _GLOBE(key='weather_globe',height=700,on_selected_change=pick,data=dict(points=points,outlines=[],
            rings=[dict(lat=p['lat'],lng=p['lng'],color=p['color'],maxRadius=4) for p in points if p['color'] in ('#ff827a',REPORTED_COLOR)],
            view=dict(lat=selected.latitude,lng=selected.longitude,altitude=2.5),view_key=selected.key,rotate=False,pulses=True))
        st.selectbox('Open location',list(places),format_func=lambda k:places[k].label,key='weather_selected')
    with right:
        st.subheader(selected.label)
        report=reported_event(selected)
        if report:
            render_reported_anomaly(report)
            st.divider()
        snapshot=snapshots.get(selected.key)
        if snapshot is None:
            st.info('Scan this location to reveal its current weather, historical comparison, and Grok briefing.')
            if not report:
                st.caption('For example, 100°F versus a comparable historical mean of 67°F is a +33°F departure. This is an illustration, not a current San Diego reading.')
            return
        if not fresh(snapshot):
            st.warning('This snapshot is out of date. Scan again before using it for current conditions.')
        st.caption(f'Conditions: {snapshot.conditions_time:%b %d, %Y · %H:%M %Z} · model estimate')
        metric_name=st.segmented_control('Weather signal',['temperature','precipitation','wind'],default='temperature') or 'temperature'
        metric=next(m for m in snapshot.metrics if m.variable==metric_name)
        fahrenheit=units=='°F' and metric.variable=='temperature'
        unit='°F' if fahrenheit else metric.unit
        def display(value,delta=False):
            if value is None: return 'Unavailable'
            number=value*1.8+(0 if delta else 32) if fahrenheit else value
            return f'{number:+.1f} {unit}' if delta else f'{number:.1f} {unit}'
        st.markdown(f'**{metric.status}**')
        a,b=st.columns(2)
        a.metric('Current estimate',display(metric.current),display(metric.difference,True) if metric.difference is not None else None,delta_color='off')
        b.metric('Historical mean',display(metric.historical_mean))
        st.plotly_chart(comparison_chart(metric,units=='°F'),width='stretch',alt='Historical distribution with the current estimate and historical mean marked')
        st.caption(f'{snapshot.baseline_period} · same local hour · calendar date ±7 days · {metric.sample_count} valid hours across {metric.year_count} years. Shading: historical 5th–95th percentiles. This is a distribution, not a time series.')
        if snapshot.baseline_error: st.warning(snapshot.baseline_error)
        st.subheader('Grok · understand & prepare')
        if st.button('Explain causes & safety actions',type='primary',disabled=not fresh(snapshot)):
            with st.spinner('Grok is reviewing the measured departures…'):
                try:
                    state.weather_briefs[snapshot.identity]=explain(snapshot)
                    st.toast('Grok briefing ready — review actions below.')
                except Exception:
                    st.error('Grok briefing unavailable. Check xAI configuration and credits, then retry. General safety resources remain below.')
        brief=state.weather_briefs.get(snapshot.identity)
        if brief:
            st.write(brief.summary)
            spoken = selected.label + '. ' + brief.summary + ' Possible causes, not confirmed: ' + ' '.join(c.hypothesis for c in brief.possible_causes) + ' Protective actions: ' + ' '.join(ACTIONS[a.action_id][0] + ' ' + a.why_it_helps for a in brief.actions)
            _SPEECH(key='announcement_'+snapshot.identity, data={'text':spoken}, height=60)
            st.markdown('**Why this may be happening**')
            for cause in brief.possible_causes:
                st.write(cause.hypothesis)
                st.caption('To verify: '+cause.what_to_check)
                st.caption('Evidence: '+', '.join(f'{ref} = {snapshot.evidence()[ref]:.2f}' for ref in cause.evidence_refs))
            st.markdown('**Actions you can take**')
            for action in brief.actions:
                label,url=ACTIONS[action.action_id]
                st.markdown(f'- [{label}]({url}) {action.why_it_helps}')
            for limitation in brief.limitations: st.caption(limitation)
            st.download_button('Download Grok briefing',brief.model_dump_json(indent=2),file_name='weather-briefing.json',mime='application/json')
        else:
            st.caption('Grok uses this exact snapshot. Possible causes need additional evidence; weather anomalies alone cannot establish event attribution.')
        with st.expander('Safety resources & methodology'):
            st.markdown('[Heat safety · CDC](https://www.cdc.gov/heat-health/about/) · [Flood safety · NWS](https://www.weather.gov/safety/flood) · [Local weather services · WMO](https://worldweather.wmo.int/)')
            st.write('Screening requires at least 20 historical years and 200 matching hours. Temperature must fall outside the 5th–95th percentile with a departure of at least 3°C; wind must exceed the 95th percentile by at least 10 km/h above the mean; hourly rain must exceed the 95th percentile and the mean by at least 1 mm. These are screening rules, not official warnings. A normal reading does not mean hazard-free.')
            st.caption('Current weather models and ERA5 history use different grids and methods. Differences can include model bias. Rain uses the latest completed model hour.')
            st.markdown(f'[Current source]({snapshot.current_source})')
            if snapshot.baseline_source: st.markdown(f'[Historical source]({snapshot.baseline_source})')
            st.markdown('[How attribution works · NOAA](https://psl.noaa.gov/csi/whatis/)')
