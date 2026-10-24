"""ECMWF SEAS5 monthly ensemble-mean anomalies; never a daily event forecast."""
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import math

import requests

from data.cache import fetch_text
from data.locations import Location
from schemas.watchlist import MonthlySignal

SOURCE = 'https://seasonal-api.open-meteo.com/v1/seasonal'
MODEL = 'ecmwf_seas5_ensemble_mean'
FIELDS = {
    'temperature_2m_anomaly': ('temperature_anomaly', 'K'),
    'precipitation_anomaly': ('precipitation_anomaly', 'mm'),
    'soil_moisture_0_to_7cm_anomaly': ('soil_moisture_anomaly', 'm³/m³'),
    'runoff_anomaly': ('runoff_anomaly', 'mm'),
}


def _today():
    return datetime.now(timezone.utc).date()


def outlook_months(today: date, months: int = 3) -> list[date]:
    if months not in (1, 2, 3):
        raise ValueError('Choose one, two, or three months.')
    base = today.year * 12 + today.month
    return [date((base + offset) // 12, (base + offset) % 12 + 1, 1)
            for offset in range(months)]


@dataclass(frozen=True)
class SeasonalSnapshot:
    location: Location
    signals: list[MonthlySignal]
    retrieved_at: datetime
    source_url: str
    window_start: date
    window_end: date
    model: str = MODEL

    def evidence(self) -> dict[str, float]:
        return {key: value for signal in self.signals for key, value in signal.evidence().items()}


def load_seasonal(location: Location, months: int = 3, *, refresh: bool = False) -> SeasonalSnapshot:
    expected = outlook_months(_today(), months)
    params = dict(latitude=location.latitude, longitude=location.longitude,
                  monthly=','.join(FIELDS), models=MODEL, forecast_days=124,
                  timezone='GMT', temperature_unit='celsius', precipitation_unit='mm')
    raw, stamp, stale = fetch_text(SOURCE, params, max_age=0 if refresh else 21600, allow_stale=False)
    retrieved = datetime.fromisoformat(stamp)
    if retrieved.tzinfo is None:
        raise ValueError('Seasonal retrieval time must include its timezone.')
    age = (datetime.now(timezone.utc) - retrieved).total_seconds()
    if stale or not -60 <= age <= 21660:
        raise ValueError('Seasonal data retrieval is out of date.')
    payload = json.loads(raw)
    if payload.get('error'):
        raise ValueError('Seasonal provider rejected the request.')
    for coord, requested in [('latitude', location.latitude), ('longitude', location.longitude)]:
        actual = payload.get(coord)
        delta = abs(actual - requested) if isinstance(actual, (int, float)) else math.inf
        if coord == 'longitude' and math.isfinite(delta):
            delta = min(delta % 360, 360 - delta % 360)
        if not math.isfinite(delta) or delta > 1:
            raise ValueError('Seasonal source returned a different area.')
    rows = payload['monthly']
    dates = [date.fromisoformat(value) for value in rows['time']]
    if len(set(dates)) != len(dates) or dates != sorted(dates):
        raise ValueError('Invalid seasonal month sequence.')
    parsed = {month: {} for month in expected}
    for field, (name, unit) in FIELDS.items():
        if payload.get('monthly_units', {}).get(field) != unit:
            raise ValueError(f'Unexpected seasonal units for {field}.')
        values = rows.get(field, [])
        if len(values) != len(dates):
            raise ValueError('Incomplete seasonal field.')
        for month, value in zip(dates, values):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('Invalid seasonal value.')
            if month in parsed:
                parsed[month][name] = value
    if any(month not in dates for month in expected):
        raise ValueError('The provider does not cover the requested outlook window.')
    signals = [MonthlySignal(month=month, **parsed[month]) for month in expected]
    if not any(signal.evidence() for signal in signals):
        raise ValueError('No seasonal anomaly data are available.')
    end = expected[-1]
    end = end.replace(day=calendar.monthrange(end.year, end.month)[1])
    source_url = requests.Request('GET', SOURCE, params=params).prepare().url
    return SeasonalSnapshot(location, signals, retrieved, source_url, expected[0], end)
