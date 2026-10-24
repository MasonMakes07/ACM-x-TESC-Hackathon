"""Shared background NOAA/Grok refresh with incremental, persisted reviews.

No Streamlit calls run on worker threads. A dashboard poll requests a check every
30 minutes while open; unchanged source editions reuse their reviewed evidence.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock

from agents.global_hazards import review_hazards
from data.noaa_hazards import load_noaa_hazards
from schemas.global_hazards import HazardFeed, ReviewedEvent

CHECK_SECONDS = 1800
BATCH_SIZE = 12


def utcnow():
    return datetime.now(timezone.utc)


def grok_ready():
    # Import loads the repository's .env configuration without exposing its values.
    import config  # noqa: F401
    return bool(os.getenv('XAI_API_KEY', '').strip() and os.getenv('XAI_MODEL', '').strip())


class HazardMonitor:
    def __init__(self, *, loader=load_noaa_hazards, reviewer=review_hazards, cache_path=None, ready=grok_ready):
        self.loader, self.reviewer, self.ready = loader, reviewer, ready
        self.path = Path(cache_path) if cache_path else Path(os.getenv('EARTHWATCH_CACHE_DIR', '.cache/earthwatch')) / 'global-hazards-v1.json'
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='hazard-monitor')
        self.future = None
        self.feed = None
        self.reviews = {}
        self.logs = []
        self.error = None
        self.review_errors = {}
        self.last_checked = None
        self.last_attempt = None
        self._restore()

    def _restore(self):
        try:
            raw = json.loads(self.path.read_text())
            feed = HazardFeed.model_validate(raw['feed'])
            reviews = {key: ReviewedEvent.model_validate(value) for key, value in raw.get('reviews', {}).items()}
            self.feed = feed
            self.reviews = {key: item for key, item in reviews.items() if item.source_fingerprint == feed.fingerprint}
        except (OSError, ValueError, KeyError, TypeError):
            return

    def _save(self):
        with self.lock:
            if self.feed is None:
                return
            payload = {'feed': self.feed.model_dump(mode='json'),
                       'reviews': {key: value.model_dump(mode='json') for key, value in self.reviews.items()}}
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix('.tmp')
                temp.write_text(json.dumps(payload))
                temp.replace(self.path)
            except OSError:
                self._log('Storage', 'Could not save this update to disk; it remains available in memory.')

    def _log(self, agent, message):
        with self.lock:
            self.logs.append({'time': utcnow().isoformat(), 'agent': agent, 'message': message})
            self.logs = self.logs[-60:]

    def snapshot(self):
        with self.lock:
            return dict(feed=self.feed, reviews=dict(self.reviews), logs=list(self.logs), error=self.error,
                        review_errors=dict(self.review_errors), last_checked=self.last_checked,
                        last_attempt=self.last_attempt, running=self.future is not None and not self.future.done())

    def request_refresh(self, *, force=False):
        with self.lock:
            if self.future is not None and not self.future.done():
                return False
            if not force and self.last_attempt and (utcnow() - self.last_attempt).total_seconds() < CHECK_SECONDS:
                return False
            self.last_attempt = utcnow()
            self.future = self.executor.submit(self._refresh)
            return True

    def _refresh(self):
        self._log('NOAA feed', 'Checking the latest publication and all ten hazard layers.')
        try:
            feed = self.loader()
        except Exception as error:
            with self.lock:
                self.error = f'NOAA update failed ({type(error).__name__}). Last downloaded data, if present, are retained and may be outdated.'
            self._log('NOAA feed', self.error)
            return
        with self.lock:
            if self.feed is not None and feed.issued < self.feed.issued:
                self.error = 'NOAA returned an older edition. The newer cached edition was retained.'
                return
            self.feed = feed
            self.last_checked = utcnow()
            self.error = None
            self.review_errors = {}
            # Reviews are valid only for the exact geometry + discussion edition.
            valid_ids = {event.event_id for event in feed.events}
            self.reviews = {key: value for key, value in self.reviews.items()
                            if key in valid_ids and value.source_fingerprint == feed.fingerprint}
        self._save()
        self._log('NOAA feed', f'{len(feed.events)} source areas loaded from {len(feed.layers_loaded)}/10 layers.')
        if not self.ready():
            self._log('Grok bots', 'Grok is not configured. Source events remain available; add XAI_API_KEY and XAI_MODEL to enable reviews.')
            return
        # Expired events stay inspectable, but do not consume new model calls.
        pending = [event for event in feed.events if event.event_id not in self.reviews and event.valid_end >= utcnow().date()]
        # Large geographic regions first, then small boundary fragments, without hiding any.
        pending.sort(key=lambda e: (-max(max(p[1] for p in ring[0]) - min(p[1] for p in ring[0]) for ring in e.geometry.coordinates), e.week))
        batches = [pending[index:index+BATCH_SIZE] for index in range(0, len(pending), BATCH_SIZE)]
        if not batches:
            self._log('Grok bots', 'No new source evidence to review. Existing explanations are up to date for this edition.')
            return
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='grok-hazards') as pool:
            jobs = {pool.submit(self.reviewer, feed, batch, self._log): batch for batch in batches}
            for future in as_completed(jobs):
                batch = jobs[future]
                try:
                    reviewed = future.result()
                except Exception as error:
                    message = f'Grok review failed ({type(error).__name__}). Refresh to retry; NOAA source details are still available.'
                    with self.lock:
                        self.review_errors.update({event.event_id: message for event in batch})
                    self._log('Grok bots', message)
                else:
                    with self.lock:
                        self.reviews.update(reviewed)
                    self._save()
                    self._log('Grok Evidence Reviewer', f'{len(reviewed)} event explanations checked and published.')
        self._log('Monitor', 'Update finished. The next source check is due in 30 minutes while the globe is open.')

    def close(self):
        self.executor.shutdown(wait=True)
