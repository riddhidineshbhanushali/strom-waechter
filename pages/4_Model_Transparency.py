"""
Page 4: Model Transparency (Modell-Transparenz).
Honest disclosure of model architectures, benchmark metrics (MAE & RMSE),
selection rationale, data coverage, missingness percentage, and backtest visualizations.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from db import (
    load_latest_model_evaluations,
    load_market_data,
    get_latest_pipeline_status,
    load_latest_forecasts,
)
from clean import calculate_data_quality_metrics
from translations import get_text

# Page setup
st.set_page_config(page_title="Modell-Transparenz | Strom-Wächter", page_icon="🔬", layout="wide")
lang = st.session_state.get("lang", "de")

st.title("🔬 " + get_text("transparency_header", lang))
st.markdown(get_text("transparency_intro", lang))

# Section 1: Data Coverage & Source Transparency
st.subheader("📡 " + get_text("data_coverage_header", lang))

market_df = load_market_data()
quality = calculate_data_quality_metrics(market_df)
pipeline_status = get_latest_pipeline_status()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        label=get_text("metric_total_records", lang),
        value=f"{quality['total_observations']:,} Std.",
    )
with c2:
    st.metric(
        label=get_text("metric_missing_pct", lang),
        value=f"{quality['missing_prices_pct']:.2f} %",
        help="Prozentsatz der Stunden ohne gültigen Börsenpreis.",
    )
with c3:
    evals_df = load_latest_model_evaluations()
    selected_row = evals_df[evals_df["is_selected"] == 1] if not evals_df.empty else pd.DataFrame()
    selected_model = selected_row.iloc[0]["model_name"] if not selected_row.empty else "Seasonal Naive Baseline"
    st.metric(
        label=get_text("metric_selected_model", lang),
        value=selected_model,
    )
with c4:
    last_update = pipeline_status.get("last_successful_update") if pipeline_status else quality.get("max_date_utc")
    st.metric(
        label="Datenstand (UTC)",
        value=str(last_update)[:16] if last_update else "N/A",
    )

st.markdown("""
- **Primäre Datenquelle:** Bundesnetzagentur [SMARD.de](https://www.smard.de/) (Offizielle Strommarktdatenplattform Deutschland)
- **Auflösung:** 1 Stunde (Hour)
- **Referenzmarkt:** Day-Ahead Deutschland/Luxemburg (Filter ID 4169, EUR/MWh)
- **Sekundärquelle (Wetter):** [Open-Meteo.com](https://open-meteo.com/) (DWD/ICON Wettermodell)
""")

st.markdown("---")

# Section 2: Model Benchmarking & Honest Comparison
st.subheader("⚖️ " + get_text("model_comparison_header", lang))

st.markdown(f"""
> [!NOTE]
> **{get_text('mae_explanation', lang)}**  
> **{get_text('rmse_explanation', lang)}**
""")

if not evals_df.empty:
    # Model evaluation comparison table
    display_evals = evals_df[["model_name", "mae", "rmse", "samples_count", "is_selected"]].copy()
    display_evals.columns = [
        get_text("col_model", lang),
        get_text("col_mae", lang),
        get_text("col_rmse", lang),
        "Test-Stunden",
        get_text("col_selected", lang),
    ]
    display_evals[get_text("col_selected", lang)] = display_evals[get_text("col_selected", lang)].apply(
        lambda x: "✅ Ja" if x == 1 else "Nein"
    )

    st.dataframe(display_evals, use_container_width=True, hide_index=True)

    # Display Honest Selection Rationale
    if not selected_row.empty and selected_row.iloc[0].get("notes"):
        st.info(f"💡 **Entscheidungsbegründung:** {selected_row.iloc[0]['notes']}")
else:
    st.info("Noch keine Modell-Evaluierungsläufe in der Datenbank vorhanden.")

st.markdown("---")

# Section 3: Forecast vs Actual Visualization
st.subheader("📈 " + get_text("chart_forecast_vs_actual", lang))

forecasts_df = load_latest_forecasts()
if not forecasts_df.empty and not market_df.empty:
    merged_view = forecasts_df.copy()
    
    fig = go.Figure()

    # Model Predicted Price
    fig.add_trace(go.Scatter(
        x=merged_view["target_time_berlin"],
        y=merged_view["predicted_price_ct_kwh"],
        mode="lines+markers",
        name="Prognostizierter Preis",
        line=dict(color="#10b981", width=2),
        marker=dict(size=5),
        hovertemplate="%{x}<br>Prognose: %{y:.2f} ct/kWh<extra></extra>",
    ))

    # Uncertainty Bound (Upper)
    if "upper_bound_ct_kwh" in merged_view.columns and merged_view["upper_bound_ct_kwh"].notnull().any():
        fig.add_trace(go.Scatter(
            x=merged_view["target_time_berlin"],
            y=merged_view["upper_bound_ct_kwh"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=merged_view["target_time_berlin"],
            y=merged_view["lower_bound_ct_kwh"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(16, 185, 129, 0.15)",
            name="80% Unsicherheitsband",
            hoverinfo="skip",
        ))

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(15, 23, 42, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=20, t=30, b=40),
        yaxis=dict(title="Preis (ct/kWh)"),
        xaxis=dict(title="Uhrzeit (Berlin)", tickangle=-45),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Erläuterung: Das grüne Band visualisiert das 80%-Konfidenzintervall, berechnet aus den empirischen Residuen des Modell-Backtestings.")
