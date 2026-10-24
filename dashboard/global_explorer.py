"""Worldwide country/place selection and local climate evidence explorer."""
from datetime import date
import pandas as pd
import streamlit as st
import translator
from data.locations import Location, countries
from dashboard.charts import observation_chart
from schemas.errors import TranslatorError


def render_global_explorer(render_assessment):
    st.caption('Worldwide climate intelligence')
    method = st.radio('Choose a location by', ['Place search', 'Coordinates'], horizontal=True)
    selected = None
    if method == 'Place search':
        choices = [{'code':'', 'name':'All countries and territories'}] + countries()
        country = st.selectbox('Country or territory', choices, format_func=lambda item: item['name'])
        query = st.text_input('City, town, region, or postal code', placeholder='Search anywhere: Tokyo, Nairobi, Toronto...')
        if st.button('Search locations'):
            try:
                with st.spinner('Finding locations...'):
                    hits = translator.search_world_locations(query, country['code'] or None)
                st.session_state.world_search = (country['code'], query, hits)
            except TranslatorError as error:
                st.error(str(error))
                st.session_state.pop('world_search', None)
        saved = st.session_state.get('world_search')
        if saved and saved[:2] == (country['code'], query):
            hits = saved[2]
            if hits:
                selected = st.selectbox('Matching location', hits, format_func=lambda loc: f'{loc.label} ({loc.latitude:.4f}, {loc.longitude:.4f})')
            else:
                st.info('No matching places found. Try another spelling or use coordinates for any point on Earth.')
        st.caption('Search is powered by Open-Meteo / GeoNames. Select a place within a country; results describe that point, not a national average.')
    else:
        name = st.text_input('Location label', value='Custom location')
        left, right = st.columns(2)
        lat = left.number_input('Latitude', min_value=-90.0, max_value=90.0, value=0.0, format='%.6f')
        lon = right.number_input('Longitude', min_value=-180.0, max_value=180.0, value=0.0, format='%.6f')
        try:
            selected = Location(name, lat, lon)
        except ValueError as error:
            st.error(str(error))
        st.caption('Coordinates support remote places, islands, oceans, and locations absent from search. Latitude: south negative. Longitude: west negative.')
    year = int(st.number_input('Observation year', min_value=1960, max_value=date.today().year, value=date.today().year, step=1))
    st.caption('Monthly temperature and precipitation are compared with the preceding 30 years (at least 20 valid years per calendar month). The current year includes published observations with a seven-day buffer; incomplete months remain unknown.')
    identity = (selected, year)
    if st.button('Load climate data', type='primary', disabled=selected is None):
        st.session_state.pop('world_climate', None)
        st.session_state.pop('world_assessment', None)
        try:
            with st.spinner('Loading local observations and historical baseline...'):
                climate = translator.load_location_climate(selected, year)
            st.session_state.world_climate = (identity, climate)
        except TranslatorError as error:
            st.error(str(error))
    stored = st.session_state.get('world_climate')
    if stored is None or stored[0] != identity:
        return
    climate = stored[1]
    st.subheader(selected.label)
    st.write(f'Coordinates: {selected.latitude:.6f}, {selected.longitude:.6f} | Baseline: {climate.baseline_period}')
    st.map(pd.DataFrame({'latitude':[selected.latitude], 'longitude':[selected.longitude]}), zoom=4)
    if climate.daily['cache_stale'].any():
        st.warning('The source is unavailable. These observations came from a stale cache; review the retrieval date below.')
    st.caption(f'ERA5 reanalysis via Open-Meteo. Retrieved: {climate.daily["retrieved_at"].iloc[-1]}. Grid estimates at a point; geographic coverage and missing values depend on the source.')
    st.caption(f'Observation coverage: {climate.daily["date"].min():%Y-%m-%d} through {climate.daily["date"].max():%Y-%m-%d}.')
    variable = st.selectbox('Climate variable', ['temperature', 'precipitation'], format_func=lambda item: {'temperature':'Air temperature', 'precipitation':'Precipitation (rain + snow)'}[item])
    monthly = climate.monthly.loc[climate.monthly['variable'] == variable]
    unit = monthly['unit'].iloc[0]
    figure = observation_chart(monthly, f'{selected.label}: {variable}, {year}', unit)
    figure.add_scatter(x=monthly['date'], y=monthly['baseline_mean'], mode='lines', name='Calendar-month baseline')
    figure.data[0].name = 'Observed'
    st.plotly_chart(figure, width='stretch')
    st.dataframe(monthly[['date', 'value', 'baseline_mean', 'anomaly', 'z_score', 'baseline_count']], hide_index=True)
    if monthly['value'].isna().any() or monthly['z_score'].isna().any():
        st.info('Some months have missing observations or insufficient baseline variance/coverage. Those results remain unknown or inconclusive.')
    st.download_button('Download daily observations', climate.daily.to_csv(index=False), file_name=f'earthwatch_{selected.key}_{year}_daily.csv', mime='text/csv')
    st.download_button('Download monthly anomalies', climate.monthly.to_csv(index=False), file_name=f'earthwatch_{selected.key}_{year}_monthly.csv', mime='text/csv')
    records = [item for item in climate.anomalies if ('temperature' in item.anomaly_id) == (variable == 'temperature')]
    if not records:
        st.info('No valid monthly measurements are available for investigation.')
        return
    observation = st.selectbox('Observation to investigate', records, format_func=lambda item: f'{item.observation_date:%B %Y}: {item.value:g} {item.unit} | {item.status}')
    assessment_key = (identity, observation.anomaly_id)
    if st.button('Run Investigation'):
        st.session_state.pop('world_assessment', None)
        with st.status('Investigating selected location...', expanded=True) as box:
            try:
                assessment, statistical_only = translator.investigate_location(climate, observation.anomaly_id, lambda event: box.write(f'{event.agent}: {event.message}'))
                st.session_state.world_assessment = (assessment_key, assessment, statistical_only)
                box.update(label='Assessment complete', state='complete')
            except TranslatorError as error:
                box.update(label='Investigation failed', state='error')
                st.error(str(error))
    stored_assessment = st.session_state.get('world_assessment')
    if stored_assessment and stored_assessment[0] == assessment_key:
        if stored_assessment[2]:
            st.info('Showing a deterministic statistical assessment of the selected location. The Grok agent workflow is not implemented yet.')
        render_assessment(stored_assessment[1], False)
    st.caption('Weather data: Open-Meteo, Copernicus ERA5 (CC BY 4.0). Place names and country list: GeoNames (CC BY 4.0).')
