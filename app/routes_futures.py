
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
