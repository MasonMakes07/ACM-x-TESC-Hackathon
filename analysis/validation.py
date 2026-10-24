"""Owner: Person 1. Common observation validation; missing values stay missing."""
import numpy as np
import pandas as pd


def validate_series(frame):
    if not isinstance(frame, pd.DataFrame) or not {'date', 'value'} <= set(frame):
        raise ValueError('Expected date and value columns')
    result = frame.copy()
    result['date'] = pd.to_datetime(result['date'], errors='raise')
    if result['date'].isna().any() or result['date'].duplicated().any():
        raise ValueError('Dates must be present and unique')
    result['value'] = pd.to_numeric(result['value'], errors='raise')
    if np.isinf(result['value'].to_numpy(dtype=float)).any():
        raise ValueError('Infinite measurements are invalid')
    return result.sort_values('date').reset_index(drop=True)
