"""Works out what kind of anomaly a record describes and where it is.

Owner: Person 2 (Grok Agent Intelligence). The shared AnomalyRecord has no
coordinate fields, so worldwide records carry them in `region` as
"Place name (-1.2864, 36.8172)"; Pacific records use the NOAA index or Peru
location names. This module turns that into a typed AnomalyContext.
"""

import calendar
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from schemas.anomaly import AnomalyRecord

PACIFIC_INDEX_REGIONS = ("Nino 1+2", "Nino 3.4")
PERU_LOCATIONS = ("Piura", "Tumbes")
MAX_PLACE_CHARS = 80
COORDINATE_PATTERN = re.compile(
    r"^(?P<place>.+?)\s*\((?P<latitude>-?\d+(?:\.\d+)?),\s*"
    r"(?P<longitude>-?\d+(?:\.\d+)?)\)\s*$"
)

Profile = Literal["pacific", "local", "unknown"]


# =============================================================================
# AnomalyContext
# =============================================================================

# Describes how to investigate one anomaly: Pacific index, local weather, or neither.
@dataclass(frozen=True)
class AnomalyContext:
    profile: Profile
    place: str
    latitude: float | None = None
    longitude: float | None = None

    # Returns the human-readable location line used in agent prompts.
    def describe(self) -> str:
        if self.latitude is None or self.longitude is None:
            return self.place
        return f"{self.place} (latitude {self.latitude}, longitude {self.longitude})"


# Classifies an anomaly record and extracts coordinates for worldwide records.
def build_context(anomaly: AnomalyRecord) -> AnomalyContext:
    region = anomaly.region.strip()
    if region in PACIFIC_INDEX_REGIONS or region in PERU_LOCATIONS:
        return AnomalyContext("pacific", region)
    match = COORDINATE_PATTERN.match(region)
    if match:
        latitude = float(match.group("latitude"))
        longitude = float(match.group("longitude"))
        if (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            place = match.group("place").strip()[:MAX_PLACE_CHARS]
            return AnomalyContext("local", place, latitude, longitude)
    return AnomalyContext("unknown", region[:MAX_PLACE_CHARS])


# Returns the last date whose data was available when the anomaly was observed.
def infer_as_of_date(anomaly: AnomalyRecord) -> date:
    observed = anomaly.observation_date
    is_monthly_value = observed.day == 1 and "7 days" not in anomaly.unit
    if not is_monthly_value:
        return observed
    last_day = calendar.monthrange(observed.year, observed.month)[1]
    return observed.replace(day=last_day)
