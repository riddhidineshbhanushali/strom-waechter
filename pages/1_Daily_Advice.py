"""
Page 1: Daily Advice (Tages-Empfehlung).
Consumer-centric hourly electricity recommendations, cheapest appliance windows,
accessible traffic-light price timeline, and plain-language market explanations.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import zoneinfo

from config import TIMEZONE_BERLIN
from db import load_market_data, load_latest_forecasts, get_latest_market_timestamp
from translations import get_text

# Page setup
st.set_page_config(page_title="Tages-Empfehlung | Strom-Wächter", page_icon="💡", layout="wide")
lang = st.session_state.get("lang", "de")
berlin_tz = zoneinfo.ZoneInfo(TIMEZONE_BERLIN)

st.title("💡 " + get_text("nav_home", lang))
st.caption(get_text("app_tagline", lang))

# Load Market Data
market_df = load_market_data(limit=336)  # Last 14 days
if market_df.empty:
    st.warning("Keine Marktdaten in der Datenbank verfügbar. Bitte führe zuerst die Pipeline aus.")
    st.stop()

# Convert timestamps to Berlin timezone
market_df["dt_utc"] = pd.to_datetime(market_df["timestamp_utc"], utc=True)
market_df["dt_berlin"] = market_df["dt_utc"].dt.tz_convert(berlin_tz)
market_df["date_berlin"] = market_df["dt_berlin"].dt.date
market_df["hour_berlin"] = market_df["dt_berlin"].dt.hour

now_berlin = datetime.now(timezone.utc).astimezone(berlin_tz)
today_date = now_berlin.date()
tomorrow_date = today_date + timedelta(days=1)

today_df = market_df[market_df["date_berlin"] == today_date].sort_values("dt_berlin")
tomorrow_df = market_df[market_df["date_berlin"] == tomorrow_date].sort_values("dt_berlin")

# Rolling 14-day average benchmark
baseline_avg_price = market_df["price_ct_kwh"].mean()

# Key Metric Row
latest_valid = market_df.dropna(subset=["price_ct_kwh"]).iloc[-1]
current_price = latest_valid["price_ct_kwh"]
today_avg = today_df["price_ct_kwh"].mean() if not today_df.empty else current_price
tomorrow_avg = tomorrow_df["price_ct_kwh"].mean() if not tomorrow_df.empty else None

# Price level assessment
if today_avg < (baseline_avg_price - 1.5):
    price_status_str = f"🟢 {get_text('cheaper_than_usual', lang)}"
elif today_avg > (baseline_avg_price + 1.5):
    price_status_str = f"🔴 {get_text('expensive_than_usual', lang)}"
else:
    price_status_str = f"🟡 {get_text('normal_price', lang)}"

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        label=get_text("current_price", lang),
        value=f"{current_price:.2f} ct/kWh",
        delta=f"{(current_price - today_avg):+.2f} ct vs. Tagesschnitt",
        delta_color="inverse",
    )
with col2:
    st.metric(
        label=get_text("today_avg", lang),
        value=f"{today_avg:.2f} ct/kWh" if pd.notnull(today_avg) else "N/A",
    )
with col3:
    if tomorrow_avg is not None and not np.isnan(tomorrow_avg):
        st.metric(
            label=get_text("tomorrow_avg", lang),
            value=f"{tomorrow_avg:.2f} ct/kWh",
            delta=f"{(tomorrow_avg - today_avg):+.2f} ct vs. heute",
            delta_color="inverse",
        )
    else:
        st.metric(
            label=get_text("tomorrow_avg", lang),
            value="Ausstehend",
            help=get_text("tomorrow_not_yet_published", lang),
        )
with col4:
    st.metric(label=get_text("price_level", lang), value=price_status_str)

st.markdown("---")

# Optimal Appliance Windows (Cheapest 2h and 3h continuous intervals)
def find_best_window(df: pd.DataFrame, window_hours: int = 2):
    if len(df) < window_hours:
        return None
    rolling_sums = df["price_ct_kwh"].rolling(window=window_hours).mean()
    min_idx = rolling_sums.idxmin()
    if pd.isna(min_idx):
        return None
    end_row = df.loc[min_idx]
    start_hour = (end_row["hour_berlin"] - window_hours + 1) % 24
    end_hour = (end_row["hour_berlin"] + 1) % 24
    avg_price = rolling_sums.loc[min_idx]
    return {
        "start": start_hour,
        "end": end_hour,
        "avg_price": avg_price,
    }

st.subheader("🧺 " + get_text("best_windows_header", lang))

tab_today, tab_tomorrow = st.tabs(["Heute (" + today_date.strftime("%d.%m.%Y") + ")", "Morgen (" + tomorrow_date.strftime("%d.%m.%Y") + ")"])

with tab_today:
    if not today_df.empty:
        best_2h = find_best_window(today_df, 2)
        best_3h = find_best_window(today_df, 3)

        wcol1, wcol2 = st.columns(2)
        with wcol1:
            if best_2h:
                st.success(
                    f"**{get_text('best_2h_window', lang)}:**\n\n"
                    f"### ⏰ {best_2h['start']:02d}:00 – {best_2h['end']:02d}:00 Uhr\n"
                    f"*Durchschnittlicher Börsenpreis: **{best_2h['avg_price']:.2f} ct/kWh***"
                )
        with wcol2:
            if best_3h:
                st.info(
                    f"**{get_text('best_3h_window', lang)}:**\n\n"
                    f"### ⏰ {best_3h['start']:02d}:00 – {best_3h['end']:02d}:00 Uhr\n"
                    f"*Durchschnittlicher Börsenpreis: **{best_3h['avg_price']:.2f} ct/kWh***"
                )
    else:
        st.info("Keine Daten für den heutigen Tag vorhanden.")

with tab_tomorrow:
    if not tomorrow_df.empty and len(tomorrow_df) >= 12:
        best_2h_tom = find_best_window(tomorrow_df, 2)
        best_3h_tom = find_best_window(tomorrow_df, 3)
        wcol1, wcol2 = st.columns(2)
        with wcol1:
            if best_2h_tom:
                st.success(
                    f"**{get_text('best_2h_window', lang)}:**\n\n"
                    f"### ⏰ {best_2h_tom['start']:02d}:00 – {best_2h_tom['end']:02d}:00 Uhr\n"
                    f"*Durchschnittlicher Börsenpreis: **{best_2h_tom['avg_price']:.2f} ct/kWh***"
                )
        with wcol2:
            if best_3h_tom:
                st.info(
                    f"**{get_text('best_3h_window', lang)}:**\n\n"
                    f"### ⏰ {best_3h_tom['start']:02d}:00 – {best_3h_tom['end']:02d}:00 Uhr\n"
                    f"*Durchschnittlicher Börsenpreis: **{best_3h_tom['avg_price']:.2f} ct/kWh***"
                )
    else:
        st.markdown(
            "ℹ️ *Die offiziellen EPEX-Day-Ahead-Auktionsergebnisse für morgen werden täglich gegen 12:45–13:00 Uhr veröffentlicht.*"
            if lang == "de" else
            "ℹ️ *Official EPEX Day-Ahead auction results for tomorrow are published daily between 12:45 and 13:00 CET.*"
        )

st.markdown("---")

# Price Timeline & Traffic-Light Chart
st.subheader("📊 " + get_text("timeline_header", lang))
st.caption(get_text("timeline_help", lang))

# Combine today and tomorrow for timeline display
display_df = market_df[market_df["date_berlin"].isin([today_date, tomorrow_date])].copy()

if not display_df.empty:
    # Compute relative quantile thresholds (lower 33% = green, upper 33% = red)
    q33 = display_df["price_ct_kwh"].quantile(0.33)
    q66 = display_df["price_ct_kwh"].quantile(0.66)

    def assign_color(val):
        if val <= q33:
            return "#10b981"  # Green
        elif val <= q66:
            return "#f59e0b"  # Yellow
        else:
            return "#ef4444"  # Red

    colors = [assign_color(v) for v in display_df["price_ct_kwh"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[dt.strftime("%d.%m %H:00") for dt in display_df["dt_berlin"]],
        y=display_df["price_ct_kwh"],
        marker_color=colors,
        text=[f"{v:.1f} ct" for v in display_df["price_ct_kwh"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Preis: %{y:.2f} ct/kWh<br>Börse: %{customdata:.1f} EUR/MWh<extra></extra>",
        customdata=display_df["price_eur_mwh"],
    ))

    # Add reference average line
    fig.add_hline(
        y=today_avg,
        line_dash="dot",
        line_color="#94a3b8",
        annotation_text=f"Tagesschnitt ({today_avg:.1f} ct)",
        annotation_position="top left",
    )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(15, 23, 42, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=20, t=30, b=40),
        yaxis=dict(title="Börsenstrompreis (ct/kWh)", zeroline=True, zerolinecolor="#64748b"),
        xaxis=dict(title="Uhrzeit (Berlin)", tickangle=-45),
        height=420,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Explanation underneath chart
    st.markdown(f"""
    **Erläuterung der Preiskategorien:**
    - 🟢 **{get_text('green_cat', lang)} (unter {q33:.1f} ct/kWh)**: Ausgezeichnete Zeitfenster für stromintensive Haushaltsgeräte (Waschmaschine, Spülmaschine, Wärmepumpen-Vorlauf).
    - 🟡 **{get_text('yellow_cat', lang)} ({q33:.1f} – {q66:.1f} ct/kWh)**: Normaler Preisbereich.
    - 🔴 **{get_text('red_cat', lang)} (über {q66:.1f} ct/kWh)**: Teure Spitzenlastzeiten. Große Verbraucher möglichst meiden oder verschieben.
    """)

# Market Context & Drivers
st.markdown("---")
st.subheader("🔍 " + get_text("plain_explanation_header", lang))

wind_current = latest_valid.get("wind_total_mwh")
solar_current = latest_valid.get("solar_mwh")
load_current = latest_valid.get("load_mwh")

explanations = []
if wind_current and wind_current > 20000:
    explanations.append(f"🌬️ **Hohe Windeinspeisung ({wind_current:,.0f} MW):** {get_text('explanation_wind_high', lang)}")
if solar_current and solar_current > 15000:
    explanations.append(f"☀️ **Starke Solareinspeisung ({solar_current:,.0f} MW):** {get_text('explanation_solar_peak', lang)}")

cur_hour = now_berlin.hour
if 17 <= cur_hour <= 21:
    explanations.append(f"🌆 **Abendliche Verbrauchsspitze:** {get_text('explanation_evening_peak', lang)}")

if not explanations:
    explanations.append(f"⚖️ **Ausgeglichene Marktlage:** {get_text('explanation_balanced', lang)}")

for exp in explanations:
    st.info(exp)

st.caption("ℹ️ *Hinweis: Diese Erläuterungen stellen beobachtete Korrelationen dar, keine rechtlich bindenden Kausalitätsbeweise.*")
