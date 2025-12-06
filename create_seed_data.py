from app.database import SessionLocal
from app.models import User, Wallet, SpotOrder, FuturesPosition, LedgerEntry
from app.core.security import hash_password

db = SessionLocal()

# --- USERS ---
u1 = User(email='demo1@blockflow.com', password_hash=hash_password('demo123'), is_active=True)
u2 = User(email='demo2@blockflow.com', password_hash=hash_password('demo123'), is_active=True)

db.add_all([u1, u2])
db.commit()

# --- WALLETS ---
w1 = Wallet(user_id=u1.id, balance=50000)
w2 = Wallet(user_id=u2.id, balance=32000)
db.add_all([w1, w2])
db.commit()

# --- LEDGER ---
db.add_all([
    LedgerEntry(user_id=u1.id, type='deposit', amount=50000),
    LedgerEntry(user_id=u2.id, type='deposit', amount=32000)
])
db.commit()

# --- SPOT TRADES ---
db.add_all([
    SpotOrder(user_id=u1.id, pair='BTC/USDT', side='buy', qty=0.01, price=60000, status='filled'),
    SpotOrder(user_id=u1.id, pair='ETH/USDT', side='buy', qty=0.5, price=3200, status='filled'),
    SpotOrder(user_id=u2.id, pair='SOL/USDT', side='buy', qty=10, price=180, status='filled')
])
db.commit()

# --- FUTURES POSITIONS ---
db.add_all([
    FuturesPosition(user_id=u1.id, pair='BTCUSDT', side='long', size=0.02, entry_price=59000, leverage=10, status='open'),
    FuturesPosition(user_id=u2.id, pair='ETHUSDT', side='short', size=1, entry_price=3300, leverage=5, status='open'),
])
db.commit()

print("Seed data successfully inserted.")
