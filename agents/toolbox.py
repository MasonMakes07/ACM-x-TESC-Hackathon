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
from datetime import date, datetime, timezone

import pandas as pd
import requests

from agents.ledger import EvidenceLedger, LedgerSource
from data import climate_sources, rainfall_sources

SST_REGIONS = ("Nino 1+2", "Nino 3.4")
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
            "https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/"
            "ensostuff/ONI_v5.php"
        ),
    },
}
MAX_ROWS = 120
MAX_TEXT_CHARS = 8000
MAX_RANGE_DAYS = 366 * 50
RETROSPECTIVE_AFTER_DAYS = 45
HTTP_TIMEOUT_SECONDS = 20
USER_AGENT = "EarthWatch-hackathon/0.1"
RAINFALL_STUB_REASON = "Rainfall pipeline not implemented yet."

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
def _rows(window: pd.DataFrame) -> list[dict]:
    recent = window.tail(MAX_ROWS)
    return [
        {"date": row_date.isoformat(), "value": round(float(row_value), 3)}
        for row_date, row_value in zip(recent["date"], recent["value"])
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

    # Validates a date window and clips it so no data after as_of_date is used.
    def _date_window(self, start_text: object, end_text: object) -> tuple:
        start = _parse_date(start_text, "start_date")
        end = _parse_date(end_text, "end_date")
        if start > end:
            raise ValueError("start_date must be on or before end_date.")
        if start > self.as_of_date:
            raise ValueError("start_date is after the investigation as-of date.")
        if (end - start).days > MAX_RANGE_DAYS:
            raise ValueError("Date range is too long (maximum 50 years).")
        clipped = end > self.as_of_date
        return start, min(end, self.as_of_date), clipped

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
        source_name = str(
            raw_series.attrs.get("source")
            or f"EarthWatch climate pipeline: {region} SST anomaly index"
        )
        self.ledger.record_source(LedgerSource(source_name, "measurement"))
        return {
            "status": "ok",
            "source": source_name,
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
        if location not in LOCATIONS:
            raise ValueError(f"location must be one of {list(LOCATIONS)}.")
        start, end, clipped = self._date_window(start_date, end_date)
        fetch_rainfall = getattr(rainfall_sources, "get_daily_rainfall", None)
        if fetch_rainfall is None:
            return self._unavailable(tool_name, RAINFALL_STUB_REASON)
        try:
            raw_series = fetch_rainfall(location, start, end)
            series = _tidy_series(raw_series)
        except NotImplementedError:
            return self._unavailable(tool_name, RAINFALL_STUB_REASON)
        except Exception:
            return self._unavailable(tool_name, "Rainfall data retrieval failed.")
        window = series[(series["date"] >= start) & (series["date"] <= end)]
        if window.empty:
            return self._unavailable(tool_name, f"No {location} rainfall in window.")
        source_name = str(
            raw_series.attrs.get("source")
            or f"EarthWatch rainfall pipeline: {location} daily precipitation"
        )
        self.ledger.record_source(LedgerSource(source_name, "measurement"))
        rainfall_mm = window["value"]
        return {
            "status": "ok",
            "source": source_name,
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
