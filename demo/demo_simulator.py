import asyncio
import httpx
import random

API_URL = "http://127.0.0.1:8000"

# random trading pairs (you can add more)
SYMBOL = "BTC/USDT"

async def place_order(client, side, price, amount):
    order = {
        "symbol": SYMBOL,
        "side": side,          # "buy" or "sell"
        "type": "limit",       # market also works
        "price": price,
        "amount": amount,
        "user_id": "demo-user"
    }
    r = await client.post(f"{API_URL}/orders", json=order)
    print(f"Placed {side.upper()} {amount} @ {price} -> {r.json()}")

async def run_simulation():
    async with httpx.AsyncClient() as client:
        # give demo-user some balance
        await client.post(f"{API_URL}/wallet/deposit", json={
            "user_id": "demo-user",
            "asset": "USDT",
            "amount": 100000
        })
        await client.post(f"{API_URL}/wallet/deposit", json={
            "user_id": "demo-user",
            "asset": "BTC",
            "amount": 10
        })

        # place random orders forever
        while True:
            price = random.randint(25000, 30000)
            amount = round(random.uniform(0.01, 0.1), 4)
            side = random.choice(["buy", "sell"])
            await place_order(client, side, price, amount)
            await asyncio.sleep(1)  # 1 sec between orders

if __name__ == "__main__":
    asyncio.run(run_simulation())
