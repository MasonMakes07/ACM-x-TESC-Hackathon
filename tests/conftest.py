"""Shared pytest fixtures. Owner: Person 3 (Product & Dashboard)."""

import pytest
import streamlit as st

import translator


# Raises NotImplementedError so a patched function behaves like an unbuilt stub.
def _not_implemented(*args, **kwargs):
    raise NotImplementedError


# Forces every workstream into stub mode so tests never call real APIs.
@pytest.fixture
def stubbed_backend(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(
        translator.anomaly_detection, "detect_anomalies", _not_implemented
    )
    monkeypatch.setattr(translator.climate_sources, "get_sst_series", _not_implemented)
    monkeypatch.setattr(translator.workflow, "run_investigation", _not_implemented)
    return monkeypatch


@pytest.fixture(autouse=True)
def isolate_global_hazard_monitor(monkeypatch):
    """App smoke tests never launch background NOAA or paid Grok requests."""
    from dashboard import global_hazards
    from agents.hazard_monitor import utcnow
    class IdleMonitor:
        def snapshot(self):
            return dict(feed=None, reviews={}, logs=[], error=None, review_errors={},
                        last_checked=None, last_attempt=utcnow(), running=False)
        def request_refresh(self, **kwargs):
            return False
    monkeypatch.setattr(global_hazards, 'get_hazard_monitor', lambda: IdleMonitor())
