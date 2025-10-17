# app/utils.py
"""
Common utility functions shared across modules.
"""

import random, string, time
from datetime import datetime

def random_trader_name() -> str:
    prefix = random.choice(["Alpha", "Sigma", "Zeta", "Orion", "Nova"])
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}_{suffix}"

def timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def random_choice_weighted(items):
    """Select an item with weighted probability."""
    total = sum(weight for item, weight in items)
    r = random.uniform(0, total)
    upto = 0
    for item, weight in items:
        if upto + weight >= r:
            return item
        upto += weight
    return items[-1][0]
