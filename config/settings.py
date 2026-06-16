import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('AVIATIONSTACK_API_KEY')

BASE_URL = 'http://api.aviationstack.com/v1/'

OUTPUT_PATH = "data/bronze"

# IATA Codes for Portuguese airports
PORTUGUESE_AIRPORTS = [
    "LIS",  # Lisbon
    "OPO",  # Porto
    "FNC",  # Funchal
    "PDL",  # Ponta Delgada
    "VRL",  # Vila Real
]

# Incremental control
STATE_FILE = "data/state/last_timestamp.txt"