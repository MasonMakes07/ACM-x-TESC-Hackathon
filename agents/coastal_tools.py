"""Coastal tools bound to one NOAA tide gauge: water levels, nearby wind and pressure.

Owner: Person 2 (Grok Agent Intelligence); added by Person 3 for coastal events. Every
result is real data or an explicit "unavailable" status. Windows are clipped to the
investigation's as-of date, and each retrieved source is recorded in the ledger.
"""

from datetime import datetime, time, timedelta, timezone

import pandas as pd

from agents.ledger import LedgerSource
from agents.toolbox import TOOL_DEFINITIONS, AgentToolbox
from data import coastal_sources

COASTAL_TOOLS = ("get_coastal_water_level", "get_coastal_weather", "fetch_official_source")
MAX_COASTAL_DAYS = 31
MAX_ROWS = 96
WEATHER_SOURCE_NAME = "Open-Meteo wind and sea-level pressure (weather model)"
DATE_PROPERTY = {"type": "string", "description": "ISO date, YYYY-MM-DD"}
WINDOW_PARAMETERS = {
    "type": "object",
    "properties": {"start_date": DATE_PROPERTY, "end_date": DATE_PROPERTY},
    "required": ["start_date", "end_date"],
}
COASTAL_DEFINITIONS = {
    "get_coastal_water_level": {
        "name": "get_coastal_water_level",
        "description": (
            "Observed water level and NOAA's astronomical tide prediction at this event's tide "
            "gauge (metres above MHHW), the residual (observed minus predicted: water the tide "
            "does not explain), and NOAA's minor high-tide-flooding threshold. Max 31 days."
        ),
        "parameters": WINDOW_PARAMETERS,
    },
    "get_coastal_weather": {
        "name": "get_coastal_weather",
        "description": (
            "Hourly wind speed/direction and sea-level pressure at the gauge's coordinates from a "
            "weather model (not a station). Use it to test wind set-up and low-pressure explanations."
        ),
        "parameters": WINDOW_PARAMETERS,
    },
}


