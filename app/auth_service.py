# app/auth_service.py
"""
Authentication Service (FIXED)
==============================
JWT token generation/validation, password hashing, and refresh token persistence
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.models import RefreshToken

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AuthService:
    """
    Handles all authentication operations:
    - Password hashing and verification
    - JWT token creation and validation
    - Token refresh logic with database persistence
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================
    # PASSWORD METHODS
    # ==================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain text password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        return pwd_context.verify(plain_password, hashed_password)
    
    # ==================
    # JWT TOKEN METHODS
    # ==================
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token
        
        Args:
            data: Payload to encode (e.g., {"user_id": 1, "email": "user@example.com"})
            expires_delta: Optional custom expiration time
        
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT refresh token
        
        Args:
            data: Payload to encode (e.g., {"user_id": 1})
            expires_delta: Optional custom expiration time
        
        Returns:
            Encoded JWT refresh token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict if valid, None if invalid/expired
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode a JWT token without verification (use carefully)
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict or None
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})
            return payload
        except Exception:
            return None
    
    # ==================
    # TOKEN VALIDATION
    # ==================
    
    def validate_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate an access token
        
        Returns:
            Payload if valid, None otherwise
        """
        payload = self.verify_token(token)
        
        if not payload:
            return None
        
        if payload.get("type") != "access":
            return None
        
        return payload
    
    def validate_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a refresh token (checks both JWT validity and database existence)
        
        Returns:
            Payload if valid, None otherwise
        """
        payload = self.verify_token(token)
        
        if not payload:
            return None
        
        if payload.get("type") != "refresh":
            return None
        
        # Check if token exists in database
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token == token
        ).first()
        
        if not db_token:
            return None
        
        # Check if token is expired
        if db_token.expires_at < datetime.utcnow():
            # Clean up expired token
            self.db.delete(db_token)
            self.db.commit()
            return None
        
        return payload
    
    # ==================
    # TOKEN PERSISTENCE
    # ==================
    
    def store_refresh_token(self, user_id: int, token: str) -> RefreshToken:
        """
        Store refresh token in database
        
        Args:
            user_id: User ID
            token: Refresh token string
        
        Returns:
            Created RefreshToken object
        """
        # Decode token to get expiration
        payload = self.decode_token(token)
        
        if not payload or "exp" not in payload:
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        else:
            expires_at = datetime.fromtimestamp(payload["exp"])
        
        # Create refresh token record
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        
        self.db.add(refresh_token)
        # Note: Caller should commit
        
        return refresh_token
    
    def revoke_refresh_token(self, token: str) -> bool:
        """
        Revoke (delete) a refresh token
        
        Args:
            token: Refresh token string to revoke
        
        Returns:
            True if token was revoked, False if not found
        """
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token == token
        ).first()
        
        if db_token:
            self.db.delete(db_token)
            self.db.commit()
            return True
        
        return False
    
    def revoke_all_user_tokens(self, user_id: int) -> int:
        """
        Revoke all refresh tokens for a user (useful for logout from all devices)
        
        Args:
            user_id: User ID
        
        Returns:
            Number of tokens revoked
        """
        count = self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id
        ).delete()
        
        self.db.commit()
        return count
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired refresh tokens (should be called periodically)
        
        Returns:
            Number of tokens deleted
        """
        count = self.db.query(RefreshToken).filter(
            RefreshToken.expires_at < datetime.utcnow()
        ).delete()
        
        self.db.commit()
        return count