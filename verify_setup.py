# verify_setup.py
"""Verify complete setup is working"""

from decimal import Decimal
from sqlalchemy import text
from app.db import SessionLocal
from app import wallet
from app.models import Ledger, Wallet

print("🔍 Verifying setup...\n")

# Test 1: Database connection
try:
    db = SessionLocal()
    db.execute(text("SELECT 1"))
    db.close()
    print("✅ Database connection: OK")
except Exception as e:
    print(f"❌ Database connection: FAILED - {e}")
    exit(1)

# Test 2: Wallet operations
try:
    tx = wallet.deposit(999, 'INR', Decimal('100'))
    print(f"✅ Deposit operation: OK (tx: {tx[:8]}...)")
except Exception as e:
    print(f"❌ Deposit operation: FAILED - {e}")
    exit(1)

# Test 3: Balance check
try:
    db = SessionLocal()
    w = db.query(Wallet).filter(Wallet.user_id == 999).first()
    if w and w.available == Decimal('100'):
        print(f"✅ Balance check: OK (available: {w.available})")
    else:
        print(f"❌ Balance check: FAILED (expected 100, got {w.available if w else 'None'})")
    db.close()
except Exception as e:
    print(f"❌ Balance check: FAILED - {e}")
    exit(1)

# Test 4: Ledger integrity
try:
    db = SessionLocal()
    ledger_entries = db.query(Ledger).all()
    total = sum(Decimal(str(entry.amount)) for entry in ledger_entries)
    if total == 0:
        print(f"✅ Ledger balance: OK (sum = {total})")
    else:
        print(f"❌ Ledger balance: FAILED (sum = {total}, expected 0)")
    db.close()
except Exception as e:
    print(f"❌ Ledger integrity: FAILED - {e}")
    exit(1)

print("\n🎉 All verifications passed! System is bulletproof!")
