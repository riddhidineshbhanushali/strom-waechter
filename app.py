"""
Strom-Wächter: Main Application & Navigation Hub.
Modern energy-tech dashboard tracking German electricity market prices (SMARD),
providing daily appliance advice, dynamic tariff savings calculations,
anomaly detection, and transparent forecast benchmarking.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import zoneinfo

from config import DB_PATH, TIMEZONE_BERLIN
from db import init_db, get_latest_market_timestamp, get_latest_pipeline_status, load_market_data
from translations import get_text

# Initialize Database on startup
init_db()

# Streamlit Page Configuration
st.set_page_config(
    page_title="Strom-Wächter | German Energy Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "lang" not in st.session_state:
    st.session_state["lang"] = "de"

# Energy-Tech CSS Styling
st.markdown("""
<style>
    /* Main Background & Fonts */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top Header Bar */
    .app-header {
        background: linear-gradient(135deg, #111827 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    
    .brand-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #10b981, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    
    .brand-tagline {
        color: #94a3b8;
        font-size: 1.05rem;
    }
    
    /* Metric Cards */
    .metric-card {
        background-color: #162032;
        border: 1px solid #27354f;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 16px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #10b981;
        transform: translateY(-2px);
    }
    .metric-title {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 4px;
    }

    /* Badges */
    .badge-live {
        display: inline-block;
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-delayed {
        display: inline-block;
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Controls
with st.sidebar:
    st.markdown("### ⚡ Strom-Wächter")
    
    # Language Switcher
    lang_choice = st.radio(
        get_text("language_switch", st.session_state["lang"]),
        options=["Deutsch", "English"],
        index=0 if st.session_state["lang"] == "de" else 1,
        horizontal=True,
    )
    st.session_state["lang"] = "de" if lang_choice == "Deutsch" else "en"
    lang = st.session_state["lang"]

    st.markdown("---")
    
    # Data Freshness Indicator
    latest_ts = get_latest_market_timestamp()
    pipe_status = get_latest_pipeline_status()

    if latest_ts:
        dt_utc = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
        dt_berlin = dt_utc.astimezone(zoneinfo.ZoneInfo(TIMEZONE_BERLIN))
        freshness_str = dt_berlin.strftime("%d.%m.%Y, %H:%M Uhr")
        badge_html = f'<span class="badge-live">● {get_text("status_live", lang)}</span>'
    else:
        freshness_str = get_text("never_updated", lang)
        badge_html = f'<span class="badge-delayed">▲ {get_text("status_warning", lang)}</span>'

    st.markdown(f"**{get_text('data_freshness', lang)}**")
    st.markdown(badge_html, unsafe_allow_html=True)
    st.caption(f"{get_text('last_update', lang)}: {freshness_str}")

    st.markdown("---")
    st.markdown("#### 📖 " + ("Seitenübersicht" if lang == "de" else "Pages"))
    st.markdown("""
    - **1. Tages-Empfehlung**: Günstigste Stunden & Ampelkarte
    - **2. Ersparnis-Rechner**: Fester vs. Dynamischer Tarif
    - **3. Preis-Anomalien**: Negativpreise & Spitzen
    - **4. Modell-Transparenz**: Fehlermaße & Methodik
    """)

# Main Content Header
lang = st.session_state["lang"]
st.markdown(f"""
<div class="app-header">
    <div class="brand-title">⚡ {get_text("app_title", lang)}</div>
    <div class="brand-tagline">{get_text("app_tagline", lang)}</div>
</div>
""", unsafe_allow_html=True)

# Load Latest Observations for Executive Overview
recent_df = load_market_data(limit=168)

if recent_df.empty:
    st.info(
        "👋 Willkommen bei Strom-Wächter! Es sind aktuell noch keine Marktdaten in der Datenbank gespeichert.\n\n"
        "Führe den Datenabruf über das Terminal oder GitHub Actions aus:\n"
        "```bash\npython pipeline.py\n```"
        if lang == "de" else
        "👋 Welcome to Strom-Wächter! No market observations recorded yet in SQLite.\n\n"
        "Execute the automated pipeline via terminal or GitHub Actions:\n"
        "```bash\npython pipeline.py\n```"
    )
else:
    # Summary Key Metrics
    latest_row = recent_df.dropna(subset=["price_ct_kwh"]).iloc[-1]
    current_price = latest_row["price_ct_kwh"]
    avg_price_7d = recent_df["price_ct_kwh"].mean()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">{get_text("current_price", lang)}</div>
            <div class="metric-value">{current_price:.2f} <span style="font-size:1rem;color:#10b981;">ct/kWh</span></div>
            <div class="metric-sub">{latest_row.get("price_eur_mwh", 0):.1f} EUR/MWh</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">{get_text("today_avg", lang)}</div>
            <div class="metric-value">{avg_price_7d:.2f} <span style="font-size:1rem;color:#06b6d4;">ct/kWh</span></div>
            <div class="metric-sub">7-Tage-Referenz</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        wind_mw = latest_row.get("wind_total_mwh")
        wind_str = f"{wind_mw:,.0f} MW" if pd.notnull(wind_mw) else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Wind-Einspeisung</div>
            <div class="metric-value" style="color:#38bdf8;">{wind_str}</div>
            <div class="metric-sub">Onshore + Offshore</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        solar_mw = latest_row.get("solar_mwh")
        solar_str = f"{solar_mw:,.0f} MW" if pd.notnull(solar_mw) else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Solar-Einspeisung</div>
            <div class="metric-value" style="color:#facc15;">{solar_str}</div>
            <div class="metric-sub">Photovoltaik DE</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "👉 **Navigiere über die linke Seitenleiste zu den Modulen:**\n"
        "- **1. Tages-Empfehlung**: Detaillierte Haushalts-Stundenempfehlungen für Waschmaschine & Co.\n"
        "- **2. Ersparnis-Rechner**: Individuelle Tarif-Simulation mit echten Verbrauchsdaten.\n"
        "- **3. Preis-Anomalien**: Analyse von Negativpreisen und Preisausschlägen.\n"
        "- **4. Modell-Transparenz**: Validierungsergebnisse aller Vorhersagemodelle."
        if lang == "de" else
        "👉 **Navigate using the left sidebar to access specific pages:**\n"
        "- **1. Daily Advice**: Granular hourly appliance guidance for laundry & EV.\n"
        "- **2. Savings Calculator**: Personalized tariff cost comparison with empirical data.\n"
        "- **3. Price Anomalies**: Deep dive into negative prices and price spikes.\n"
        "- **4. Model Transparency**: Cross-validation results and forecasting errors."
    )
