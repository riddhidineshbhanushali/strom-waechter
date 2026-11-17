"""
Database management for Strom-Wächter.
SQLite schema definition, connection management, queries, and persistence.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
import pandas as pd

from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with WAL journal mode enabled."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes all database tables and indexes."""
    conn = get_connection(db_path)
    try:
        with conn:
            # 1. Market Data (Electricity prices, generation, load)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp_utc TEXT PRIMARY KEY,
                timestamp_berlin TEXT NOT NULL,
                price_eur_mwh REAL,
                price_ct_kwh REAL,
                solar_mwh REAL,
                wind_onshore_mwh REAL,
                wind_offshore_mwh REAL,
                wind_total_mwh REAL,
                load_mwh REAL,
                total_generation_mwh REAL,
                residual_load_mwh REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_berlin ON market_data (timestamp_berlin);
            """)

            # 2. Weather Data (Historical & Forecast)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS weather_data (
                timestamp_utc TEXT PRIMARY KEY,
                timestamp_berlin TEXT NOT NULL,
                temperature_c REAL,
                wind_speed_ms REAL,
                solar_radiation_wm2 REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. Forecasts
            conn.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_issue_time_utc TEXT NOT NULL,
                target_time_utc TEXT NOT NULL,
                target_time_berlin TEXT NOT NULL,
                model_name TEXT NOT NULL,
                predicted_price_ct_kwh REAL NOT NULL,
                lower_bound_ct_kwh REAL,
                upper_bound_ct_kwh REAL,
                is_published_market_price INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(target_time_utc, model_name, forecast_issue_time_utc)
            );
            """)

            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_forecasts_target ON forecasts (target_time_utc, model_name);
            """)

            # 4. Model Evaluations
            conn.execute("""
            CREATE TABLE IF NOT EXISTS model_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_time_utc TEXT NOT NULL,
                model_name TEXT NOT NULL,
                mae REAL NOT NULL,
                rmse REAL NOT NULL,
                samples_count INTEGER NOT NULL,
                is_selected INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 5. Price Anomalies
            conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT UNIQUE NOT NULL,
                timestamp_berlin TEXT NOT NULL,
                price_ct_kwh REAL NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity_score REAL,
                z_score REAL,
                wind_total_mwh REAL,
                solar_mwh REAL,
                load_mwh REAL,
                explanation TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)

            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_ts ON anomalies (timestamp_utc);
            """)

            # 6. Pipeline Run Logs
            conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time_utc TEXT NOT NULL,
                status TEXT NOT NULL,
                records_ingested INTEGER DEFAULT 0,
                details TEXT,
                last_successful_update TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
        logger.info("Database initialized successfully at %s", db_path or DB_PATH)
    finally:
        conn.close()


def upsert_market_data(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    """
    Upserts a DataFrame of market observations into SQLite.
    Returns the number of rows inserted or updated.
    """
    if df.empty:
        return 0

    required_cols = ["timestamp_utc", "timestamp_berlin"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column in market_data: {col}")

    conn = get_connection(db_path)
    inserted = 0
    try:
        with conn:
            for _, row in df.iterrows():
                conn.execute("""
                INSERT INTO market_data (
                    timestamp_utc, timestamp_berlin, price_eur_mwh, price_ct_kwh,
                    solar_mwh, wind_onshore_mwh, wind_offshore_mwh, wind_total_mwh,
                    load_mwh, total_generation_mwh, residual_load_mwh
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(timestamp_utc) DO UPDATE SET
                    timestamp_berlin = excluded.timestamp_berlin,
                    price_eur_mwh = COALESCE(excluded.price_eur_mwh, market_data.price_eur_mwh),
                    price_ct_kwh = COALESCE(excluded.price_ct_kwh, market_data.price_ct_kwh),
                    solar_mwh = COALESCE(excluded.solar_mwh, market_data.solar_mwh),
                    wind_onshore_mwh = COALESCE(excluded.wind_onshore_mwh, market_data.wind_onshore_mwh),
                    wind_offshore_mwh = COALESCE(excluded.wind_offshore_mwh, market_data.wind_offshore_mwh),
                    wind_total_mwh = COALESCE(excluded.wind_total_mwh, market_data.wind_total_mwh),
                    load_mwh = COALESCE(excluded.load_mwh, market_data.load_mwh),
                    total_generation_mwh = COALESCE(excluded.total_generation_mwh, market_data.total_generation_mwh),
                    residual_load_mwh = COALESCE(excluded.residual_load_mwh, market_data.residual_load_mwh);
                """, (
                    str(row["timestamp_utc"]),
                    str(row["timestamp_berlin"]),
                    row.get("price_eur_mwh"),
                    row.get("price_ct_kwh"),
                    row.get("solar_mwh"),
                    row.get("wind_onshore_mwh"),
                    row.get("wind_offshore_mwh"),
                    row.get("wind_total_mwh"),
                    row.get("load_mwh"),
                    row.get("total_generation_mwh"),
                    row.get("residual_load_mwh"),
                ))
                inserted += 1
        return inserted
    finally:
        conn.close()


def load_market_data(
    start_utc: Optional[str] = None,
    end_utc: Optional[str] = None,
    limit: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Loads market data within an optional UTC date range as a pandas DataFrame."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM market_data WHERE 1=1"
        params: list[Any] = []
        if start_utc:
            query += " AND timestamp_utc >= ?"
            params.append(start_utc)
        if end_utc:
            query += " AND timestamp_utc <= ?"
            params.append(end_utc)
        query += " ORDER BY timestamp_utc ASC"
        if limit:
            query += f" LIMIT {int(limit)}"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()


def get_latest_market_timestamp(db_path: Optional[Path] = None) -> Optional[str]:
    """Returns the latest timestamp_utc recorded in market_data."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT MAX(timestamp_utc) as max_ts FROM market_data WHERE price_ct_kwh IS NOT NULL"
        ).fetchone()
        return row["max_ts"] if row and row["max_ts"] else None
    finally:
        conn.close()


