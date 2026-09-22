import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
for path in [CURRENT_DIR, BASE_DIR]:
  if path not in sys.path:
    sys.path.insert(0, path)

from typing import List, Optional
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Order, OrderStatus, Product, UserProfile
from schemas import (
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    AIAnswerRequest,
    AIAnswerResponse,
    CheckItem,
    CheckStats,
    CheckTasksResponse,
    MeetingAnalyzeRequest,
    OrderCreate,
    OrderCreateAIRequest,
    OrderCreateAIResponse,
    OrderResponse,
    OrderStatusUpdate,
    PlanCreateRequest,
    PlanCreateResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    RefreshTokenRequest,
    TaskItem,
    TokenResponse,
    UserLogin,
    UserProfileCreate,
    UserProfileResponse,
)
from settings_for_auth import (
    blacklisted_tokens,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_password_hash,
    oauth2_scheme,
    verify_password,
)

from chain.meetings_chain import analyze_meeting, create_plan
from chain.ticket_chain import (
    analyze_ticket,
    answer_ticket,
    parse_order_create,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DeliveryOperator API", version="1.0.0")

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
product_router = APIRouter(prefix="/products", tags=["Products"])
order_router = APIRouter(prefix="/orders", tags=["Orders"])
ai_router = APIRouter(prefix="/ai", tags=["AI Assistant"])
meetings_router = APIRouter(prefix="/meetings", tags=["Meetings"])
todos_router = APIRouter(prefix="/todos", tags=["Todos"])


@auth_router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: UserProfileCreate, db: Session = Depends(get_db)):
  if (
      db.query(UserProfile)
      .filter(UserProfile.username == user_data.username)
      .first()
  ):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Username is already registered",
    )
  if (
      db.query(UserProfile)
      .filter(UserProfile.email == user_data.email)
      .first()
  ):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email is already registered",
    )

  new_user = UserProfile(
      username=user_data.username,
      email=user_data.email,
      phone_number=user_data.phone_number,
      password=get_password_hash(user_data.password),
  )
  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  return new_user


@auth_router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
  user = (
      db.query(UserProfile)
      .filter(UserProfile.username == credentials.username)
      .first()
  )
  if not user or not verify_password(credentials.password, user.password):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

  access_token = create_access_token(data={"sub": user.username})
  refresh_token = create_refresh_token(data={"sub": user.username})

  return TokenResponse(
      access_token=access_token,
      refresh_token=refresh_token,
      token_type="bearer",
  )


@auth_router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
  blacklisted_tokens.add(token)
  return {"detail": "Successfully logged out"}


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)
):
  payload = decode_token(refresh_data.refresh_token, expected_type="refresh")
  username: str = payload.get("sub")

  user = db.query(UserProfile).filter(UserProfile.username == username).first()
  if not user:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
    )

  new_access_token = create_access_token(data={"sub": user.username})
  new_refresh_token = create_refresh_token(data={"sub": user.username})

  return TokenResponse(
      access_token=new_access_token,
      refresh_token=new_refresh_token,
      token_type="bearer",
  )


@auth_router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: UserProfile = Depends(get_current_user)):
  return current_user


# =====================================================================
# Product Endpoints
# =====================================================================
@product_router.post(
    "/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED
)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  product = Product(**product_data.dict())
  db.add(product)
  db.commit()
  db.refresh(product)
  return product


@product_router.get("/", response_model=List[ProductResponse])
def get_products(
    category: Optional[str] = None,
    store: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
  query = db.query(Product)
  if category:
    query = query.filter(Product.category.ilike(f"%{category}%"))
  if store:
    query = query.filter(Product.store.ilike(f"%{store}%"))
  return query.offset(skip).limit(limit).all()


@product_router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
  product = db.query(Product).filter(Product.id == product_id).first()
  if not product:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
    )
  return product


@product_router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  product = db.query(Product).filter(Product.id == product_id).first()
  if not product:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
    )

  for key, value in product_update.dict(exclude_unset=True).items():
    setattr(product, key, value)

  db.commit()
  db.refresh(product)
  return product


@product_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  product = db.query(Product).filter(Product.id == product_id).first()
  if not product:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
    )
  db.delete(product)
  db.commit()
  return None



