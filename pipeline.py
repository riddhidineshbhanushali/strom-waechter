"""
Automated Data Pipeline for Strom-Wächter.
Orchestrates:
FETCH -> CLEAN -> VALIDATE -> STORE -> GENERATE FEATURES -> FORECAST -> DETECT ANOMALIES.

Supports both full backfill (multi-year) and fast incremental runs.
Logs every run with structured status and execution metrics.
"""

import sys
import logging
import argparse
from datetime import datetime, timezone
import pandas as pd

from config import DB_PATH
from db import (
    init_db,
    upsert_market_data,
    load_market_data,
    get_latest_market_timestamp,
    log_pipeline_run,
)
from fetch import fetch_all_smard_data, OpenMeteoClient
from clean import validate_and_clean_raw_records, add_berlin_timestamps
from forecast import generate_upcoming_forecasts
from anomalies import detect_price_anomalies

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("strom_waechter_pipeline")


def run_pipeline(
    max_weeks: int = 52,
    incremental: bool = True,
    force_forecast: bool = True,
) -> bool:
    """
    Executes the end-to-end data pipeline.
    Returns True if execution succeeded, False otherwise.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("Starting Strom-Wächter data pipeline execution...")

    # 1. Initialize SQLite Database
    init_db()

    # 2. Determine incremental cutoff if enabled
    since_ts_ms = None
    if incremental:
        latest_utc = get_latest_market_timestamp()
        if latest_utc:
            dt_latest = datetime.fromisoformat(latest_utc.replace("Z", "+00:00"))
            since_ts_ms = int(dt_latest.timestamp() * 1000)
            logger.info("Incremental update mode active. Latest DB record: %s", latest_utc)

    # 3. FETCH: Ingest SMARD data
    try:
        raw_df = fetch_all_smard_data(
            max_weeks=max_weeks,
            since_timestamp_ms=since_ts_ms,
        )
    except Exception as exc:
        logger.error("Failed during SMARD API ingestion: %s", exc)
        log_pipeline_run("ERROR", 0, f"API fetch failed: {exc}")
        return False

    records_ingested = 0
    if not raw_df.empty:
        # 4. CLEAN & VALIDATE: Timezones, 23h/25h DST, unit conversions, bounds
        logger.info("Cleaning and validating raw market observations...")
        cleaned_df = validate_and_clean_raw_records(raw_df)
        cleaned_df = add_berlin_timestamps(cleaned_df)

        # 5. STORE: Upsert into SQLite
        logger.info("Upserting cleaned records into SQLite database...")
        records_ingested = upsert_market_data(cleaned_df)
        logger.info("Successfully upserted %d records.", records_ingested)
    else:
        logger.info("No new market records fetched (already up to date or API offline).")

    # 6. Load comprehensive history from DB for modeling and anomaly detection
    full_market_df = load_market_data(limit=8760)
    if full_market_df.empty:
        logger.warning("Market database is empty. Cannot run forecasting or anomaly detection.")
        log_pipeline_run("WARNING", records_ingested, "Database empty after fetch.")
        return False

    # 7. FORECAST: Train models, benchmark, and generate upcoming predictions
    if force_forecast or records_ingested > 0:
        logger.info("Running forecasting engine and model evaluations...")
        try:
            forecasts = generate_upcoming_forecasts(full_market_df, horizon_hours=48)
            logger.info("Generated %d upcoming forecast / market price hours.", len(forecasts))
        except Exception as exc:
            logger.error("Forecasting engine encounter an error: %s", exc)

    # 8. ANOMALY DETECTION: Detect negative prices, spikes, and jumps
    logger.info("Running robust anomaly detection engine...")
    try:
        anomalies = detect_price_anomalies(full_market_df)
        logger.info("Identified and logged %d price anomalies.", len(anomalies))
    except Exception as exc:
        logger.error("Anomaly detection failed: %s", exc)

    # 9. Record Pipeline Success Log
    now_utc_str = datetime.now(timezone.utc).isoformat()
    log_pipeline_run(
        status="SUCCESS",
        records_ingested=records_ingested,
        details=f"Pipeline completed successfully. Total records in DB: {len(full_market_df)}",
        last_successful=now_utc_str,
    )
    logger.info("Pipeline execution completed in %.2f seconds.", (datetime.now(timezone.utc) - start_time).total_seconds())
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strom-Wächter Data Pipeline Runner")
    parser.add_argument("--weeks", type=int, default=12, help="Number of weekly chunks to fetch (default: 12)")
    parser.add_argument("--full", action="store_true", help="Force full historical reload instead of incremental")
    args = parser.parse_args()

    success = run_pipeline(
        max_weeks=args.weeks,
        incremental=not args.full,
    )
    sys.exit(0 if success else 1)
