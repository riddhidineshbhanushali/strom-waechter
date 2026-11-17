"""
Page 3: Price Anomalies (Preis-Anomalien).
Detection and inspection of negative prices, extreme spikes, and rapid ramp-rate jumps
with full renewable generation context (wind, solar, load) and plain-language driver explanations.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import zoneinfo

from config import TIMEZONE_BERLIN
from db import load_anomalies, load_market_data
from anomalies import detect_price_anomalies
from translations import get_text

# Page setup
st.set_page_config(page_title="Preis-Anomalien | Strom-Wächter", page_icon="⚡", layout="wide")
lang = st.session_state.get("lang", "de")
berlin_tz = zoneinfo.ZoneInfo(TIMEZONE_BERLIN)

st.title("⚡ " + get_text("anomalies_header", lang))
st.markdown(get_text("anomalies_intro", lang))

# Load anomalies from database
anomalies_df = load_anomalies(limit=250)

# If no anomalies recorded yet, run detection on market data
if anomalies_df.empty:
    market_df = load_market_data(limit=1000)
    if not market_df.empty:
        anomalies_df = detect_price_anomalies(market_df)

if anomalies_df.empty:
    st.info("Aktuell wurden keine extremen Preisanomalien im vorliegenden Datensatz identifiziert.")
    st.stop()

# Anomaly Filter
anomaly_types = {
    get_text("all_types", lang): "all",
    get_text("type_negative", lang): "negative_price",
    get_text("type_extreme", lang): "extreme_high",
    get_text("type_jump", lang): "sudden_jump",
}

selected_label = st.selectbox(
    get_text("filter_type", lang),
    options=list(anomaly_types.keys()),
    index=0,
)
selected_type = anomaly_types[selected_label]

filtered_df = anomalies_df.copy()
if selected_type != "all":
    filtered_df = filtered_df[filtered_df["anomaly_type"] == selected_type]

# Key Summary Metrics
neg_count = (anomalies_df["anomaly_type"] == "negative_price").sum()
spike_count = (anomalies_df["anomaly_type"] == "extreme_high").sum()
jump_count = (anomalies_df["anomaly_type"] == "sudden_jump").sum()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="❄️ Negativpreise", value=f"{neg_count} Vorfälle")
with col2:
    st.metric(label="🔥 Extreme Preisspitzen", value=f"{spike_count} Vorfälle")
with col3:
    st.metric(label="⚡ Rapide Preissprünge", value=f"{jump_count} Vorfälle")

st.markdown("---")

# Visual Anomaly Scatter on Timeline
st.subheader("📈 " + ("Visualisierung der Preisausschläge" if lang == "de" else "Price Anomaly Scatter"))

recent_market = load_market_data(limit=500)
if not recent_market.empty:
    recent_market["dt_berlin"] = pd.to_datetime(recent_market["timestamp_utc"], utc=True).dt.tz_convert(berlin_tz)
    
    fig = go.Figure()
    # Baseline market price line
    fig.add_trace(go.Scatter(
        x=recent_market["dt_berlin"],
        y=recent_market["price_ct_kwh"],
        mode="lines",
        name="Börsenstrompreis",
        line=dict(color="#475569", width=1.5),
        hovertemplate="%{x}<br>Preis: %{y:.2f} ct/kWh<extra></extra>",
    ))

    # Overlay anomaly points
    plot_anomalies = anomalies_df[
        anomalies_df["timestamp_utc"].isin(recent_market["timestamp_utc"])
    ].copy()
    if not plot_anomalies.empty:
        plot_anomalies["dt_berlin"] = pd.to_datetime(plot_anomalies["timestamp_utc"], utc=True).dt.tz_convert(berlin_tz)
        
        color_map = {
            "negative_price": "#06b6d4",  # Cyan for negative
            "extreme_high": "#ef4444",    # Red for extreme high
            "sudden_jump": "#f59e0b",     # Amber for sudden jump
        }
        
        for atype, c in color_map.items():
            subset = plot_anomalies[plot_anomalies["anomaly_type"] == atype]
            if not subset.empty:
                fig.add_trace(go.Scatter(
                    x=subset["dt_berlin"],
                    y=subset["price_ct_kwh"],
                    mode="markers",
                    name=atype,
                    marker=dict(color=c, size=9, symbol="diamond"),
                    hovertemplate="<b>%{x}</b><br>Preis: %{y:.2f} ct/kWh<br>Typ: " + atype + "<extra></extra>",
                ))

    fig.add_hline(y=0.0, line_dash="dash", line_color="#06b6d4", annotation_text="0 ct/kWh Nulllinie")

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(15, 23, 42, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=20, t=30, b=40),
        yaxis=dict(title="Börsenstrompreis (ct/kWh)"),
        xaxis=dict(title="Datum & Uhrzeit (Berlin)"),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

# Anomaly Detail List
st.markdown("---")
st.subheader("📋 " + ("Erfasste Anomalien im Detail" if lang == "de" else "Detected Anomalies Log"))

if filtered_df.empty:
    st.info("Keine Einträge für den ausgewählten Filter.")
else:
    for _, row in filtered_df.head(25).iterrows():
        p = row["price_ct_kwh"]
        atype = row["anomaly_type"]
        ts_berlin = row["timestamp_berlin"]
        
        icon = "❄️" if atype == "negative_price" else ("🔥" if atype == "extreme_high" else "⚡")
        header_text = f"{icon} **{ts_berlin}** — **{p:.2f} ct/kWh** ({atype})"
        
        with st.expander(header_text):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown(f"**Wind-Einspeisung:** {row.get('wind_total_mwh', 'N/A')} MW")
            with col_b:
                st.markdown(f"**Solar-Einspeisung:** {row.get('solar_mwh', 'N/A')} MW")
            with col_c:
                st.markdown(f"**Netzlast:** {row.get('load_mwh', 'N/A')} MW")

            st.markdown(f"**Mögliche Markteinflüsse:** {row.get('explanation', '')}")
