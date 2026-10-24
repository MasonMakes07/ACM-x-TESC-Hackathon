"""Source-populated global event globe with continuously updated Grok reviews."""
from html import escape

import streamlit as st

from agents.hazard_monitor import CHECK_SECONDS, HazardMonitor, grok_ready, utcnow
from dashboard.globe import GLOBE_CSS, GLOBE_JS
from schemas.global_hazards import HAZARD_NAMES

COLORS = {'TC': '#D65D62', 'WET': '#63B891', 'DRY': '#C19960', 'WARM': '#E39054', 'COLD': '#6DAAE0'}
SELECTED_KEY = 'global_hazard_selected'
_HTML = '''
<div class="stage"><div id="globeViz" role="img" aria-label="NOAA global hazard outlook globe. Click a forecast area or use Choose an event below."></div>
<div id="fallback" role="status">The 3D view could not load. Choose an event below to read every forecast and source.</div>
<div id="legend"><div>● Rose · cyclone formation &nbsp; ● Green · wetter &nbsp; ● Sand · drier</div>
<div>● Orange · warmer &nbsp; ● Blue · cooler</div>
<div class="hint">Click a shaded area or marker · colors show forecast type, not severity</div></div></div>
'''
_GLOBE = st.components.v2.component('earthwatch_global_hazards', html=_HTML, css=GLOBE_CSS, js=GLOBE_JS)


@st.cache_resource
def get_hazard_monitor():
    return HazardMonitor()


def event_label(event, reviews):
    review = reviews.get(event.event_id)
    area = review.explanation.area_name if review else event.coordinate_label
    return f'{HAZARD_NAMES[event.hazard]} · {area} · week {event.week} · ≥{event.probability}%'


def build_globe_data(events, selected_id, reviews, *, rotate=True):
    points, polygons = [], []
    for event in events:
        color = COLORS[event.hazard]
        selected = event.event_id == selected_id
        label = event_label(event, reviews)
        tooltip = f'<b>{escape(label)}</b><br>{event.valid_start:%b %d}–{event.valid_end:%b %d, %Y}<br>NOAA forecast · click for evidence and Grok review'
        points.append(dict(lat=event.latitude, lng=event.longitude, radius=0.85 if selected else 0.38,
                           color=color, label=label if selected else '', region=selected,
                           tooltip=tooltip, anomaly_id=event.event_id))
        polygons.append(dict(geometry=event.geometry.model_dump(mode='json'), color=color,
                             fill=color + ('99' if selected else '45'), selected=selected,
                             tooltip=tooltip, anomaly_id=event.event_id))
    selected = next((event for event in events if event.event_id == selected_id), None)
    return dict(points=points, polygons=polygons, outlines=[], rings=[], rotate=rotate, pulses=False,
                view=dict(lat=selected.latitude if selected else 12, lng=selected.longitude if selected else 40, altitude=2.5),
                view_key=selected_id or 'all-global-hazards')


def select_event_from_globe():
    selected = st.session_state.get('global_hazard_globe', {}).get('selected')
    allowed = st.session_state.get('global_hazard_visible_ids', [])
    if selected in allowed:
        st.session_state[SELECTED_KEY] = selected


def render_event(event, review, feed, error=None):
    with st.container(border=True):
        st.caption(f'NOAA FORECAST / WEEK {event.week}')
        st.subheader(HAZARD_NAMES[event.hazard])
        if review:
            st.markdown(f'**{review.explanation.area_name}**')
        st.caption(f'Map focus: {event.coordinate_label} · source polygon, not a city forecast')
        st.metric('NOAA probability contour', f'≥{event.probability}%')
        st.write(f'**Valid:** {event.valid_start:%d %b} – {event.valid_end:%d %b %Y}')
        st.caption(f'Issued {event.issued:%d %b %Y} · {"Expired outlook" if event.valid_end < utcnow().date() else "Forecast outlook"}')
        if event.hazard == 'TC':
            st.write('Probability of tropical cyclone formation within this area and period. This does not predict a landfall or storm track.')
        else:
            st.write('Probability of the indicated weekly departure from typical conditions. This is not a measurement or an official local warning.')
        if review:
            st.divider()
            st.markdown('**Grok · event explanation**')
            st.write(review.explanation.summary)
            st.markdown('**Possible drivers**')
            st.write(review.explanation.possible_drivers)
            st.markdown('**What to monitor**')
            st.write(review.explanation.watch_for)
            st.caption(review.explanation.uncertainty)
            st.caption(f'Reviewed by Grok Scout + Evidence Reviewer · {review.reviewed_at:%d %b %Y, %H:%M UTC} · {review.model}')
        elif error:
            st.warning(error)
        else:
            st.info('Grok explanation is pending. The NOAA forecast and its source are already available.')
        st.link_button('Open NOAA outlook', feed.source_url, width='stretch')
        st.link_button('Open original geographic data (KML)', event.source_url, width='stretch')
        st.caption(f'Source feature: {event.source_feature}')


