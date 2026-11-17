"""
Central configuration for Strom-Wächter.
All API endpoints, SMARD filter IDs, tariff components, and defaults are centralized here.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "strom_waechter.db"

# Timezone configurations
TIMEZONE_BERLIN = "Europe/Berlin"
TIMEZONE_UTC = "UTC"

# Official Bundesnetzagentur SMARD API Configuration
# Base API URL: https://www.smard.de/app/chart_data
SMARD_BASE_URL = "https://www.smard.de/app/chart_data"
SMARD_REGION_DE = "DE"
SMARD_RESOLUTION_HOUR = "hour"

# Verified SMARD Filter IDs
# Verified against official SMARD API chart_data endpoints:
# 4169: Day-Ahead electricity wholesale price (EUR/MWh)
# 4069: Photovoltaik generation (MWh)
# 4068: Wind Onshore generation (MWh)
# 4067: Wind Offshore generation (MWh)
# 410:  Realisierter Stromverbrauch / Total Grid Load (MWh)
# 4071: Gesamte Erzeugung / Total Generation (MWh)
# 4359: Residuallast / Residual Load (MWh)
SMARD_FILTERS = {
    "day_ahead_price": 4169,
    "solar": 4069,
    "wind_onshore": 4068,
    "wind_offshore": 4067,
    "grid_load": 410,
    "total_generation": 4071,
    "residual_load": 4359,
}

# Unit labels
UNITS = {
    "day_ahead_price": "EUR/MWh",
    "price_ct_kwh": "ct/kWh",
    "solar": "MWh",
    "wind_onshore": "MWh",
    "wind_offshore": "MWh",
    "wind_total": "MWh",
    "grid_load": "MWh",
    "total_generation": "MWh",
    "residual_load": "MWh",
}

# Open-Meteo Configuration (Free weather API for Germany)
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GERMANY_COORDINATES = {
    "latitude": 51.1657,
    "longitude": 10.4515,
}
OPEN_METEO_VARS = [
    "temperature_2m",
    "wind_speed_10m",
    "direct_normal_irradiance",
]

# German Electricity Retail Tariff Components (Defaults for German households in 2024/2026)
# Note: Final household prices consist of:
# Wholesale Price + Supplier Markup + Grid Fees + Concession Fee + Electricity Tax + Levies + 19% VAT
@dataclass
class GermanTariffDefaults:
    # Tax and Levies (ct/kWh)
    vat_rate: float = 0.19                 # 19% Umsatzsteuer
    electricity_tax: float = 2.05          # Stromsteuer (ct/kWh)
    grid_fee: float = 9.50                 # Netzentgelte (average German distribution grid, ct/kWh)
    concession_levy: float = 1.66          # Konzessionsabgabe (ct/kWh)
    kwkg_levy: float = 0.28                # KWKG-Umlage (ct/kWh)
    offshore_levy: float = 0.66            # Offshore-Netzumlage (ct/kWh)
    
    # Dynamic Tariff Specifics
    dynamic_markup: float = 1.50           # Supplier margin / pass-through handling (ct/kWh)
    dynamic_monthly_base_fee: float = 5.99 # Monthly base fee (EUR/month)
    
    # Fixed Tariff Reference Benchmark
    fixed_tariff_rate: float = 32.50       # All-inclusive fixed price (ct/kWh)
    fixed_monthly_base_fee: float = 11.90  # Fixed monthly base fee (EUR/month)

    @property
    def total_statutory_levies_ct_kwh(self) -> float:
        """Sum of taxes, grid fees and levies excluding wholesale price and VAT."""
        return (
            self.electricity_tax
            + self.grid_fee
            + self.concession_levy
            + self.kwkg_levy
            + self.offshore_levy
        )

# Predefined Household Consumption Profiles (relative hourly weights summing to 1.0)
def get_default_usage_profiles() -> Dict[str, list[float]]:
    """
    Returns 24-hour relative weight vectors for:
    - Evening-heavy: typical commuter household (peaks 18-22)
    - Flexible: shifted laundry/appliances to solar peak (11-15) and overnight (01-04)
    - EV Charging: high overnight charging (23-05) plus light evening usage
    """
    # 24 hours: 00:00 to 23:00
    evening_heavy = [
        0.02, 0.02, 0.01, 0.01, 0.02, 0.03,  # 00-05
        0.05, 0.06, 0.05, 0.04, 0.03, 0.03,  # 06-11
        0.04, 0.04, 0.03, 0.04, 0.05, 0.07,  # 12-17
        0.10, 0.11, 0.09, 0.08, 0.05, 0.03,  # 18-23
    ]
    # Normalize
    s = sum(evening_heavy)
    evening_heavy = [w / s for w in evening_heavy]

    flexible = [
        0.04, 0.04, 0.04, 0.03, 0.02, 0.02,  # 00-05 (some night shifting)
        0.03, 0.04, 0.04, 0.05, 0.08, 0.09,  # 06-11 (lunch/solar)
        0.10, 0.09, 0.08, 0.06, 0.05, 0.04,  # 12-17 (afternoon solar)
        0.04, 0.04, 0.03, 0.03, 0.02, 0.02,  # 18-23 (avoiding evening peak)
    ]
    s = sum(flexible)
    flexible = [w / s for w in flexible]

    ev_charging = [
        0.09, 0.09, 0.09, 0.08, 0.08, 0.04,  # 00-05 (overnight EV charging)
        0.03, 0.03, 0.02, 0.02, 0.02, 0.02,  # 06-11
        0.03, 0.03, 0.03, 0.03, 0.03, 0.04,  # 12-17
        0.05, 0.06, 0.05, 0.04, 0.04, 0.06,  # 18-23
    ]
    s = sum(ev_charging)
    ev_charging = [w / s for w in ev_charging]

    return {
        "evening_heavy": evening_heavy,
        "flexible": flexible,
        "ev_charging": ev_charging,
    }

# Anomaly Detection Settings
ANOMALY_ZSCORE_THRESHOLD = 2.5
ANOMALY_SPIKE_RATE_THRESHOLD_CT = 12.0  # >12 ct/kWh hourly jump
