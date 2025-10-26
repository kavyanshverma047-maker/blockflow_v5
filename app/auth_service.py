from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db import get_db
from app.models import User, RefreshToken, APIKey

from app.utils.security import (
    hash_password, verify_password, create_access_token, decode_access_token,
    generate_refresh_token, hash_token, generate_api_key
)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class RegisterIn(BaseModel):
    username: str
    email: EmailStr | None = None
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None

class LoginIn(BaseModel):
    username: str
    password: str

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=payload.username, email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "user": user.username}

@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = create_access_token(subject=str(user.id), data={"username": user.username})
    refresh_plain = generate_refresh_token()
    token = RefreshToken(user_id=user.id, token_hash=hash_token(refresh_plain),
                         expires_at=datetime.utcnow() + timedelta(days=30))
    db.add(token)
    db.commit()
    return TokenOut(access_token=access, refresh_token=refresh_plain, expires_in=900)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user

@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email}

@router.post("/apikeys")
def create_api_key(user=Depends(get_current_user), db: Session = Depends(get_db)):
    plain = generate_api_key()
    api_key = ApiKey(user_id=user.id, name=f"Key_{datetime.utcnow().isoformat()}", key_hash=hash_token(plain))
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {"api_key": plain, "key_id": api_key.id}
