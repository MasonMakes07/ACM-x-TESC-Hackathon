"""Controlled tools the Grok agents may call during one investigation.

Owner: Person 2 (Grok Agent Intelligence). Every result is either real data or an
explicit "unavailable" status; tools never invent values. Data tools call Person
1's functions, block data dated after the anomaly (no hindsight), and record each
retrieved source in the EvidenceLedger so provenance can be verified in code.
"""

import html
import json
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from agents.context import PACIFIC_INDEX_REGIONS, PERU_LOCATIONS
from agents.ledger import EvidenceLedger, LedgerSource
from data import climate_sources, rainfall_sources, weather_sources
from data.locations import Location

SST_REGIONS = PACIFIC_INDEX_REGIONS
LOCATIONS = {
    "Piura": {"department": "Piura", "latitude": -5.19, "longitude": -80.63},
    "Tumbes": {"department": "Tumbes", "latitude": -3.57, "longitude": -80.45},
}
OFFICIAL_SOURCES = {
    "noaa_enso_discussion": {
        "name": "NOAA CPC ENSO Diagnostic Discussion",
        "url": (
            "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/"
            "enso_advisory/ensodisc.shtml"
        ),
    },
    "noaa_oni_table": {
        "name": "NOAA CPC Oceanic Nino Index (ONI) table",
        "url": (
            "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/"
            "ensostuff/ONI_v5.php"
        ),
    },
}
MAX_ROWS = 120
MAX_MONTH_ROWS = 60
RECENT_DAILY_ROWS = 14
MAX_TEXT_CHARS = 8000
MAX_RANGE_DAYS = 366 * 50
DATA_DELAY_DAYS = 7
EARLIEST_WEATHER_DATE = date(1940, 1, 1)
RETROSPECTIVE_AFTER_DAYS = 45
HTTP_TIMEOUT_SECONDS = 20
USER_AGENT = "EarthWatch-hackathon/0.1"
RAINFALL_STUB_REASON = "Rainfall pipeline not implemented yet."
STALE_CACHE_NOTE = "Served from a stale cache because the live source was unreachable."
SELECTED_LOCATION_NAME = "Selected location"

DATE_PROPERTY = {"type": "string", "description": "ISO date, YYYY-MM-DD"}
TOOL_DEFINITIONS = {
    "get_climate_observations": {
        "name": "get_climate_observations",
        "description": "Real SST anomaly observations for a Pacific index region.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "enum": list(SST_REGIONS)},
                "start_date": DATE_PROPERTY,
                "end_date": DATE_PROPERTY,
            },
            "required": ["region", "start_date", "end_date"],
        },
    },
    "get_rainfall_history": {
        "name": "get_rainfall_history",
        "description": "Real daily rainfall (mm) for a northern Peru location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "enum": list(LOCATIONS)},
                "start_date": DATE_PROPERTY,
                "end_date": DATE_PROPERTY,
            },
            "required": ["location", "start_date", "end_date"],
        },
    },
    "get_local_weather": {
        "name": "get_local_weather",
        "description": (
            "Real ERA5 reanalysis air temperature and precipitation at any "
            "coordinates on Earth (nearest grid cell, not a station reading). "
            "Returns monthly means/totals for complete months and recent days."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "start_date": DATE_PROPERTY,
                "end_date": DATE_PROPERTY,
            },
            "required": ["latitude", "longitude", "start_date", "end_date"],
        },
    },
    "fetch_official_source": {
        "name": "fetch_official_source",
        "description": "Text of an allow-listed official NOAA climate publication.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "enum": list(OFFICIAL_SOURCES)},
            },
            "required": ["source_id"],
        },
    },
    "get_regional_context": {
        "name": "get_regional_context",
        "description": "Coordinates and department for a monitored Peru location.",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string", "enum": list(LOCATIONS)}},
            "required": ["location"],
        },
    },
}


