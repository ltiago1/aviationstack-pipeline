"""
DuckDB storage handler for bronze layer data.

Manages all interactions with DuckDB database including:
- Connection management
- Bronze table schema and upserts
- Data querying
"""

import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from ..utils.logger import get_logger

logger = get_logger(name="duckdb_handler", level="info")

# Database path
DB_PATH = Path("data") / "aviation.duckdb"


def get_connection():
    """Get or create DuckDB connection."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=False)


def init_bronze_table(conn):
    """
    Initialize bronze table if it doesn't exist.
    Bronze table stores raw flight data as-is from the API.
    Uses a unique constraint on (flight_id, dep_scheduled, arr_scheduled)
    to enable true upserts by flight operation. Each record gets a UUID primary key.
    """
    conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze.flights (
            record_id VARCHAR PRIMARY KEY DEFAULT uuid(),
            data_retrieved_at TIMESTAMP DEFAULT current_timestamp,
            api_call_id VARCHAR,
            flight_id VARCHAR NOT NULL,
            flight_iata VARCHAR,
            flight_icao VARCHAR,
            flight_number VARCHAR,
            aircraft_icao VARCHAR,
            aircraft_iata VARCHAR,
            aircraft_registration VARCHAR,
            aircraft_serial VARCHAR,
            aircraft_type VARCHAR,
            airline_id INTEGER,
            airline_name VARCHAR,
            airline_iata VARCHAR,
            airline_icao VARCHAR,
            codeshare_airline_iata VARCHAR,
            codeshare_airline_icao VARCHAR,
            codeshare_flight_iata VARCHAR,
            codeshare_flight_number VARCHAR,
            dep_airport VARCHAR,
            dep_iata VARCHAR,
            dep_icao VARCHAR,
            dep_terminal VARCHAR,
            dep_gate VARCHAR,
            dep_delay INTEGER,
            dep_scheduled TIMESTAMP,
            dep_estimated TIMESTAMP,
            dep_actual TIMESTAMP,
            dep_timezone VARCHAR,
            arr_airport VARCHAR,
            arr_iata VARCHAR,
            arr_icao VARCHAR,
            arr_terminal VARCHAR,
            arr_gate VARCHAR,
            arr_baggage VARCHAR,
            arr_delay INTEGER,
            arr_scheduled TIMESTAMP,
            arr_estimated TIMESTAMP,
            arr_actual TIMESTAMP,
            arr_timezone VARCHAR,
            flight_status VARCHAR,
            flight_updated TIMESTAMP,
            raw_json VARCHAR,
            ingested_at TIMESTAMP DEFAULT current_timestamp,
            UNIQUE (flight_id, dep_scheduled, arr_scheduled)
        )
    """)

    logger.info("Bronze table initialized or already exists")


def upsert_flight_data(data: list[dict]) -> int:
    """
    Upsert flight data into bronze table.

    Args:
        data: List of flight dictionaries from API

    Returns:
        Number of rows inserted
    """
    conn = get_connection()

    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        init_bronze_table(conn)

        df = pd.DataFrame(data)
        df_flattened = _flatten_flight_data(df)

        # Only keep rows with a flight_id
        if "flight_id" in df_flattened.columns:
            df_flattened = df_flattened[df_flattened["flight_id"].notna()]
        else:
            df_flattened = pd.DataFrame()

        if df_flattened.empty:
            logger.warning("No valid flights to ingest")
            return 0

        conn.register("temp_flights", df_flattened)

        # Delete existing records for these flight IDs
        # (Simple approach: upsert by flight_id alone for now)
        conn.execute("""
            DELETE FROM bronze.flights
            WHERE flight_id IN (SELECT DISTINCT flight_id FROM temp_flights)
        """)

        columns_to_insert = ",".join(df_flattened.columns)
        conn.execute(f"""
            INSERT INTO bronze.flights ({columns_to_insert})
            SELECT {columns_to_insert} FROM temp_flights
        """)

        conn.unregister("temp_flights")
        rows = len(df_flattened)
        logger.info(f"Upserted {rows} rows into bronze.flights")
        return rows

    finally:
        conn.close()


