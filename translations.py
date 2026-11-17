"""
Internationalization and Translation Dictionary for Strom-Wächter.
Supports German (Default) and English with plain-language explanations of energy concepts.
"""

TRANSLATIONS = {
    "de": {
        # App Header & Navigation
        "app_title": "Strom-Wächter",
        "app_tagline": "Wisse, wann Strom günstig ist. Smarte Energieentscheidungen für dein Zuhause.",
        "language_switch": "Sprache / Language",
        "theme_label": "Design-Modus",
        "theme_dark": "Dunkel (Tech-Navy)",
        "theme_light": "Hell (Clean)",
        "nav_home": "Tages-Empfehlung",
        "nav_savings": "Ersparnis-Rechner",
        "nav_anomalies": "Preis-Anomalien",
        "nav_transparency": "Modell-Transparenz",
        "last_update": "Stand der Marktdaten",
        "never_updated": "Noch keine Daten geladen",
        "data_freshness": "Daten-Aktualität",
        "status_live": "Echtzeit-Synchronisiert",
        "status_warning": "Verzögerte Daten",

        # Metric Badges
        "current_price": "Aktueller Börsenpreis",
        "today_avg": "Heutiger Durchschnitt",
        "tomorrow_avg": "Morgiger Durchschnitt",
        "price_level": "Preiseinstufung",
        "cheaper_than_usual": "Günstiger als üblich",
        "normal_price": "Normaler Preisbereich",
        "expensive_than_usual": "Teurer als üblich",
        "tomorrow_not_yet_published": "Auktionsergebnis für morgen ab ca. 13:00 Uhr verfügbar",

        # Daily Advice Page
        "best_windows_header": "Günstigste Zeitfenster für Haushaltsgeräte",
        "best_2h_window": "Optimal für Waschmaschine (2 Std.)",
        "best_3h_window": "Optimal für Spülmaschine / Trockner (3 Std.)",
        "timeline_header": "Stündlicher Preisverlauf & Ampelsystem",
        "timeline_help": "Grün: Günstig (unteres Drittel) | Gelb: Moderat | Rot: Teuer (Spitzenlast)",
        "green_cat": "Günstig",
        "yellow_cat": "Mittel",
        "red_cat": "Teuer",
        "plain_explanation_header": "Marktlage & Preistreiber",
        "explanation_wind_high": "Hohe Windeinspeisung senkt aktuell das Preisniveau spürbar.",
        "explanation_solar_peak": "Die Photovoltaik-Mittagssonne drückt den Preis zur Mittagszeit.",
        "explanation_evening_peak": "Die abendliche Spitzenlast (18–21 Uhr) führt zu typischen Preisspitzen.",
        "explanation_balanced": "Ausgeglichenes Verhältnis von Erzeugung und Verbrauch.",

        # Savings Calculator
        "calc_header": "Dynamischer Tarif vs. Fester Tarif",
        "calc_intro": "Vergleiche deinen aktuellen Festpreistarif mit einem dynamischen Börsenstromtarif anhand echter stündlicher Marktdaten.",
        "input_consumption": "Jahresverbrauch (kWh)",
        "input_fixed_rate": "Fester Arbeitspreis (ct/kWh)",
        "input_fixed_base": "Feste Grundgebühr (€/Monat)",
        "input_dynamic_markup": "Anbieter-Aufschlag (ct/kWh)",
        "input_dynamic_base": "Dynamische Grundgebühr (€/Monat)",
        "input_grid_fee": "Netzentgelte (ct/kWh)",
        "profile_label": "Verbrauchsprofil deines Haushalts",
        "profile_evening": "Standard / Berufstätig (Schwerpunkt abends)",
        "profile_flexible": "Flexibel (Geräte mittags / nachts)",
        "profile_ev": "E-Auto / Wärmepumpe (Nachtladung)",
        "calc_results_title": "Ergebnis des Kostenvergleichs",
        "annual_fixed_cost": "Kosten Festpreis",
        "annual_dynamic_cost": "Kosten Dynamisch",
        "potential_savings": "Geschätzte Ersparnis",
        "effective_rate_dynamic": "Effektiver dynamischer Endpreis",
        "effective_rate_fixed": "Effektiver Festpreis",
        "exposure_metrics_title": "Markt- und Risikoanalyse",
        "negative_hours_label": "Stunden mit Negativpreisen",
        "peak_hours_label": "Stunden über 30 ct/kWh",
        "max_price_label": "Höchster Börsenpreis",
        "min_price_label": "Tiefster Börsenpreis",
        "monthly_chart_title": "Monatlicher Kostenvergleich",
        "disclaimer_text": (
            "Hinweis: Dies ist eine Modellrechnung basierend auf historischen Börsenpreisen, "
            "gesetzlichen Abgaben (Netzentgelte, Stromsteuer, Umlagen) und 19% Mehrwertsteuer. "
            "Reale Ersparnisse hängen von deinem tatsächlichen Vertrag und individuellem Verbrauchsverhalten ab."
        ),

        # Anomalies Page
        "anomalies_header": "Erkennung von Preisanomalien",
        "anomalies_intro": "Statistische Erkennung extremer Ausschläge, negativer Preise und rapider Preissprünge.",
        "filter_type": "Anomalie-Typ filtern",
        "all_types": "Alle Typen",
        "type_negative": "Negativer Preis (< 0 ct/kWh)",
        "type_extreme": "Extremer Preisausschlag (Z-Score > 2.5)",
        "type_jump": "Rapider Sprung (> 12 ct/kWh/h)",
        "col_time": "Zeitpunkt (Berlin)",
        "col_price": "Preis (ct/kWh)",
        "col_type": "Typ",
        "col_wind": "Wind (MW)",
        "col_solar": "Solar (MW)",
        "col_load": "Netzlast (MW)",
        "col_explanation": "Mögliche Faktoren",

        # Model Transparency Page
        "transparency_header": "Modell-Transparenz & Prognosegüte",
        "transparency_intro": "Offene Offenlegung aller Trainingsdaten, Fehlermaße und Modellentscheidungen.",
        "data_coverage_header": "Datenabdeckung & Qualität",
        "metric_total_records": "Erfasste Stunden",
        "metric_missing_pct": "Fehlende Werte",
        "metric_selected_model": "Aktives Vorhersagemodell",
        "model_comparison_header": "Modell-Benchmarking im Backtesting",
        "mae_explanation": (
            "MAE (Mittlerer absoluter Fehler): Gibt an, um wie viele ct/kWh die Vorhersage im Schnitt daneben lag. "
            "Kleinere Werte sind besser."
        ),
        "rmse_explanation": (
            "RMSE (Wurzel des mittleren quadratischen Fehlers): Bestraft größere Vorhersagefehler überproportional stark."
        ),
        "col_model": "Modell",
        "col_mae": "MAE (ct/kWh)",
        "col_rmse": "RMSE (ct/kWh)",
        "col_selected": "Ausgewählt",
        "chart_forecast_vs_actual": "Modellprognose vs. Tatsächlicher Marktpreis",
    },
    "en": {
        # App Header & Navigation
        "app_title": "Strom-Wächter",
        "app_tagline": "Know when electricity is cheap. Make smarter energy decisions for your home.",
        "language_switch": "Language / Sprache",
        "theme_label": "Display Theme",
        "theme_dark": "Dark (Tech-Navy)",
        "theme_light": "Light (Clean)",
        "nav_home": "Daily Advice",
        "nav_savings": "Savings Calculator",
        "nav_anomalies": "Price Anomalies",
        "nav_transparency": "Model Transparency",
        "last_update": "Market Data Freshness",
        "never_updated": "No data retrieved yet",
        "data_freshness": "Data Freshness",
        "status_live": "Real-time Synced",
        "status_warning": "Delayed Data",

        # Metric Badges
        "current_price": "Current Wholesale Price",
        "today_avg": "Today's Average",
        "tomorrow_avg": "Tomorrow's Average",
        "price_level": "Price Category",
        "cheaper_than_usual": "Cheaper than usual",
        "normal_price": "Normal price range",
        "expensive_than_usual": "More expensive than usual",
        "tomorrow_not_yet_published": "Auction results for tomorrow available around 13:00 CET",

        # Daily Advice Page
        "best_windows_header": "Optimal Appliance Time Windows",
        "best_2h_window": "Best for Washing Machine (2h)",
        "best_3h_window": "Best for Dishwasher / Dryer (3h)",
        "timeline_header": "Hourly Timeline & Traffic Light System",
        "timeline_help": "Green: Cheap (lower third) | Yellow: Moderate | Red: Expensive (peak demand)",
        "green_cat": "Cheap",
        "yellow_cat": "Moderate",
        "red_cat": "Expensive",
        "plain_explanation_header": "Market Drivers & Context",
        "explanation_wind_high": "Strong wind generation is currently depressing market prices.",
        "explanation_solar_peak": "Midday solar power is driving prices down during lunch hours.",
        "explanation_evening_peak": "Evening residential demand peak (18:00–21:00) causes typical price peaks.",
        "explanation_balanced": "Balanced supply and demand balance across the grid.",

        # Savings Calculator
        "calc_header": "Dynamic Tariff vs. Fixed Tariff",
        "calc_intro": "Compare your current fixed electricity contract against a dynamic spot-market tariff using genuine empirical hourly prices.",
        "input_consumption": "Annual Consumption (kWh)",
        "input_fixed_rate": "Fixed Working Price (ct/kWh)",
        "input_fixed_base": "Fixed Base Fee (€/month)",
        "input_dynamic_markup": "Supplier Markup (ct/kWh)",
        "input_dynamic_base": "Dynamic Base Fee (€/month)",
        "input_grid_fee": "Grid Fees / Netzentgelte (ct/kWh)",
        "profile_label": "Household Usage Profile",
        "profile_evening": "Standard / Commuter (Evening Peak)",
        "profile_flexible": "Flexible (Appliances midday / overnight)",
        "profile_ev": "EV / Heat Pump (Night charging)",
        "calc_results_title": "Cost Comparison Results",
        "annual_fixed_cost": "Fixed Tariff Total",
        "annual_dynamic_cost": "Dynamic Tariff Total",
        "potential_savings": "Estimated Potential Savings",
        "effective_rate_dynamic": "Effective Dynamic Retail Rate",
        "effective_rate_fixed": "Effective Fixed Rate",
        "exposure_metrics_title": "Market & Risk Exposure",
        "negative_hours_label": "Negative Price Hours",
        "peak_hours_label": "Hours Above 30 ct/kWh",
        "max_price_label": "Maximum Wholesale Price",
        "min_price_label": "Minimum Wholesale Price",
        "monthly_chart_title": "Monthly Cost Comparison",
        "disclaimer_text": (
            "Notice: This simulation is an estimate based on historical wholesale prices, "
            "statutory charges (grid fees, electricity tax, levies), and 19% German VAT. "
            "Actual household savings depend strictly on your energy contract and individual consumption timing."
        ),

        # Anomalies Page
        "anomalies_header": "Price Anomaly Detection",
        "anomalies_intro": "Statistical detection of price dips below zero, extreme spikes, and rapid hourly price jumps.",
        "filter_type": "Filter Anomaly Type",
        "all_types": "All Types",
        "type_negative": "Negative Price (< 0 ct/kWh)",
        "type_extreme": "Extreme Price Spike (Z-Score > 2.5)",
        "type_jump": "Rapid Hourly Jump (> 12 ct/kWh/h)",
        "col_time": "Timestamp (Berlin)",
        "col_price": "Price (ct/kWh)",
        "col_type": "Type",
        "col_wind": "Wind (MW)",
        "col_solar": "Solar (MW)",
        "col_load": "Grid Load (MW)",
        "col_explanation": "Contextual Factors",

        # Model Transparency Page
        "transparency_header": "Model Transparency & Forecasting Accuracy",
        "transparency_intro": "Honest disclosure of model architectures, backtested errors, and data coverage.",
        "data_coverage_header": "Data Coverage & Quality",
        "metric_total_records": "Recorded Hours",
        "metric_missing_pct": "Missing Values",
        "metric_selected_model": "Active Forecast Model",
        "model_comparison_header": "Model Benchmarking & Backtesting",
        "mae_explanation": (
            "MAE (Mean Absolute Error): Average discrepancy in ct/kWh between forecast and actual price. "
            "Lower numbers represent higher accuracy."
        ),
        "rmse_explanation": (
            "RMSE (Root Mean Squared Error): Measures prediction error, penalizing larger outliers more severely."
        ),
        "col_model": "Model",
        "col_mae": "MAE (ct/kWh)",
        "col_rmse": "RMSE (ct/kWh)",
        "col_selected": "Selected",
        "chart_forecast_vs_actual": "Model Forecast vs. Actual Market Clearing Price",
    },
}


def get_text(key: str, lang: str = "de") -> str:
    """Returns translated string for key in selected language with German fallback."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["de"]).get(key, TRANSLATIONS["de"].get(key, key))
