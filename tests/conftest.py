"""Shared pytest fixtures. Owner: Person 3 (Product & Dashboard)."""

import pytest

import translator


# Raises NotImplementedError so a patched function behaves like an unbuilt stub.
def _not_implemented(*args, **kwargs):
    raise NotImplementedError


# Forces every workstream into stub mode so tests never call real APIs.
@pytest.fixture
def stubbed_backend(monkeypatch):
    monkeypatch.setattr(
        translator.anomaly_detection, "detect_anomalies", _not_implemented
    )
    monkeypatch.setattr(translator.climate_sources, "get_sst_series", _not_implemented)
    monkeypatch.setattr(translator.workflow, "run_investigation", _not_implemented)
    return monkeypatch
