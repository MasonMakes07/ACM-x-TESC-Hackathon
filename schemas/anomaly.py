"""Shared anomaly contract between the climate pipeline, agents and dashboard.

SHARED FILE: changing it changes the contract for all three workstreams. Agree as
a team first, update sample_data/ in the same commit, and run pytest before pushing.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnomalyStatus = Literal["detected", "monitoring", "inconclusive"]

# Columns every observation-series DataFrame must contain (date, numeric value).
SERIES_COLUMNS = ("date", "value")


# =============================================================================
# AnomalyRecord
# =============================================================================

# One detected environmental anomaly produced by the climate pipeline (Person 1).
class AnomalyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anomaly_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    variable: str = Field(min_length=1)
    region: str = Field(min_length=1)
    observation_date: date
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1)
    baseline_period: str = Field(min_length=1)
    source: str = Field(min_length=1)
    detection_method: str = Field(min_length=1)
    status: AnomalyStatus
