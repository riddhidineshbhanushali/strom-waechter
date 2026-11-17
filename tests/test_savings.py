"""
Unit tests for the household savings calculator and tariff component math in Strom-Wächter.
"""

import pytest
import pandas as pd
import numpy as np

from savings import compute_tariff_comparison
from config import GermanTariffDefaults, get_default_usage_profiles


@pytest.fixture
def sample_market_series():
    """Generates 720 hours (30 days) of realistic market prices."""
    dates = pd.date_range("2026-01-01", periods=720, freq="1h", tz="UTC")
    # Base pattern with morning and evening peaks, occasional negative hour
    prices = []
    for d in dates:
        h = d.hour
        base = 8.0
        if 7 <= h <= 9:
            base += 4.0
        elif 17 <= h <= 20:
            base += 6.0
        elif 12 <= h <= 14:
            base -= 2.0
        # Introduce a negative price on Sundays at 13:00
        if d.day_of_week == 6 and h == 13:
            base = -3.5
        prices.append(base)

    return pd.DataFrame({
        "timestamp_utc": [d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in dates],
        "price_ct_kwh": prices,
    })


def test_consumption_normalization(sample_market_series):
    """Verify that simulated hourly consumption sums exactly to the annual target."""
    target_kwh = 4000.0
    result = compute_tariff_comparison(
        sample_market_series,
        annual_consumption_kwh=target_kwh,
        profile_key="flexible",
    )
    assert result.annual_consumption_kwh == target_kwh
    monthly_sum_kwh = result.monthly_breakdown["kwh"].sum()
    assert np.isclose(monthly_sum_kwh, target_kwh, rtol=1e-5)


def test_fixed_tariff_exact_cost(sample_market_series):
    """Verify that fixed tariff calculation matches standard formula."""
    target_kwh = 3000.0
    fixed_rate = 30.0  # 30 ct/kWh
    fixed_base = 10.0  # 10 €/month

    result = compute_tariff_comparison(
        sample_market_series,
        annual_consumption_kwh=target_kwh,
        fixed_price_override=fixed_rate,
        fixed_base_override=fixed_base,
    )

    expected_energy = (target_kwh * fixed_rate) / 100.0  # 900.0 €
    expected_base = 10.0 * 12.0  # 120.0 €
    expected_total = expected_energy + expected_base  # 1020.0 €

    assert np.isclose(result.fixed_annual_energy_eur, expected_energy)
    assert np.isclose(result.fixed_annual_base_eur, expected_base)
    assert np.isclose(result.fixed_annual_total_eur, expected_total)


def test_negative_wholesale_price_exposure(sample_market_series):
    """Verify negative price intervals are identified and incorporated."""
    result = compute_tariff_comparison(
        sample_market_series,
        annual_consumption_kwh=2500.0,
        profile_key="evening_heavy",
    )
    # We introduced at least 4 Sunday negative hours
    assert result.negative_price_hours >= 4
    assert result.min_observed_price_ct_kwh < 0.0


def test_statutory_levies_and_vat_applied(sample_market_series):
    """Verify dynamic price components properly apply VAT and statutory charges."""
    result = compute_tariff_comparison(
        sample_market_series,
        annual_consumption_kwh=3500.0,
    )
    # Dynamic annual total must strictly exceed pure wholesale energy cost
    assert result.dynamic_annual_total_eur > result.average_wholesale_rate_ct_kwh * 35.0
    # Statutory levies and VAT must be tracked
    assert result.dynamic_annual_statutory_eur > 0
    assert result.dynamic_annual_vat_eur > 0
