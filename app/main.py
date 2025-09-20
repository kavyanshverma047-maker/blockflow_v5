from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Blockflow backend is live 🚀"}

from fastapi.middleware.cors import CORSMiddleware

# STEP 3: create the FastAPI app
app = FastAPI()

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

# Example route (optional)
@app.get("/health")
async def health_check():
    return {"status": "ok"}

from pydantic import BaseModel
from decimal import Decimal
from .db import Base, engine, SessionLocal
from . import models, ledger, wallet
Base.metadata.create_all(bind=engine)
app = FastAPI(title='Blockflow v5 Ledger Demo')
class DepositIn(BaseModel):
    user_id:int; currency:str; amount:Decimal
class ReserveIn(BaseModel):
    user_id:int; currency:str; amount:Decimal
@app.post('/deposit')
def deposit(p: DepositIn):
    wallet.deposit(p.user_id, p.currency, p.amount); return {'ok':True}
@app.post('/reserve')
def reserve(p: ReserveIn):
    tx = wallet.reserve(p.user_id, p.currency, p.amount); return {'tx':tx}
@app.post('/release')
def release(p: ReserveIn):
    tx = wallet.release(p.user_id, p.currency, p.amount); return {'tx':tx}
@app.post('/settle_trade')
def settle(from_user:int, to_user:int, currency:str, amount:Decimal, fee:Decimal=0):
    tx = wallet.settle(from_user, to_user, currency, amount, fee); return {'tx':tx}
@app.get('/balances/{user_id}')
def balances(user_id:int):
    db = SessionLocal()
    try:
        rows = db.query(models.Wallet).filter(models.Wallet.user_id==user_id).all()
        return [{'currency':r.currency,'available':str(r.available),'reserved':str(r.reserved)} for r in rows]
    finally:
        db.close()
