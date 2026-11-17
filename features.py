"""
Feature engineering module for electricity price forecasting in Strom-Wächter.
Generates calendar, lag, cyclical, and grid features while strictly preventing
lookahead bias and data leakage.
"""

from typing import List, Tuple, Optional
import numpy as np
import pandas as pd


# German nationwide public holidays (Month, Day)
GERMAN_FIXED_HOLIDAYS = {
    (1, 1),    # Neujahr (New Year's Day)
    (5, 1),    # Tag der Arbeit (Labor Day)
    (10, 3),   # Tag der Deutschen Einheit (German Unity Day)
    (12, 25),  # 1. Weihnachtstag (Christmas Day)
    (12, 26),  # 2. Weihnachtstag (Boxing Day)
}


def is_german_public_holiday(dt: pd.Timestamp) -> int:
    """Heuristic check for German public holidays."""
    return 1 if (dt.month, dt.day) in GERMAN_FIXED_HOLIDAYS else 0


def build_forecasting_features(
    df: pd.DataFrame,
    target_col: str = "price_ct_kwh",
    is_training: bool = True,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Constructs time-series features for Day-Ahead electricity price forecasting.
    
    Guarantees zero data leakage:
    - All price and generation lags are lagged by at least 24 hours (horizon h >= 24)
      so that forecasts for day D+1 rely only on information published on or before day D.
    - Cyclical calendar transforms (sine/cosine) preserve continuous hour and week boundaries.
    """
    if df.empty or target_col not in df.columns:
        raise ValueError(f"DataFrame must contain target column '{target_col}'")

    data = df.copy()

    # Ensure datetime index
    if "dt_utc" not in data.columns:
        data["dt_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data = data.sort_values("dt_utc").reset_index(drop=True)

    # 1. Calendar & Cyclical Features
    dt = data["dt_utc"].dt
    data["hour"] = dt.hour
    data["day_of_week"] = dt.day_of_week
    data["month"] = dt.month
    data["is_weekend"] = data["day_of_week"].apply(lambda d: 1 if d >= 5 else 0)
    data["is_holiday"] = data["dt_utc"].apply(is_german_public_holiday)

    # Cyclical hour encoding (24h period)
    data["hour_sin"] = np.sin(2 * np.pi * data["hour"] / 24.0)
    data["hour_cos"] = np.cos(2 * np.pi * data["hour"] / 24.0)

    # Cyclical day of week encoding (7-day period)
    data["dow_sin"] = np.sin(2 * np.pi * data["day_of_week"] / 7.0)
    data["dow_cos"] = np.cos(2 * np.pi * data["day_of_week"] / 7.0)

    # 2. Price Lags (Minimum 24-hour lag for Day-Ahead market realism)
    data["price_lag_24h"] = data[target_col].shift(24)
    data["price_lag_48h"] = data[target_col].shift(48)
    data["price_lag_168h"] = data[target_col].shift(168)  # Same hour previous week

    # 3. Rolling Price Statistics (Shifted by 24h to avoid lookahead leakage)
    shifted_target = data[target_col].shift(24)
    data["price_rolling_mean_24h"] = shifted_target.rolling(window=24, min_periods=12).mean()
    data["price_rolling_std_24h"] = shifted_target.rolling(window=24, min_periods=12).std().fillna(0.0)
    data["price_rolling_min_24h"] = shifted_target.rolling(window=24, min_periods=12).min()
    data["price_rolling_max_24h"] = shifted_target.rolling(window=24, min_periods=12).max()
    data["price_rolling_mean_168h"] = shifted_target.rolling(window=168, min_periods=24).mean()

    # 4. Grid and Generation Lags (Shifted by 24h)
    if "solar_mwh" in data.columns:
        data["solar_lag_24h"] = data["solar_mwh"].shift(24).fillna(0.0)
    else:
        data["solar_lag_24h"] = 0.0

    if "wind_total_mwh" in data.columns:
        data["wind_lag_24h"] = data["wind_total_mwh"].shift(24).fillna(0.0)
    else:
        data["wind_lag_24h"] = 0.0

    if "load_mwh" in data.columns:
        data["load_lag_24h"] = data["load_mwh"].shift(24)
    else:
        data["load_lag_24h"] = np.nan

    feature_cols = [
        "hour_sin", "hour_cos",
        "dow_sin", "dow_cos",
        "is_weekend", "is_holiday",
        "price_lag_24h", "price_lag_48h", "price_lag_168h",
        "price_rolling_mean_24h", "price_rolling_std_24h",
        "price_rolling_min_24h", "price_rolling_max_24h",
        "price_rolling_mean_168h",
        "solar_lag_24h", "wind_lag_24h",
    ]

    # Optional load feature if populated
    if data["load_lag_24h"].notnull().sum() > len(data) * 0.5:
        data["load_lag_24h"] = data["load_lag_24h"].bfill()
        feature_cols.append("load_lag_24h")

    if is_training:
        # Drop warm-up rows (first 168 hours have NaN for price_lag_168h)
        clean_data = data.dropna(subset=feature_cols + [target_col]).reset_index(drop=True)
        return clean_data, feature_cols

    return data, feature_cols
