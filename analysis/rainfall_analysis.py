"""Owner: Person 1. Complete-month totals and seasonally matched rain ranks."""
import numpy as np
import pandas as pd
from analysis.validation import validate_series
from analysis.anomaly_detection import calculate_anomaly


def rainfall_metrics(series, baseline_start='1982-01-01', baseline_end='2011-12-31', *, min_years=20):
    frame = validate_series(series)
    if (frame['value'].dropna() < 0).any():
        raise ValueError('Rainfall cannot be negative')
    # Explicit daily grid prevents windows from bridging absent dates.
    daily = frame.set_index('date').reindex(pd.date_range(frame['date'].min(), frame['date'].max(), name='date'))
    daily['rolling_7day_mm'] = daily['value'].rolling(7, min_periods=7).sum()
    start, end = pd.Timestamp(baseline_start), pd.Timestamp(baseline_end)
    if start > end:
        raise ValueError('Invalid baseline period')
    reference = daily.loc[start:end]
    daily['seasonal_percentile'] = np.nan
    for month in range(1, 13):
        pool = reference.loc[reference.index.month == month, 'rolling_7day_mm'].dropna()
        if pool.index.year.nunique() < min_years:
            continue
        target = (daily.index.month == month) & daily['rolling_7day_mm'].notna()
        daily.loc[target, 'seasonal_percentile'] = 100 * np.searchsorted(
            np.sort(pool.to_numpy()), daily.loc[target, 'rolling_7day_mm'], side='right'
        ) / len(pool)
    monthly = daily['value'].resample('MS').agg(['sum', 'count'])
    monthly['value'] = monthly['sum'].where(monthly['count'] == monthly.index.days_in_month)
    monthly = monthly[['value']].reset_index()
    baseline = monthly.loc[monthly['date'].between(start, end)]
    monthly = calculate_anomaly(monthly, baseline, min_years=min_years)
    monthly['baseline_period'] = f'{start.year}-{end.year}'
    monthly['unit'] = 'mm/month'
    for column in ['region', 'source', 'retrieved_at', 'measurement_kind']:
        if column in frame:
            monthly[column] = frame[column].iloc[-1]
    return daily.reset_index(), monthly


def detect_rainfall(series, *, percentile_threshold=95, min_years=20):
    """Return latest rain signal using same-month seven-day empirical percentile."""
    from schemas.anomaly import AnomalyRecord
    if not 0 < percentile_threshold <= 100:
        raise ValueError('Percentile threshold must be in (0, 100]')
    daily, _ = rainfall_metrics(series, min_years=min_years)
    row = daily.iloc[-1]
    if pd.isna(row['rolling_7day_mm']) or pd.isna(row['seasonal_percentile']):
        raise ValueError('Insufficient rainfall observations or baseline coverage')
    location = str(series['region'].iloc[-1])
    return AnomalyRecord(
        anomaly_id=f'{location.lower()}_rain_{row["date"]:%Y%m%d}',
        variable='Seven-day precipitation total', region=location,
        observation_date=row['date'].date(), value=float(row['rolling_7day_mm']),
        unit='mm/7 days', baseline_period='1982-2011', source=str(series['source'].iloc[-1]),
        detection_method=f'Same-calendar-month endpoint empirical percentile={row["seasonal_percentile"]:.2f}; threshold={percentile_threshold:g}; ERA5 reanalysis, not flood prediction',
        status='detected' if row['seasonal_percentile'] >= percentile_threshold else 'monitoring')
