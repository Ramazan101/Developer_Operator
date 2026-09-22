from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
try:
  from .models import OrderStatus
except (ImportError, ValueError):
  from models import OrderStatus

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


class AIAnalyzeRequest(BaseModel):
    text: str


class AIAnalyzeResponse(BaseModel):
    answer: str
    order_id: Optional[int] = None
    priority: int


class AIAnswerRequest(BaseModel):
    text: str
    facts: Optional[str] = ""


class AIAnswerResponse(BaseModel):
    text_draft: str
    review: bool


class OrderCreateAIRequest(BaseModel):
    text: str


class OrderItemAI(BaseModel):
    title: str
    category: str
    store: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1
    price: Optional[float] = None
    total_price: Optional[float] = None


class OrderCreateAIResponse(BaseModel):
    items: List[OrderItemAI]

class MeetingAnalyzeRequest(BaseModel):
  text: str


class TaskItem(BaseModel):
  title: str
  assignee: Optional[str] = None
  deadline_text: Optional[str] = None


class CheckItem(BaseModel):
  task_number: int
  needs_clarification: bool
  missing_fields: List[str]


class CheckStats(BaseModel):
  total_tasks: int
  complete_tasks: int
  without_assignee: int
  without_deadline: int


class CheckTasksResponse(BaseModel):
  stats: CheckStats
  checks: List[CheckItem]


class PlanCreateRequest(BaseModel):
  goal: str
  constraints: str
  count_tasks: int = 3


class PlanTask(BaseModel):
  task_number: int
  title: str
  details: str
  priority: int
  status: str = "todo"


class PlanCreateResponse(BaseModel):
  plan_status: str = "draft"
  tasks: List[PlanTask]
  tasks_count: int