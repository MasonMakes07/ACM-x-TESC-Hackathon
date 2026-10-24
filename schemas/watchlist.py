"""Seasonal outlooks are separate from measured anomalies and official warnings."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Hazard = Literal['Flood', 'Drought', 'Heat wave', 'Wildfire conditions', 'Heavy rainfall']
HAZARDS = ('Flood', 'Drought', 'Heat wave', 'Wildfire conditions', 'Heavy rainfall')


class MonthlySignal(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    month: date
    temperature_anomaly: float | None = None
    precipitation_anomaly: float | None = None
    soil_moisture_anomaly: float | None = None
    runoff_anomaly: float | None = None

    def evidence(self) -> dict[str, float]:
        return {f'{self.month:%Y-%m}:{key}': value for key, value in self.model_dump().items()
                if key != 'month' and value is not None}


class HazardOutlook(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    hazard: Hazard
    level: Literal['Elevated watch', 'Monitor', 'Inconclusive']
    confidence: Literal['low', 'moderate', 'inconclusive']
    summary: str = Field(min_length=1, max_length=600)
    rationale: str = Field(min_length=1, max_length=1600)
    evidence_refs: list[str] = Field(max_length=12)
    limitations: list[str] = Field(min_length=1, max_length=8)
    monitoring_triggers: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode='after')
    def evidence_required(self):
        if self.level != 'Inconclusive' and not self.evidence_refs:
            raise ValueError('An assessed watch requires retrieved seasonal evidence.')
        if self.level == 'Inconclusive' and self.confidence != 'inconclusive':
            raise ValueError('Inconclusive outlooks must have inconclusive confidence.')
        if self.level != 'Inconclusive' and self.confidence == 'inconclusive':
            raise ValueError('An assessed watch needs low or moderate confidence.')
        return self


class SeasonalReview(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    summary: str = Field(min_length=1, max_length=1200)
    outlooks: list[HazardOutlook] = Field(min_length=5, max_length=5)

    @model_validator(mode='after')
    def all_hazards_once(self):
        if {item.hazard for item in self.outlooks} != set(HAZARDS):
            raise ValueError('Review all five hazards exactly once.')
        return self


class WatchResult(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    location_key: str
    location_label: str
    latitude: float
    longitude: float
    window_start: date
    window_end: date
    retrieved_at: datetime
    assessed_at: datetime
    source_url: str
    model: str
    signals: list[MonthlySignal]
    review: SeasonalReview
