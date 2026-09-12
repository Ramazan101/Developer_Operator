from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=4, max_length=16)
    email: Optional[str] = None
    password: str = Field(min_length=3, max_length=32)
    phone_number: Optional[str] = None


class UserUpdate(BaseModel):
    username: str = Field(min_length=4, max_length=16)
    email: Optional[str] = None
    password: str = Field(min_length=3, max_length=32)
    phone_number: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str = Field(min_length=4, max_length=16)
    email: Optional[str] = None
    password: str = Field(min_length=3, max_length=32)
    phone_number: Optional[str] = None
    registered_date: datetime

    model_config = {"from_attributes": True}


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"