@st.fragment(run_every='10s')
def render_global_hazards():
    monitor = get_hazard_monitor()
    st.caption('GLOBAL HAZARDS / NOAA EVIDENCE × GROK BOTS')
    st.header('A world of signals. Every event explained.')
    st.write('Explore NOAA’s rainfall, temperature, and cyclone-formation outlooks. Click an area on Earth to read its forecast and the Grok bots’ evidence review.')
    with st.container(horizontal=True, vertical_alignment='center'):
        refresh = st.button('Update events with Grok', type='primary', icon=':material/refresh:', key='refresh_global_hazards')
        auto = st.toggle('Automatic updates', value=True, key='global_hazard_auto', help='Check NOAA every 30 minutes while this view is open. Grok reviews new or changed source evidence.')
    state = monitor.snapshot()
    if refresh or (auto and (state['last_attempt'] is None or (utcnow() - state['last_attempt']).total_seconds() >= CHECK_SECONDS)):
        monitor.request_refresh(force=refresh)
        state = monitor.snapshot()
    st.caption('NOAA publishes this tropical outlook weekly. Automatic checks run every 30 minutes while open; unchanged events reuse their Grok reviews. Coverage follows NOAA’s published areas, not every country.')
    if not grok_ready():
        st.info('Add XAI_API_KEY and XAI_MODEL to .env and restart to enable Grok reviews. NOAA events can still load.')
    if state['error']:
        st.warning(state['error'])
    if state['running']:
        latest = state['logs'][-1] if state['logs'] else {'agent': 'Monitor', 'message': 'Starting the NOAA update…'}
        st.info(f"{latest['agent']} · {latest['message']}")
    feed, reviews = state['feed'], state['reviews']
    if feed is None:
        st.info('Loading NOAA’s published areas. The globe will fill as soon as the source has been checked.' if state['running'] else 'No verified NOAA feed is available yet. Use Update events with Grok to try again.')
        return
    if not state['last_checked']:
        st.warning('Showing the last downloaded edition while the latest source is checked.')
    elif (utcnow() - feed.retrieved_at).total_seconds() > CHECK_SECONDS * 2:
        st.warning('This download is over an hour old. Refresh to check for a newer publication.')
    for warning in feed.warnings:
        st.warning(warning)
    if feed.events and all(event.valid_end < utcnow().date() for event in feed.events):
        st.warning('This NOAA outlook has expired. The globe shows its dated forecast areas, not current hazards.')
    with st.container(horizontal=True):
        st.metric('Published areas', len(feed.events), border=True)
        st.metric('Grok reviews', f'{len(reviews)} / {len(feed.events)}', border=True)
        st.metric('Source layers', f'{len(feed.layers_loaded)} / 10', border=True)
    st.caption(f'NOAA edition: {feed.issued:%d %b %Y} · Downloaded: {feed.retrieved_at:%d %b, %H:%M UTC}')
    filter_left, filter_right = st.columns([2, 1])
    with filter_left:
        hazards = st.multiselect('Event types', list(HAZARD_NAMES), default=list(HAZARD_NAMES), format_func=HAZARD_NAMES.get, key='global_hazard_types')
    with filter_right:
        week = st.segmented_control('Forecast period', ['Both weeks', 'Week 2', 'Week 3'], default='Both weeks', key='global_hazard_week')
    visible = [event for event in feed.events if event.hazard in hazards and (week in (None, 'Both weeks') or event.week == int(week[-1]))]
    ids = [event.event_id for event in visible]
    st.session_state['global_hazard_visible_ids'] = ids
    if st.session_state.get(SELECTED_KEY) not in ids:
        st.session_state[SELECTED_KEY] = None
    if not visible:
        st.info('No published areas match these filters. Empty NOAA layers mean no areas were posted for that category, not that the world is hazard-free.')
    else:
        globe, details = st.columns([3, 2], gap='large')
        with globe:
            rotate = st.toggle('Automatic rotation', value=True, key='global_hazard_rotate')
            _GLOBE(key='global_hazard_globe', data=build_globe_data(visible, st.session_state.get(SELECTED_KEY), reviews, rotate=rotate),
                   height=700, on_selected_change=select_event_from_globe)
            st.caption('Shading is NOAA’s published forecast footprint. Dots are map focus points; nearby or overlapping shapes may describe the same system.')
        with details:
            lookup = {event.event_id: event for event in visible}
            selected = st.selectbox('Choose an event', ids, index=None, placeholder='Click the globe or choose an event',
                                    format_func=lambda key: event_label(lookup[key], reviews), key=SELECTED_KEY)
            if selected:
                render_event(lookup[selected], reviews.get(selected), feed, state['review_errors'].get(selected))
            else:
                st.subheader('Follow a signal')
                st.write('Select any shaded area or marker to see its probability, dates, source, and Grok explanation. Use the selector for keyboard access.')
                st.caption('Green indicates above-median rainfall; it does not mean safe conditions. Forecast colors identify the event type.')
    with st.expander('Grok bot activity & source discussion'):
        for item in state['logs'][-16:]:
            st.text(f"{item['time'][11:19]} UTC · {item['agent']} · {item['message']}")
        st.markdown('**NOAA forecast discussion**')
        st.write(feed.discussion)
        st.link_button('Read the full NOAA publication', feed.source_url)
    st.download_button('Download sourced events (GeoJSON)', data=events_geojson(feed, reviews),
                       file_name=f'earthwatch-noaa-{feed.issued}.geojson', mime='application/geo+json')


def events_geojson(feed, reviews):
    import json
    features = []
    for event in feed.events:
        properties = event.evidence()
        if event.event_id in reviews:
            properties['grok_review'] = reviews[event.event_id].model_dump(mode='json')
        features.append(dict(type='Feature', id=event.event_id, geometry=event.geometry.model_dump(mode='json'), properties=properties))
    return json.dumps(dict(type='FeatureCollection', features=features))
