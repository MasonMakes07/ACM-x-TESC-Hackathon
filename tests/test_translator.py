"""Translator tests: bad backend output must become TranslatorError, never a crash.

Owner: Person 3 (Product & Dashboard).
"""

import pandas as pd
import pytest

import translator
from schemas.errors import TranslatorError

pytestmark = pytest.mark.usefixtures("stubbed_backend")

SAMPLE_ID = "sample_nino12_001"


# Raises a generic runtime error to simulate a crashing workstream.
def _crash(*args, **kwargs):
    raise RuntimeError("boom")


# Checks anomalies fall back to sample data while Person 1's code is a stub.
def test_load_anomalies_uses_sample_when_stubbed():
    anomalies, is_sample = translator.load_anomalies()
    assert is_sample
    assert anomalies


# Checks valid dicts from the pipeline are converted into AnomalyRecords.
def test_load_anomalies_accepts_valid_dicts(stubbed_backend):
    sample_records = [item.model_dump() for item in translator._load_sample_anomalies()]
    stubbed_backend.setattr(
        translator.anomaly_detection, "detect_anomalies", lambda: sample_records
    )
    anomalies, is_sample = translator.load_anomalies()
    assert not is_sample
    assert anomalies[0].anomaly_id == SAMPLE_ID


# Checks pipeline crashes, bad records and wrong types all become TranslatorError.
@pytest.mark.parametrize(
    "fake_pipeline",
    [_crash, lambda: [{"anomaly_id": "x"}], lambda: "not a list", lambda: None],
)
def test_load_anomalies_rejects_bad_pipeline_output(stubbed_backend, fake_pipeline):
    stubbed_backend.setattr(
        translator.anomaly_detection, "detect_anomalies", fake_pipeline
    )
    with pytest.raises(TranslatorError):
        translator.load_anomalies()


# Checks the observation series falls back to sample data while stubbed.
def test_load_series_uses_sample_when_stubbed():
    series, is_sample = translator.load_observation_series("Nino 1+2")
    assert is_sample
    assert list(series.columns) == ["date", "value"]
    assert series["date"].is_monotonic_increasing


# Checks regions outside the allow-list are rejected before any backend call.
@pytest.mark.parametrize("region", ["Atlantic", "", "Nino 1+2; rm -rf /", None])
def test_load_series_rejects_unknown_region(region):
    with pytest.raises(TranslatorError):
        translator.load_observation_series(region)


# Checks bad series output from the pipeline becomes TranslatorError.
@pytest.mark.parametrize(
    "fake_series",
    [_crash, lambda region: pd.DataFrame({"when": [1]}), lambda region: [1, 2]],
)
def test_load_series_rejects_bad_pipeline_output(stubbed_backend, fake_series):
    stubbed_backend.setattr(translator.climate_sources, "get_sst_series", fake_series)
    with pytest.raises(TranslatorError):
        translator.load_observation_series("Nino 1+2")


# Checks unparseable dates are dropped and rows come back sorted by date.
def test_load_series_cleans_and_sorts(stubbed_backend):
    messy_series = pd.DataFrame(
        {"date": ["2023-02-01", "garbage", "2023-01-01"], "value": ["2", "3", "x"]}
    )
    stubbed_backend.setattr(
        translator.climate_sources, "get_sst_series", lambda region: messy_series
    )
    series, is_sample = translator.load_observation_series("Nino 3.4")
    assert not is_sample
    assert len(series) == 2
    assert series["date"].is_monotonic_increasing
    assert series["value"].isna().sum() == 1


# Checks malformed or code-like anomaly ids are rejected.
@pytest.mark.parametrize(
    "anomaly_id", ["", "../etc/passwd", "<script>", "UPPER", "a" * 65, 123, None]
)
def test_investigate_rejects_invalid_ids(anomaly_id):
    with pytest.raises(TranslatorError):
        translator.investigate_anomaly(anomaly_id, lambda event: None)