# Downsamples a time-indexed frame so a tool result stays a readable size.
def _thin(frame: pd.DataFrame, limit: int = MAX_ROWS) -> pd.DataFrame:
    if len(frame) <= limit:
        return frame
    step = -(-len(frame) // limit)
    return frame.iloc[::step]


# Formats a timestamp column as ISO strings for JSON.
def _iso(frame: pd.DataFrame) -> list[dict]:
    rows = frame.copy()
    rows["time"] = rows["time"].dt.strftime("%Y-%m-%dT%H:%MZ")
    return rows.round(3).to_dict("records")


# Tools for one coastal investigation, bound to the event's station and coordinates.
class CoastalToolbox(AgentToolbox):
    # Binds the station and its coordinates; tools refuse any other location.
    def __init__(self, ledger, as_of_date, station: str, latitude: float, longitude: float, **kwargs) -> None:
        super().__init__(ledger, as_of_date, **kwargs)
        self.station, self.latitude, self.longitude = station, latitude, longitude
        self._handlers["get_coastal_water_level"] = self.get_coastal_water_level
        self._handlers["get_coastal_weather"] = self.get_coastal_weather

    # Returns tool definitions, adding the coastal tools to the shared ones.
    def definitions(self, tool_names: tuple[str, ...]) -> list[dict]:
        return [
            {"type": "function", "function": COASTAL_DEFINITIONS.get(name) or TOOL_DEFINITIONS[name]}
            for name in tool_names
        ]

    # Validates a coastal window: at most 31 days and never past the as-of date.
    def _coastal_window(self, start_date: object, end_date: object):
        start, end, clipped = self._date_window(start_date, end_date)
        if (end - start).days >= MAX_COASTAL_DAYS:
            raise ValueError(f"Coastal windows are limited to {MAX_COASTAL_DAYS} days.")
        return start, end, clipped

    # Returns observed vs predicted water levels, the residual and the flood threshold.
    def get_coastal_water_level(self, start_date: str, end_date: str) -> dict:
        tool = "get_coastal_water_level"
        start, end, clipped = self._coastal_window(start_date, end_date)
        begin = datetime.combine(start, time.min, timezone.utc)
        finish = min(datetime.combine(end + timedelta(days=1), time.min, timezone.utc),
                     datetime.now(timezone.utc).replace(second=0, microsecond=0))
        try:
            data = coastal_sources.get_station_levels(self.station, begin, finish)
        except Exception as error:
            return self._unavailable(tool, f"NOAA water levels could not be retrieved ({type(error).__name__}).")
        levels = data.levels.dropna(subset=["observed_m"])
        highest = levels.loc[levels["observed_m"].idxmax()]
        daily = levels.set_index("time").resample("1D").agg(
            {"observed_m": "max", "predicted_m": "max", "residual_m": "mean"}
        ).dropna(how="all").reset_index()
        name = f"NOAA CO-OPS {data.name} tide gauge {self.station} water levels"
        self.ledger.record_source(LedgerSource(name, "measurement", data.source, data.retrieved_at))
        return {
            "status": "ok", "source": name, "url": data.source, "retrieved_at": data.retrieved_at,
            "cache_stale": data.stale, "window_clipped_to_as_of_date": clipped,
            "units": "metres relative to MHHW (mean higher high water)",
            "minor_flood_threshold_m": data.minor_flood_m,
            "highest_water": {
                "time": highest["time"].strftime("%Y-%m-%dT%H:%MZ"),
                "observed_m": round(float(highest["observed_m"]), 3),
                "predicted_tide_m": None if pd.isna(highest["predicted_m"]) else round(float(highest["predicted_m"]), 3),
                "residual_m": None if pd.isna(highest["residual_m"]) else round(float(highest["residual_m"]), 3),
            },
            "residual_summary_m": {
                "mean": round(float(levels["residual_m"].mean()), 3),
                "min": round(float(levels["residual_m"].min()), 3),
                "max": round(float(levels["residual_m"].max()), 3),
            },
            "daily": _iso(daily.rename(columns={"observed_m": "max_observed_m", "predicted_m": "max_predicted_m",
                                                "residual_m": "mean_residual_m"})),
            "samples": _iso(_thin(levels[["time", "observed_m", "predicted_m", "residual_m"]])),
            "caveat": "One tide gauge. The prediction is NOAA's astronomical tide only; the residual "
                      "includes weather, ocean temperature and long-term sea-level effects combined.",
        }

    # Returns hourly wind and sea-level pressure near the gauge for the window.
    def get_coastal_weather(self, start_date: str, end_date: str) -> dict:
        tool = "get_coastal_weather"
        start, end, clipped = self._coastal_window(start_date, end_date)
        try:
            frame, retrieved_at, stale = coastal_sources.get_coastal_weather(self.latitude, self.longitude, start, end)
        except Exception as error:
            return self._unavailable(tool, f"Wind and pressure could not be retrieved ({type(error).__name__}).")
        frame = frame.dropna(how="all", subset=["wind_speed_kmh", "pressure_msl_hpa"])
        if frame.empty:
            return self._unavailable(tool, "The weather model returned no values for this window.")
        self.ledger.record_source(
            LedgerSource(WEATHER_SOURCE_NAME, "reference", coastal_sources.WEATHER_PAGE, retrieved_at)
        )
        lowest = frame.loc[frame["pressure_msl_hpa"].idxmin()]
        windiest = frame.loc[frame["wind_speed_kmh"].idxmax()]
        return {
            "status": "ok", "source": WEATHER_SOURCE_NAME, "url": coastal_sources.WEATHER_PAGE,
            "retrieved_at": retrieved_at, "cache_stale": stale, "window_clipped_to_as_of_date": clipped,
            "coordinates": [self.latitude, self.longitude],
            "units": {"wind_speed": "km/h", "wind_direction": "degrees FROM which wind blows", "pressure": "hPa"},
            "lowest_pressure": {"time": lowest["time"].strftime("%Y-%m-%dT%H:%MZ"),
                                "pressure_msl_hpa": round(float(lowest["pressure_msl_hpa"]), 1)},
            "strongest_wind": {"time": windiest["time"].strftime("%Y-%m-%dT%H:%MZ"),
                               "wind_speed_kmh": round(float(windiest["wind_speed_kmh"]), 1),
                               "wind_direction_deg": round(float(windiest["wind_direction_deg"]), 0)},
            "samples": _iso(_thin(frame)),
            "caveat": "Weather-model values at a grid point, not a measured station record.",
        }
