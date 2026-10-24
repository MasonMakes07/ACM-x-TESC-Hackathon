"""Contract tests: sample data must match the shared schemas.

Owner: whole team. If these fail, someone changed schemas/ or sample_data/ alone.
"""

import json
import math
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from schemas.anomaly import SERIES_COLUMNS, AnomalyRecord
from schemas.assessment import Assessment

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


# Loads one JSON file from sample_data/.
def load_sample(file_name: str):
    return json.loads((SAMPLE_DIR / file_name).read_text(encoding="utf-8"))


VALID_ANOMALY = load_sample("anomalies.json")[0]
VALID_ASSESSMENT = load_sample("assessment.json")


# Checks every sample anomaly matches the AnomalyRecord schema.
def test_sample_anomalies_match_schema():
    records = load_sample("anomalies.json")
    assert records
    for record in records:
        AnomalyRecord.model_validate(record)


# Checks the sample assessment matches the Assessment schema.
def test_sample_assessment_matches_schema():
    Assessment.model_validate(VALID_ASSESSMENT)


# Checks the sample series has the columns the translator requires.
def test_sample_series_has_required_columns():
    series = pd.read_csv(SAMPLE_DIR / "sst_series.csv")
    assert set(SERIES_COLUMNS) <= set(series.columns)
    assert not series.empty


# Checks AnomalyRecord rejects bad ids, non-finite values and unknown statuses.
@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("anomaly_id", "x'; DROP TABLE anomalies;--"),
        ("anomaly_id", "<script>alert(1)</script>"),
        ("anomaly_id", ""),
        ("anomaly_id", "a" * 65),
        ("value", math.nan),
        ("value", math.inf),
        ("status", "panic"),
        ("unit", ""),
        ("observation_date", "not-a-date"),
    ],
)
def test_anomaly_rejects_invalid_values(field_name, bad_value):
    with pytest.raises(ValidationError):
        AnomalyRecord.model_validate({**VALID_ANOMALY, field_name: bad_value})


# Checks AnomalyRecord rejects fields that are not in the contract.
def test_anomaly_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AnomalyRecord.model_validate({**VALID_ANOMALY, "surprise": 1})


# Checks AnomalyRecord rejects records with a required field missing.
def test_anomaly_rejects_missing_fields():
    incomplete = {key: value for key, value in VALID_ANOMALY.items() if key != "unit"}
    with pytest.raises(ValidationError):
        AnomalyRecord.model_validate(incomplete)


# Checks Assessment rejects confidence levels outside the agreed set.
def test_assessment_rejects_unknown_confidence():
    with pytest.raises(ValidationError):
        Assessment.model_validate({**VALID_ASSESSMENT, "confidence": "certain"})


# Checks Assessment rejects evidence with an unknown evidence type.
def test_assessment_rejects_unknown_evidence_type():
    bad_evidence = [{**VALID_ASSESSMENT["evidence"][0], "evidence_type": "vibes"}]
    with pytest.raises(ValidationError):
        Assessment.model_validate({**VALID_ASSESSMENT, "evidence": bad_evidence})
