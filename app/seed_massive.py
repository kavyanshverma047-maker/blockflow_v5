# app/seed_massive.py
"""
Blockflow Massive Data Seeding Script
Generates 10 Million Demo Users + Trades for Investor Demo
"""

import random
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from app.models import Base, User, SpotTrade, MarginTrade, FuturesUsdmTrade, P2POrder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# ✅ Pull from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Create independent SQLAlchemy session
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Configuration
TARGET_USERS = 10_000_000  # 10 million users
TRADES_PER_USER = 5  # Average trades per user
BATCH_SIZE = 10_000  # Insert in batches

# Trading pairs
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "MATICUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT", "DOTUSDT"]
SIDES = ["buy", "sell"]

# Price ranges
PRICE_RANGES = {
    "BTCUSDT": (25000, 70000),
    "ETHUSDT": (1500, 4500),
    "SOLUSDT": (15, 250),
    "MATICUSDT": (0.5, 2.5),
    "BNBUSDT": (200, 700),
    "ADAUSDT": (0.25, 3.5),
    "DOGEUSDT": (0.05, 0.35),
    "DOTUSDT": (4, 45),
}

def generate_user_batch(start_id: int, count: int):
    """Generate batch of users"""
    users = []
    for i in range(count):
        user_id = start_id + i
        users.append(User(
            username=f"trader_{user_id}",
            email=f"trader_{user_id}@blockflow.demo",
            password="demo_password",
            balance_usdt=round(random.uniform(100, 50000), 2),
            balance_inr=round(random.uniform(10000, 5000000), 2)
        ))
    return users

def generate_spot_trades_batch(start_user: int, end_user: int, trades_per_user: int):
    """Generate batch of spot trades"""
    trades = []
    for user_id in range(start_user, end_user):
        for _ in range(random.randint(0, trades_per_user * 2)):
            pair = random.choice(PAIRS)
            price_min, price_max = PRICE_RANGES[pair]
            trades.append(SpotTrade(
                username=f"trader_{user_id}",
                pair=pair,
                side=random.choice(SIDES),
                price=round(random.uniform(price_min, price_max), 2),
                amount=round(random.uniform(0.001, 5.0), 6),
                timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 365))
            ))
    return trades

def generate_margin_trades_batch(start_user: int, end_user: int):
    """Generate batch of margin trades"""
    trades = []
    for user_id in range(start_user, min(end_user, start_user + 1000)):
        if random.random() < 0.3:  # 30% of users do margin
            pair = random.choice(PAIRS)
            price_min, price_max = PRICE_RANGES[pair]
            trades.append(MarginTrade(
                username=f"trader_{user_id}",
                pair=pair,
                side=random.choice(SIDES),
                leverage=random.choice([3, 5, 10]),
                price=round(random.uniform(price_min, price_max), 2),
                amount=round(random.uniform(0.01, 3.0), 4),
                pnl=round(random.uniform(-500, 1500), 2),
                timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 180))
            ))
    return trades

def seed_massive_data():
    """Main seeding function"""
    print("🚀 Blockflow Massive Data Seeding Started")
    print(f"📊 Target: {TARGET_USERS:,} users with {TRADES_PER_USER} trades each")
    print(f"💾 Database: {DATABASE_URL}")
    
    db = SessionLocal()
    
    try:
        # Check existing data
        existing_users = db.query(User).count()
        print(f"✅ Existing users: {existing_users:,}")
        
        if existing_users >= TARGET_USERS:
            print("⚠️  Target already reached!")
            return
        
        start_time = time.time()
        start_id = existing_users
        
        # Seed users in batches
        print(f"\n📝 Seeding {TARGET_USERS - existing_users:,} users...")
        for batch_start in range(start_id, TARGET_USERS, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, TARGET_USERS)
            users = generate_user_batch(batch_start, batch_end - batch_start)
            db.bulk_save_objects(users)
            db.commit()
            
            progress = ((batch_end - start_id) / (TARGET_USERS - start_id)) * 100
            print(f"  ✓ Users: {batch_end:,} / {TARGET_USERS:,} ({progress:.1f}%)")
        
        print(f"✅ All users created!\n")
        
        # Seed spot trades in batches
        print(f"📈 Seeding spot trades...")
        total_trades = 0
        for batch_start in range(start_id, TARGET_USERS, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, TARGET_USERS)
            trades = generate_spot_trades_batch(batch_start, batch_end, TRADES_PER_USER)
            db.bulk_save_objects(trades)
            db.commit()
            total_trades += len(trades)
            
            if batch_end % (BATCH_SIZE * 10) == 0:
                print(f"  ✓ Spot trades: {total_trades:,}")
        
        print(f"✅ Total spot trades: {total_trades:,}\n")
        
        # Seed margin trades (subset)
        print(f"📊 Seeding margin trades...")
        margin_count = 0
        for batch_start in range(start_id, min(TARGET_USERS, start_id + 100000), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, TARGET_USERS)
            trades = generate_margin_trades_batch(batch_start, batch_end)
            if trades:
                db.bulk_save_objects(trades)
                db.commit()
                margin_count += len(trades)
        
        print(f"✅ Total margin trades: {margin_count:,}\n")
        
        # Seed futures trades
        print(f"🚀 Seeding futures trades...")
        futures_count = 0
        for batch_start in range(start_id, min(TARGET_USERS, start_id + 50000), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, TARGET_USERS)
            for user_id in range(batch_start, batch_end):
                if random.random() < 0.2:  # 20% of users
                    pair = random.choice(PAIRS)
                    price_min, price_max = PRICE_RANGES[pair]
                    trade = FuturesUsdmTrade(
                        username=f"trader_{user_id}",
                        pair=pair,
                        side=random.choice(SIDES),
                        leverage=random.choice([10, 20, 50]),
                        price=round(random.uniform(price_min, price_max), 2),
                        amount=round(random.uniform(0.01, 10.0), 4),
                        pnl=round(random.uniform(-1000, 3000), 2),
                        timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 90))
                    )
                    db.add(trade)
                    futures_count += 1
            
            if batch_end % (BATCH_SIZE * 5) == 0:
                db.commit()
                print(f"  ✓ Futures trades: {futures_count:,}")
        
        db.commit()
        print(f"✅ Total futures trades: {futures_count:,}\n")
        
        # Final stats
        elapsed = time.time() - start_time
        final_users = db.query(User).count()
        final_spot = db.query(SpotTrade).count()
        final_margin = db.query(MarginTrade).count()
        final_futures = db.query(FuturesUsdmTrade).count()
        
        print("=" * 60)
        print("🎉 SEEDING COMPLETE!")
        print("=" * 60)
        print(f"👥 Total Users:        {final_users:,}")
        print(f"📈 Spot Trades:        {final_spot:,}")
        print(f"📊 Margin Trades:      {final_margin:,}")
        print(f"🚀 Futures Trades:     {final_futures:,}")
        print(f"💰 Total Volume:       {final_spot + final_margin + final_futures:,}")
        print(f"⏱️  Time Elapsed:       {elapsed:.2f} seconds")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_massive_data()
