from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from .models import OrderStatus


class UserProfileBase(BaseModel):
    username: str
    email: EmailStr
    phone_number: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(UserProfileBase):
    id: int
    registered_date: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class ProductBase(BaseModel):
    category: str
    store: str
    product_name: str
    price: float


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    category: Optional[str] = None
    store: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[float] = None


class ProductResponse(ProductBase):
    id: int
    created_date: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class OrderCreate(BaseModel):
    product_id: int


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    status: OrderStatus
    created_date: datetime
    product: Optional[ProductResponse] = None
    user: Optional[UserProfileResponse] = None

    class Config:
        orm_mode = True
        from_attributes = True