# Parses an ISO date string, raising ValueError with a readable message.
def _parse_date(text: object, label: str) -> date:
    try:
        return date.fromisoformat(str(text))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD).") from error


# Converts a pipeline DataFrame into clean, date-sorted date/value rows.
def _tidy_series(raw_series: object) -> pd.DataFrame:
    if not isinstance(raw_series, pd.DataFrame) or not {"date", "value"} <= set(
        raw_series.columns
    ):
        raise ValueError("Pipeline returned data without date and value columns.")
    series = raw_series.loc[:, ["date", "value"]].copy()
    series["date"] = pd.to_datetime(series["date"], errors="coerce").dt.date
    series["value"] = pd.to_numeric(series["value"], errors="coerce")
    return series.dropna().sort_values("date").reset_index(drop=True)


# Summarises a date/value window with count, range, mean and latest value.
def _summarise(window: pd.DataFrame) -> dict:
    values = window["value"]
    return {
        "count": int(values.size),
        "min": round(float(values.min()), 3),
        "max": round(float(values.max()), 3),
        "mean": round(float(values.mean()), 3),
        "latest_date": window["date"].iloc[-1].isoformat(),
        "latest_value": round(float(values.iloc[-1]), 3),
    }


# Converts the most recent rows of a window into JSON-friendly dicts.
def _rows(window: pd.DataFrame, limit: int = MAX_ROWS) -> list[dict]:
    recent = window.tail(limit)
    return [
        {"date": row_date.isoformat(), "value": round(float(row_value), 3)}
        for row_date, row_value in zip(recent["date"], recent["value"])
    ]


# Returns the last non-missing value of a provenance column, or None.
def _last_value(raw_series: pd.DataFrame, column: str):
    if column not in raw_series.columns:
        return None
    present = raw_series[column].dropna()
    return present.iloc[-1] if not present.empty else None


# Collects source name, URL and retrieval details from a pipeline DataFrame.
def _provenance(raw_series: pd.DataFrame, default_name: str) -> dict:
    kind = _last_value(raw_series, "measurement_kind")
    url = _last_value(raw_series, "source")
    retrieved_at = _last_value(raw_series, "retrieved_at")
    return {
        "name": f"{default_name} ({kind})" if kind else default_name,
        "url": str(url) if url else None,
        "retrieved_at": str(retrieved_at) if retrieved_at else None,
        "cache_stale": bool(_last_value(raw_series, "cache_stale")),
        "measurement_kind": str(kind) if kind else None,
    }


# Builds the provenance fields included in every data tool result.
def _provenance_fields(provenance: dict) -> dict:
    fields = {
        "source": provenance["name"],
        "url": provenance["url"],
        "retrieved_at": provenance["retrieved_at"],
        "cache_stale": provenance["cache_stale"],
    }
    if provenance["cache_stale"]:
        fields["note"] = STALE_CACHE_NOTE
    return fields


# Builds complete-month mean temperature and total precipitation rows.
def _monthly_rows(weather: pd.DataFrame) -> list[dict]:
    indexed = weather.set_index(pd.to_datetime(weather["date"]))
    monthly: dict[str, dict] = {}
    for column, aggregation, output_name in (
        ("temperature", "mean", "mean_temperature_degC"),
        ("precipitation", "sum", "total_precipitation_mm"),
    ):
        grouped = indexed[column].resample("MS")
        counts = grouped.count()
        values = getattr(grouped, aggregation)()
        for month_start, value in values.items():
            is_complete = counts[month_start] == month_start.days_in_month
            row = monthly.setdefault(
                f"{month_start:%Y-%m}",
                {"month": f"{month_start:%Y-%m}"},
            )
            row[output_name] = round(float(value), 2) if is_complete else None
    return list(monthly.values())[-MAX_MONTH_ROWS:]


# Rounds a number for output, keeping missing values as None (never invented).
def _round_or_none(value: object) -> float | None:
    return None if pd.isna(value) else round(float(value), 2)


