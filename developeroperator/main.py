from datetime import timedelta
from pathlib import Path
import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from developeroperator.models import UserProfile
from developeroperator.schemas import (
    AccessTokenResponse,
    RefreshRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
    UserUpdate,
)

from developeroperator.settings_for_auth import (
    hash_password, verify_password,
    create_token, get_current_user,
    get_db
)

load_dotenv(Path(__file__).resolve().parent / ".env")
SECRET_KEY = os.getenv(
    "SECRET_KEY"
)
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login/")

app = FastAPI(title="Developer Operator")

@app.post("/register/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    if db.query(UserProfile).filter(UserProfile.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if db.query(UserProfile).filter(UserProfile.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    user = UserProfile(
        username=user_data.username,
        email=str(user_data.email),
        password=hash_password(user_data.password),
        phone_number=user_data.phone_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login/", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(UserProfile).filter(UserProfile.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_token(
        {"sub": user.username, "user_id": user.id, "token_type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_token(
        {"sub": user.username, "user_id": user.id, "token_type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@app.post("/refresh/", response_model=AccessTokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(UserProfile).filter(UserProfile.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_access_token = create_token(
        {"sub": user.username, "user_id": user.id, "token_type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": new_access_token, "token_type": "bearer"}


@app.post("/logout/")
def logout():
    return {"message": "Successfully logged out"}


@app.get("/me/", response_model=UserResponse)
def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user


@app.put("/me/update/", response_model=UserResponse)
def update_me(
    update_data: UserUpdate,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    values = update_data.model_dump(exclude_unset=True)

    new_username = values.get("username")
    if new_username and new_username != current_user.username:
        exists = (
            db.query(UserProfile).filter(UserProfile.username == new_username).first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Username already exists")

    new_email = values.get("email")
    if new_email and str(new_email) != current_user.email:
        exists = db.query(UserProfile).filter(UserProfile.email == str(new_email)).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already exists")
        values["email"] = str(new_email)

    new_password = values.pop("password", None)
    if new_password:
        current_user.password = hash_password(new_password)

    for key, value in values.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@app.delete("/me/delete/")
def delete_me(
    current_user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)
):
    db.delete(current_user)
    db.commit()
    return {"message": "User deleted successfully"}


@app.get("/verify/")
def verify(current_user: UserProfile = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "is_official": current_user.is_official,
    }