def _flatten_flight_data(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten nested JSON structures from API response. Handles missing columns."""
    df_flat = df.copy()
    df_flat["data_retrieved_at"] = datetime.now()
    df_flat["api_call_id"] = None

    def safe_get(col, key):
        if col not in df.columns:
            return None
        return df[col].apply(lambda x: x.get(key) if isinstance(x, dict) else None)

    # Create flight_id from iata code (e.g., "GEC8385" for flight iata)
    # Fallback to icao if iata is not available
    df_flat["flight_id"] = safe_get("flight", "iata")
    if df_flat["flight_id"].isna().all():
        df_flat["flight_id"] = safe_get("flight", "icao")

    df_flat["flight_iata"] = safe_get("flight", "iata")
    df_flat["flight_icao"] = safe_get("flight", "icao")
    df_flat["flight_number"] = safe_get("flight", "number")
    df_flat["aircraft_iata"] = safe_get("aircraft", "iata")
    df_flat["aircraft_registration"] = safe_get("aircraft", "registration")
    df_flat["aircraft_serial"] = safe_get("aircraft", "serial")
    df_flat["aircraft_type"] = safe_get("aircraft", "type")

    df_flat["airline_id"] = safe_get("airline", "id")
    df_flat["airline_name"] = safe_get("airline", "name")
    df_flat["airline_iata"] = safe_get("airline", "iata")
    df_flat["airline_icao"] = safe_get("airline", "icao")

    df_flat["codeshare_airline_iata"] = safe_get("codeshare", "airline_iata")
    df_flat["codeshare_airline_icao"] = safe_get("codeshare", "airline_icao")
    df_flat["codeshare_flight_iata"] = safe_get("codeshare", "flight_iata")
    df_flat["codeshare_flight_number"] = safe_get("codeshare", "flight_number")

    df_flat["dep_airport"] = safe_get("departure", "airport")
    df_flat["dep_iata"] = safe_get("departure", "iata")
    df_flat["dep_icao"] = safe_get("departure", "icao")
    df_flat["dep_terminal"] = safe_get("departure", "terminal")
    df_flat["dep_gate"] = safe_get("departure", "gate")
    df_flat["dep_delay"] = safe_get("departure", "delay")
    df_flat["dep_scheduled"] = safe_get("departure", "scheduled")
    df_flat["dep_estimated"] = safe_get("departure", "estimated")
    df_flat["dep_actual"] = safe_get("departure", "actual")
    df_flat["dep_timezone"] = safe_get("departure", "timezone")

    df_flat["arr_airport"] = safe_get("arrival", "airport")
    df_flat["arr_iata"] = safe_get("arrival", "iata")
    df_flat["arr_icao"] = safe_get("arrival", "icao")
    df_flat["arr_terminal"] = safe_get("arrival", "terminal")
    df_flat["arr_gate"] = safe_get("arrival", "gate")
    df_flat["arr_baggage"] = safe_get("arrival", "baggage")
    df_flat["arr_delay"] = safe_get("arrival", "delay")
    df_flat["arr_scheduled"] = safe_get("arrival", "scheduled")
    df_flat["arr_estimated"] = safe_get("arrival", "estimated")
    df_flat["arr_actual"] = safe_get("arrival", "actual")
    df_flat["arr_timezone"] = safe_get("arrival", "timezone")

    df_flat["flight_status"] = (
        df["flight_status"] if "flight_status" in df.columns else None
    )
    df_flat["flight_updated"] = df["updated"] if "updated" in df.columns else None

    df_flat["raw_json"] = df.apply(lambda r: r.to_json(), axis=1)

    bronze_columns = [
        "data_retrieved_at",
        "api_call_id",
        "flight_id",
        "flight_iata",
        "flight_icao",
        "flight_number",
        "aircraft_icao",
        "aircraft_iata",
        "aircraft_registration",
        "aircraft_serial",
        "aircraft_type",
        "airline_id",
        "airline_name",
        "airline_iata",
        "airline_icao",
        "codeshare_airline_iata",
        "codeshare_airline_icao",
        "codeshare_flight_iata",
        "codeshare_flight_number",
        "dep_airport",
        "dep_iata",
        "dep_icao",
        "dep_terminal",
        "dep_gate",
        "dep_delay",
        "dep_scheduled",
        "dep_estimated",
        "dep_actual",
        "dep_timezone",
        "arr_airport",
        "arr_iata",
        "arr_icao",
        "arr_terminal",
        "arr_gate",
        "arr_baggage",
        "arr_delay",
        "arr_scheduled",
        "arr_estimated",
        "arr_actual",
        "arr_timezone",
        "flight_status",
        "flight_updated",
        "raw_json",
    ]

    return df_flat[[c for c in bronze_columns if c in df_flat.columns]]


def query_bronze(query: str) -> pd.DataFrame:
    """Execute a query against the bronze table."""
    conn = get_connection()
    try:
        return conn.execute(query).df()
    finally:
        conn.close()


def export_bronze_to_parquet(output_path: str = "data/bronze_export") -> str:
    """Export bronze table to parquet file."""
    conn = get_connection()
    try:
        os.makedirs(output_path, exist_ok=True)
        output_file = (
            Path(output_path)
            / f"flights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        )
        conn.execute(f"COPY bronze.flights TO '{output_file}' (FORMAT PARQUET)")
        logger.info(f"Bronze data exported to {output_file}")
        return str(output_file)
    finally:
        conn.close()
