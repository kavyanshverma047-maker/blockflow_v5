from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Blockflow v5 Ledger Demo + Trading API", version="0.2.0")

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in prod: restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory user store (demo only)
USERS = {}

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}


# Reset a demo account
@app.post("/reset/{username}")
def reset(username: str):
    USERS[username] = {
        "balance": 10000,   # start every demo with $10,000
        "orders": []
    }
    return {"message": f"Demo account for {username} reset with $10000"}


# Get portfolio
@app.get("/portfolio/{username}")
def get_portfolio(username: str):
    user = USERS.get(username)
    if not user:
        return {"balance": 0, "orders": []}
    return {"balance": user["balance"], "orders": user["orders"]}


# Get orders
@app.get("/orders/{username}")
def get_orders(username: str):
    user = USERS.get(username)
    if not user:
        return []
    return user["orders"]


# Place trade
@app.post("/trade")
def place_trade(username: str, side: str, amount: float, price: float):
    user = USERS.get(username)
    if not user:
        return {"error": "User not found"}

    cost = amount * price

    if side == "buy":
        if user["balance"] < cost:
            return {"error": "Insufficient balance"}
        user["balance"] -= cost
        user["orders"].append({"side": "buy", "amount": amount, "price": price})

    elif side == "sell":
        # For demo, just credit balance (no inventory tracking yet)
        user["balance"] += cost
        user["orders"].append({"side": "sell", "amount": amount, "price": price})

    return {
        "message": f"{side} order placed",
        "balance": user["balance"],
        "orders": user["orders"]
    }

   

