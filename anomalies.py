"""
Anomaly Detection module for Strom-Wächter.
Detects negative prices, extreme spikes, and sudden hourly rate-of-change jumps
using robust statistics (Rolling Median, Median Absolute Deviation).
Correlates anomalies with wind, solar, and grid load to generate plain-language explanations.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from config import ANOMALY_ZSCORE_THRESHOLD, ANOMALY_SPIKE_RATE_THRESHOLD_CT
from db import save_anomalies


def calculate_robust_z_scores(series: pd.Series, window: int = 168) -> pd.Series:
    """
    Computes robust rolling z-scores using Median and Median Absolute Deviation (MAD):
    Robust Z = (x - median) / (1.4826 * MAD)
    Unlike standard deviation, MAD is not distorted by extreme outliers.
    """
    rolling_median = series.rolling(window=window, min_periods=24).median()
    rolling_mad = (series - rolling_median).abs().rolling(window=window, min_periods=24).median()
    # Avoid division by zero
    mad_scaled = (1.4826 * rolling_mad).replace(0, np.nan).fillna(1.0)
    return (series - rolling_median) / mad_scaled


def explain_anomaly(
    price_ct: float,
    anomaly_type: str,
    z_score: float,
    wind_mw: Optional[float],
    solar_mw: Optional[float],
    load_mw: Optional[float],
    hour: int,
    is_weekend: bool,
) -> str:
    """
    Generates plain-language contextual explanations of observed contributing factors.
    Carefully uses cautious phrasing ('may have contributed' / 'coincided with')
    rather than claiming unproven direct causation.
    """
    parts = []

    if anomaly_type == "negative_price":
        parts.append(
            f"Electricity prices dropped below zero to {price_ct:.2f} ct/kWh."
        )
        renewables = []
        if wind_mw and wind_mw > 15000:
            renewables.append(f"high wind generation ({wind_mw:,.0f} MW)")
        if solar_mw and solar_mw > 12000:
            renewables.append(f"strong solar feed-in ({solar_mw:,.0f} MW)")

        if renewables:
            feedin_str = " alongside ".join(renewables)
            load_context = "low weekend grid demand" if is_weekend else "moderate grid demand"
            parts.append(
                f"This coincided with {feedin_str} during {load_context}. "
                "Inflexible generation baseloads combined with surplus renewable supply "
                "may have driven wholesale prices into negative territory."
            )
        else:
            parts.append(
                "Excess supply relative to available grid transmission and consumer load "
                "was observed during this clearing interval."
            )

    elif anomaly_type == "extreme_high":
        parts.append(
            f"Electricity price spiked to an unusually high {price_ct:.2f} ct/kWh "
            f"(robust deviation score: +{abs(z_score):.1f})."
        )
        if wind_mw is not None and wind_mw < 5000 and (solar_mw is None or solar_mw < 3000):
            parts.append(
                "Low renewable generation (a 'Dunkelflaute' condition) occurred concurrently, "
                "requiring more expensive fossil and gas peaking plants to clear the market."
            )
        elif load_mw and load_mw > 65000:
            parts.append(
                f"High peak system demand ({load_mw:,.0f} MW) coincided with this interval, "
                "activating marginal power plants with higher operational costs."
            )
        else:
            parts.append(
                "High fuel/gas generation costs or cross-border export demand may have contributed."
            )

    elif anomaly_type == "sudden_jump":
        parts.append(
            f"A rapid hourly price shift of {abs(z_score):.1f} ct/kWh occurred within 60 minutes."
        )
        parts.append(
            "Rapid demand transitions or sudden shifts in solar/wind generation frequently cause "
            "short-term ramp-rate price rebalancing."
        )

    return " ".join(parts)


def detect_price_anomalies(df: pd.DataFrame, window: int = 168) -> pd.DataFrame:
    """
    Scans the market dataset for:
    1. Negative electricity prices (price_ct_kwh < 0)
    2. Unusually high prices (robust z-score > 2.5)
    3. Sudden rapid hourly jumps (|P_t - P_{t-1}| > threshold)
    """
    if df.empty or "price_ct_kwh" not in df.columns:
        return pd.DataFrame()

    data = df.copy()
    data["dt_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data = data.sort_values("dt_utc").reset_index(drop=True)

    # 1. Hourly rate of change
    data["price_change_hourly"] = data["price_ct_kwh"].diff().abs()

    # 2. Robust z-scores
    data["robust_z"] = calculate_robust_z_scores(data["price_ct_kwh"], window=window)

    anomaly_records = []

    for i, row in data.iterrows():
        p_val = row["price_ct_kwh"]
        if pd.isna(p_val):
            continue

        z_val = row["robust_z"]
        change_val = row["price_change_hourly"]

        anomaly_type = None
        severity = 1.0

        if p_val < 0.0:
            anomaly_type = "negative_price"
            severity = min(5.0, 1.0 + abs(p_val) / 5.0)
        elif pd.notnull(z_val) and z_val >= ANOMALY_ZSCORE_THRESHOLD:
            anomaly_type = "extreme_high"
            severity = min(5.0, float(z_val))
        elif pd.notnull(change_val) and change_val >= ANOMALY_SPIKE_RATE_THRESHOLD_CT:
            anomaly_type = "sudden_jump"
            severity = min(5.0, change_val / 5.0)

        if anomaly_type is not None:
            dt = row["dt_utc"]
            w_total = row.get("wind_total_mwh")
            sol = row.get("solar_mwh")
            ld = row.get("load_mwh")

            explanation = explain_anomaly(
                price_ct=p_val,
                anomaly_type=anomaly_type,
                z_score=z_val if pd.notnull(z_val) else (change_val or 0.0),
                wind_mw=w_total if pd.notnull(w_total) else None,
                solar_mw=sol if pd.notnull(sol) else None,
                load_mw=ld if pd.notnull(ld) else None,
                hour=dt.hour,
                is_weekend=dt.dayofweek >= 5,
            )

            anomaly_records.append({
                "timestamp_utc": row["timestamp_utc"],
                "timestamp_berlin": row.get("timestamp_berlin", row["timestamp_utc"]),
                "price_ct_kwh": round(p_val, 2),
                "anomaly_type": anomaly_type,
                "severity_score": round(severity, 2),
                "z_score": round(float(z_val), 2) if pd.notnull(z_val) else 0.0,
                "wind_total_mwh": round(w_total, 1) if pd.notnull(w_total) else None,
                "solar_mwh": round(sol, 1) if pd.notnull(sol) else None,
                "load_mwh": round(ld, 1) if pd.notnull(ld) else None,
                "explanation": explanation,
            })

    result_df = pd.DataFrame(anomaly_records)
    if not result_df.empty:
        save_anomalies(result_df)
    return result_df
