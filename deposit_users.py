import requests

API_URL = "http://127.0.0.1:8000"

# Users and their deposits
deposits = [
    {"user_id": 1, "currency": "USDT", "amount": 10000},
    {"user_id": 2, "currency": "USDT", "amount": 10000},
    {"user_id": 3, "currency": "USDT", "amount": 10000},
]

for d in deposits:
    r = requests.post(f"{API_URL}/deposit", json=d)
    print(f"Deposit for user {d['user_id']}: {r.status_code} -> {r.json()}")

# Verify balances
for d in deposits:
    r = requests.get(f"{API_URL}/balances/{d['user_id']}")
    print(f"Balance for user {d['user_id']}: {r.json()}")


