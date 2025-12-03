import os
import sys
sys.path.insert(0, 'E:/blockflow_v5-main')
os.chdir('E:/blockflow_v5-main')

from dotenv import load_dotenv
load_dotenv()

from app.models import Base, User, UserAsset, LedgerEntry
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from passlib.context import CryptContext

# Setup
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Hash password
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
hashed = pwd_context.hash('Test123!@#')

# Create user
user = User(
    username='livetrader999',
    email='livetrader999@test.com',
    hashed_password=hashed,
    balance_inr=Decimal('100000'),
    balance_usdt=Decimal('0')
)
db.add(user)
db.flush()

# Add USDT balance
ua = UserAsset(user_id=user.id, asset='USDT', balance=Decimal('1000'))
db.add(ua)

# Ledger entries
db.add(LedgerEntry(
    user_id=user.id,
    currency='INR',
    amount=Decimal('100000'),
    balance_after=Decimal('100000'),
    txn_type='deposit',
    description='Initial INR'
))

db.add(LedgerEntry(
    user_id=user.id,
    currency='USDT',
    amount=Decimal('1000'),
    balance_after=Decimal('1000'),
    txn_type='deposit',
    description='Initial USDT'
))

db.commit()

print('✅ User created successfully!')
print(f'Username: {user.username}')
print(f'Email: {user.email}')
print(f'Password: Test123!@#')
print(f'INR Balance: {user.balance_inr}')
print(f'USDT Balance: {ua.balance}')
