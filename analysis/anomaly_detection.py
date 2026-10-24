"""Owner: Person 1. Deterministic monthly and published-index detection."""
import math
import pandas as pd
from analysis.validation import validate_series
from data.climate_sources import get_sst_series, REGIONS
from schemas.anomaly import AnomalyRecord


def calculate_anomaly(series, baseline, *, min_years=20):
    """Calendar-month baseline mean/sample SD; never use on published anomalies."""
    observations, reference = validate_series(series), validate_series(baseline)
    if reference.empty:
        raise ValueError('Empty baseline')
    if reference['date'].dt.to_period('M').duplicated().any():
        raise ValueError('Baseline must contain one measurement per month')
    grouped = reference.groupby(reference['date'].dt.month)['value']
    stats = grouped.agg(['mean', 'std', 'count'])
    months = observations['date'].dt.month
    observations['baseline_mean'] = months.map(stats['mean'])
    observations['baseline_std'] = months.map(stats['std'])
    observations['baseline_count'] = months.map(stats['count']).fillna(0)
    valid = observations['baseline_count'] >= min_years
    observations['anomaly'] = (observations['value'] - observations['baseline_mean']).where(valid)
    observations['z_score'] = (observations['anomaly'] / observations['baseline_std'].where(observations['baseline_std'] > 0)).where(valid)
    return observations


def detect_series(series, *, threshold=1.0, persistence=3):
    """Published SST departures: latest date only; gaps break persistence."""
    if not math.isfinite(threshold) or threshold <= 0 or persistence < 1:
        raise ValueError('Threshold and persistence must be positive')
    frame = validate_series(series)
    if frame.empty:
        raise ValueError('No SST observations')
    row = frame.iloc[-1]
    value = row['value']
    status = 'inconclusive' if pd.isna(value) else ('detected' if abs(value) >= threshold else 'monitoring')
    tail = frame.tail(persistence)
    continuous = len(tail) == persistence and tail['date'].dt.to_period('M').astype('int64').diff().dropna().eq(1).all()
    persistent = bool(continuous and tail['value'].notna().all() and ((tail['value'] >= threshold).all() or (tail['value'] <= -threshold).all()))
    label = str(row['region']).lower().replace(' ', '_').replace('+', '_').replace('.', '_')
    method = f'Published anomaly absolute threshold {threshold:g} degC; {persistence}-month same-sign persistence={persistent}; internal heuristic, not ENSO classification'
    if pd.isna(value):
        # The shared contract forbids NaN: no fabricated record can represent this.
        raise ValueError(f'Missing latest SST observation for {row["region"]}')
    if bool(row.get('cache_stale', False)):
        method += '; stale cached retrieval'
    return AnomalyRecord(anomaly_id=f'{label}_{row["date"]:%Y%m}', variable='Sea surface temperature anomaly', region=row['region'], observation_date=row['date'].date(), value=float(value), unit=row['unit'], baseline_period=row['baseline_period'], source=row['source'], detection_method=method, status=status)


def detect_anomalies() -> list[AnomalyRecord]:
    return [detect_series(get_sst_series(region)) for region in REGIONS]
