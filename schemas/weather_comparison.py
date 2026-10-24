"""Current weather versus a matching historical local-hour distribution."""
from datetime import datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WeatherMetric(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    variable: Literal['temperature', 'precipitation', 'wind']
    unit: str
    current: float | None
    historical_mean: float | None
    difference: float | None
    p05: float | None
    p95: float | None
    sample_count: int
    year_count: int
    samples: list[float]
    status: str
    unusual: bool = False
    reading_time: datetime


class WeatherComparison(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    location_key: str
    location_label: str
    latitude: float
    longitude: float
    conditions_time: datetime
    retrieved_at: datetime
    timezone: str
    current_source: str
    baseline_source: str | None
    baseline_retrieved_at: datetime | None
    baseline_period: str = '1991–2020'
    baseline_error: str | None = None
    metrics: list[WeatherMetric]

    @property
    def identity(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()

    def evidence(self) -> dict[str, float]:
        result = {}
        for metric in self.metrics:
            for name in ('current', 'historical_mean', 'difference', 'p05', 'p95'):
                value = getattr(metric, name)
                if value is not None:
                    result[f'{metric.variable}.{name}'] = value
                    if metric.variable == 'temperature':
                        result[f'temperature.{name}_fahrenheit'] = value * 1.8 + (0 if name == 'difference' else 32)
        return result


class PossibleCause(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    hypothesis: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(min_length=1, max_length=8)
    what_to_check: str = Field(min_length=1, max_length=700)


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    action_id: str
    why_it_helps: str = Field(min_length=1, max_length=800)


class WeatherExplanation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    summary: str = Field(min_length=1, max_length=1200)
    possible_causes: list[PossibleCause] = Field(min_length=1, max_length=3)
    actions: list[RecommendedAction] = Field(min_length=1, max_length=6)
    limitations: list[str] = Field(min_length=1, max_length=8)
