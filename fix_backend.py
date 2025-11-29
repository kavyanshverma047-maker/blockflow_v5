import re

# ---------- PATCH MODELS ----------
text = open('app/models.py','r',encoding='utf8').read()

if 'class Ledger' in text and 'tx_id' not in text:
    print('? Adding tx_id to Ledger...')
    text = re.sub(
        r'class Ledger([^\\n]*\\n)',
        r'class Ledger\\1    tx_id = Column(String, nullable=False, index=True)\\n',
        text
    )
    open('app/models.py','w',encoding='utf8').write(text)
else:
    print('? tx_id exists or Ledger missing')

# ---------- ENSURE STRING IMPORT ----------
text2 = open('app/models.py','r',encoding='utf8').read()
if 'String' not in text2:
    print('? Adding String import...')
    text2 = re.sub(
        r'from sqlalchemy import',
        r'from sqlalchemy import String,',
        text2
    )
    open('app/models.py','w',encoding='utf8').write(text2)

# ---------- WRITE CLEAN FUTURES ROUTE ----------
print('? Writing clean futures route...')
open('app/routes_futures.py','w',encoding='utf8').write("""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from decimal import Decimal
from uuid import uuid4

def get_db():
    from app.main import get_db as _db
    return _db()

def get_current_user():
    from app.main import get_current_user as _user
    return _user()

class FuturesOpenRequest(BaseModel):
    pair: str
    side: str
    price: Decimal
    amount: Decimal
    leverage: int

router = APIRouter(prefix='/api/futures', tags=['futures'])

@router.post('/open')
def open_futures(payload: FuturesOpenRequest, user = Depends(lambda: get_current_user()), db: Session = Depends(lambda: get_db())):
    from app.models import FuturesUsdmTrade
    try:
        tx_id = str(uuid4())
        trade = FuturesUsdmTrade(
            username=user.username,
            pair=payload.pair,
            side=payload.side,
            price=payload.price,
            amount=payload.amount,
            leverage=payload.leverage
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return {"success": True, "id": trade.id, "tx_id": tx_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
""")

print("? PATCH COMPLETE")
