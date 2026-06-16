{{
  config(
    materialized='table',
    schema='marts',
    description='Dimension table for airlines'
  )
}}

SELECT DISTINCT
    airline_id,
    airline_iata,
    airline_icao,
    airline_name,
    CURRENT_TIMESTAMP() as dim_loaded_at
FROM {{ ref('stg_flights') }}
WHERE
    airline_id IS NOT NULL
    OR airline_iata IS NOT NULL

QUALIFY ROW_NUMBER() OVER (PARTITION BY airline_iata ORDER BY airline_name) = 1