def save_forecasts(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    """Saves generated forecasts to the forecasts table."""
    if df.empty:
        return 0
    conn = get_connection(db_path)
    saved = 0
    try:
        with conn:
            for _, row in df.iterrows():
                conn.execute("""
                INSERT OR REPLACE INTO forecasts (
                    forecast_issue_time_utc, target_time_utc, target_time_berlin,
                    model_name, predicted_price_ct_kwh, lower_bound_ct_kwh,
                    upper_bound_ct_kwh, is_published_market_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row["forecast_issue_time_utc"]),
                    str(row["target_time_utc"]),
                    str(row["target_time_berlin"]),
                    str(row["model_name"]),
                    float(row["predicted_price_ct_kwh"]),
                    float(row["lower_bound_ct_kwh"]) if pd.notnull(row.get("lower_bound_ct_kwh")) else None,
                    float(row["upper_bound_ct_kwh"]) if pd.notnull(row.get("upper_bound_ct_kwh")) else None,
                    int(row.get("is_published_market_price", 0)),
                ))
                saved += 1
        return saved
    finally:
        conn.close()


def load_latest_forecasts(model_name: Optional[str] = None, db_path: Optional[Path] = None) -> pd.DataFrame:
    """Loads the most recently computed forecast for each future target timestamp."""
    conn = get_connection(db_path)
    try:
        query = """
        SELECT f.* FROM forecasts f
        INNER JOIN (
            SELECT target_time_utc, MAX(forecast_issue_time_utc) as max_issue
            FROM forecasts
            GROUP BY target_time_utc
        ) latest ON f.target_time_utc = latest.target_time_utc
                 AND f.forecast_issue_time_utc = latest.max_issue
        """
        params: list[Any] = []
        if model_name:
            query += " WHERE f.model_name = ?"
            params.append(model_name)
        query += " ORDER BY f.target_time_utc ASC"
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def save_model_evaluations(eval_rows: List[Dict[str, Any]], db_path: Optional[Path] = None) -> None:
    """Records evaluation metrics for forecasting models."""
    conn = get_connection(db_path)
    try:
        with conn:
            for row in eval_rows:
                conn.execute("""
                INSERT INTO model_evaluations (
                    evaluation_time_utc, model_name, mae, rmse, samples_count, is_selected, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["evaluation_time_utc"],
                    row["model_name"],
                    float(row["mae"]),
                    float(row["rmse"]),
                    int(row["samples_count"]),
                    int(row.get("is_selected", 0)),
                    row.get("notes", ""),
                ))
    finally:
        conn.close()


def load_latest_model_evaluations(db_path: Optional[Path] = None) -> pd.DataFrame:
    """Loads the latest evaluation summary for each model."""
    conn = get_connection(db_path)
    try:
        query = """
        SELECT e.* FROM model_evaluations e
        INNER JOIN (
            SELECT model_name, MAX(evaluation_time_utc) as max_eval
            FROM model_evaluations
            GROUP BY model_name
        ) latest ON e.model_name = latest.model_name
                 AND e.evaluation_time_utc = latest.max_eval
        ORDER BY e.mae ASC
        """
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def save_anomalies(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    """Saves detected anomalies into the anomalies table."""
    if df.empty:
        return 0
    conn = get_connection(db_path)
    saved = 0
    try:
        with conn:
            for _, row in df.iterrows():
                conn.execute("""
                INSERT OR REPLACE INTO anomalies (
                    timestamp_utc, timestamp_berlin, price_ct_kwh, anomaly_type,
                    severity_score, z_score, wind_total_mwh, solar_mwh, load_mwh, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row["timestamp_utc"]),
                    str(row["timestamp_berlin"]),
                    float(row["price_ct_kwh"]),
                    str(row["anomaly_type"]),
                    float(row.get("severity_score", 1.0)),
                    float(row.get("z_score", 0.0)),
                    float(row.get("wind_total_mwh")) if pd.notnull(row.get("wind_total_mwh")) else None,
                    float(row.get("solar_mwh")) if pd.notnull(row.get("solar_mwh")) else None,
                    float(row.get("load_mwh")) if pd.notnull(row.get("load_mwh")) else None,
                    str(row.get("explanation", "")),
                ))
                saved += 1
        return saved
    finally:
        conn.close()


def load_anomalies(limit: int = 100, db_path: Optional[Path] = None) -> pd.DataFrame:
    """Loads recorded price anomalies ordered by timestamp descending."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM anomalies ORDER BY timestamp_utc DESC LIMIT ?"
        return pd.read_sql_query(query, conn, params=(limit,))
    finally:
        conn.close()


def log_pipeline_run(
    status: str,
    records_ingested: int,
    details: str,
    last_successful: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Logs the execution result of the data pipeline."""
    conn = get_connection(db_path)
    try:
        with conn:
            now_utc = datetime.now(timezone.utc).isoformat()
            conn.execute("""
            INSERT INTO pipeline_logs (run_time_utc, status, records_ingested, details, last_successful_update)
            VALUES (?, ?, ?, ?, ?)
            """, (now_utc, status, records_ingested, details, last_successful or now_utc))
    finally:
        conn.close()


def get_latest_pipeline_status(db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the most recent pipeline log entry."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM pipeline_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
