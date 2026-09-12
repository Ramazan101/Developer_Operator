from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
import hashlib
import hmac
import uuid

from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import secrets


from developeroperator.models import SessionLocal, UserProfile

load_dotenv(Path(__file__).resolve().parent / ".env")
SECRET_KEY = os.getenv(
    "SECRET_KEY"
)
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login/")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload.setdefault("jti", uuid.uuid4().hex)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> UserProfile:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != "access":
            raise credentials_error
        username = payload.get("sub")
        if not username:
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    user = db.query(UserProfile).filter(UserProfile.username == username).first()
    if user is None:
        raise credentials_error
    return user