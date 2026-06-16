{{
  config(
    materialized='view',
    schema='staging',
    description='Cleaned and standardized flight data from bronze layer'
  )
}}

SELECT
    -- Flight identifiers
    flight_id,
    COALESCE(flight_iata, flight_icao, flight_number) as flight_identifier,
    flight_iata,
    flight_icao,
    flight_number,

    -- Aircraft
    aircraft_icao,
    aircraft_iata,
    aircraft_registration,
    aircraft_serial,
    aircraft_type,

    -- Airline
    airline_id,
    airline_name,
    airline_iata,
    airline_icao,

    -- Departure details
    dep_iata as departure_airport_iata,
    dep_icao as departure_airport_icao,
    dep_airport as departure_airport_name,
    dep_terminal,
    dep_gate,
    CAST(dep_delay AS INTEGER) as departure_delay_minutes,
    TRY_CAST(dep_scheduled AS TIMESTAMP) as departure_scheduled_time,
    TRY_CAST(dep_estimated AS TIMESTAMP) as departure_estimated_time,
    TRY_CAST(dep_actual AS TIMESTAMP) as departure_actual_time,
    dep_timezone as departure_timezone,

    -- Arrival details
    arr_iata as arrival_airport_iata,
    arr_icao as arrival_airport_icao,
    arr_airport as arrival_airport_name,
    arr_terminal,
    arr_gate,
    arr_baggage,
    CAST(arr_delay AS INTEGER) as arrival_delay_minutes,
    TRY_CAST(arr_scheduled AS TIMESTAMP) as arrival_scheduled_time,
    TRY_CAST(arr_estimated AS TIMESTAMP) as arrival_estimated_time,
    TRY_CAST(arr_actual AS TIMESTAMP) as arrival_actual_time,
    arr_timezone as arrival_timezone,

    -- Flight status
    flight_status,
    TRY_CAST(flight_updated AS TIMESTAMP) as flight_status_updated_at,

    -- Metadata
    data_retrieved_at,
    ingested_at,

    -- Data quality flags
    CASE WHEN flight_id IS NULL THEN TRUE ELSE FALSE END as is_invalid_flight_id,
    CASE WHEN dep_iata IS NULL AND dep_icao IS NULL THEN TRUE ELSE FALSE END as is_missing_departure_airport,
    CASE WHEN arr_iata IS NULL AND arr_icao IS NULL THEN TRUE ELSE FALSE END as is_missing_arrival_airport,

FROM {{ source('bronze', 'flights') }}

WHERE
    -- Filter out obvious data quality issues
    flight_id IS NOT NULL
    AND (dep_iata IS NOT NULL OR dep_icao IS NOT NULL)
    AND (arr_iata IS NOT NULL OR arr_icao IS NOT NULL)

QUALIFY ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY data_retrieved_at DESC) = 1
