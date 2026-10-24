"""Detects unusual coastal water levels at NOAA tide gauges.

Owner: Person 3 (added for coastal events; Person 1 may take ownership). The expected
level is NOAA's own astronomical tide prediction, so the anomaly is the non-tidal
residual: how much higher the water stood than the tide alone explains.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from data.coastal_sources import STATIONS, StationLevels, get_recent_levels
from schemas.anomaly import AnomalyRecord

logger = logging.getLogger(__name__)

COASTAL_VARIABLE = "Coastal water level above predicted tide"
COASTAL_UNIT = "m above predicted tide"
COASTAL_BASELINE = "NOAA harmonic tide prediction (MHHW, NTDE 1983-2001)"
DETECT_RESIDUAL_M = 0.30
MONITOR_RESIDUAL_M = 0.15
WINDOW_HOURS = 72


# Classifies a peak: detected at/above NOAA's flood threshold or a large residual.
def classify(peak_m: float, residual_m: float, minor_flood_m: float | None) -> str | None:
    if (minor_flood_m is not None and peak_m >= minor_flood_m) or residual_m >= DETECT_RESIDUAL_M:
        return "detected"
    if residual_m >= MONITOR_RESIDUAL_M:
        return "monitoring"
    return None


# Turns one station's recent levels into an anomaly record for its highest water, or None.
def station_event(levels: StationLevels) -> AnomalyRecord | None:
    rows = levels.levels.dropna(subset=["residual_m"])
    if rows.empty:
        return None
    highest = rows.loc[rows["observed_m"].idxmax()]
    residual = float(highest["residual_m"])
    status = classify(float(highest["observed_m"]), residual, levels.minor_flood_m)
    if status is None:
        return None
    threshold = (
        f"NOAA minor high-tide-flooding threshold {levels.minor_flood_m:+.3f} m MHHW"
        if levels.minor_flood_m is not None else "no NOAA flood threshold published"
    )
    method = (
        f"Highest water in the last {WINDOW_HOURS} h: observed {highest['observed_m']:+.3f} m MHHW at "
        f"{highest['time']:%Y-%m-%d %H:%M} UTC; NOAA predicted tide {highest['predicted_m']:+.3f} m; "
        f"{threshold}. Residual over the window: mean {rows['residual_m'].mean():+.3f} m, "
        f"max {rows['residual_m'].max():+.3f} m. Detected if at/above the threshold or residual >= "
        f"{DETECT_RESIDUAL_M} m; monitoring if residual >= {MONITOR_RESIDUAL_M} m "
        "(internal heuristic, not an official warning)"
    )
    if levels.stale:
        method += "; stale cached retrieval"
    return AnomalyRecord(
        anomaly_id=f"coastal_{levels.station}_{highest['time']:%Y%m%d}",
        variable=COASTAL_VARIABLE,
        region=f"{levels.name} ({levels.latitude}, {levels.longitude})",
        observation_date=highest["time"].date(),
        value=round(residual, 3),
        unit=COASTAL_UNIT,
        baseline_period=COASTAL_BASELINE,
        source=levels.source,
        detection_method=method,
        status=status,
    )


# Fetches one station and returns its event, logging (not raising) when the station fails.
def _safe_station_event(station: str, now: datetime | None) -> AnomalyRecord | None:
    try:
        return station_event(get_recent_levels(station, WINDOW_HOURS, now))
    except Exception:
        logger.exception("Coastal station %s could not be checked", station)
        return None


# Returns unusual coastal water levels across the monitored NOAA stations.
def detect_coastal_events(now: datetime | None = None) -> list[AnomalyRecord]:
    with ThreadPoolExecutor(max_workers=len(STATIONS)) as pool:
        results = list(pool.map(lambda station: _safe_station_event(station, now), STATIONS))
    return [record for record in results if record is not None]
