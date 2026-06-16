from config.settings import API_KEY, BASE_URL


def fetch_flight_data(limit=100, verify_tls=True):
    """Fetch flight data from AviationStack API.

    Performs a lazy import of `requests` to avoid import-time issues
    (e.g., environment-specific SSL certificate handling). Uses
    `certifi` bundle for verification when available.
    """
    # Lazy import to avoid top-level import blocking the process
    try:
        import requests
    except Exception as e:
        raise ImportError("requests package is required to fetch flight data") from e

    # Prefer certifi's CA bundle if available
    verify = True
    if verify_tls:
        try:
            import certifi

            verify = certifi.where()
        except Exception:
            verify = True

    params = {"access_key": API_KEY, "limit": limit}

    response = requests.get(
        f"{BASE_URL}flights", params=params, verify=verify, timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"API Error: status {response.status_code}")

    data = response.json().get("data", [])
    return data