# Checks an id that is well-formed but not detected is rejected.
def test_investigate_rejects_unknown_id():
    with pytest.raises(TranslatorError):
        translator.investigate_anomaly("does_not_exist", lambda event: None)


# Checks the stubbed workflow returns a labelled sample and one progress event.
def test_investigate_uses_sample_when_stubbed():
    progress_events = []
    assessment, is_sample = translator.investigate_anomaly(
        SAMPLE_ID, progress_events.append
    )
    assert is_sample
    assert assessment.anomaly_id == SAMPLE_ID
    assert len(progress_events) == 1


# Checks a valid workflow result is returned and not marked as sample.
def test_investigate_accepts_valid_assessment(stubbed_backend):
    real_result = translator._load_sample_assessment(SAMPLE_ID).model_dump()
    stubbed_backend.setattr(
        translator.workflow, "run_investigation", lambda anomaly, report: real_result
    )
    assessment, is_sample = translator.investigate_anomaly(
        SAMPLE_ID, lambda event: None
    )
    assert not is_sample
    assert assessment.anomaly_id == SAMPLE_ID


# Checks workflow crashes, invalid output and wrong-anomaly results are rejected.
@pytest.mark.parametrize(
    "fake_workflow",
    [
        _crash,
        lambda anomaly, report: {"summary": "missing fields"},
        lambda anomaly, report: translator._load_sample_assessment("other_id"),
    ],
)
def test_investigate_rejects_bad_workflow_output(stubbed_backend, fake_workflow):
    stubbed_backend.setattr(translator.workflow, "run_investigation", fake_workflow)
    with pytest.raises(TranslatorError):
        translator.investigate_anomaly(SAMPLE_ID, lambda event: None)


# Worldwide region names reach the climate source when real observations are available.
@pytest.mark.parametrize('region', ['Indian Ocean', 'Mediterranean', 'São Paulo'])
def test_load_series_accepts_worldwide_regions(stubbed_backend, region):
    calls = []
    series = pd.DataFrame({'date': ['2023-06-01'], 'value': [1.2]})

    # Records which global region was requested without making any API call.
    def source(selected_region):
        calls.append(selected_region)
        return series

    stubbed_backend.setattr(translator.climate_sources, 'get_sst_series', source)
    result, is_sample = translator.load_observation_series(region)
    assert calls == [region]
    assert not is_sample
    assert result['value'].iloc[0] == 1.2


# Sample Pacific measurements must not be silently reused for another part of the world.
def test_unbuilt_global_source_does_not_relabel_pacific_sample():
    with pytest.raises(TranslatorError, match='No observations have been supplied'):
        translator.load_observation_series('Indian Ocean')


# Checks a Grok service failure tells the user why, without hiding it behind a generic message.
def test_investigation_failure_explains_grok_refusal(stubbed_backend):
    from agents.agent_errors import GrokError

    def refuse(*args, **kwargs):
        raise GrokError("Grok API returned HTTP 403: team has no credits")

    stubbed_backend.setattr(translator.workflow, "run_investigation", refuse)
    anomaly_id = translator.load_anomalies()[0][0].anomaly_id
    with pytest.raises(TranslatorError, match="no credits"):
        translator.investigate_anomaly(anomaly_id, lambda event: None)


# Checks a missing API key is reported by name instead of as a generic failure.
def test_investigation_failure_reports_missing_key(stubbed_backend):
    def missing(*args, **kwargs):
        raise RuntimeError("Missing XAI_API_KEY. Copy .env.example to .env and set it.")

    stubbed_backend.setattr(translator.workflow, "run_investigation", missing)
    anomaly_id = translator.load_anomalies()[0][0].anomaly_id
    with pytest.raises(TranslatorError, match="XAI_API_KEY"):
        translator.investigate_anomaly(anomaly_id, lambda event: None)
