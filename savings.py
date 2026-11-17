"""
Household Savings Calculator for Strom-Wächter.
Simulates and compares dynamic electricity tariffs against traditional fixed contracts
using empirical German market price time series, detailed statutory fee breakdowns,
and realistic household consumption profiles.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import numpy as np
import pandas as pd

from config import GermanTariffDefaults, get_default_usage_profiles


@dataclass
class TariffComparisonResult:
    """Detailed financial outcome of tariff comparison."""
    annual_consumption_kwh: float
    profile_name: str

    # Costs (EUR)
    fixed_annual_total_eur: float
    fixed_annual_energy_eur: float
    fixed_annual_base_eur: float

    dynamic_annual_total_eur: float
    dynamic_annual_energy_eur: float
    dynamic_annual_base_eur: float
    dynamic_annual_statutory_eur: float
    dynamic_annual_vat_eur: float

    # Differential Metrics
    annual_savings_eur: float
    savings_percent: float

    # Effective Average Unit Rates (ct/kWh)
    fixed_effective_rate_ct_kwh: float
    dynamic_effective_rate_ct_kwh: float
    average_wholesale_rate_ct_kwh: float

    # Risk & Market Exposure
    negative_price_hours: int
    peak_price_hours_above_30ct: int
    max_observed_price_ct_kwh: float
    min_observed_price_ct_kwh: float

    # Monthly Breakdown DataFrame
    monthly_breakdown: pd.DataFrame


def compute_tariff_comparison(
    market_df: pd.DataFrame,
    annual_consumption_kwh: float = 3500.0,
    profile_key: str = "evening_heavy",
    custom_weights: Optional[List[float]] = None,
    tariffs: Optional[GermanTariffDefaults] = None,
    fixed_price_override: Optional[float] = None,
    fixed_base_override: Optional[float] = None,
    dynamic_markup_override: Optional[float] = None,
    dynamic_base_override: Optional[float] = None,
    grid_fee_override: Optional[float] = None,
) -> TariffComparisonResult:
    """
    Simulates annual household electricity cost under fixed and dynamic pricing.
    
    Formula for dynamic tariff hourly cost:
    Retail_Price_t = (Wholesale_ct_t + Supplier_Markup + Statutory_Levies) * (1 + VAT)
    Total_Dynamic_Cost = sum(Retail_Price_t * kWh_t) + (12 * Dynamic_Monthly_Base_Fee * (1 + VAT))
    """
    if market_df.empty or "price_ct_kwh" not in market_df.columns:
        raise ValueError("Market DataFrame must contain 'price_ct_kwh'")

    t = tariffs or GermanTariffDefaults()

    # User parameter overrides
    fixed_rate_ct = fixed_price_override if fixed_price_override is not None else t.fixed_tariff_rate
    fixed_base_eur = fixed_base_override if fixed_base_override is not None else t.fixed_monthly_base_fee

    dynamic_markup_ct = dynamic_markup_override if dynamic_markup_override is not None else t.dynamic_markup
    dynamic_base_eur = dynamic_base_override if dynamic_base_override is not None else t.dynamic_monthly_base_fee

    grid_fee_ct = grid_fee_override if grid_fee_override is not None else t.grid_fee
    statutory_levies_ct = (
        t.electricity_tax
        + grid_fee_ct
        + t.concession_levy
        + t.kwkg_levy
        + t.offshore_levy
    )
    vat_multiplier = 1.0 + t.vat_rate

    # Hourly Profile Weights
    profiles = get_default_usage_profiles()
    if custom_weights and len(custom_weights) == 24:
        s = sum(custom_weights)
        weights_24 = [w / s for w in custom_weights] if s > 0 else profiles["evening_heavy"]
    else:
        weights_24 = profiles.get(profile_key, profiles["evening_heavy"])

    df = market_df.dropna(subset=["price_ct_kwh"]).copy()
    if "dt_utc" not in df.columns:
        df["dt_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["hour"] = df["dt_utc"].dt.hour
    df["month"] = df["dt_utc"].dt.month

    # Assign hourly weights
    df["profile_weight"] = df["hour"].apply(lambda h: weights_24[h])
    # Normalize weights across the entire dataset duration to equal annual consumption
    sum_weights = df["profile_weight"].sum()
    df["hourly_kwh"] = (df["profile_weight"] / sum_weights) * annual_consumption_kwh

    # Dynamic pricing calculation per hour
    # Note: If wholesale price is negative, levies still apply; base can drop below statutory levies
    # but supplier markup + levies still buffer the price.
    df["dynamic_pretax_ct_kwh"] = df["price_ct_kwh"] + dynamic_markup_ct + statutory_levies_ct
    # Apply VAT (19%)
    df["dynamic_final_ct_kwh"] = df["dynamic_pretax_ct_kwh"] * vat_multiplier

    # Hourly costs in EUR (ct / 100 * kWh)
    df["dynamic_cost_eur"] = (df["dynamic_final_ct_kwh"] / 100.0) * df["hourly_kwh"]
    df["fixed_cost_eur"] = (fixed_rate_ct / 100.0) * df["hourly_kwh"]

    # Component tracking for dynamic tariff
    df["wholesale_cost_eur"] = ((df["price_ct_kwh"] * vat_multiplier) / 100.0) * df["hourly_kwh"]
    df["statutory_cost_eur"] = ((statutory_levies_ct * vat_multiplier) / 100.0) * df["hourly_kwh"]

    # Totals
    dynamic_energy_eur = df["dynamic_cost_eur"].sum()
    dynamic_base_total_eur = dynamic_base_eur * 12.0
    dynamic_total_eur = dynamic_energy_eur + dynamic_base_total_eur

    fixed_energy_eur = df["fixed_cost_eur"].sum()
    fixed_base_total_eur = fixed_base_eur * 12.0
    fixed_total_eur = fixed_energy_eur + fixed_base_total_eur

    annual_savings_eur = fixed_total_eur - dynamic_total_eur
    savings_pct = (annual_savings_eur / fixed_total_eur) * 100.0 if fixed_total_eur > 0 else 0.0

    # Risk Metrics
    neg_count = int((df["price_ct_kwh"] < 0.0).sum())
    high_count = int((df["price_ct_kwh"] > 30.0).sum())
    max_p = float(df["price_ct_kwh"].max())
    min_p = float(df["price_ct_kwh"].min())

    # Effective Average Rates
    fixed_effective_rate = (fixed_total_eur / annual_consumption_kwh) * 100.0
    dynamic_effective_rate = (dynamic_total_eur / annual_consumption_kwh) * 100.0
    avg_wholesale_rate = float(df["price_ct_kwh"].mean())

    # Monthly aggregation
    monthly_grouped = df.groupby("month").agg(
        kwh=("hourly_kwh", "sum"),
        dynamic_energy=("dynamic_cost_eur", "sum"),
        fixed_energy=("fixed_cost_eur", "sum"),
        avg_wholesale_ct=("price_ct_kwh", "mean"),
    ).reset_index()

    monthly_grouped["dynamic_total_eur"] = monthly_grouped["dynamic_energy"] + dynamic_base_eur
    monthly_grouped["fixed_total_eur"] = monthly_grouped["fixed_energy"] + fixed_base_eur
    monthly_grouped["savings_eur"] = monthly_grouped["fixed_total_eur"] - monthly_grouped["dynamic_total_eur"]

    return TariffComparisonResult(
        annual_consumption_kwh=annual_consumption_kwh,
        profile_name=profile_key,
        fixed_annual_total_eur=round(fixed_total_eur, 2),
        fixed_annual_energy_eur=round(fixed_energy_eur, 2),
        fixed_annual_base_eur=round(fixed_base_total_eur, 2),
        dynamic_annual_total_eur=round(dynamic_total_eur, 2),
        dynamic_annual_energy_eur=round(dynamic_energy_eur, 2),
        dynamic_annual_base_eur=round(dynamic_base_total_eur, 2),
        dynamic_annual_statutory_eur=round(df["statutory_cost_eur"].sum(), 2),
        dynamic_annual_vat_eur=round(dynamic_total_eur - (dynamic_total_eur / vat_multiplier), 2),
        annual_savings_eur=round(annual_savings_eur, 2),
        savings_percent=round(savings_pct, 1),
        fixed_effective_rate_ct_kwh=round(fixed_effective_rate, 2),
        dynamic_effective_rate_ct_kwh=round(dynamic_effective_rate, 2),
        average_wholesale_rate_ct_kwh=round(avg_wholesale_rate, 2),
        negative_price_hours=neg_count,
        peak_price_hours_above_30ct=high_count,
        max_observed_price_ct_kwh=round(max_p, 2),
        min_observed_price_ct_kwh=round(min_p, 2),
        monthly_breakdown=monthly_grouped,
    )