# Lists the most recent daily temperature and precipitation values.
def _recent_days(weather: pd.DataFrame) -> list[dict]:
    recent = weather.tail(RECENT_DAILY_ROWS)
    return [
        {
            "date": pd.Timestamp(row_date).date().isoformat(),
            "temperature_degC": _round_or_none(temperature),
            "precipitation_mm": _round_or_none(precipitation),
        }
        for row_date, temperature, precipitation in zip(
            recent["date"], recent["temperature"], recent["precipitation"]
        )
    ]


# Strips scripts, styles and tags from HTML and collapses whitespace.
def _strip_html(page_html: str) -> str:
    without_code = re.sub(
        r"<(script|style)\b.*?</\1>", " ", page_html, flags=re.S | re.I
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_code)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


# =============================================================================
# AgentToolbox
# =============================================================================

# Executes agent tool calls safely and records provenance in the ledger.
class AgentToolbox:
    # Binds the toolbox to one investigation's ledger and as-of date.
    def __init__(
        self,
        ledger: EvidenceLedger,
        as_of_date: date,
        http_get: Callable[..., requests.Response] = requests.get,
        today: date | None = None,
    ) -> None:
        self.ledger = ledger
        self.as_of_date = as_of_date
        self.today = today or datetime.now(timezone.utc).date()
        self._http_get = http_get
        self._page_cache: dict[str, str] = {}
        self._handlers: dict[str, Callable[..., dict]] = {
            "get_climate_observations": self.get_climate_observations,
            "get_rainfall_history": self.get_rainfall_history,
            "get_local_weather": self.get_local_weather,
            "fetch_official_source": self.fetch_official_source,
            "get_regional_context": self.get_regional_context,
        }

    # Returns Grok function-calling tool definitions for the requested tool names.
    def definitions(self, tool_names: tuple[str, ...]) -> list[dict]:
        return [
            {"type": "function", "function": TOOL_DEFINITIONS[name]}
            for name in tool_names
        ]

    # Runs one tool call and returns a JSON string; never raises.
    def execute(self, tool_name: str, raw_arguments: object) -> str:
        handler = self._handlers.get(tool_name)
        if handler is None:
            return json.dumps({"status": "error", "message": "Unknown tool."})
        try:
            arguments = (
                json.loads(raw_arguments or "{}")
                if isinstance(raw_arguments, str)
                else raw_arguments
            )
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object.")
            result = handler(**arguments)
        except TypeError:
            result = {"status": "error", "message": "Invalid tool arguments."}
        except ValueError as error:
            result = {"status": "error", "message": str(error)}
        return json.dumps(result, default=str)

    # Records an unavailable tool result in the ledger and returns it.
    def _unavailable(self, tool_name: str, reason: str) -> dict:
        self.ledger.record_unavailable(tool_name, reason)
        return {"status": "unavailable", "reason": reason}

    # Records a retrieved measurement source and returns its provenance fields.
    def _record_measurement(self, provenance: dict) -> dict:
        self.ledger.record_source(
            LedgerSource(
                provenance["name"],
                "measurement",
                provenance["url"],
                provenance["retrieved_at"],
            )
        )
        return _provenance_fields(provenance)

    # Validates a date window and clips it so no data after as_of_date is used.
    def _date_window(
        self,
        start_text: object,
        end_text: object,
        *,
        earliest: date | None = None,
        publication_delay_days: int | None = None,
    ) -> tuple[date, date, bool]:
        start = _parse_date(start_text, "start_date")
        end = _parse_date(end_text, "end_date")
        if start > end:
            raise ValueError("start_date must be on or before end_date.")
        if start > self.as_of_date:
            raise ValueError("start_date is after the investigation as-of date.")
        if (end - start).days > MAX_RANGE_DAYS:
            raise ValueError("Date range is too long (maximum 50 years).")
        if earliest is not None and start < earliest:
            raise ValueError(f"start_date must be on or after {earliest.isoformat()}.")
        clipped = end > self.as_of_date
        end = min(end, self.as_of_date)
        if publication_delay_days is not None:
            latest_published = self.today - timedelta(days=publication_delay_days)
            if end > latest_published:
                end, clipped = latest_published, True
                if start > end:
                    raise ValueError("No published data exists yet for that window.")
        return start, end, clipped

    # Returns real SST anomaly observations for a region and date window.
    def get_climate_observations(
        self, region: str, start_date: str, end_date: str
    ) -> dict:
        tool_name = "get_climate_observations"
        if region not in SST_REGIONS:
            raise ValueError(f"region must be one of {list(SST_REGIONS)}.")
        start, end, clipped = self._date_window(start_date, end_date)
        try:
            raw_series = climate_sources.get_sst_series(region)
            series = _tidy_series(raw_series)
        except NotImplementedError:
            return self._unavailable(tool_name, "Climate pipeline not implemented yet.")
        except Exception:
            return self._unavailable(tool_name, "Climate data retrieval failed.")
        window = series[(series["date"] >= start) & (series["date"] <= end)]
        if window.empty:
            return self._unavailable(tool_name, f"No {region} data in that window.")
        provenance = _provenance(raw_series, f"NOAA CPC {region} SST anomaly index")
        return {
            "status": "ok",
            **self._record_measurement(provenance),
            "region": region,
            "window": [start.isoformat(), end.isoformat()],
            "clipped_to_as_of_date": clipped,
            "summary": _summarise(window),
            "observations": _rows(window),
        }

    # Returns real daily rainfall for a location and date window, with totals.
    def get_rainfall_history(
        self, location: str, start_date: str, end_date: str
    ) -> dict:
        tool_name = "get_rainfall_history"
        if location not in PERU_LOCATIONS:
            raise ValueError(f"location must be one of {list(PERU_LOCATIONS)}.")
        start, end, clipped = self._date_window(
            start_date, end_date, publication_delay_days=DATA_DELAY_DAYS
        )
        try:
            raw_series = rainfall_sources.get_rainfall_history(
                location, start.isoformat(), end.isoformat()
            )
            series = _tidy_series(raw_series)
        except NotImplementedError:
            return self._unavailable(tool_name, RAINFALL_STUB_REASON)
        except Exception:
            return self._unavailable(tool_name, "Rainfall data retrieval failed.")
        window = series[(series["date"] >= start) & (series["date"] <= end)]
        if window.empty:
            return self._unavailable(tool_name, f"No {location} rainfall in window.")
        provenance = _provenance(
            raw_series, f"Open-Meteo {location} daily precipitation"
        )
        rainfall_mm = window["value"]
        return {
            "status": "ok",
            **self._record_measurement(provenance),
            "location": location,
            "unit": "mm",
            "window": [start.isoformat(), end.isoformat()],
            "clipped_to_as_of_date": clipped,
            "summary": {
                **_summarise(window),
                "total_mm": round(float(rainfall_mm.sum()), 1),
                "max_7day_total_mm": round(
                    float(rainfall_mm.rolling(7, min_periods=1).sum().max()), 1
                ),
            },
            "observations": _rows(window),
        }

    # Returns real ERA5 temperature and precipitation at any coordinates on Earth.
    def get_local_weather(
        self, latitude: float, longitude: float, start_date: str, end_date: str
    ) -> dict:
        tool_name = "get_local_weather"
        try:
            place = Location(SELECTED_LOCATION_NAME, float(latitude), float(longitude))
        except (TypeError, ValueError) as error:
            raise ValueError(
                "latitude (-90..90) and longitude (-180..180) must be valid numbers."
            ) from error
        start, end, clipped = self._date_window(
            start_date,
            end_date,
            earliest=EARLIEST_WEATHER_DATE,
            publication_delay_days=DATA_DELAY_DAYS,
        )
        try:
            raw_weather = weather_sources.get_weather_history(
                place, start.isoformat(), end.isoformat()
            )
            row_dates = raw_weather["date"].dt.date
            raw_weather = raw_weather.loc[(row_dates >= start) & (row_dates <= end)]
            temperature = _tidy_series(
                raw_weather[["date", "temperature"]].rename(
                    columns={"temperature": "value"}
                )
            )
            precipitation = _tidy_series(
                raw_weather[["date", "precipitation"]].rename(
                    columns={"precipitation": "value"}
                )
            )
        except NotImplementedError:
            return self._unavailable(tool_name, "Weather pipeline not implemented yet.")
        except Exception:
            return self._unavailable(tool_name, "Weather data retrieval failed.")
        if temperature.empty and precipitation.empty:
            return self._unavailable(tool_name, "No weather observations in window.")
        provenance = _provenance(raw_weather, "Open-Meteo")
        return {
            "status": "ok",
            **self._record_measurement(provenance),
            "requested_coordinates": [place.latitude, place.longitude],
            "grid_cell_coordinates": [
                _last_value(raw_weather, "grid_latitude"),
                _last_value(raw_weather, "grid_longitude"),
            ],
            "window": [start.isoformat(), end.isoformat()],
            "clipped_to_as_of_or_publication_date": clipped,
            "temperature_summary_degC": (
                _summarise(temperature) if not temperature.empty else None
            ),
            "precipitation_summary_mm": (
                _summarise(precipitation) if not precipitation.empty else None
            ),
            "monthly": _monthly_rows(raw_weather),
            "recent_days": _recent_days(raw_weather),
            "caveat": (
                "Gridded reanalysis estimate for the nearest grid cell; not a "
                "station reading and not a national or regional average."
            ),
        }

    # Returns the text of an allow-listed official source, labelled by timing.
    def fetch_official_source(self, source_id: str) -> dict:
        tool_name = "fetch_official_source"
        entry = OFFICIAL_SOURCES.get(source_id)
        if entry is None:
            raise ValueError(f"source_id must be one of {list(OFFICIAL_SOURCES)}.")
        if source_id not in self._page_cache:
            try:
                response = self._http_get(
                    entry["url"],
                    timeout=HTTP_TIMEOUT_SECONDS,
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
            except requests.RequestException:
                return self._unavailable(tool_name, f"{entry['name']} unreachable.")
            self._page_cache[source_id] = _strip_html(response.text)[:MAX_TEXT_CHARS]
        retrieved_at = self.today.isoformat()
        is_retrospective = (
            self.today - self.as_of_date
        ).days > RETROSPECTIVE_AFTER_DAYS
        self.ledger.record_source(
            LedgerSource(entry["name"], "official_report", entry["url"], retrieved_at)
        )
        return {
            "status": "ok",
            "source": entry["name"],
            "url": entry["url"],
            "retrieved_at": retrieved_at,
            "publication_timing": (
                "retrospective" if is_retrospective else "contemporaneous"
            ),
            "timing_note": (
                "Current publication retrieved long after the anomaly date: use it "
                "only as retrospective validation, not as information available then."
                if is_retrospective
                else "Published close to the anomaly date."
            ),
            "text": self._page_cache[source_id],
        }

    # Returns coordinates and department for a monitored Peru location.
    def get_regional_context(self, location: str) -> dict:
        if location not in LOCATIONS:
            raise ValueError(f"location must be one of {list(LOCATIONS)}.")
        source_name = "EarthWatch monitored-location table"
        self.ledger.record_source(LedgerSource(source_name, "reference"))
        return {
            "status": "ok",
            "source": source_name,
            "location": location,
            **LOCATIONS[location],
            "note": "Coordinates only; no hazard data is bundled with this tool.",
        }
