"""
Unit tests for data cleaning, timezone conversions, DST handling,
and boundary validations in Strom-Wächter.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import zoneinfo

from clean import (
    validate_and_clean_raw_records,
    add_berlin_timestamps,
    detect_dst_transition_day,
    build_continuous_hourly_grid,
    calculate_data_quality_metrics,
    MIN_PRICE_EUR_MWH,
    MAX_PRICE_EUR_MWH,
)


def test_unit_conversion_eur_mwh_to_ct_kwh():
    """Verify exact 10:1 ratio from EUR/MWh to ct/kWh."""
    raw = pd.DataFrame({
        "timestamp_utc": ["2026-11-17T00:00:00Z", "2026-11-17T01:00:00Z"],
        "price_eur_mwh": [142.50, -20.00],
    })
    cleaned = validate_and_clean_raw_records(raw)
    assert cleaned.loc[0, "price_ct_kwh"] == 14.25
    assert cleaned.loc[1, "price_ct_kwh"] == -2.00


def test_deduplication():
    """Verify duplicate timestamps are resolved cleanly."""
    raw = pd.DataFrame({
        "timestamp_utc": [
            "2026-11-17T00:00:00Z",
            "2026-11-17T00:00:00Z",
            "2026-11-17T01:00:00Z",
        ],
        "price_eur_mwh": [100.0, 105.0, 110.0],
    })
    cleaned = validate_and_clean_raw_records(raw)
    assert len(cleaned) == 2
    # Last duplicate is kept
    assert cleaned.loc[0, "price_eur_mwh"] == 105.0


def test_price_bounds_validation():
    """Verify prices outside EPEX technical boundaries are invalidated."""
    raw = pd.DataFrame({
        "timestamp_utc": [
            "2026-11-17T00:00:00Z",
            "2026-11-17T01:00:00Z",
            "2026-11-17T02:00:00Z",
        ],
        "price_eur_mwh": [-600.0, 100.0, 5000.0],
    })
    cleaned = validate_and_clean_raw_records(raw)
    assert np.isnan(cleaned.loc[0, "price_eur_mwh"])
    assert cleaned.loc[1, "price_eur_mwh"] == 100.0
    assert np.isnan(cleaned.loc[2, "price_eur_mwh"])


def test_generation_non_negative():
    """Verify solar and wind generation are clipped to non-negative values."""
    raw = pd.DataFrame({
        "timestamp_utc": ["2026-11-17T00:00:00Z"],
        "price_eur_mwh": [50.0],
        "solar_mwh": [-10.0],
        "wind_onshore_mwh": [150.0],
        "wind_offshore_mwh": [50.0],
    })
    cleaned = validate_and_clean_raw_records(raw)
    assert cleaned.loc[0, "solar_mwh"] == 0.0
    assert cleaned.loc[0, "wind_total_mwh"] == 200.0


def test_berlin_timezone_conversion():
    """Verify UTC timestamps convert to Europe/Berlin with correct daylight offset."""
    # Winter time (CET, UTC+1)
    df_winter = pd.DataFrame({
        "timestamp_utc": ["2026-01-15T12:00:00Z"],
    })
    res_winter = add_berlin_timestamps(df_winter)
    assert res_winter.loc[0, "timestamp_berlin"] == "2026-01-15T13:00:00+01:00"

    # Summer time (CEST, UTC+2)
    df_summer = pd.DataFrame({
        "timestamp_utc": ["2026-07-15T12:00:00Z"],
    })
    res_summer = add_berlin_timestamps(df_summer)
    assert res_summer.loc[0, "timestamp_berlin"] == "2026-07-15T14:00:00+02:00"


def test_dst_transition_detection():
    """Verify detection of 23-hour (Spring) and 25-hour (Fall) DST days."""
    # In 2026:
    # Spring DST transition in Europe: Sunday March 29, 2026 (23 hours)
    # Fall DST transition in Europe: Sunday October 25, 2026 (25 hours)
    is_spring, hours_spring = detect_dst_transition_day("2026-03-29")
    assert is_spring is True
    assert hours_spring == 23

    is_fall, hours_fall = detect_dst_transition_day("2026-10-25")
    assert is_fall is True
    assert hours_fall == 25

    # Normal day
    is_normal, hours_normal = detect_dst_transition_day("2026-05-15")
    assert is_normal is False
    assert hours_normal == 24


def test_build_continuous_hourly_grid_no_fabrication():
    """Verify grid reindexing fills gaps with NaN rather than inventing prices."""
    raw = pd.DataFrame({
        "timestamp_utc": [
            "2026-11-17T00:00:00Z",
            "2026-11-17T03:00:00Z",  # Gap at 01:00 and 02:00
        ],
        "price_eur_mwh": [50.0, 80.0],
        "price_ct_kwh": [5.0, 8.0],
    })
    grid = build_continuous_hourly_grid(
        raw,
        start_utc="2026-11-17T00:00:00Z",
        end_utc="2026-11-17T03:00:00Z",
    )
    assert len(grid) == 4
    # Gaps must remain NaN
    assert pd.isna(grid.loc[1, "price_ct_kwh"])
    assert pd.isna(grid.loc[2, "price_ct_kwh"])
    assert grid.loc[3, "price_ct_kwh"] == 8.0


def test_quality_metrics():
    """Verify calculation of missing data percentage."""
    df = pd.DataFrame({
        "timestamp_utc": ["2026-11-17T00:00:00Z", "2026-11-17T01:00:00Z"],
        "price_ct_kwh": [10.0, np.nan],
    })
    metrics = calculate_data_quality_metrics(df)
    assert metrics["total_observations"] == 2
    assert metrics["missing_prices_count"] == 1
    assert metrics["missing_prices_pct"] == 50.0
