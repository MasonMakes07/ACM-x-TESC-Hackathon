"""Live agent integration, station freshness, and source accuracy regression checks."""
from datetime import datetime, timezone, timedelta
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from agents import live_tools
from agents.context import build_context, infer_as_of_date
from agents.ledger import EvidenceLedger
from agents.sentinel import monitor
from data import station_weather
from data.locations import Location
from data.live_weather import LiveWeather
import translator

NOW = datetime(2026,10,24,19,30,tzinfo=timezone.utc)


@pytest.fixture
def snapshot(monkeypatch):
    monkeypatch.setattr(live_tools,'_now',lambda:NOW)
    monkeypatch.setattr(station_weather,'_now',lambda:NOW)
    place = Location('San Diego',32.7336,-117.1831,country_code='US')
    frame = pd.DataFrame({'date':pd.date_range(NOW,periods=2,freq='h'),
                          'temperature_2m':[23.0,24.0],'precipitation':[0.0,0.0],
                          'data_kind':['Model estimate','Forecast']})
    current = dict(temperature_2m=23.0,apparent_temperature=24.0,relative_humidity_2m=60,precipitation=0,wind_speed_10m=5)
    return LiveWeather(place,current,frame,NOW,NOW,'America/Los_Angeles',900)


def station():
    return dict(status='ok',station='KSAN',name='San Diego Airport',distance_km=0.1,
                observed_at=(NOW-timedelta(minutes=10)).isoformat(),retrieved_at=NOW.isoformat(),
                temperature_degC=22.0,source='https://api.weather.gov/stations/KSAN/observations/latest')


def test_station_discovery_and_unit_conversion(snapshot,monkeypatch):
    def get(url,refresh=False):
        if '/points/' in url:
            return {'properties':{'observationStations':'https://api.weather.gov/gridpoints/SGX/1,2/stations'}},NOW.isoformat()
        if url.endswith('/stations'):
            return {'features':[{'geometry':{'coordinates':[-117.1831,32.7336]},'properties':{'stationIdentifier':'KSAN','name':'San Diego Airport'}}]},NOW.isoformat()
        return {'properties':{'timestamp':NOW.isoformat(),'temperature':{'value':22.0,'unitCode':'wmoUnit:degC'},'windSpeed':{'value':2.0,'unitCode':'wmoUnit:m_s-1'},'precipitationLastHour':{'value':0.001,'unitCode':'wmoUnit:m'}}},NOW.isoformat()
    monkeypatch.setattr(station_weather,'_get',get)
    result = station_weather.get_station_observation(snapshot.location)
    assert result['station'] == 'KSAN'
    assert result['wind_speed_kmh'] == 7.2
    assert result['precipitation_last_hour_mm'] == 1.0
    assert result['relative_humidity_pct'] is None
    assert station_weather.compare_station(snapshot,result)['model_minus_station_degC'] == 1


def test_station_old_or_misaligned_not_compared(snapshot):
    data=station()
    data['observed_at']=(NOW-timedelta(hours=2)).isoformat()
    assert station_weather.compare_station(snapshot,data)['status']=='not_time_aligned'


def box(snapshot):
    return live_tools.LiveWeatherToolbox(EvidenceLedger(),NOW.date(),snapshot.location,weather=snapshot,station=station())


def test_live_tool_exact_values_and_station_provenance(snapshot):
    tool=box(snapshot)
    result=json.loads(tool.execute('get_current_weather',{'latitude':snapshot.location.latitude,'longitude':snapshot.location.longitude}))
    assert result['status']=='ok'
    assert result['current']==snapshot.current
    assert result['conditions_time']==NOW.isoformat()
    assert result['comparison']['model_minus_station_degC']==1
    assert tool.ledger.find('',snapshot.source).kind=='reference'
    assert tool.ledger.find('',station()['source']).kind=='measurement'


def test_live_tool_rejects_wrong_place_and_historical_tool(snapshot):
    tool=box(snapshot)
    assert json.loads(tool.execute('get_current_weather',{'latitude':0,'longitude':0}))['status']!='ok'
    assert json.loads(tool.execute('get_local_weather',{}))['status']=='error'


def test_expired_live_snapshot_never_replaced_with_history(snapshot):
    snapshot.current_time=NOW-timedelta(hours=3)
    result=json.loads(box(snapshot).execute('get_current_weather',{'latitude':snapshot.location.latitude,'longitude':snapshot.location.longitude}))
    assert result['status']=='unavailable'


def test_current_record_and_sentinel(snapshot):
    record=translator.live_weather_record(snapshot)
    assert record.value==23
    assert record.status=='monitoring'
    assert infer_as_of_date(record)==NOW.date()
    report=monitor(box(snapshot),record,build_context(record),lambda event:None)
    assert report.status=='confirmed'
    wrong=record.model_copy(update={'value':99})
    assert monitor(box(snapshot),wrong,build_context(wrong),lambda event:None).status=='mismatch'


def test_live_workflow_uses_current_tool_only(snapshot,monkeypatch):
    from agents import investigator, regional_impact
    calls=[]
    def run(*a,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(model_dump_json=lambda **k:'{}')
    monkeypatch.setattr(investigator,'run_agent',run)
    monkeypatch.setattr(regional_impact,'run_agent',run)
    record=translator.live_weather_record(snapshot)
    report=investigator.investigate(None,box(snapshot),record,lambda event:None)
    regional_impact.assess_regional_impact(None,box(snapshot),record,report,lambda event:None)
    assert all(call['tool_names']==('get_current_weather',) for call in calls)
    assert "TODAY" in calls[0]['system_prompt']


def test_first_day_current_weather_is_not_expanded_to_month_end(snapshot):
    record=translator.live_weather_record(snapshot).model_copy(update={'observation_date':NOW.date().replace(day=1)})
    assert infer_as_of_date(record).day==1
