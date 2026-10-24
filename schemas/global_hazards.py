"""Source-owned hazard geometry and separately attributed Grok explanations."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HazardCode = Literal['TC', 'WET', 'DRY', 'WARM', 'COLD']
HAZARD_NAMES = {
    'TC': 'Tropical cyclone formation', 'WET': 'Above-median rainfall',
    'DRY': 'Below-median rainfall', 'WARM': 'Above-normal temperature',
    'COLD': 'Below-normal temperature',
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)


class HazardGeometry(StrictModel):
    type: Literal['MultiPolygon'] = 'MultiPolygon'
    # polygon -> rings (outer, then holes) -> [longitude, latitude]
    coordinates: list[list[list[tuple[float, float]]]]

    @model_validator(mode='after')
    def valid_rings(self):
        if not self.coordinates:
            raise ValueError('A hazard needs source geometry.')
        for polygon in self.coordinates:
            if not polygon:
                raise ValueError('Missing outer boundary.')
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError('A source polygon ring must be closed.')
                if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in ring):
                    raise ValueError('Invalid geographic coordinate.')
        return self


class HazardEvent(StrictModel):
    event_id: str
    hazard: HazardCode
    week: Literal[2, 3]
    probability: int
    issued: date
    valid_start: date
    valid_end: date
    source_url: str
    source_feature: str
    geometry: HazardGeometry
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @model_validator(mode='after')
    def dates_and_probability(self):
        allowed = (20, 40, 60) if self.hazard == 'TC' else (50, 65, 80)
        if self.probability not in allowed:
            raise ValueError('Unknown NOAA probability contour.')
        if not self.issued <= self.valid_start <= self.valid_end:
            raise ValueError('Inconsistent outlook dates.')
        return self

    @property
    def coordinate_label(self):
        return f'{abs(self.latitude):.1f}°{"N" if self.latitude >= 0 else "S"}, {abs(self.longitude):.1f}°{"E" if self.longitude >= 0 else "W"}'

    def evidence(self):
        return {key: value for key, value in self.model_dump(mode='json').items() if key != 'geometry'}


class HazardFeed(StrictModel):
    issued: date
    retrieved_at: datetime
    discussion: str
    source_url: str
    events: list[HazardEvent]
    layers_loaded: list[str]
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str


class EventExplanation(StrictModel):
    event_id: str
    area_name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    possible_drivers: str = Field(min_length=1, max_length=650)
    watch_for: str = Field(min_length=1, max_length=400)
    uncertainty: str = Field(min_length=1, max_length=400)
    evidence_refs: list[str] = Field(min_length=1, max_length=2)


class HazardReview(StrictModel):
    events: list[EventExplanation] = Field(min_length=1, max_length=12)


class ReviewedEvent(StrictModel):
    explanation: EventExplanation
    reviewed_at: datetime
    source_fingerprint: str
    model: str
