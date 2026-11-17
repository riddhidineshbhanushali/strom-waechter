"""
Data cleaning, validation, and harmonization module for Strom-Wächter.
Strictly handles UTC canonical timestamps, Europe/Berlin local time conversions,
23-hour (Spring forward) and 25-hour (Fall back) DST transitions, bounds validation,
and explicit missing-value handling without silently fabricating prices.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
import zoneinfo
import numpy as np
import pandas as pd

from config import TIMEZONE_BERLIN, TIMEZONE_UTC

BERLIN_TZ = zoneinfo.ZoneInfo(TIMEZONE_BERLIN)
UTC_TZ = zoneinfo.ZoneInfo(TIMEZONE_UTC)

# Physical and European market sanity boundaries
# EPEX SPOT technical price limits are -500 EUR/MWh (-50 ct/kWh) to +4000 EUR/MWh (+400 ct/kWh)
MIN_PRICE_EUR_MWH = -500.0
MAX_PRICE_EUR_MWH = 4000.0
MIN_PRICE_CT_KWH = MIN_PRICE_EUR_MWH / 10.0  # -50.0 ct/kWh
MAX_PRICE_CT_KWH = MAX_PRICE_EUR_MWH / 10.0  # +400.0 ct/kWh


def validate_and_clean_raw_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans raw fetched market observations:
    - Deduplicates timestamps.
    - Validates price and generation boundaries.
    - Ensures UTC timestamp ordering.
    """
    if df.empty:
        return df

    cleaned = df.copy()

    # Deduplicate by timestamp_utc, keeping latest observation
    cleaned = cleaned.drop_duplicates(subset=["timestamp_utc"], keep="last")

    # Validate price boundaries (log/clamp or set to NaN if corrupted)
    if "price_eur_mwh" in cleaned.columns:
        invalid_mask = (cleaned["price_eur_mwh"] < MIN_PRICE_EUR_MWH) | (
            cleaned["price_eur_mwh"] > MAX_PRICE_EUR_MWH
        )
        cleaned.loc[invalid_mask, "price_eur_mwh"] = np.nan

    # Calculate price in ct/kWh (1 EUR/MWh = 0.1 ct/kWh)
    if "price_eur_mwh" in cleaned.columns:
        cleaned["price_ct_kwh"] = cleaned["price_eur_mwh"].apply(
            lambda v: round(v * 0.1, 4) if pd.notnull(v) else np.nan
        )

    # Physical generation and load must be non-negative
    for col in ["solar_mwh", "wind_onshore_mwh", "wind_offshore_mwh", "wind_total_mwh", "load_mwh", "total_generation_mwh"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].apply(
                lambda v: max(0.0, float(v)) if pd.notnull(v) and not np.isnan(v) else np.nan
            )

    # Compute wind total if components exist
    if "wind_onshore_mwh" in cleaned.columns and "wind_offshore_mwh" in cleaned.columns:
        cleaned["wind_total_mwh"] = cleaned.apply(
            lambda r: (
                (r["wind_onshore_mwh"] or 0.0) + (r["wind_offshore_mwh"] or 0.0)
                if pd.notnull(r["wind_onshore_mwh"]) or pd.notnull(r["wind_offshore_mwh"])
                else np.nan
            ),
            axis=1,
        )

    # Sort strictly by timestamp
    cleaned = cleaned.sort_values("timestamp_utc").reset_index(drop=True)
    return cleaned


def add_berlin_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds timestamp_berlin column in ISO 8601 format with explicit timezone offset
    (e.g., 2026-10-25T02:00:00+02:00 vs 2026-10-25T02:00:00+01:00).
    Properly handles 23-hour and 25-hour DST transition days.
    """
    if df.empty or "timestamp_utc" not in df.columns:
        return df

    result = df.copy()
    berlin_times = []

    for ts_str in result["timestamp_utc"]:
        # Parse UTC string (handling both 'Z' and offset format)
        if isinstance(ts_str, str):
            dt_utc = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        elif isinstance(ts_str, pd.Timestamp):
            dt_utc = ts_str.to_pydatetime()
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        else:
            berlin_times.append("")
            continue

        dt_berlin = dt_utc.astimezone(BERLIN_TZ)
        berlin_times.append(dt_berlin.isoformat())

    result["timestamp_berlin"] = berlin_times
    return result


def detect_dst_transition_day(date_str: str) -> Tuple[bool, int]:
    """
    Checks if a given calendar date (YYYY-MM-DD) in Germany is a DST transition day.
    Returns (is_transition_day, hours_in_day):
    - Normal day: (False, 24)
    - Spring forward day (March): (True, 23)
    - Fall back day (October): (True, 25)
    """
    try:
        # Construct midnight at start and midnight at end in Berlin local time
        start_berlin = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BERLIN_TZ)
        next_day = start_berlin.date() + pd.Timedelta(days=1)
        end_berlin = datetime(next_day.year, next_day.month, next_day.day, tzinfo=BERLIN_TZ)
        hours = int((end_berlin.astimezone(timezone.utc) - start_berlin.astimezone(timezone.utc)).total_seconds() / 3600)
        return (hours != 24, hours)
    except Exception:
        return (False, 24)


def build_continuous_hourly_grid(
    df: pd.DataFrame,
    start_utc: Optional[str] = None,
    end_utc: Optional[str] = None,
) -> pd.DataFrame:
    """
    Constructs a regular, unbroken UTC hourly index between start and end.
    Missing intervals have NaN for prices and load without silently fabricating data.
    """
    if df.empty:
        return df

    data = df.copy()
    data["dt_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data = data.sort_values("dt_utc").drop_duplicates(subset=["dt_utc"]).set_index("dt_utc")

    min_ts = pd.to_datetime(start_utc, utc=True) if start_utc else data.index.min()
    max_ts = pd.to_datetime(end_utc, utc=True) if end_utc else data.index.max()

    full_grid = pd.date_range(start=min_ts, end=max_ts, freq="1h", tz="UTC", name="dt_utc")
    reindexed = data.reindex(full_grid)

    reindexed["timestamp_utc"] = [dt.strftime("%Y-%m-%dT%H:%M:%SZ") for dt in reindexed.index]
    reindexed = reindexed.reset_index(drop=True)
    reindexed = add_berlin_timestamps(reindexed)

    return reindexed


def calculate_data_quality_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates transparency metrics on coverage, missing data, and date range.
    """
    if df.empty:
        return {
            "total_observations": 0,
            "missing_prices_count": 0,
            "missing_prices_pct": 100.0,
            "min_date_utc": None,
            "max_date_utc": None,
        }

    total = len(df)
    missing_prices = df["price_ct_kwh"].isna().sum() if "price_ct_kwh" in df.columns else total
    missing_pct = round((missing_prices / total) * 100.0, 2) if total > 0 else 100.0

    return {
        "total_observations": total,
        "missing_prices_count": int(missing_prices),
        "missing_prices_pct": missing_pct,
        "min_date_utc": df["timestamp_utc"].min() if "timestamp_utc" in df.columns else None,
        "max_date_utc": df["timestamp_utc"].max() if "timestamp_utc" in df.columns else None,
    }
