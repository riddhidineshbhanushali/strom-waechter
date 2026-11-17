"""
Unit tests for feature engineering and data leakage prevention in Strom-Wächter.
"""

import pytest
import pandas as pd
import numpy as np

from features import (
    build_forecasting_features,
    is_german_public_holiday,
)


def test_is_german_public_holiday():
    """Verify holiday detection for major German holidays."""
    new_year = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")
    labor_day = pd.Timestamp("2026-05-01 08:00:00", tz="UTC")
    normal_day = pd.Timestamp("2026-06-15 14:00:00", tz="UTC")

    assert is_german_public_holiday(new_year) == 1
    assert is_german_public_holiday(labor_day) == 1
    assert is_german_public_holiday(normal_day) == 0


def test_no_future_leakage_in_lags():
    """
    Verify that price and generation lags are strictly lagged by >= 24 hours
    so day D+1 predictions never use information from day D+1 or future hours.
    """
    n_hours = 250
    dates = pd.date_range("2026-01-01", periods=n_hours, freq="1h", tz="UTC")
    prices = [10.0 + (i % 24) * 0.5 for i in range(n_hours)]
    
    df = pd.DataFrame({
        "timestamp_utc": [d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in dates],
        "price_ct_kwh": prices,
        "solar_mwh": [100.0] * n_hours,
        "wind_total_mwh": [200.0] * n_hours,
    })

    featured, feature_cols = build_forecasting_features(df, is_training=True)

    # For any row i, verify price_lag_24h equals the target from exactly 24 hours prior
    row_idx = 10  # after warm-up
    current_target = featured.loc[row_idx, "price_ct_kwh"]
    lag24 = featured.loc[row_idx, "price_lag_24h"]
    lag168 = featured.loc[row_idx, "price_lag_168h"]

    # Original index in df is row_idx + 168 (since 168 rows dropped for warm-up)
    orig_idx = row_idx + 168
    assert lag24 == df.loc[orig_idx - 24, "price_ct_kwh"]
    assert lag168 == df.loc[orig_idx - 168, "price_ct_kwh"]


def test_cyclical_hour_encoding():
    """Verify that hour 0 and hour 24 wrap around smoothly."""
    dates = pd.date_range("2026-01-01", periods=200, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "timestamp_utc": [d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in dates],
        "price_ct_kwh": [12.0] * 200,
    })
    featured, _ = build_forecasting_features(df, is_training=False)

    # Hour 0
    h0 = featured[featured["hour"] == 0].iloc[0]
    assert np.isclose(h0["hour_sin"], 0.0)
    assert np.isclose(h0["hour_cos"], 1.0)

    # Hour 6
    h6 = featured[featured["hour"] == 6].iloc[0]
    assert np.isclose(h6["hour_sin"], 1.0)
    assert np.isclose(h6["hour_cos"], 0.0, atol=1e-7)
