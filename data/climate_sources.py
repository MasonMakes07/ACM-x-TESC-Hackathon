"""Retrieves NOAA sea-surface-temperature anomaly indices.

Owner: Person 1 (Climate Intelligence).
CONTRACT: translator.py calls get_sst_series(); keep its name and signature.
"""

import pandas as pd


# Returns the SST anomaly series for a region as a DataFrame with date and value.
def get_sst_series(region: str) -> pd.DataFrame:
    raise NotImplementedError("Person 1: implement NOAA SST retrieval.")
