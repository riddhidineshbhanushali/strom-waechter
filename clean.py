"""
Data cleaning and harmonization module for Strom-Wächter.
Handles timezones, Daylight Saving Time (23h / 25h days), unit conversions,
and missing value imputation.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd


def raw_series_to_dataframe(
    raw_series: List[List[Any]],
    value_column: str
) -> pd.DataFrame:
    """
    Converts SMARD raw series [[epoch_ms, value], ...] into a pandas DataFrame.
    Filters out None/null values and handles duplicate timestamps.
    """
    if not raw_series:
        return pd.DataFrame(columns=["timestamp_utc", value_column])

    df = pd.DataFrame(raw_series, columns=["epoch_ms", value_column])
    # Coerce values to numeric; replace None with NaN
    df[value_column] = pd.to_numeric(df[value_column], errors="coerce")
    df = df.dropna(subset=["epoch_ms"])

    # Convert epoch milliseconds to UTC datetime
    df["timestamp_utc"] = pd.to_datetime(df["epoch_ms"], unit="ms", utc=True)
    df = df.drop(columns=["epoch_ms"])
    # Drop exact duplicate timestamps, keeping first
    df = df.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc")
    return df


def handle_dst_and_timezones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures continuous UTC hourly grid and generates ISO 8601 strings with Berlin offset.
    Properly handles 23-hour days (Spring DST transition) and 25-hour days (Fall DST transition)
    without dropping hours or creating index ambiguity.
    """
    if df.empty or "timestamp_utc" not in df.columns:
        return df

    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp_utc"]):
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    df = df.sort_values("timestamp_utc").drop_duplicates(subset=["timestamp_utc"])
    df = df.set_index("timestamp_utc")

    # Reindex to an unbroken hourly frequency in UTC
    full_idx = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq="1h",
        tz="UTC",
        name="timestamp_utc"
    )
    df = df.reindex(full_idx)

    # Convert UTC to Europe/Berlin timezone
    berlin_tz = df.index.tz_convert("Europe/Berlin")
    # Store formatted ISO-8601 strings with explicit offset (e.g. +01:00 or +02:00)
    df["timestamp_cet"] = berlin_tz.strftime("%Y-%m-%d %H:%M:%S%z")
    df["timestamp_cet_iso"] = berlin_tz.isoformat()
    df = df.reset_index()
    # Format UTC as string
    df["timestamp_utc"] = df["timestamp_utc"].dt.strftime("%Y-%m-%d %H:%M:%SZ")

    return df


def impute_missing_values(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """
    Handles missing values in time-series data:
    - Linear interpolation for isolated gaps (up to 3 consecutive hours)
    - Forward-fill followed by backward-fill for remaining edge cases
    """
    df = df.copy()
    for col in numeric_cols:
        if col in df.columns:
            # Interpolate short gaps linearly
            df[col] = df[col].interpolate(method="linear", limit=3)
            # Fill remaining with ffill and bfill
            df[col] = df[col].ffill().bfill()
    return df


def harmonize_market_data(
    price_df: pd.DataFrame,
    load_df: Optional[pd.DataFrame] = None,
    solar_df: Optional[pd.DataFrame] = None,
    wind_onshore_df: Optional[pd.DataFrame] = None,
    wind_offshore_df: Optional[pd.DataFrame] = None,
    residual_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Combines all distinct SMARD streams into a single cleaned, aligned DataFrame.
    Performs unit conversions (EUR/MWh -> ct/kWh) and computes renewable totals.
    """
    if price_df.empty:
        raise ValueError("Price dataframe cannot be empty")

    merged = price_df.copy()

    # Merge each auxiliary stream on timestamp_utc
    aux_frames = [
        ("load_df", load_df, "grid_load_mw"),
        ("solar_df", solar_df, "solar_mw"),
        ("wind_onshore_df", wind_onshore_df, "wind_onshore_mw"),
        ("wind_offshore_df", wind_offshore_df, "wind_offshore_mw"),
        ("residual_df", residual_df, "residual_load_mw")
    ]

    for name, f, col_name in aux_frames:
        if f is not None and not f.empty:
            merged = pd.merge(merged, f[["timestamp_utc", col_name]], on="timestamp_utc", how="left")
        else:
            merged[col_name] = np.nan

    # Clean and regularize timegrid
    merged = handle_dst_and_timezones(merged)

    # Numerical imputation
    data_cols = [
        "price_eur_mwh", "grid_load_mw", "solar_mw",
        "wind_onshore_mw", "wind_offshore_mw", "residual_load_mw"
    ]
    merged = impute_missing_values(merged, data_cols)

    # Calculate derivative columns
    merged["price_ct_kwh"] = (merged["price_eur_mwh"] * 0.1).round(4)

    merged["wind_onshore_mw"] = merged["wind_onshore_mw"].fillna(0.0).clip(lower=0.0)
    merged["wind_offshore_mw"] = merged["wind_offshore_mw"].fillna(0.0).clip(lower=0.0)
    merged["wind_total_mw"] = merged["wind_onshore_mw"] + merged["wind_offshore_mw"]
    merged["solar_mw"] = merged["solar_mw"].fillna(0.0).clip(lower=0.0)

    # Fill grid load if still missing based on residual load or standard profile
    if merged["grid_load_mw"].isna().any():
        mean_load = merged["grid_load_mw"].mean()
        if np.isnan(mean_load):
            mean_load = 55000.0  # German average grid load ~55 GW
        merged["grid_load_mw"] = merged["grid_load_mw"].fillna(mean_load)

    # Compute residual load: Load - (Wind + Solar)
    calc_residual = merged["grid_load_mw"] - (merged["wind_total_mw"] + merged["solar_mw"])
    merged["residual_load_mw"] = merged["residual_load_mw"].fillna(calc_residual)

    return merged
