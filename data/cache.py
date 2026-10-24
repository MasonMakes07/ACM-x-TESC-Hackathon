"""Owner: Person 1. Validated HTTP cache; stale data is explicitly labelled."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def fetch_text(url, params=None, *, max_age=86400, allow_stale=True):
    root = Path(os.environ.get('EARTHWATCH_CACHE_DIR', '.cache/earthwatch'))
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = root / (key + '.json')
    cached = None
    try:
        cached = json.loads(path.read_text(encoding='utf-8'))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached['retrieved_at'])).total_seconds()
        if age <= max_age:
            return cached['text'], cached['retrieved_at'], False
    except (OSError, ValueError, KeyError, TypeError):
        cached = None
    session = requests.Session()
    session.headers.update({'User-Agent': 'EarthWatch/0.1 (https://github.com/MasonMakes07/ACM-x-TESC-Hackathon)'})
    session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])))
    try:
        response = session.get(url, params=params, timeout=(10, 60))
        response.raise_for_status()
        stamp = datetime.now(timezone.utc).isoformat()
        payload = dict(text=response.text, retrieved_at=stamp)
        root.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(payload), encoding='utf-8')
        temp.replace(path)
        return response.text, stamp, False
    except requests.RequestException:
        if cached is None or not allow_stale:
            raise
        return cached['text'], cached['retrieved_at'], True
    finally:
        session.close()
