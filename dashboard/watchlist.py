"""The default EarthWatch experience: editable areas and Grok seasonal watches."""
from datetime import datetime, timedelta, timezone
import json

import pandas as pd
import streamlit as st

import translator
from data.locations import Location
from data.seasonal import outlook_months
from schemas.errors import TranslatorError
from schemas.watchlist import HAZARDS
from dashboard.watch_map import watch_map

SEED_AREAS = (
    Location('Bangladesh · Dhaka area', 23.81, 90.41),
    Location('Pakistan · Indus basin near Multan', 30.20, 71.47),
    Location('Kenya · eastern lowlands', -0.45, 39.64),
    Location('Brazil · central Amazon near Manaus', -3.12, -60.02),
    Location('Spain · Andalusia near Seville', 37.39, -5.98),
    Location('United States · Arizona near Phoenix', 33.45, -112.07),
    Location('Australia · New South Wales near Dubbo', -32.26, 148.60),
    Location('Vietnam · Mekong delta near Can Tho', 10.05, 105.75),
)
RANK = {'Elevated watch': 3, 'Monitor': 2, 'Inconclusive': 1}
COLORS = {'Elevated watch': '#F6AD55', 'Monitor': '#70E1BB',
          'Inconclusive': '#A8B7CA', 'Not assessed': '#75859A', 'Needs refresh': '#75859A',
          'Scan failed': '#D78D9D'}


def current_result(result, months):
    now = datetime.now(timezone.utc)
    return bool(result and result.window_start == outlook_months(now.date(), months)[0]
                and len(result.signals) == months
                and timedelta(seconds=-60) <= now - result.retrieved_at <= timedelta(hours=6))


def scan_areas(keys, months):
    areas = st.session_state['watch_areas']
    results = st.session_state['watch_results']
    failures = st.session_state['watch_failures']
    events = st.session_state['watch_events']
    failed = 0
    with st.status('Reviewing seasonal conditions with Grok...', expanded=True) as status:
        progress = st.progress(0)
        for index, key in enumerate(keys):
            place = areas[key]
            events[key] = []

            def report(event):
                events[key].append(event)
                status.write(f'{event.agent} · {event.message}')

            try:
                results[key] = translator.scan_seasonal_area(place, months, report)
                failures.pop(key, None)
            except TranslatorError as error:
                failures[key] = str(error)
                failed += 1
                status.write(f'{place.label}: {error}')
            progress.progress((index + 1) / len(keys))
        status.update(label=f'Scan finished · {len(keys)-failed} reviewed · {failed} failed',
                      state='error' if failed else 'complete', expanded=bool(failed))


def manage_areas():
    with st.sidebar.expander('Manage watched areas', icon=':material/add_location_alt:'):
        st.caption('Watch a representative point in any area. A point forecast does not describe an entire country or river basin.')
        with st.form('add_watch_area', clear_on_submit=True):
            name = st.text_input('Area name', max_chars=100)
            lat = st.number_input('Latitude', min_value=-90.0, max_value=90.0, format='%.4f')
            lon = st.number_input('Longitude', min_value=-180.0, max_value=180.0, format='%.4f')
            if st.form_submit_button('Add to watchlist', width='stretch'):
                try:
                    place = Location(name.strip(), lat, lon)
                    areas = st.session_state['watch_areas']
                    if place.key in areas:
                        st.info('This point is already on your watchlist.')
                    elif len(areas) >= 30:
                        st.error('Keep up to 30 areas on this watchlist. Remove one before adding another.')
                    else:
                        areas[place.key] = place
                        st.success(f'Added {place.label}. Choose it in Areas to scan.')
                except ValueError as error:
                    st.error(str(error))
        areas = st.session_state['watch_areas']
        if areas:
            remove = st.selectbox('Area to remove', list(areas), format_func=lambda key: areas[key].label)
            if st.button('Remove area', key='remove_watch_area'):
                areas.pop(remove)
                for collection in ('watch_results', 'watch_failures', 'watch_events'):
                    st.session_state[collection].pop(remove, None)
                if 'watch_scan_selection' in st.session_state:
                    st.session_state['watch_scan_selection'] = [key for key in st.session_state['watch_scan_selection'] if key != remove]
                st.rerun()
        st.download_button('Export watched areas', json.dumps([
            dict(name=place.name, latitude=place.latitude, longitude=place.longitude)
            for place in areas.values()], indent=2), file_name='earthwatch_areas.json', mime='application/json')
        uploaded = st.file_uploader('Restore watched areas', type='json', key='restore_watch_areas')
        if st.button('Import areas', disabled=uploaded is None):
            try:
                raw = json.loads(uploaded.getvalue())
                if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
                    raise ValueError('Import a list of 1–30 areas.')
                imported = [Location(**item) for item in raw]
                if len(areas.keys() | {place.key for place in imported}) > 30:
                    raise ValueError('This import would exceed 30 watched areas.')
                areas.update({place.key: place for place in imported})
                st.success('Areas imported. Select them for your next scan.')
            except (ValueError, TypeError, KeyError):
                st.error('Import a valid EarthWatch areas JSON file with up to 30 named coordinate pairs.')
        st.caption('Your watchlist is kept in this browser session. Export it to restore it later.')


