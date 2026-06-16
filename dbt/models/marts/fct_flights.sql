{{
  config(
    materialized='table',
    schema='marts',
    description='Fact table for flight operations with key metrics'
  )
}}

SELECT
    -- Flight identifiers
    {{ dbt_utils.generate_surrogate_key(['flight_id', 'departure_scheduled_time']) }} as flight_key,
    flight_id,
    flight_identifier,
    flight_iata,
    flight_icao,
    flight_number,

    -- Aircraft
    aircraft_icao,
    aircraft_iata,
    aircraft_registration,
    aircraft_type,

    -- Airline
    airline_id,
    airline_name,
    airline_iata,
    airline_icao,

    -- Airports (using IATA as keys)
    departure_airport_iata,
    arrival_airport_iata,

    -- Scheduled times
    departure_scheduled_time,
    arrival_scheduled_time,
    EXTRACT(EPOCH FROM (arrival_scheduled_time - departure_scheduled_time))/3600 as scheduled_flight_duration_hours,

    -- Actual times and performance
    departure_actual_time,
    arrival_actual_time,
    CASE
        WHEN departure_actual_time IS NOT NULL AND departure_scheduled_time IS NOT NULL
        THEN EXTRACT(EPOCH FROM (departure_actual_time - departure_scheduled_time))/60
        ELSE NULL
    END as departure_delay_minutes_actual,
    CASE
        WHEN arrival_actual_time IS NOT NULL AND arrival_scheduled_time IS NOT NULL
        THEN EXTRACT(EPOCH FROM (arrival_actual_time - arrival_scheduled_time))/60
        ELSE NULL
    END as arrival_delay_minutes_actual,

    -- Estimated times
    departure_estimated_time,
    arrival_estimated_time,

    -- Terminal and gate information
    dep_terminal,
    dep_gate,
    arr_terminal,
    arr_gate,

    -- Operational details
    flight_status,
    CASE
        WHEN flight_status = 'scheduled' THEN 'Scheduled'
        WHEN flight_status = 'active' THEN 'Active (In Air)'
        WHEN flight_status = 'landed' THEN 'Landed'
        WHEN flight_status = 'cancelled' THEN 'Cancelled'
        ELSE flight_status
    END as flight_status_description,

    -- Data quality indicators
    is_invalid_flight_id,
    is_missing_departure_airport,
    is_missing_arrival_airport,

    -- Metadata
    data_retrieved_at as data_retrieved_at,
    ingested_at as record_ingested_at,
    CURRENT_TIMESTAMP() as fact_table_loaded_at

FROM {{ ref('stg_flights') }}
