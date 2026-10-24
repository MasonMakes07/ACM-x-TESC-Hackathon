"""Sentinel Bot: re-checks the detected signal against source data (no LLM).

Owner: Person 2 (Grok Agent Intelligence). Person 1's code detects anomalies; the
Sentinel confirms that the record's value reproduces from the data before any
agent builds on it, and measures how persistent the signal is. It uses the same
guarded toolbox as the other bots, so every source it reads lands in the ledger.
"""

import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from agents.context import AnomalyContext, PACIFIC_INDEX_REGIONS, PERU_LOCATIONS
from agents.context import is_live_weather
from agents.runner import ProgressCallback, emit
from agents.toolbox import AgentToolbox
from schemas.anomaly import AnomalyRecord

AGENT_NAME = "Sentinel Bot"
LOOKBACK_MONTHS = 12
RAIN_WINDOW_DAYS = 7
RELATIVE_TOLERANCE = 0.01
ABSOLUTE_TOLERANCE = 0.05
LOCAL_MONTHLY_KEYS = {
    "Monthly mean air temperature": "mean_temperature_degC",
    "Monthly precipitation total": "total_precipitation_mm",
}

SentinelStatus = Literal["confirmed", "mismatch", "unverified"]


# =============================================================================
# SentinelReport
# =============================================================================

# The Sentinel's code-checked verdict on whether the record reproduces.
@dataclass(frozen=True)
class SentinelReport:
    status: SentinelStatus
    detail: str
    same_sign_run_months: int | None = None

    # Returns a one-line description for agent prompts and progress messages.
    def describe(self) -> str:
        run_note = (
            f" Same-sign run: {self.same_sign_run_months} month(s)."
            if self.same_sign_run_months is not None
            else ""
        )
        return f"Sentinel Bot check ({self.status}): {self.detail}{run_note}"


# Returns the first day of the month `months` before the given date.
def _months_before(day: date, months: int) -> date:
    month_index = day.year * 12 + (day.month - 1) - months
    return date(month_index // 12, month_index % 12 + 1, 1)


# Returns the number of consecutive latest values sharing the final value's sign.
def same_sign_run(values: list[float]) -> int:
    if not values or values[-1] == 0:
        return 0
    final_sign = math.copysign(1, values[-1])
    run_length = 0
    for value in reversed(values):
        if value == 0 or math.copysign(1, value) != final_sign:
            break
        run_length += 1
    return run_length


# Compares a recomputed value with the record's value using a small tolerance.
def _compare(actual: float, anomaly: AnomalyRecord, label: str) -> SentinelReport:
    if math.isclose(
        actual, anomaly.value, rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE
    ):
        return SentinelReport(
            "confirmed",
            f"{label} reproduces the record: {actual:g} {anomaly.unit} "
            f"(record: {anomaly.value:g}).",
        )
    return SentinelReport(
        "mismatch",
        f"{label} gives {actual:g} {anomaly.unit} but the record says "
        f"{anomaly.value:g}; the record could not be reproduced.",
    )


# Builds an unverified report with a reason.
def _unverified(reason: str) -> SentinelReport:
    return SentinelReport("unverified", reason)


# Re-checks a Pacific SST index record and measures its same-sign run.
def _check_sst_index(toolbox: AgentToolbox, anomaly: AnomalyRecord) -> SentinelReport:
    start = _months_before(anomaly.observation_date, LOOKBACK_MONTHS)
    result = json.loads(
        toolbox.execute(
            "get_climate_observations",
            {
                "region": anomaly.region,
                "start_date": start.isoformat(),
                "end_date": toolbox.as_of_date.isoformat(),
            },
        )
    )
    if result.get("status") != "ok":
        return _unverified(f"SST data tool was {result.get('status')}.")
    rows = result["observations"]
    target = anomaly.observation_date.isoformat()
    matching = [row["value"] for row in rows if row["date"] == target]
    if not matching:
        return _unverified(f"The source has no {anomaly.region} value for {target}.")
    report = _compare(matching[0], anomaly, f"NOAA {anomaly.region} index")
    values_to_date = [row["value"] for row in rows if row["date"] <= target]
    return SentinelReport(
        report.status, report.detail, same_sign_run(values_to_date)
    )


# Re-checks a Piura/Tumbes seven-day rainfall total against daily rainfall.
def _check_peru_rainfall(
    toolbox: AgentToolbox, anomaly: AnomalyRecord
) -> SentinelReport:
    if "7 days" not in anomaly.unit:
        return _unverified("No automated re-check exists for this rainfall record.")
    start = anomaly.observation_date - timedelta(days=RAIN_WINDOW_DAYS - 1)
    result = json.loads(
        toolbox.execute(
            "get_rainfall_history",
            {
                "location": anomaly.region,
                "start_date": start.isoformat(),
                "end_date": anomaly.observation_date.isoformat(),
            },
        )
    )
    if result.get("status") != "ok":
        return _unverified(f"Rainfall data tool was {result.get('status')}.")
    daily_values = [row["value"] for row in result["observations"]]
    if len(daily_values) != RAIN_WINDOW_DAYS:
        return _unverified("The source lacks a complete seven-day window.")
    return _compare(sum(daily_values), anomaly, f"{anomaly.region} seven-day rainfall")


# Re-checks a worldwide monthly temperature or precipitation record.
def _check_local_month(
    toolbox: AgentToolbox, anomaly: AnomalyRecord, context: AnomalyContext
) -> SentinelReport:
    monthly_key = LOCAL_MONTHLY_KEYS.get(anomaly.variable)
    if monthly_key is None:
        return _unverified(f"No automated re-check exists for '{anomaly.variable}'.")
    start = _months_before(anomaly.observation_date, LOOKBACK_MONTHS)
    result = json.loads(
        toolbox.execute(
            "get_local_weather",
            {
                "latitude": context.latitude,
                "longitude": context.longitude,
                "start_date": start.isoformat(),
                "end_date": toolbox.as_of_date.isoformat(),
            },
        )
    )
    if result.get("status") != "ok":
        return _unverified(f"Weather data tool was {result.get('status')}.")
    month_label = f"{anomaly.observation_date:%Y-%m}"
    month_rows = [row for row in result["monthly"] if row["month"] == month_label]
    actual = month_rows[0].get(monthly_key) if month_rows else None
    if actual is None:
        return _unverified(f"The source has no complete value for {month_label}.")
    return _compare(actual, anomaly, f"ERA5 at {context.place}")


# Re-checks the detected signal and reports whether it reproduces from the data.
def monitor(
    toolbox: AgentToolbox,
    anomaly: AnomalyRecord,
    context: AnomalyContext,
    on_progress: ProgressCallback,
) -> SentinelReport:
    emit(on_progress, AGENT_NAME, "Re-checking the signal against source data.")
    if is_live_weather(anomaly):
        result = json.loads(toolbox.execute('get_current_weather', {'latitude':context.latitude,'longitude':context.longitude}))
        actual = result.get('current',{}).get('temperature_2m')
        report = _compare(actual,anomaly,'Current model temperature') if result.get('status') == 'ok' and actual is not None else _unverified('Fresh current weather was unavailable.')
    elif anomaly.region in PACIFIC_INDEX_REGIONS:
        report = _check_sst_index(toolbox, anomaly)
    elif anomaly.region in PERU_LOCATIONS:
        report = _check_peru_rainfall(toolbox, anomaly)
    elif context.profile == "local":
        report = _check_local_month(toolbox, anomaly, context)
    else:
        report = _unverified("The record's region is not supported for re-checking.")
    emit(on_progress, AGENT_NAME, report.describe())
    return report
