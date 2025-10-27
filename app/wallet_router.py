# app/wallet_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, condecimal
from typing import Optional, List
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from .dependencies import get_async_session  # you may already have a dependency util; adjust path if needed
from .wallet_service import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])
service = WalletService()

# Request schemas
class AmountRequest(BaseModel):
    user_id: int = Field(..., example=1)
    asset: str = Field(..., example="USDT")
    amount: condecimal(gt=0, decimal_places=8) = Field(..., example="10.5")
    metadata: Optional[dict] = None

class TransferRequest(BaseModel):
    from_user_id: int = Field(..., example=1)
    to_user_id: int = Field(..., example=2)
    asset: str = Field(..., example="USDT")
    amount: condecimal(gt=0, decimal_places=8) = Field(..., example="1.0")
    metadata: Optional[dict] = None

# Response schemas (keep lightweight)
class LedgerEntryOut(BaseModel):
    id: int
    user_id: int
    asset: str
    amount: Decimal
    balance_after: Optional[Decimal] = None
    type: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None

    class Config:
        orm_mode = True

@router.post("/deposit", response_model=LedgerEntryOut)
async def deposit(req: AmountRequest, session: AsyncSession = Depends(get_async_session)):
    try:
        entry = await service.deposit(session=session, user_id=req.user_id, asset=req.asset, amount=Decimal(req.amount), metadata=req.metadata)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="deposit failed")
    return entry

@router.post("/withdraw", response_model=LedgerEntryOut)
async def withdraw(req: AmountRequest, session: AsyncSession = Depends(get_async_session)):
    try:
        entry = await service.withdraw(session=session, user_id=req.user_id, asset=req.asset, amount=Decimal(req.amount), metadata=req.metadata)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="withdraw failed")
    return entry

@router.post("/transfer")
async def transfer(req: TransferRequest, session: AsyncSession = Depends(get_async_session)):
    try:
        result = await service.transfer(session=session, from_user_id=req.from_user_id, to_user_id=req.to_user_id, asset=req.asset, amount=Decimal(req.amount), metadata=req.metadata)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="transfer failed")
    # result shape depends on ledger_service.transfer_between_users; return minimally
    return {"status": "ok", "detail": "transfer completed", "result": result}

@router.get("/ledger/{user_id}", response_model=List[LedgerEntryOut])
async def get_ledger(user_id: int, limit: int = 100, offset: int = 0, session: AsyncSession = Depends(get_async_session)):
    try:
        entries = await service.get_ledger(session=session, user_id=user_id, limit=limit, offset=offset)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="could not fetch ledger")
    return entries

@router.get("/balance/{user_id}/{asset}")
async def get_balance(user_id: int, asset: str, session: AsyncSession = Depends(get_async_session)):
    try:
        bal = await service.get_balance(session=session, user_id=user_id, asset=asset)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="could not fetch balance")
    return {"user_id": user_id, "asset": asset, "balance": str(bal)}


