import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import hashlib
import secrets

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "blockflow-secret-key")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

def hash_password(password: str) -> str:
    return PWD_CONTEXT.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return PWD_CONTEXT.verify(plain, hashed)

def create_access_token(subject: str, data: dict = None, expires_delta: int = None):
    to_encode = {"sub": subject}
    if data:
        to_encode.update(data)
    expire = datetime.utcnow() + timedelta(minutes=(expires_delta or ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def decode_access_token(token: str):
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return payload

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def generate_api_key() -> str:
    return secrets.token_urlsafe(40)
