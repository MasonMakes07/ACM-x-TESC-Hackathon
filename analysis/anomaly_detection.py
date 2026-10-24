"""Detects unusual observations and packages them as AnomalyRecord objects.

Owner: Person 1 (Climate Intelligence).
CONTRACT: translator.py calls detect_anomalies(); keep its name and signature.
"""

from schemas.anomaly import AnomalyRecord


# Returns every anomaly currently detected by the climate pipeline.
def detect_anomalies() -> list[AnomalyRecord]:
    raise NotImplementedError("Person 1: implement anomaly detection.")
