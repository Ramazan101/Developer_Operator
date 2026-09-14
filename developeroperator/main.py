from typing import List, Optional
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from requests import Request
from sqlalchemy.orm import Session

from chain.ticket_chain import analyze_ticket, answer_ticket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .database import Base, engine, get_db
from .models import Order, OrderStatus, Product, UserProfile
from .schemas import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserProfileCreate,
    UserProfileResponse,
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    AIAnswerRequest,
    AIAnswerResponse,
)
from .settings_for_auth import (
    blacklisted_tokens,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_password_hash,
    oauth2_scheme,
    verify_password,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DeliveryOperator API", version="1.0.0")

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
product_router = APIRouter(prefix="/products", tags=["Products"])
order_router = APIRouter(prefix="/orders", tags=["Orders"])
ai_router = APIRouter(prefix="/ai", tags=["AI Assistant"])


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
def analyze_endpoint(payload: AIAnalyzeRequest):
    # Если передан пустой текст, возвращаем 422
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Маалымат туура эмес форматта берилди",
        )

    result = analyze_ticket(payload.text)
    return result


@ai_router.post("/answer/", response_model=AIAnswerResponse)
def answer_endpoint(payload: AIAnswerRequest):
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Маалымат туура эмес форматта берилди",
        )

    result = answer_ticket(payload.text, payload.facts or "")
    return result


app.include_router(auth_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(ai_router)
