{{
  config(
    materialized='table',
    schema='marts',
    description='Dimension table for airports'
  )
}}

WITH airports_combined AS (
    -- Departure airports
    SELECT DISTINCT
        departure_airport_iata as airport_iata,
        NULL as airport_icao,
        departure_airport_name as airport_name,
        'departure' as airport_role
    FROM {{ ref('stg_flights') }}
    WHERE departure_airport_iata IS NOT NULL

    UNION ALL

    -- Arrival airports
    SELECT DISTINCT
        arrival_airport_iata as airport_iata,
        NULL as airport_icao,
        arrival_airport_name as airport_name,
        'arrival' as airport_role
    FROM {{ ref('stg_flights') }}
    WHERE arrival_airport_iata IS NOT NULL
)

SELECT
    airport_iata,
    airport_name,
    STRING_AGG(DISTINCT airport_role, ', ') as airport_roles,
    COUNT(*) as appearance_count,
    CURRENT_TIMESTAMP() as dim_loaded_at
FROM airports_combined
GROUP BY airport_iata, airport_name
ORDER BY appearance_count DESC
