import time

CACHE = {}
TTL = 10  # seconds

def cache_get(key):
    if key in CACHE:
        value, ts = CACHE[key]
        if time.time() - ts < TTL:
            return value
    return None

def cache_set(key, value):
    CACHE[key] = (value, time.time())
