"""Current conditions and today's hourly weather for any selected location."""
import pandas as pd
import streamlit as st

from dashboard.charts import observation_chart
from schemas.errors import TranslatorError
import translator
from data.station_weather import compare_station


@st.fragment(run_every=300)
def render_live_weather(location):
    st.caption('Current conditions refresh every five minutes while this page is open. Times use the selected location\'s timezone.')
    requested = st.button("Load today's weather", type='primary', disabled=location is None)
    if requested:
        st.session_state.live_location = location
    if location is None or st.session_state.get('live_location') != location:
        return
    refresh = st.button('Refresh live weather')
    try:
        with st.spinner("Fetching today's weather..."):
            weather = translator.load_live_weather(location, refresh=requested or refresh)
    except TranslatorError as error:
        st.error(str(error))
        return
    st.subheader(f'Today in {location.label}')
    st.write(f'Conditions at {weather.current_time:%Y-%m-%d %H:%M %Z}')
    st.caption(f'Retrieved {weather.retrieved_at.astimezone(weather.current_time.tzinfo):%Y-%m-%d %H:%M:%S %Z} | Source: Open-Meteo | Timezone: {weather.timezone}')
    st.info('Current conditions are weather-model estimates. Future hourly values are forecasts; they are not station observations or historical climate anomalies.')
    station = translator.load_station_weather(location,refresh=requested or refresh)
    if station.get('status') == 'ok':
        observed = pd.Timestamp(station['observed_at']).tz_convert(weather.timezone)
        st.markdown('**Independent station observation**')
        st.write(f"{station['name']} ({station['station']}), {station['distance_km']:g} km away — {observed:%Y-%m-%d %H:%M %Z}")
        st.write(f"Observed temperature: **{station['temperature_degC']:g} °C** ({station['temperature_degC'] * 9/5 + 32:.1f} °F). {station.get('description') or ''}")
        st.caption(f"[NOAA NWS station source]({station['source']}) | Retrieved {station['retrieved_at']}")
        comparison = compare_station(weather,station)
        if comparison['status'] == 'compared':
            st.write(f"Model minus station: {comparison['model_minus_station_degC']:+g} °C; readings {comparison['separation_minutes']:g} minutes apart.")
            if abs(comparison['model_minus_station_degC']) > 3:
                st.warning('The model and station differ by more than 3 °C. Review both locations and timestamps; do not treat them as an exact match.')
        else:
            st.info('The station and model timestamps are not sufficiently aligned for a direct comparison.')
    else:
        st.info(station.get('reason','Independent station observation unavailable.'))
    current = weather.current

    def value(field, suffix):
        number = current[field]
        return 'Unavailable' if number is None else f'{number:g} {suffix}'

    left, middle, right = st.columns(3)
    left.metric('Temperature', value('temperature_2m', '\u00b0C'))
    middle.metric('Feels like', value('apparent_temperature', '\u00b0C'))
    right.metric('Relative humidity', value('relative_humidity_2m', '%'))
    left, right = st.columns(2)
    left.metric('Wind speed', value('wind_speed_10m', 'km/h'))
    right.metric(f'Precipitation over preceding {weather.interval_seconds // 60} minutes', value('precipitation', 'mm'))
    st.map(pd.DataFrame({'latitude':[location.latitude], 'longitude':[location.longitude]}), zoom=6)
    choice = st.selectbox("Today's hourly variable", ['temperature_2m', 'precipitation', 'wind_speed_10m'], format_func=lambda key: {'temperature_2m':'Temperature', 'precipitation':'Hourly precipitation', 'wind_speed_10m':'Wind speed'}[key])
    units = {'temperature_2m':'degC', 'precipitation':'mm/hour', 'wind_speed_10m':'km/h'}
    series = weather.hourly[['date', choice]].rename(columns={choice:'value'})
    chart = observation_chart(series, f"Today's {choice.replace('_', ' ')}", units[choice])
    chart.add_vline(x=weather.current_time.timestamp() * 1000, line_dash='dash')
    st.plotly_chart(chart, width='stretch')
    st.caption('Dashed line: current conditions timestamp. Hourly precipitation is the amount over the preceding hour; future hours are forecasts.')
    st.dataframe(weather.hourly[['date', *weather.current.keys(), 'data_kind']], hide_index=True)
    st.download_button("Download today's hourly weather", weather.hourly.to_csv(index=False), file_name=f'earthwatch_{location.key}_{weather.current_time:%Y%m%d}_hourly.csv', mime='text/csv')
    snapshot = dict(location=location.label, latitude=location.latitude, longitude=location.longitude, time=weather.current_time.isoformat(), retrieved_at=weather.retrieved_at.isoformat(), timezone=weather.timezone, source=weather.source, data_kind='Current model estimate', precipitation_interval_seconds=weather.interval_seconds, temperature_unit='degC', precipitation_unit='mm', wind_speed_unit='km/h', **current)
    st.download_button('Download current conditions', pd.DataFrame([snapshot]).to_csv(index=False), file_name=f'earthwatch_{location.key}_{weather.current_time:%Y%m%d}_current.csv', mime='text/csv')
    identity = (location,weather.current_time.isoformat(),station.get('observed_at'))
    if requested or refresh:
        st.session_state.pop('live_assessment',None)
    if st.button("Investigate today's weather with Grok"):
        st.session_state.pop('live_assessment',None)
        with st.status('Investigating current weather...',expanded=True) as box:
            try:
                assessment = translator.investigate_live_weather(weather,station,lambda event:box.write(f'{event.agent}: {event.message}'))
                st.session_state.live_assessment = (identity,assessment)
                box.update(label='Current weather assessment complete',state='complete')
            except TranslatorError as error:
                box.update(label='Investigation failed',state='error')
                st.error(str(error))
    saved = st.session_state.get('live_assessment')
    if saved and saved[0] == identity:
        assessment = saved[1]
        st.subheader(assessment.summary)
        st.write(f'Confidence in interpretation: {assessment.confidence}. This is not the accuracy rating of a measured temperature.')
        for item in assessment.evidence:
            st.write(f'[{item.evidence_type}] {item.claim}')
            if item.url:
                st.caption(f'[Source]({item.url}) | Date: {item.source_date}')
        for limitation in assessment.limitations:
            st.caption(limitation)
    st.caption('[Weather data by Open-Meteo](https://open-meteo.com/) (CC BY 4.0). Use Climate history for historical baseline comparisons.')
