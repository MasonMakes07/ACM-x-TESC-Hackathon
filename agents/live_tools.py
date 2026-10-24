"""Live-only tools bound to the selected location and one fresh snapshot."""
from datetime import datetime, timezone
import json
import math

from agents.ledger import LedgerSource
from agents.toolbox import AgentToolbox
from data.live_weather import get_live_weather
from data.station_weather import get_station_observation, compare_station
from data import research_sources

LIVE_TOOL_NAMES = ('get_current_weather','get_national_weather','get_satellite_imagery')

DEFINITION = {
    'type':'function', 'function': {
        'name':'get_current_weather',
        'description': 'Current model estimates and independent nearby station observation for the selected coordinates, with source timestamps. Future hourly rows are forecasts, not observations.',
        'parameters': {'type':'object', 'properties': {
            'latitude': {'type':'number'}, 'longitude': {'type':'number'}},
            'required':['latitude','longitude'], 'additionalProperties':False},
    },
}


def _now():
    return datetime.now(timezone.utc)


def _research_definition(name, description, extra=None):
    fields={'latitude':{'type':'number'},'longitude':{'type':'number'}}
    fields.update(extra or {})
    return {'type':'function','function':{'name':name,'description':description,
            'parameters':{'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}}}


DEFINITIONS = {
    'get_current_weather':DEFINITION,
    'get_national_weather':_research_definition('get_national_weather','Official NOAA/NWS observations and active alerts (US), and MET Norway global forecasts. Forecasts are not observed conditions.'),
    'get_satellite_imagery':_research_definition('get_satellite_imagery','Retrieve actual NASA GIBS MODIS Terra/Aqua true-color satellite scenes. Imagery is not automatically interpreted; never derive temperatures from this metadata.',{'scene_date':{'type':'string','description':'UTC YYYY-MM-DD within past seven days, not future; try yesterday if today is unavailable.'}}),
}


class LiveWeatherToolbox(AgentToolbox):
    def __init__(self, ledger, as_of_date, location, *, weather=None, station=None):
        super().__init__(ledger, as_of_date)
        self.location, self.weather, self.station = location, weather, station
        self._research_cache = {}

    def definitions(self, tool_names):
        if any(name not in DEFINITIONS for name in tool_names):
            raise ValueError('Unsupported live research tool')
        return [DEFINITIONS[name] for name in tool_names]

    def execute(self, tool_name, raw_arguments):
        if tool_name not in DEFINITIONS:
            return json.dumps(dict(status='error', message='Only location-bound live research tools are allowed.'))
        try:
            args = json.loads(raw_arguments) if isinstance(raw_arguments,str) else raw_arguments
            fields=set(DEFINITIONS[tool_name]['function']['parameters']['properties'])
            if not isinstance(args,dict) or set(args) != fields:
                raise ValueError('Tool arguments do not match the allowed fields')
            if not math.isclose(float(args['latitude']),self.location.latitude,abs_tol=0.00001,rel_tol=0) or not math.isclose(float(args['longitude']),self.location.longitude,abs_tol=0.00001,rel_tol=0):
                raise ValueError('Coordinates do not match the selected location')
            if tool_name != 'get_current_weather':
                return json.dumps(self._research(tool_name,args))
            if self.weather is None:
                self.weather = get_live_weather(self.location,refresh=True)
            weather = self.weather
            if weather.location.latitude != self.location.latitude or weather.location.longitude != self.location.longitude:
                raise ValueError('Snapshot belongs to a different location')
            now = _now().astimezone(weather.current_time.tzinfo)
            if weather.current_time.date() != now.date() or self.as_of_date != now.date() or not -900 <= (now-weather.current_time).total_seconds() <= 5400:
                raise ValueError('Live weather snapshot is not current; refresh it')
            if not -60 <= (now-weather.retrieved_at).total_seconds() <= 600:
                raise ValueError('Live weather retrieval expired; refresh it')
            if self.station is None:
                self.station = get_station_observation(self.location)
            comparison = compare_station(weather,self.station)
            self.ledger.record_source(LedgerSource('Open-Meteo current model estimate','reference',weather.source,weather.retrieved_at.isoformat()))
            if self.station.get('status') == 'ok':
                self.ledger.record_source(LedgerSource('NOAA NWS '+self.station['station']+' station observation','measurement',self.station['source'],self.station['retrieved_at']))
            rows = json.loads(weather.hourly[['date','temperature_2m','precipitation','data_kind']].to_json(orient='records',date_format='iso'))
            return json.dumps(dict(status='ok', requested_coordinates=[self.location.latitude,self.location.longitude],
                                   source=weather.source, source_name='Open-Meteo current model estimate',
                                   conditions_time=weather.current_time.isoformat(), retrieved_at=weather.retrieved_at.isoformat(),
                                   current=weather.current, temperature_unit='degC', humidity_unit='%', wind_unit='km/h',
                                   precipitation_unit='mm', precipitation_interval_seconds=weather.interval_seconds,
                                   station=self.station, comparison=comparison, hourly=rows,
                                   caveat='Current model estimates and station observations are distinct. Future hourly rows are forecasts. No climate baseline or hazard classification was calculated.'))
        except (ValueError, TypeError, KeyError) as error:
            return json.dumps(self._unavailable(tool_name,str(error)))
        except Exception:
            return json.dumps(self._unavailable(tool_name,'Live weather retrieval failed; no invented or historical replacement data was used.'))

    def _research(self,name,args):
        now=_now().astimezone(self.weather.current_time.tzinfo) if self.weather else _now()
        if self.as_of_date != now.date():
            raise ValueError('Current research cannot be used as historical evidence')
        cache_key=(name,json.dumps(args,sort_keys=True))
        if cache_key in self._research_cache:
            return self._research_cache[cache_key]
        if name=='get_national_weather':
            result=research_sources.national_weather(self.location)
            for source in result.get('sources',[]):
                self.ledger.record_source(LedgerSource(source['name'],source['kind'],source['url'],source['retrieved_at']))
            for reason in result.get('unavailable',[]):
                self.ledger.record_unavailable(name,reason)
        elif name=='get_satellite_imagery':
            result=research_sources.satellite_imagery(self.location,args['scene_date'])
            for image in result.get('images',[]):
                self.ledger.record_source(LedgerSource(image['source'],'reference',image['url'],image['retrieved_at']))
        if result.get('status')!='ok':
            self.ledger.record_unavailable(name,result.get('reason','Source unavailable'))
        self._research_cache[cache_key]=result
        return result

    @property
    def research_results(self):
        return list(self._research_cache.values())
