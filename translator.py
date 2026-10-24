"""Translator: the only bridge between the Streamlit dashboard and the backend.

Owner: Person 3 (Product & Dashboard). The dashboard calls only these functions.
Each one validates its input, calls the owning workstream, validates the output
against schemas/, and falls back to clearly labelled sample data while that
workstream still raises NotImplementedError. Real failures become TranslatorError
so the UI can show a message instead of crashing.
"""

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

import pandas as pd
from pydantic import BaseModel, ValidationError

from agents import workflow
from analysis import anomaly_detection
from data import climate_sources
from schemas.anomaly import SERIES_COLUMNS, AnomalyRecord
from schemas.assessment import Assessment, ProgressEvent
from schemas.errors import TranslatorError

logger = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).parent / "sample_data"
ANOMALY_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
REGION_PATTERN = re.compile(r"^[\w +.,()\-]{1,100}$", re.UNICODE)

ModelT = TypeVar("ModelT", bound=BaseModel)


# Validates a payload against a schema, turning failures into a TranslatorError.
def _validate(schema: type[ModelT], payload: object, label: str) -> ModelT:
    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        logger.exception("%s failed schema validation", label)
        raise TranslatorError(f"{label} did not match the shared schema.") from error


# Loads the sample anomaly records used until Person 1's pipeline exists.
def _load_sample_anomalies() -> list[AnomalyRecord]:
    raw_records = json.loads(
        (SAMPLE_DIR / "anomalies.json").read_text(encoding="utf-8")
    )
    return [AnomalyRecord.model_validate(record) for record in raw_records]


# Loads the sample assessment used until Person 2's workflow exists.
def _load_sample_assessment(anomaly_id: str) -> Assessment:
    raw_assessment = json.loads(
        (SAMPLE_DIR / "assessment.json").read_text(encoding="utf-8")
    )
    sample = Assessment.model_validate(raw_assessment)
    return sample.model_copy(update={"anomaly_id": anomaly_id})


# Returns detected anomalies and whether they came from sample data.
def load_anomalies() -> tuple[list[AnomalyRecord], bool]:
    try:
        raw_anomalies = anomaly_detection.detect_anomalies()
    except NotImplementedError:
        return _load_sample_anomalies(), True
    except Exception as error:
        logger.exception("detect_anomalies() failed")
        raise TranslatorError(
            "The climate pipeline failed to load anomalies."
        ) from error
    if not isinstance(raw_anomalies, list):
        raise TranslatorError("The climate pipeline did not return a list.")
    anomalies = [_validate(AnomalyRecord, item, "Anomaly") for item in raw_anomalies]
    return anomalies, False


# Returns a region's observation series (date, value) and whether it is sample data.
def load_observation_series(region: str) -> tuple[pd.DataFrame, bool]:
    if not isinstance(region, str) or not region.strip() or not REGION_PATTERN.fullmatch(region):
        raise TranslatorError(f"Unsupported region: {region!r}.")
    is_mock = False
    try:
        series = climate_sources.get_sst_series(region)
    except NotImplementedError:
        if region not in {item.region for item in _load_sample_anomalies()}:
            raise TranslatorError(f"No observations have been supplied for {region}.")
        series = pd.read_csv(SAMPLE_DIR / "sst_series.csv")
        is_mock = True
    except Exception as error:
        logger.exception("get_sst_series(%r) failed", region)
        raise TranslatorError(f"Could not load observations for {region}.") from error
    if not isinstance(series, pd.DataFrame) or not set(SERIES_COLUMNS) <= set(
        series.columns
    ):
        raise TranslatorError(f"Series must be a DataFrame with {SERIES_COLUMNS}.")
    tidy_series = series.loc[:, list(SERIES_COLUMNS)].copy()
    tidy_series["date"] = pd.to_datetime(tidy_series["date"], errors="coerce")
    tidy_series["value"] = pd.to_numeric(tidy_series["value"], errors="coerce")
    tidy_series = tidy_series.dropna(subset=["date"]).sort_values("date")
    return tidy_series.reset_index(drop=True), is_mock


# Runs an investigation for one anomaly; returns the assessment and a mock flag.
def investigate_anomaly(
    anomaly_id: str, on_progress: Callable[[ProgressEvent], None]
) -> tuple[Assessment, bool]:
    if not isinstance(anomaly_id, str) or not ANOMALY_ID_PATTERN.fullmatch(
        anomaly_id
    ):
        raise TranslatorError("Invalid anomaly id.")
    anomalies, _ = load_anomalies()
    anomaly = next(
        (item for item in anomalies if item.anomaly_id == anomaly_id), None
    )
    if anomaly is None:
        raise TranslatorError(f"Unknown anomaly id: {anomaly_id}.")
    try:
        raw_assessment = workflow.run_investigation(anomaly, on_progress)
    except NotImplementedError:
        on_progress(
            ProgressEvent(
                timestamp=datetime.now(timezone.utc),
                agent="Sample mode",
                message="Agent workflow not implemented; showing sample assessment.",
            )
        )
        return _load_sample_assessment(anomaly_id), True
    except Exception as error:
        logger.exception("run_investigation(%s) failed", anomaly_id)
        raise TranslatorError("The investigation failed to complete.") from error
    assessment = _validate(Assessment, raw_assessment, "Assessment")
    if assessment.anomaly_id != anomaly_id:
        raise TranslatorError("Assessment returned for the wrong anomaly.")
    return assessment, False
