import subprocess
from datetime import datetime

from ..ingestion.aviationstack_client import fetch_flight_data
from ..storage.duckdb_handler import upsert_flight_data
from ..utils.logger import get_logger
from ..utils.state import save_last_timestamp

logger = get_logger(name="pipeline", level="info", log_dir="logs", console=True)


def run_pipeline():
    logger.info("=" * 60)
    logger.info("Pipeline execution started")
    logger.info("=" * 60)

    try:
        # ────────────────────────────────────
        # STAGE 1: DATA INGESTION (Bronze)
        # ────────────────────────────────────
        logger.info("STAGE 1: Ingesting flight data...")
        data = fetch_flight_data(limit=100)

        if not data:
            logger.warning("No data fetched from source.")
            return

        logger.info(f"Successfully fetched {len(data)} records")

        # Store raw data in DuckDB bronze layer
        rows_ingested = upsert_flight_data(data)
        logger.info(f"Data ingested into DuckDB bronze layer: {rows_ingested} records")

        # ────────────────────────────────────
        # STAGE 2: TRANSFORMATION (via dbt)
        # ────────────────────────────────────
        logger.info("STAGE 2: Running dbt transformation pipeline...")
        logger.info("  - Staging layer (Silver): Cleaning and standardizing data")
        logger.info("  - Marts layer (Gold): Building facts and dimensions")
        
        try:
            # Run dbt from the dbt directory
            result = subprocess.run(
                ["dbt", "run", "--profiles-dir", "dbt", "--project-dir", "dbt"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("dbt transformation completed successfully")
            else:
                logger.warning(f"dbt run had warnings or issues: {result.stderr}")
                
            # Run dbt tests
            logger.info("Running dbt tests...")
            test_result = subprocess.run(
                ["dbt", "test", "--profiles-dir", "dbt", "--project-dir", "dbt"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if test_result.returncode == 0:
                logger.info("dbt tests passed")
            else:
                logger.warning(f"Some dbt tests failed: {test_result.stderr}")
                
        except FileNotFoundError:
            logger.error("dbt not found. Please install dbt-duckdb: pip install dbt-duckdb")
            raise

        # ────────────────────────────────────
        # STAGE 3: STATE MANAGEMENT
        # ────────────────────────────────────
        # Save the timestamp of the last fetched data for incremental updates
        save_last_timestamp(datetime.now().isoformat())
        logger.info("Pipeline state updated with latest timestamp")

        logger.info("=" * 60)
        logger.info("Pipeline execution completed successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    run_pipeline()
