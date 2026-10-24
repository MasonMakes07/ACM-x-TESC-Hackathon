"""Multi-source weather retrieval, satellite validation, and source provenance."""
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import pytest
import requests

from agents.ledger import EvidenceLedger
from agents.live_tools import LiveWeatherToolbox, LIVE_TOOL_NAMES
from data.locations import Location
from data import research_sources as sources

NOW=datetime(2026,10,24,20,0,tzinfo=timezone.utc)
PLACE=Location('San Diego',32.7336,-117.1831,country_code='US')


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(sources,'_now',lambda:NOW)
    from agents import live_tools
    monkeypatch.setattr(live_tools,'_now',lambda:NOW)


def test_national_sources_distinguish_forecasts_and_alerts(monkeypatch):
    monkeypatch.setattr(sources,'get_station_observation',lambda loc:{'status':'ok','station':'KSAN','source':'https://api.weather.gov/stations/KSAN/observations/latest','retrieved_at':NOW.isoformat()})
    def fake(url,params=None):
        if 'alerts' in url:
            return {'features':[{'properties':{'event':'Test warning','expires':(NOW+timedelta(hours=1)).isoformat()}},{'properties':{'event':'Expired','expires':(NOW-timedelta(hours=1)).isoformat()}}]},NOW.isoformat()
        return {'properties':{'meta':{'updated_at':NOW.isoformat(),'units':{'air_temperature':'celsius','wind_speed':'m/s'}},'timeseries':[{'time':NOW.isoformat(),'data':{'instant':{'details':{'air_temperature':20,'wind_speed':2}}}}]}},NOW.isoformat()
    monkeypatch.setattr(sources,'_json',fake)
    result=sources.national_weather(PLACE)
    assert result['status']=='ok'
    assert len(result['alerts'])==1
    assert result['forecast']['rows'][0]['data_kind']=='Forecast'
    assert result['forecast']['rows'][0]['wind_speed_kmh']==7.2
    assert {item['kind'] for item in result['sources']}=={'measurement','official_report','reference'}


def test_national_failure_does_not_invent_no_alerts(monkeypatch):
    monkeypatch.setattr(sources,'get_station_observation',lambda loc:{'status':'unavailable','reason':'offline'})
    def fail(*args): raise requests.ConnectionError('offline')
    monkeypatch.setattr(sources,'_json',fail)
    result=sources.national_weather(PLACE)
    assert result['status']=='unavailable'
    assert 'alerts' not in result


def png(transparent=False):
    buf=BytesIO()
    Image.new('RGBA',(8,8),(100,150,200,0 if transparent else 255)).save(buf,format='PNG')
    return buf.getvalue()


class Response:
    def __init__(self,body=None,content=None):
        self.body,self.content=body,content
    def raise_for_status(self): pass
    def json(self): return self.body


@pytest.mark.parametrize('kind',['image','blank','xml'])
def test_satellite_download_is_real_dated_nonblank_png(tmp_path,monkeypatch,kind):
    monkeypatch.setenv('EARTHWATCH_CACHE_DIR',str(tmp_path))
    content=b'<error>unavailable</error>' if kind=='xml' else png(kind=='blank')
    urls=[]
    def get(url,**kwargs):
        urls.append(url)
        return Response(content=content)
    monkeypatch.setattr(sources.requests,'get',get)
    result=sources.satellite_imagery(PLACE,'2026-10-23')
    assert len(urls)==2 and all('TIME=2026-10-23' in url for url in urls)
    if kind=='image':
        assert result['status']=='ok'
        assert len(result['images'])==2
        assert all(Path(item['local_path']).read_bytes()==content for item in result['images'])
        assert all('not been interpreted' in item['interpretation'] for item in result['images'])
    else:
        assert result['status']=='unavailable'


@pytest.mark.parametrize('day',['2026-10-25','2026-10-01'])
def test_satellite_future_and_old_dates_rejected(day):
    with pytest.raises(ValueError): sources.satellite_imagery(PLACE,day)


def test_agent_tools_are_location_bound_and_record_sources(monkeypatch):
    calls=[]
    def national(loc):
        calls.append(loc)
        return {'status':'ok','sources':[{'name':'MET Norway Locationforecast','url':sources.MET_URL,'kind':'reference','retrieved_at':NOW.isoformat()}]}
    monkeypatch.setattr(sources,'national_weather',national)
    toolbox=LiveWeatherToolbox(EvidenceLedger(),NOW.date(),PLACE)
    assert len(toolbox.definitions(LIVE_TOOL_NAMES))==3
    wrong=json.loads(toolbox.execute('get_national_weather',{'latitude':1,'longitude':2}))
    assert wrong['status']!='ok' and not calls
    args={'latitude':PLACE.latitude,'longitude':PLACE.longitude}
    assert json.loads(toolbox.execute('get_national_weather',args))['status']=='ok'
    assert json.loads(toolbox.execute('get_national_weather',args))['status']=='ok'
    assert len(calls)==1
    assert toolbox.ledger.find('',sources.MET_URL).kind=='reference'


def test_research_cannot_leak_current_data_into_history(monkeypatch):
    monkeypatch.setattr(sources,'national_weather',lambda *a:pytest.fail('Historical case fetched current data'))
    toolbox=LiveWeatherToolbox(EvidenceLedger(),NOW.date()-timedelta(days=1),PLACE)
    result=json.loads(toolbox.execute('get_national_weather',{'latitude':PLACE.latitude,'longitude':PLACE.longitude}))
    assert result['status']!='ok'


def test_removed_search_tool_is_not_exposed_or_executable():
    toolbox=LiveWeatherToolbox(EvidenceLedger(),NOW.date(),PLACE)
    assert set(LIVE_TOOL_NAMES)=={'get_current_weather','get_national_weather','get_satellite_imagery'}
    result=json.loads(toolbox.execute('search_google',{'latitude':PLACE.latitude,'longitude':PLACE.longitude,'query':'weather'}))
    assert result['status']=='error'
