"""Location-specific global climate monitoring, with a prior 30-year baseline."""
from dataclasses import dataclass
from datetime import date, timedelta
import pandas as pd
from analysis.anomaly_detection import calculate_anomaly
from data.locations import Location
from data.weather_sources import get_weather_history, SOURCE
from schemas.anomaly import AnomalyRecord


@dataclass
class LocationClimate:
    location: Location
    year: int
    daily: pd.DataFrame
    monthly: pd.DataFrame
    anomalies: list[AnomalyRecord]
    baseline_period: str


def analyze_location(location, year, *, threshold=2.0):
    if not isinstance(year, int) or not 1960 <= year <= date.today().year:
        raise ValueError('Choose an observation year from 1960 through the current year')
    if not 0 < threshold < float('inf'):
        raise ValueError('Threshold must be a finite positive z score')
    baseline_start, baseline_end = max(1940, year - 30), year - 1
    # ERA5 is published with a delay; allow a seven-day buffer for updates.
    end = min(date(year, 12, 31), date.today() - timedelta(days=7))
    if end.year < year:
        raise ValueError('Current-year observations are not available yet; choose the previous year')
    frame = get_weather_history(location, f'{baseline_start}-01-01', str(end))
    baseline_label = f'{baseline_start}-{baseline_end}'
    monthly_parts, records = [], []
    for variable, aggregation, unit in [('temperature', 'mean', 'degC'), ('precipitation', 'sum', 'mm/month')]:
        daily = frame.set_index('date')[variable]
        grouped = daily.resample('MS')
        monthly = getattr(grouped, aggregation)().where(grouped.count() == grouped.count().index.days_in_month)
        series = monthly.rename('value').reset_index()
        baseline = series.loc[series['date'].dt.year <= baseline_end]
        calculated = calculate_anomaly(series, baseline)
        selected = calculated.loc[calculated['date'].dt.year == year].copy()
        selected['variable'], selected['unit'] = variable, unit
        selected['baseline_period'], selected['source'] = baseline_label, SOURCE
        for column in ['region', 'country_code', 'latitude', 'longitude', 'grid_latitude', 'grid_longitude', 'timezone', 'retrieved_at', 'cache_stale', 'measurement_kind']:
            if column in frame:
                selected[column] = frame[column].iloc[-1]
        monthly_parts.append(selected)
        for _, row in selected.iterrows():
            if pd.isna(row['value']):
                continue  # Missing measurements are exposed in chart/table, never fabricated.
            z = row['z_score']
            status = 'inconclusive' if pd.isna(z) else ('detected' if abs(z) >= threshold else 'monitoring')
            records.append(AnomalyRecord(
                anomaly_id=f'loc_{location.key}_{variable}_{row["date"]:%Y%m}',
                variable='Monthly mean air temperature' if variable == 'temperature' else 'Monthly precipitation total',
                region=f'{location.label} ({location.latitude:.4f}, {location.longitude:.4f})',
                observation_date=row['date'].date(), value=float(row['value']), unit=unit,
                baseline_period=baseline_label, source=SOURCE,
                detection_method=f'Calendar-month baseline; anomaly={row["anomaly"]:.3f} {unit}; z={z:.3f}; |z|>={threshold:g}; n={int(row["baseline_count"])}; ERA5 reanalysis', status=status))
    return LocationClimate(location, year, frame.loc[frame['date'].dt.year == year].copy(), pd.concat(monthly_parts, ignore_index=True), records, baseline_label)