def render_watchlist():
    st.session_state.setdefault('watch_areas', {place.key: place for place in SEED_AREAS})
    for key in ('watch_results', 'watch_failures', 'watch_events'):
        st.session_state.setdefault(key, {})
    st.subheader('Global climate-risk watchlist')
    st.caption('A 1–3 month outlook · seasonal forecast evidence, reviewed by Grok agents')
    with st.container(border=True):
        st.markdown('**See where conditions deserve a closer watch.**')
        st.write('Track flood, drought, heat-wave, wildfire-weather, and heavy-rainfall potential across your watched areas. Grok reviews seasonal model anomalies and explains what they may mean, what remains uncertain, and what to monitor next.')
        st.caption('Start with the seeded locations or add your own. These are watch candidates, not areas already predicted to experience a disaster. No scan runs until you request one.')
    with st.sidebar:
        st.subheader('Seasonal watch settings')
        months = st.select_slider('Outlook window', options=[1, 2, 3], value=3,
                                  format_func=lambda value: f'{value} month' + ('s' if value > 1 else ''), key='watch_months')
    manage_areas()
    areas = st.session_state['watch_areas']
    dates = outlook_months(datetime.now(timezone.utc).date(), months)
    st.caption(f'Forecast window: {dates[0]:%B %Y} – {dates[-1]:%B %Y} · next {months} full calendar month(s)')
    selected = st.sidebar.multiselect('Areas to scan', list(areas), default=list(areas),
                                     format_func=lambda key: areas[key].label, key='watch_scan_selection')
    hazards = st.sidebar.multiselect('Hazards to show', list(HAZARDS), default=list(HAZARDS), key='watch_hazard_filter')
    level_filter = st.sidebar.selectbox('Watch level', ['All levels', 'Elevated watch', 'Monitor', 'Inconclusive'], key='watch_level_filter')
    ready = translator.seasonal_agent_ready()
    if not ready:
        st.info('Grok is not configured. Set XAI_API_KEY and XAI_MODEL in the local .env file, then restart the app to enable seasonal scans.')
    with st.container(horizontal=True, vertical_alignment='center'):
        run = st.button('Scan selected areas with Grok', type='primary', icon=':material/radar:',
                        disabled=not selected or not ready, key='scan_watchlist')
        st.caption(f'{len(selected)} area(s) selected · seasonal evidence → scout → impact review → skeptic')
    if run:
        scan_areas(selected, months)
    with st.expander('New here? How the watchlist works', icon=':material/help:'):
        st.markdown('1. **Choose your areas and window** in the sidebar. Add or import places under Manage watched areas.\n2. **Scan with Grok.** The app retrieves ECMWF seasonal anomalies, then Scout, Impact Analyst, and Skeptic bots review them.\n3. **Filter the watchlist** by hazard or watch level. Select an area below to read the rationale and exact source values.\n4. **Check what would change the outlook.** Read monitoring triggers, limitations, and more recent local forecasts before taking action.')
        st.caption('Seasonal watches identify potential, not exact disasters or official warnings. These are model-climatology anomalies, not direct observations. Climate-change context does not establish the cause of a particular event. Sources: [ECMWF seasonal data via Open-Meteo](https://open-meteo.com/en/docs/seasonal-forecast-api), CC BY 4.0; [IPCC climate extremes assessment](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-11/).')
    results = st.session_state['watch_results']
    failures = st.session_state['watch_failures']
    fresh = {key: result for key, result in results.items()
             if key in areas and key not in failures and result.location_label == areas[key].label
             and current_result(result, months)}
    elevated = sum(any(item.level == 'Elevated watch' for item in result.review.outlooks) for result in fresh.values())
    with st.container(horizontal=True):
        st.metric('Watched areas', len(areas), border=True)
        st.metric('Current reviews', len(fresh), border=True)
        st.metric('Areas with elevated watches', elevated, border=True)
        st.metric('Awaiting review or refresh', len(areas) - len(fresh), border=True)
    rows, points, matching = [], [], []
    for key, place in areas.items():
        result = fresh.get(key)
        outlooks = [item for item in result.review.outlooks if item.hazard in hazards] if result else []
        if not hazards:
            continue
        if level_filter != 'All levels':
            outlooks = [item for item in outlooks if item.level == level_filter]
            if not outlooks:
                continue
        level = max((item.level for item in outlooks), key=RANK.get, default=(
            'Scan failed' if key in failures else 'Needs refresh' if key in results else 'Not assessed'))
        if result and not outlooks:
            continue
        signals = ', '.join(item.hazard for item in outlooks if item.level == 'Elevated watch') or '—'
        rows.append({'Area': place.label, 'Watch level': level, 'Elevated hazard potential': signals,
                     'Reviewed (UTC)': result.assessed_at.strftime('%d %b %H:%M') if result else '—'})
        points.append({'latitude': place.latitude, 'longitude': place.longitude, 'color': COLORS[level],
                       'key': key, 'label': place.label, 'level': level})
        matching.append(key)
    st.markdown('**Your global watch**')
    st.caption('Orange: elevated seasonal watch · teal: monitor · gray: inconclusive or unassessed · rose: scan failed. Map markers represent the watched coordinates, not hazard footprints.')
    if rows:
        ordered = sorted(zip(rows, matching), key=lambda pair: RANK.get(pair[0]['Watch level'], 0), reverse=True)
        rows, matching = map(list, zip(*ordered))
        def select_map_area():
            selection = st.session_state['watch_world_map'].get('selection', {}).get('points', [])
            if selection:
                key = selection[-1].get('customdata')
                if key in matching:
                    st.session_state['watch_detail_area'] = key

        st.plotly_chart(watch_map(points), key='watch_world_map', width='stretch',
                        on_select=select_map_area, selection_mode='points',
                        config={'displayModeBar': False},
                        alt='World map with watched areas colored by seasonal watch status; select a marker to read that area')
        st.caption('Select a map marker to read its outlook. Boundaries: Natural Earth, public domain. Map shows representative area points, not the extent of a predicted event.')
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch', alt='Global watchlist with area status and elevated hazard potential')
    else:
        st.info('No areas match these filters. Add an area or include more hazards and watch levels.')
        return
    choice = st.selectbox('Read an area outlook', matching, format_func=lambda key: areas[key].label, key='watch_detail_area')
    result = results.get(choice)
    if choice in failures:
        st.error(failures[choice])
    if result is None:
        st.info('This area has not been assessed. Select it in Areas to scan, then run the Grok scan.')
        return
    if choice not in fresh:
        st.warning('Previous review shown for reference. It does not match the current window, is older than six hours, or the latest scan failed. Run a new scan before treating it as current.')
    st.subheader(result.location_label)
    st.write(result.review.summary)
    st.caption(f'{result.window_start:%d %b %Y} – {result.window_end:%d %b %Y} · Grok review {result.assessed_at:%d %b %Y %H:%M UTC} · seasonal model: ECMWF SEAS5 ensemble mean')
    for item in sorted(result.review.outlooks, key=lambda item: RANK[item.level], reverse=True):
        if item.hazard not in hazards or (level_filter != 'All levels' and item.level != level_filter):
            continue
        with st.container(border=True):
            st.markdown(f'**{item.hazard} potential · {item.level}**')
            st.caption(f'Confidence in this interpretation: {item.confidence} · not an event probability')
            st.write(item.summary)
            with st.expander('Why this is on the watchlist'):
                st.write(item.rationale)
                st.markdown('**Evidence used**')
                evidence = {key: value for signal in result.signals for key, value in signal.evidence().items()}
                for ref in item.evidence_refs:
                    st.text(f'{ref} = {evidence[ref]:g}')
                st.markdown('**What to monitor next**')
                for trigger in item.monitoring_triggers:
                    st.write(f'• {trigger}')
                st.markdown('**Limitations**')
                for limitation in item.limitations:
                    st.write(f'• {limitation}')
    with st.expander('Seasonal data and source provenance'):
        st.caption(f'Retrieved {result.retrieved_at:%d %b %Y %H:%M UTC}. Retrieval time is not the model initialization time; the provider does not supply the run issue date here.')
        frame = pd.DataFrame([signal.model_dump() for signal in result.signals]).rename(columns={
            'temperature_anomaly': 'Temperature anomaly (K)', 'precipitation_anomaly': 'Precipitation anomaly (mm/month)',
            'soil_moisture_anomaly': 'Surface soil moisture anomaly (m³/m³)', 'runoff_anomaly': 'Runoff anomaly (mm/month)',
        })
        st.dataframe(frame, hide_index=True, alt='Monthly ensemble-mean anomaly values used by the Grok bots')
        st.link_button('Open the exact seasonal data request', result.source_url)
        st.caption('Forecasts relative to the model climatology; no observational baseline or hindcast calibration is supplied here. These data are not bias-corrected. Positive/negative anomalies alone are not validated hazard thresholds. Monthly means cannot predict exact heat-wave days, flood occurrence, drought onset, or wildfire ignition.')
    with st.expander('Grok review activity'):
        for event in st.session_state['watch_events'].get(choice, []):
            st.caption(f'{event.timestamp:%H:%M:%S UTC} · {event.agent} · {event.message}')
    st.download_button('Download area outlook', result.model_dump_json(indent=2), file_name=f'earthwatch_{choice}_seasonal.json', mime='application/json')
    st.caption('Climate change can alter the background likelihood and intensity of extremes. This seasonal scan does not attribute any individual event to climate change. [IPCC climate extremes assessment](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-11/). Seasonal data: [Open-Meteo / ECMWF](https://open-meteo.com/en/docs/seasonal-forecast-api), CC BY 4.0. Watches are decision support, not official warnings.')
