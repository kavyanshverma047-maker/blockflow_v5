from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from .db import Base, engine, SessionLocal
from . import models, ledger, wallet

# Create the FastAPI app (only once)
app = FastAPI(title='Blockflow v5 Ledger Demo')

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vibe-1758132969629.vercel.app",  # frontend
        "http://localhost:3000",                  # local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure DB and tables exist
Base.metadata.create_all(bind=engine)

# --------- Routes ---------
@app.get("/")
def home():
    return {"message": "Blockflow backend is live 🚀"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

class DepositIn(BaseModel):
    user_id: int
    currency: str
    amount: Decimal

class ReserveIn(BaseModel):
    user_id: int
    currency: str
    amount: Decimal

@app.post("/deposit")
def deposit(p: DepositIn):
    wallet.deposit(p.user_id, p.currency, p.amount)
    return {"ok": True}

@app.post("/reserve")
def reserve(p: ReserveIn):
    tx = wallet.reserve(p.user_id, p.currency, p.amount)
    return {"tx": tx}

@app.post("/release")
def release(p: ReserveIn):
    tx = wallet.release(p.user_id, p.currency, p.amount)
    return {"tx": tx}

@app.post("/settle_trade")
def settle(from_user: int, to_user: int, currency: str, amount: Decimal, fee: Decimal = 0):
    tx = wallet.settle(from_user, to_user, currency, amount, fee)
    return {"tx": tx}

@app.get('/balances/{user_id}')
def balances(user_id: int):
    db = SessionLocal()
    try:
        rows = db.query(models.Wallet).filter(models.Wallet.user_id == user_id).all()
        return [
            {
                'currency': r.currency,
                'available': str(r.available),
                'reserved': str(r.reserved)
            }
            for r in rows
        ]
    finally:
        db.close()
import requests

@app.get("/markets")
def get_markets():
    try:
        # Fetch live prices from Binance (USDT pairs)
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        prices = {}

        for symbol in symbols:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            resp = requests.get(url).json()
            prices[symbol] = float(resp["price"])

        # Get USD/INR conversion
        forex_url = "https://api.exchangerate.host/latest?base=USD&symbols=INR"
        forex_resp = requests.get(forex_url).json()
        usd_inr = forex_resp["rates"]["INR"]

        # Convert to INR
        markets = [
            {"symbol": "BTC-INR", "price": round(prices["BTCUSDT"] * usd_inr, 2)},
            {"symbol": "ETH-INR", "price": round(prices["ETHUSDT"] * usd_inr, 2)},
            {"symbol": "SOL-INR", "price": round(prices["SOLUSDT"] * usd_inr, 2)},
        ]

        return markets

    except Exception as e:
        return {"error": str(e)}

