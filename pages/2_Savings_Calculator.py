"""
Page 2: Household Savings Calculator (Ersparnis-Rechner).
Interactive comparison of fixed electricity tariffs vs dynamic spot-market tariffs
with empirical German wholesale data, statutory fee breakdowns, and customizable consumption profiles.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from config import GermanTariffDefaults, get_default_usage_profiles
from db import load_market_data
from savings import compute_tariff_comparison
from translations import get_text

# Page setup
st.set_page_config(page_title="Ersparnis-Rechner | Strom-Wächter", page_icon="💰", layout="wide")
lang = st.session_state.get("lang", "de")

st.title("💰 " + get_text("calc_header", lang))
st.markdown(get_text("calc_intro", lang))

# Load market data (up to last 12 months = 8760 hours)
market_df = load_market_data(limit=8760)
if market_df.empty or "price_ct_kwh" not in market_df.columns:
    st.error("Keine Marktdaten in der Datenbank gefunden. Bitte zuerst Pipeline ausführen.")
    st.stop()

# Layout: Configuration Column vs Results Column
col_config, col_results = st.columns([1, 2], gap="large")

with col_config:
    st.subheader("⚙️ " + ("Vertrag & Verbrauch" if lang == "de" else "Contract & Usage"))

    # Preset selector
    preset = st.selectbox(
        "Haushalts-Größe / Presets" if lang == "de" else "Household Presets",
        options=[
            "1-Person / Student (1.500 kWh)",
            "2-Personen / Paar (2.500 kWh)",
            "Familie / WG (3.500 kWh)",
            "E-Auto / Wärmepumpe (5.500 kWh)",
            "Individuell",
        ],
        index=2,
    )

    preset_map = {
        "1-Person / Student (1.500 kWh)": 1500.0,
        "2-Personen / Paar (2.500 kWh)": 2500.0,
        "Familie / WG (3.500 kWh)": 3500.0,
        "E-Auto / Wärmepumpe (5.500 kWh)": 5500.0,
    }
    default_kwh = preset_map.get(preset, 3500.0)

    annual_kwh = st.number_input(
        get_text("input_consumption", lang),
        min_value=500.0,
        max_value=25000.0,
        value=default_kwh,
        step=250.0,
    )

    # Usage profile selector
    profile_choice = st.selectbox(
        get_text("profile_label", lang),
        options=[
            ("evening_heavy", get_text("profile_evening", lang)),
            ("flexible", get_text("profile_flexible", lang)),
            ("ev_charging", get_text("profile_ev", lang)),
        ],
        format_func=lambda x: x[1],
        index=0,
    )
    profile_key = profile_choice[0]

    st.markdown("#### 🔒 " + ("Bisheriger Festpreis-Tarif" if lang == "de" else "Existing Fixed Tariff"))
    fixed_ct = st.number_input(
        get_text("input_fixed_rate", lang),
        min_value=15.0,
        max_value=60.0,
        value=32.50,
        step=0.5,
    )
    fixed_base_monthly = st.number_input(
        get_text("input_fixed_base", lang),
        min_value=0.0,
        max_value=30.0,
        value=11.90,
        step=0.5,
    )

    st.markdown("#### 📈 " + ("Dynamischer Tarif" if lang == "de" else "Dynamic Tariff"))
    dyn_markup = st.number_input(
        get_text("input_dynamic_markup", lang),
        min_value=0.0,
        max_value=10.0,
        value=1.50,
        step=0.1,
        help="Aufschlag des Anbieters (z.B. Tibber, Rabot Energy, 1.5 ct/kWh)",
    )
    dyn_base_monthly = st.number_input(
        get_text("input_dynamic_base", lang),
        min_value=0.0,
        max_value=25.0,
        value=5.99,
        step=0.5,
    )

    with st.expander("🏛️ " + ("Gesetzliche Steuern & Umlagen" if lang == "de" else "Statutory Levies & Taxes")):
        st.caption("Standardwerte für Deutschland (2024/2026):")
        grid_fee = st.number_input(get_text("input_grid_fee", lang), value=9.50, step=0.5)
        st.markdown("""
        - **Stromsteuer:** 2,05 ct/kWh
        - **Konzessionsabgabe:** 1,66 ct/kWh
        - **KWKG-Umlage:** 0,28 ct/kWh
        - **Offshore-Netzumlage:** 0,66 ct/kWh
        - **Mehrwertsteuer:** 19%
        """)

# Execute financial simulation
tariffs = GermanTariffDefaults()
results = compute_tariff_comparison(
    market_df=market_df,
    annual_consumption_kwh=annual_kwh,
    profile_key=profile_key,
    fixed_price_override=fixed_ct,
    fixed_base_override=fixed_base_monthly,
    dynamic_markup_override=dyn_markup,
    dynamic_base_override=dyn_base_monthly,
    grid_fee_override=grid_fee,
)

with col_results:
    st.subheader("📊 " + get_text("calc_results_title", lang))

    # Big Summary Metric Cards
    res_col1, res_col2, res_col3 = st.columns(3)

    with res_col1:
        st.metric(
            label=get_text("annual_fixed_cost", lang),
            value=f"{results.fixed_annual_total_eur:,.2f} €",
            help=f"Arbeitspreis: {results.fixed_annual_energy_eur:.2f} € | Grundpreis: {results.fixed_annual_base_eur:.2f} €",
        )

    with res_col2:
        st.metric(
            label=get_text("annual_dynamic_cost", lang),
            value=f"{results.dynamic_annual_total_eur:,.2f} €",
            help=f"Effektiver Endpreis: {results.dynamic_effective_rate_ct_kwh:.2f} ct/kWh",
        )

    with res_col3:
        savings = results.annual_savings_eur
        savings_color = "normal" if savings >= 0 else "inverse"
        st.metric(
            label=get_text("potential_savings", lang),
            value=f"{savings:+,.2f} €",
            delta=f"{results.savings_percent:+.1f} %",
            delta_color=savings_color,
        )

    st.markdown("---")

    # Monthly Breakdown Chart
    st.markdown(f"#### 📅 {get_text('monthly_chart_title', lang)}")
    m_df = results.monthly_breakdown

    fig_month = go.Figure()
    fig_month.add_trace(go.Bar(
        x=[f"Monat {int(m)}" for m in m_df["month"]],
        y=m_df["fixed_total_eur"],
        name="Festpreis-Tarif",
        marker_color="#64748b",
        hovertemplate="%{x}<br>Festpreis: %{y:.2f} €<extra></extra>",
    ))
    fig_month.add_trace(go.Bar(
        x=[f"Monat {int(m)}" for m in m_df["month"]],
        y=m_df["dynamic_total_eur"],
        name="Dynamischer Tarif",
        marker_color="#10b981",
        hovertemplate="%{x}<br>Dynamisch: %{y:.2f} €<extra></extra>",
    ))

    fig_month.update_layout(
        barmode="group",
        template="plotly_dark",
        plot_bgcolor="rgba(15, 23, 42, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=20, t=30, b=40),
        yaxis=dict(title="Monatliche Kosten (€)"),
        xaxis=dict(title=""),
        height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_month, use_container_width=True)

    # Market Exposure & Risk Metrics
    st.markdown(f"#### ⚡ {get_text('exposure_metrics_title', lang)}")
    risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)

    with risk_col1:
        st.metric(
            label=get_text("negative_hours_label", lang),
            value=f"{results.negative_price_hours} Std.",
            help="Stunden, in denen der reine Börsenpreis unter 0 ct/kWh lag.",
        )
    with risk_col2:
        st.metric(
            label=get_text("peak_hours_label", lang),
            value=f"{results.peak_price_hours_above_30ct} Std.",
            help="Stunden, in denen der reine Börsenpreis über 30 ct/kWh stieg.",
        )
    with risk_col3:
        st.metric(
            label=get_text("max_price_label", lang),
            value=f"{results.max_observed_price_ct_kwh:.1f} ct",
            help="Höchste im Zeitraum beobachtete Börsenpreisspitze.",
        )
    with risk_col4:
        st.metric(
            label=get_text("min_price_label", lang),
            value=f"{results.min_observed_price_ct_kwh:.1f} ct",
            help="Tiefster im Zeitraum erfasster Negativpreis.",
        )

    # Statutory Cost Transparency Breakdown
    with st.expander("🔍 " + ("Detaillierte Kostenaufschlüsselung des dynamischen Tarifs" if lang == "de" else "Detailed Dynamic Cost Breakdown")):
        st.markdown(f"""
        - **Reine Börsenstromkosten:** {(results.average_wholesale_rate_ct_kwh * annual_kwh / 100):,.2f} € ({results.average_wholesale_rate_ct_kwh:.2f} ct/kWh)
        - **Gesetzliche Abgaben & Netzentgelte:** {results.dynamic_annual_statutory_eur:,.2f} €
        - **Grundgebühren (jährlich):** {results.dynamic_annual_base_eur:,.2f} €
        - **Enthaltene Mehrwertsteuer (19%):** {results.dynamic_annual_vat_eur:,.2f} €
        """)

    # Prominent Disclaimer
    st.warning("⚠️ " + get_text("disclaimer_text", lang))
