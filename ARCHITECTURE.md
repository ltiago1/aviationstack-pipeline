# AviationStack Data Pipeline - Architecture

## Overview

The project has been refactored to use a **database-driven architecture** with **dbt for SQL-based transformations**. This decouples data ingestion from data transformation and enables better maintainability and scalability.

## Architecture Layers

```
┌─────────────────────────────────────────┐
│        AviationStack API                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    Bronze Layer (DuckDB)                │
│  - Raw flight data from API             │
│  - `bronze.flights` table               │
│  - Incremental ingestion via upsert     │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┐
        │   via dbt run   │
        ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│  Silver Layer    │  │  Gold/Marts Layer│
│  (Staging)       │  │  (Analytics)     │
│ ─────────────    │  │ ─────────────    │
│ stg_flights      │  │ fct_flights      │
│                  │  │ dim_airlines     │
│                  │  │ dim_airports     │
└──────────────────┘  └──────────────────┘
```

## Key Changes

### 1. **Bronze Layer - DuckDB Storage**
   - **Before**: Raw JSON → Parquet files (`data/bronze/`)
   - **After**: Raw JSON → DuckDB `bronze.flights` table

   **Benefits**:
   - SQL access to raw data
   - Incremental upserts (prevents duplicates)
   - ACID compliance
   - Easier to integrate with dbt

### 2. **Staging Layer - Silver (dbt models)**
   - **Location**: `dbt/models/staging/stg_flights.sql`
   - **Type**: SQL View
   - **Transformations**:
     - Flattens nested JSON structures
     - Standardizes column names (e.g., `dep_iata`, `arr_iata`)
     - Type conversions and datetime parsing
     - Data quality flags (missing values, invalid IDs)
     - Deduplication (most recent record per flight)

### 3. **Marts Layer - Gold (dbt models)**
   - **Location**: `dbt/models/marts/`
   - **Models**:
     - `fct_flights`: Fact table with flight operations and performance metrics
     - `dim_airlines`: Dimension table for airlines
     - `dim_airports`: Dimension table for airports

## File Structure

```
project-root/
├── src/
│   ├── ingestion/
│   │   └── aviationstack_client.py       # API client
│   ├── storage/
│   │   ├── write_parquet.py              # (deprecated)
│   │   └── duckdb_handler.py             # NEW: DuckDB handler
│   ├── pipelines/
│   │   └── run_pipeline.py               # Updated to use dbt
│   ├── transform/
│   │   └── bronze_to_silver.py           # (deprecated)
│   └── utils/
│       ├── logger.py
│       └── state.py
├── dbt/                                  # NEW: dbt project
│   ├── dbt_project.yml                   # dbt configuration
│   ├── profiles.yml                      # dbt profiles
│   └── models/
│       ├── staging/
│       │   ├── schema.yml
│       │   └── stg_flights.sql
│       └── marts/
│           ├── fct_flights.sql
│           ├── dim_airlines.sql
│           └── dim_airports.sql
├── data/
│   ├── aviation.duckdb                   # NEW: DuckDB database
│   └── bronze_export/                    # (optional: parquet exports)
└── requirements.txt                      # Updated with dbt packages
```

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure DuckDB and dbt
The DuckDB database and dbt configuration are automatically initialized when you run the pipeline.

### 3. Run the Pipeline
```bash
python -m src.pipelines.run_pipeline
```

This executes three stages:
1. **Ingestion**: Fetches data from AviationStack API and stores in DuckDB bronze layer
2. **Transformation**: Runs dbt to build staging (silver) and marts (gold) layers
3. **Testing**: Runs dbt tests to validate data quality

## dbt Commands

### Development
```bash
# Navigate to dbt directory
cd dbt

# Run all models
dbt run

# Run specific model
dbt run --select stg_flights

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve

# Run in debug mode
dbt debug
```

### Production
```bash
dbt run --profiles-dir dbt --project-dir dbt
```

## Data Quality & Testing

dbt tests are defined in `dbt/models/staging/schema.yml`:
- `not_null`: Ensures required fields are populated
- `unique`: Validates unique identifiers
- `relationships`: (Optional) Can add foreign key validation between tables

Run tests with:
```bash
cd dbt
dbt test
```

## GitHub Actions

The workflow (`.github/workflows/run_pipeline.yml`) has been updated to:
1. Install dbt-duckdb
2. Run the pipeline with `python -m src.pipelines.run_pipeline`
3. This triggers both dbt run and dbt test

### Scheduling Note
GitHub Actions scheduled workflows can experience delays due to runner queue congestion. If the workflow runs every 6 hours instead of every hour, this is a known GitHub limitation. Once Apache Airflow is implemented, workflows will be triggered directly with more reliable scheduling.

## Future Enhancements

### 1. Airflow Integration
Replace GitHub Actions with Apache Airflow for:
- Better scheduling reliability
- Task dependencies and retries
- Monitoring and alerting
- Complex orchestration

### 2. Data Lineage
Use dbt's built-in lineage capabilities to visualize data flow:
```bash
dbt docs generate
dbt docs serve  # View at http://localhost:8000
```

### 3. Snapshots & SCD
Implement Slowly Changing Dimensions (SCD) for tracking historical changes:
```sql
{% snapshot flights_snapshot %}
  ...
{% endsnapshot %}
```

### 4. Incremental Models
Optimize for large datasets:
```sql
{{
  config(
    materialized='incremental',
    unique_key='flight_id'
  )
}}
```

### 5. Alerts & Monitoring
Integrate with monitoring tools to alert on:
- Pipeline failures
- Data quality issues (test failures)
- Performance degradation

## Troubleshooting

### dbt Not Found
```bash
pip install dbt-duckdb
```

### DuckDB Lock Errors
Multiple processes accessing the same DuckDB file. Use file-based locking or implement queuing.

### dbt Compilation Errors
```bash
dbt parse  # Check for syntax errors
dbt debug  # Validate configuration
```

### Missing Profiles
Ensure `dbt/profiles.yml` points to the correct DuckDB file path.

## References

- [dbt Documentation](https://docs.getdbt.com)
- [dbt-duckdb Adapter](https://github.com/dbt-labs/dbt-duckdb)
- [DuckDB Documentation](https://duckdb.org/docs)
- [AviationStack API](https://aviationstack.com/documentation)
