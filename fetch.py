"""
Data ingestion module for Strom-Wächter.
Integrates with the official Bundesnetzagentur SMARD API and Open-Meteo API.
Implements robust retries, exponential backoff, timeouts, and incremental updates.
"""

import time
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone
import requests
import pandas as pd

from config import (
    SMARD_BASE_URL,
    SMARD_REGION_DE,
    SMARD_RESOLUTION_HOUR,
    SMARD_FILTERS,
    OPEN_METEO_BASE_URL,
    GERMANY_COORDINATES,
    OPEN_METEO_VARS,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 12.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class SMARDClient:
    """Official client for the Bundesnetzagentur SMARD chart_data API."""

    def __init__(
        self,
        base_url: str = SMARD_BASE_URL,
        region: str = SMARD_REGION_DE,
        resolution: str = SMARD_RESOLUTION_HOUR,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.region = region
        self.resolution = resolution
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Strom-Waechter-Energy-Analytics/1.0 (+https://github.com/example/strom-waechter)",
            "Accept": "application/json",
        })

    def _request_with_retry(self, url: str) -> Optional[dict]:
        """Makes an HTTP GET request with retries and exponential backoff."""
        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning("SMARD resource not found (404): %s", url)
                    return None
                else:
                    logger.warning(
                        "SMARD HTTP %s on %s (attempt %d/%d)",
                        response.status_code, url, attempt, MAX_RETRIES
                    )
            except (requests.RequestException, ValueError) as exc:
                logger.warning(
                    "SMARD request error on %s: %s (attempt %d/%d)",
                    url, exc, attempt, MAX_RETRIES
                )

            if attempt < MAX_RETRIES:
                time.sleep(backoff)
                backoff *= 2.0

        logger.error("Failed to retrieve SMARD endpoint after %d attempts: %s", MAX_RETRIES, url)
        return None

    def fetch_index(self, filter_id: int) -> List[int]:
        """
        Retrieves the list of available weekly epoch millisecond timestamps for a filter.
        URL pattern: https://www.smard.de/app/chart_data/{filter}/{region}/index_{resolution}.json
        """
        url = f"{self.base_url}/{filter_id}/{self.region}/index_{self.resolution}.json"
        data = self._request_with_retry(url)
        if not data or "timestamps" not in data:
            return []
        return sorted(data["timestamps"])

    def fetch_chunk(self, filter_id: int, timestamp: int) -> List[Tuple[int, Optional[float]]]:
        """
        Retrieves one weekly chunk of hourly data for a filter.
        URL pattern: https://www.smard.de/app/chart_data/{filter}/{region}/{filter}_{region}_{resolution}_{timestamp}.json
        Returns list of (timestamp_ms, value).
        """
        url = f"{self.base_url}/{filter_id}/{self.region}/{filter_id}_{self.region}_{self.resolution}_{timestamp}.json"
        data = self._request_with_retry(url)
        if not data or "series" not in data:
            return []
        series = []
        for point in data.get("series", []):
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                ts, val = point[0], point[1]
                series.append((int(ts), float(val) if val is not None else None))
        return series

    def fetch_filter_series(
        self,
        filter_id: int,
        max_chunks: Optional[int] = None,
        since_timestamp_ms: Optional[int] = None,
    ) -> Dict[int, Optional[float]]:
        """
        Fetches series observations for a filter across multiple weekly chunks.
        Optionally filters chunks to only those >= since_timestamp_ms (for incremental updates).
        """
        timestamps = self.fetch_index(filter_id)
        if not timestamps:
            logger.warning("No timestamp index returned for filter %s", filter_id)
            return {}

        if since_timestamp_ms is not None:
            # Keep chunks that overlap with or follow since_timestamp_ms (minus 1 week for safety)
            cutoff = since_timestamp_ms - (7 * 24 * 3600 * 1000)
            target_chunks = [t for t in timestamps if t >= cutoff]
            # Ensure at least the last 2 chunks are fetched to pick up revisions/day-ahead
            if len(target_chunks) < 2 and len(timestamps) >= 2:
                target_chunks = timestamps[-2:]
        elif max_chunks is not None:
            target_chunks = timestamps[-max_chunks:]
        else:
            target_chunks = timestamps

        results: Dict[int, Optional[float]] = {}
        for chunk_ts in target_chunks:
            chunk_data = self.fetch_chunk(filter_id, chunk_ts)
            for ts, val in chunk_data:
                # Later chunks overwrite earlier chunks for revisions
                results[ts] = val
            # Modest delay between chunk downloads to be polite to the SMARD server
            time.sleep(0.05)

        return results


class OpenMeteoClient:
    """Client for the free Open-Meteo weather API."""

    def __init__(
        self,
        base_url: str = OPEN_METEO_BASE_URL,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = base_url
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Strom-Waechter-Weather/1.0",
            "Accept": "application/json",
        })

    def fetch_weather_forecast(self, days: int = 3) -> Optional[pd.DataFrame]:
        """
        Retrieves hourly weather forecast for Germany center.
        Variables: temperature_2m, wind_speed_10m, direct_normal_irradiance.
        """
        params = {
            "latitude": GERMANY_COORDINATES["latitude"],
            "longitude": GERMANY_COORDINATES["longitude"],
            "hourly": ",".join(OPEN_METEO_VARS),
            "forecast_days": max(1, min(days, 7)),
            "timezone": "UTC",
        }
        try:
            resp = self.session.get(self.base_url, params=params, timeout=DEFAULT_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("Open-Meteo request failed with HTTP %s", resp.status_code)
                return None
            data = resp.json()
            hourly = data.get("hourly", {})
            if "time" not in hourly:
                return None
            
            df = pd.DataFrame({
                "timestamp_utc": [f"{t}:00Z" if not t.endswith("Z") else t for t in hourly["time"]],
                "temperature_c": hourly.get("temperature_2m"),
                "wind_speed_ms": hourly.get("wind_speed_10m"),
                "solar_radiation_wm2": hourly.get("direct_normal_irradiance"),
            })
            return df
        except Exception as exc:
            logger.warning("Error fetching Open-Meteo weather forecast: %s", exc)
            return None


def fetch_all_smard_data(
    max_weeks: int = 104,
    since_timestamp_ms: Optional[int] = None,
) -> pd.DataFrame:
    """
    Coordinates fetching across Day-Ahead price, Solar, Wind, and Load from SMARD.
    Aligns all series by timestamp into a single raw DataFrame.
    """
    client = SMARDClient()

    # 1. Fetch Day-Ahead Price (Primary requirement)
    logger.info("Fetching SMARD Day-Ahead wholesale price (filter 4169)...")
    price_series = client.fetch_filter_series(
        SMARD_FILTERS["day_ahead_price"],
        max_chunks=max_weeks,
        since_timestamp_ms=since_timestamp_ms,
    )
    if not price_series:
        logger.error("No Day-Ahead price series could be retrieved from SMARD.")
        return pd.DataFrame()

    all_timestamps = set(price_series.keys())

    # 2. Fetch Solar Generation (Filter 4069)
    logger.info("Fetching SMARD Photovoltaik generation (filter 4069)...")
    solar_series = client.fetch_filter_series(
        SMARD_FILTERS["solar"],
        max_chunks=max_weeks,
        since_timestamp_ms=since_timestamp_ms,
    )

    # 3. Fetch Wind Onshore Generation (Filter 4068)
    logger.info("Fetching SMARD Wind Onshore generation (filter 4068)...")
    wind_onshore_series = client.fetch_filter_series(
        SMARD_FILTERS["wind_onshore"],
        max_chunks=max_weeks,
        since_timestamp_ms=since_timestamp_ms,
    )

    # 4. Fetch Wind Offshore Generation (Filter 4067)
    logger.info("Fetching SMARD Wind Offshore generation (filter 4067)...")
    wind_offshore_series = client.fetch_filter_series(
        SMARD_FILTERS["wind_offshore"],
        max_chunks=max_weeks,
        since_timestamp_ms=since_timestamp_ms,
    )

    # 5. Fetch Total Grid Load (Filter 410)
    logger.info("Fetching SMARD Total Grid Load (filter 410)...")
    load_series = client.fetch_filter_series(
        SMARD_FILTERS["grid_load"],
        max_chunks=max_weeks,
        since_timestamp_ms=since_timestamp_ms,
    )

    # 6. Fetch Total Generation (Filter 4071)
    logger.info("Fetching SMARD Total Generation (filter 4071)...")
    gen_series = client.fetch_filter_series(
        SMARD_FILTERS["total_generation"],
        max_chunks=max_weeks,
        since_timestamp_ms=since_timestamp_ms,
    )

    # Combine timestamps
    for s in (solar_series, wind_onshore_series, wind_offshore_series, load_series, gen_series):
        all_timestamps.update(s.keys())

    rows = []
    for ts_ms in sorted(all_timestamps):
        dt_utc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        iso_utc = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        p_mwh = price_series.get(ts_ms)
        p_ct = (p_mwh / 10.0) if p_mwh is not None else None
        sol = solar_series.get(ts_ms)
        w_on = wind_onshore_series.get(ts_ms)
        w_off = wind_offshore_series.get(ts_ms)
        
        w_tot = None
        if w_on is not None or w_off is not None:
            w_tot = (w_on or 0.0) + (w_off or 0.0)

        ld = load_series.get(ts_ms)
        gen = gen_series.get(ts_ms)

        rows.append({
            "timestamp_ms": ts_ms,
            "timestamp_utc": iso_utc,
            "price_eur_mwh": p_mwh,
            "price_ct_kwh": p_ct,
            "solar_mwh": sol,
            "wind_onshore_mwh": w_on,
            "wind_offshore_mwh": w_off,
            "wind_total_mwh": w_tot,
            "load_mwh": ld,
            "total_generation_mwh": gen,
        })

    df = pd.DataFrame(rows)
    logger.info("Successfully fetched %d raw SMARD observation rows", len(df))
    return df
