from decimal import Decimal
from .db import SessionLocal
from .models import Ledger, Wallet
import uuid

def _account_user_available(user_id:int, currency:str):
    return f'user:{user_id}:{currency}:available'
def _account_user_reserved(user_id:int, currency:str):
    return f'user:{user_id}:{currency}:reserved'
def _account_platform_fees(currency:str):
    return f'platform:fees:{currency}'

def post_transaction(entries, ref=None):
    """Post a grouped transaction (list of dicts with account and amount). Amounts must sum to zero."""
    tx_id = str(uuid.uuid4())
    total = sum(Decimal(e['amount']) for e in entries)
    if total != 0:
        raise Exception('transaction not balanced')
    db = SessionLocal()
    try:
        for e in entries:
            acc = e['account']; amt = Decimal(e['amount'])
            entry_type = 'credit' if amt > 0 else 'debit'
            rec = Ledger(tx_id=tx_id, account=acc, amount=amt, entry_type=entry_type, ref=ref)
            db.add(rec)
            # apply to wallets if account matches wallet patterns
            parts = acc.split(':')
            if parts[0]=='user' and parts[3] in ('available','reserved'):
                uid = int(parts[1]); cur = parts[2]; which = parts[3]
                w = db.query(Wallet).filter(Wallet.user_id==uid, Wallet.currency==cur).with_for_update().first()
                if not w:
                    w = Wallet(user_id=uid, currency=cur, available=0, reserved=0)
                    db.add(w); db.flush()
                if which=='available':
                    w.available = (w.available or 0) + amt
                else:
                    w.reserved = (w.reserved or 0) + amt
        db.commit()
        return tx_id
    finally:
        db.close()

def create_reserve(user_id:int, currency:str, amount):
    """Reserve funds: credit reserved account, debit available account (amount should be positive)"""
    amt = Decimal(amount)
    entries = [
        {'account': _account_user_reserved(user_id,currency), 'amount': str(amt)},
        {'account': _account_user_available(user_id,currency), 'amount': str(-amt)}
    ]
    return post_transaction(entries, ref='reserve')

def release_reserve(user_id:int, currency:str, amount):
    amt = Decimal(amount)
    entries = [
        {'account': _account_user_reserved(user_id,currency), 'amount': str(-amt)},
        {'account': _account_user_available(user_id,currency), 'amount': str(amt)}
    ]
    return post_transaction(entries, ref='release')

def settle_trade(from_user:int, to_user:int, currency:str, amount, fee_amount=0):
    """Settle trade: move amount from from_user reserved to to_user available, collect fee to platform."""
    amt = Decimal(amount)
    fee = Decimal(fee_amount)
    platform_acc = _account_platform_fees(currency)
    entries = []
    # debit from_user reserved
    entries.append({'account': _account_user_reserved(from_user,currency), 'amount': str(-amt)})
    # credit to_user available (gross)
    entries.append({'account': _account_user_available(to_user,currency), 'amount': str(amt - fee)})
    # credit platform fees
    if fee != 0:
        entries.append({'account': platform_acc, 'amount': str(fee)})
        # balancing counter entry: platform fee is a credit, need an opposite debit: reduce buyer's reserved by fee as part of debit from_user_reserved already
        # The initial debit covers both transfer and fee since we debited full amt from reserved, and credited net to recipient and credited fee to platform. Total balances sum to zero.
    return post_transaction(entries, ref='settle')
