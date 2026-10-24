"""Runs the Investigator -> Regional Impact -> Skeptic -> Briefing pipeline.

Owner: Person 2 (Grok Agent Intelligence).
CONTRACT: translator.py calls run_investigation(); keep its name and signature.
Call on_progress(ProgressEvent(...)) at each real step so the dashboard can show it.
"""

from collections.abc import Callable

from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, ProgressEvent

ProgressCallback = Callable[[ProgressEvent], None]


# Investigates one anomaly end to end and returns a validated Assessment.
def run_investigation(
    anomaly: AnomalyRecord, on_progress: ProgressCallback
) -> Assessment:
    raise NotImplementedError("Person 2: implement the agent workflow.")