@order_router.post(
    "/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED
)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  product = (
      db.query(Product).filter(Product.id == order_data.product_id).first()
  )
  if not product:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
    )

  order = Order(
      product_id=order_data.product_id,
      user_id=current_user.id,
      status=OrderStatus.pending,
  )
  db.add(order)
  db.commit()
  db.refresh(order)
  return order


@order_router.get("/", response_model=List[OrderResponse])
def get_orders(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  return (
      db.query(Order)
      .filter(Order.user_id == current_user.id)
      .offset(skip)
      .limit(limit)
      .all()
  )


@order_router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  order = (
      db.query(Order)
      .filter(Order.id == order_id, Order.user_id == current_user.id)
      .first()
  )
  if not order:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
    )
  return order


@order_router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  order = (
      db.query(Order)
      .filter(Order.id == order_id, Order.user_id == current_user.id)
      .first()
  )
  if not order:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
    )

  order.status = status_data.status
  db.commit()
  db.refresh(order)
  return order


@order_router.delete("/{order_id}", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
  order = (
      db.query(Order)
      .filter(Order.id == order_id, Order.user_id == current_user.id)
      .first()
  )
  if not order:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
    )

  order.status = OrderStatus.cancel
  db.commit()
  db.refresh(order)
  return order



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
  return JSONResponse(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      content={"detail": "Маалымат туура эмес форматта берилди"},
  )


@ai_router.post("/analyze/", response_model=AIAnalyzeResponse)
@ai_router.post("/analyze", response_model=AIAnalyzeResponse)
def analyze_endpoint(payload: AIAnalyzeRequest):
  if not payload.text or not payload.text.strip():
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Маалымат туура эмес форматта берилди",
    )
  return analyze_ticket(payload.text)


@ai_router.post("/answer/", response_model=AIAnswerResponse)
@ai_router.post("/answer", response_model=AIAnswerResponse)
def answer_endpoint(payload: AIAnswerRequest):
  if not payload.text or not payload.text.strip():
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Маалымат туура эмес форматта берилди",
    )
  return answer_ticket(payload.text, payload.facts or "")


@ai_router.post("/order_create/", response_model=OrderCreateAIResponse)
@ai_router.post("/order_create", response_model=OrderCreateAIResponse)
def order_create_endpoint(payload: OrderCreateAIRequest):
  if not payload.text or not payload.text.strip():
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Маалымат туура эмес форматта берилди",
    )
  return parse_order_create(payload.text)


@meetings_router.post("/analyze/", response_model=List[TaskItem])
@meetings_router.post("/analyze", response_model=List[TaskItem])
def meetings_analyze_endpoint(payload: MeetingAnalyzeRequest):
  return analyze_meeting(payload.text)


@meetings_router.post("/check_tasks/", response_model=CheckTasksResponse)
@meetings_router.post("/check_tasks", response_model=CheckTasksResponse)
def check_tasks_endpoint(tasks: List[TaskItem]):
  checks = []
  without_assignee = 0
  without_deadline = 0
  complete_tasks = 0

  for idx, task in enumerate(tasks, start=1):
    missing = []
    if not task.assignee:
      missing.append("assignee")
      without_assignee += 1
    if not task.deadline_text:
      missing.append("deadline_text")
      without_deadline += 1

    needs_clarification = len(missing) > 0
    if not needs_clarification:
      complete_tasks += 1

    checks.append(
        CheckItem(
            task_number=idx,
            needs_clarification=needs_clarification,
            missing_fields=missing,
        )
    )

  return CheckTasksResponse(
      stats=CheckStats(
          total_tasks=len(tasks),
          complete_tasks=complete_tasks,
          without_assignee=without_assignee,
          without_deadline=without_deadline,
      ),
      checks=checks,
  )


@todos_router.post("/plan_create/", response_model=PlanCreateResponse)
@todos_router.post("/plan_create", response_model=PlanCreateResponse)
@meetings_router.post("/todos/plan_create/", response_model=PlanCreateResponse)
def plan_create_endpoint(payload: PlanCreateRequest):
  return create_plan(payload.goal, payload.constraints, payload.count_tasks)


app.include_router(auth_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(ai_router)
app.include_router(meetings_router)
app.include_router(todos_router)



if __name__ == "__main__":
  import uvicorn

  uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)