# app/account_service.py
accounts = {}

def get_balance(user_id: str):
    return accounts.get(user_id, {"usdt": 10000.0, "locked": 0.0})

def update_balance(user_id: str, delta: float):
    acc = get_balance(user_id)
    acc["usdt"] += delta
    if acc["usdt"] < 0:
        acc["usdt"] = 0.0
    accounts[user_id] = acc
    return acc
