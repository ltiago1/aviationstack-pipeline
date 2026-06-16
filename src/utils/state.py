import os


def save_last_timestamp(ts, filepath = "data/state/last_timestamp.txt"):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(str(ts))

def load_last_timestamp(filepath = "data/state/last_timestamp.txt"):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r') as f:
        return f.read().strip()