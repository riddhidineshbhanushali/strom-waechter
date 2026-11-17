"""
Unit tests for forecasting models, backtesting evaluation,
and API resilience in Strom-Wächter.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from forecast import (
    SeasonalNaiveModel,
    SeasonalARModel,
    GradientBoostingModel,
    evaluate_forecast_models,
)
from fetch import SMARDClient


@pytest.fixture
def synthetic_training_data():
    """Generates 500 hours of synthetic electricity market time series."""
    dates = pd.date_range("2026-01-01", periods=500, freq="1h", tz="UTC")
    prices = []
    for i, d in enumerate(dates):
        # 24h cycle + weekly component + realistic variation
        daily = 3.0 * np.sin(2 * np.pi * d.hour / 24.0)
        weekly = 2.0 if d.day_of_week < 5 else -1.0
        drift = 0.5 * np.sin(i / 15.0) + (0.1 * (i % 11))
        prices.append(10.0 + daily + weekly + drift)

    return pd.DataFrame({
        "timestamp_utc": [d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in dates],
        "timestamp_berlin": [d.strftime("%Y-%m-%dT%H:%M:%S+01:00") for d in dates],
        "price_ct_kwh": prices,
        "solar_mwh": [max(0.0, 5000 * np.sin(np.pi * (d.hour - 6) / 12.0)) if 6 <= d.hour <= 18 else 0.0 for d in dates],
        "wind_total_mwh": [10000.0 + 2000.0 * np.cos(i / 20.0) for i, d in enumerate(dates)],
        "load_mwh": [50000.0 + 10000.0 * np.sin(2 * np.pi * d.hour / 24.0) for d in dates],
    })


def test_seasonal_naive_baseline_prediction():
    """Verify SeasonalNaiveModel predicts exact t-168h lag."""
    model = SeasonalNaiveModel()
    df_test = pd.DataFrame({
        "price_lag_168h": [12.5, 14.0],
        "price_lag_24h": [10.0, 11.0],
    })
    preds = model.predict(df_test)
    assert preds[0] == 12.5
    assert preds[1] == 14.0


def test_evaluate_forecast_models_metrics(synthetic_training_data):
    """Verify chronological backtesting produces valid MAE and RMSE metrics."""
    eval_res = evaluate_forecast_models(synthetic_training_data, test_hours=72)
    
    assert "best_model_name" in eval_res
    assert "evaluations" in eval_res
    assert "Seasonal Naive Baseline" in eval_res["evaluations"]

    naive_metrics = eval_res["evaluations"]["Seasonal Naive Baseline"]
    assert naive_metrics["mae"] > 0.0
    assert naive_metrics["rmse"] >= naive_metrics["mae"]  # RMSE mathematically >= MAE


def test_honest_model_selection(synthetic_training_data):
    """Verify that selection rationale honestly reflects validation performance."""
    eval_res = evaluate_forecast_models(synthetic_training_data, test_hours=48)
    best_name = eval_res["best_model_name"]
    rationale = eval_res["selection_rationale"]

    assert len(rationale) > 10
    if best_name == "Seasonal Naive Baseline":
        assert "did not outperform the simple baseline" in rationale
    else:
        assert best_name in rationale


def test_smard_client_mocked_network_failure():
    """Verify SMARDClient handles connection failures gracefully without raising unhandled exceptions."""
    client = SMARDClient(base_url="https://invalid.test.domain")
    with patch.object(client.session, "get", side_effect=Exception("Connection timed out")):
        res = client._request_with_retry("https://invalid.test.domain/test.json")
        assert res is None

        idx = client.fetch_index(4169)
        assert idx == []
