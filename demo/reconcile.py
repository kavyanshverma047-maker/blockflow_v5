# Reconciliation script: check ledger account aggregates vs wallets table
from sqlalchemy import text
from app.db import SessionLocal, engine, Base
from app import models
from decimal import Decimal
def reconcile():
    db = SessionLocal()
    try:
        # aggregate ledger by account
        rows = db.execute(text('SELECT account, SUM(amount) as s FROM ledger GROUP BY account')).fetchall()
        ledger_map = {r[0]: Decimal(r[1] or 0) for r in rows}
        # build wallet map of available and reserved
        wallets = db.query(models.Wallet).all()
        wallet_map = {}
        for w in wallets:
            wallet_map[f'user:{w.user_id}:{w.currency}:available'] = Decimal(w.available or 0)
            wallet_map[f'user:{w.user_id}:{w.currency}:reserved'] = Decimal(w.reserved or 0)
        # compare
        inconsistencies = []
        for acc, val in ledger_map.items():
            if acc.startswith('user:'):
                wval = wallet_map.get(acc, Decimal(0))
                if wval != val:
                    inconsistencies.append((acc, str(val), str(wval)))
        return inconsistencies
    finally:
        db.close()

if __name__=='__main__':
    inc = reconcile()
    if not inc:
        print('All reconciled ✅')
    else:
        print('Inconsistencies found:')
        for i in inc: print(i)
