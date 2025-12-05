"""User related API routes."""

from __future__ import annotations

import re
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, desc
from sqlmodel import Session, select

from .. import models, schemas
from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from ..database import get_session
from ..profanity import contains_profanity
from ..rate_limit import (
    check_login_rate_limit,
    check_register_rate_limit,
    reset_login_rate_limit,
)

router = APIRouter(prefix="/users", tags=["users"])

# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: schemas.UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    _rate_limit: None = Depends(check_register_rate_limit),
):
    clean_username = user_in.username.strip()
    if not clean_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nazwa użytkownika nie może być pusta.",
        )
    
    if contains_profanity(clean_username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nazwa użytkownika zawiera niedozwolone słowa.",
        )
    
    # Password validation
    if len(user_in.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hasło musi zawierać co najmniej 8 znaków.",
        )

    clean_email = None
    if user_in.email is not None:
        stripped_email = user_in.email.strip()
        if stripped_email:
            # Validate email format
            if not EMAIL_REGEX.match(stripped_email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nieprawidłowy format adresu email.",
                )
            clean_email = stripped_email

    clean_avatar_url = None
    if user_in.avatar_url is not None:
        stripped_avatar = user_in.avatar_url.strip()
        clean_avatar_url = stripped_avatar or None

    existing = session.exec(
        select(models.User).where(models.User.username == clean_username)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ta nazwa użytkownika jest już zajęta.")

    user = models.User(
        username=clean_username,
        email=clean_email,
        avatar_url=clean_avatar_url,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    user_in: schemas.UserLogin,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    _rate_limit: None = Depends(check_login_rate_limit),
):
    # 1. Fetch user for locking check (username only)
    user = session.exec(select(models.User).where(models.User.username == user_in.username)).first()
    
    if not user:
        # Mitigate timing attacks
        verify_password("dummy", "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowa nazwa użytkownika lub hasło")

    # 2. Check lock status
    if user.locked_until and user.locked_until > dt.datetime.now():
        wait_seconds = (user.locked_until - dt.datetime.now()).seconds
        minutes = max(1, wait_seconds // 60)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Konto zablokowane z powodu zbyt wielu prób. Spróbuj ponownie za {minutes} min."
        )

    # 3. Verify password
    if not verify_password(user_in.password, user.hashed_password):
        # Increment failure counter
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        user.last_failed_login = dt.datetime.now()
        
        # Check if should lock (e.g. 5th attempt failed)
        if user.failed_login_attempts >= 5:
            user.locked_until = dt.datetime.now() + dt.timedelta(minutes=15)
            session.add(user)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Zbyt wiele nieudanych prób. Konto zostało zablokowane na 15 minut."
            )
            
        session.add(user)
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowa nazwa użytkownika lub hasło")

    # 4. Success - Reset counters
    if (user.failed_login_attempts or 0) > 0 or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        session.add(user)
        session.commit()
    
    # 5. Create token & Set HttpOnly Cookie
    reset_login_rate_limit(request)
    
    token = create_access_token({"sub": str(user.id)})
    
    # Set secure HttpOnly cookie for SSR authentication
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False, # WARNING: Set to True in production with HTTPS
    )
    
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserRead)
async def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserRead)
def update_current_user(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    updated = False

    if payload.email is not None:
        email_value = payload.email.strip() or None
        if current_user.email != email_value:
            current_user.email = email_value
            updated = True

    if payload.avatar_url is not None:
        avatar_value = payload.avatar_url.strip() or None
        if current_user.avatar_url != avatar_value:
            current_user.avatar_url = avatar_value
            updated = True

    if payload.new_password:
        if len(payload.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hasło musi zawierać co najmniej 8 znaków.",
            )
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Niepoprawne bieżące hasło.",
            )
        current_user.hashed_password = get_password_hash(payload.new_password)
        updated = True

    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    return current_user


@router.get("/", response_model=list[schemas.UserRead])
def read_users(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """Get list of users (Admin only logic to be added later)."""
    users = session.exec(select(models.User).offset(skip).limit(limit)).all()
    return users


@router.get("/stats/dashboard")
def get_dashboard_stats(session: Session = Depends(get_session)):
    """Get aggregated statistics for the Collector App Dashboard."""
    
    # 1. Total Users
    total_users = session.exec(select(func.count(models.User.id))).one()
    
    # 2. Total Collections
    total_collections = session.exec(select(func.count(models.Collection.id))).one()
    
    # 3. Total Cards in Database
    total_cards = session.exec(select(func.count(models.CardRecord.id))).one()
    
    # 4. Total Products in Database
    total_products = session.exec(select(func.count(models.ProductRecord.id))).one()
    
    # 5. Average Card Price
    avg_price_result = session.exec(
        select(func.avg(models.CardRecord.price))
        .where(models.CardRecord.price.is_not(None))
    ).first()
    average_card_price = float(avg_price_result) if avg_price_result else 0.0
    
    # 6. Most Added Card (from collections)
    most_popular_card_stmt = (
        select(models.Card.name, models.Card.set_code, models.Card.number, func.count(models.CollectionEntry.id).label("count"))
        .join(models.CollectionEntry)
        .group_by(models.Card.id)
        .order_by(desc("count"))
        .limit(1)
    )
    popular_card = session.exec(most_popular_card_stmt).first()
    
    popular_card_data = None
    if popular_card:
        popular_card_data = {
            "name": popular_card[0],
            "set_code": popular_card[1],
            "number": popular_card[2],
            "count": popular_card[3]
        }

    # 7. Most Valuable Card (in master DB)
    most_valuable_stmt = (
        select(models.Card)
        .where(models.Card.price.is_not(None))
        .order_by(desc(models.Card.price))
        .limit(1)
    )
    expensive_card = session.exec(most_valuable_stmt).first()
    
    expensive_card_data = None
    if expensive_card:
        expensive_card_data = {
            "name": expensive_card.name,
            "set_code": expensive_card.set_code,
            "number": expensive_card.number,
            "price": expensive_card.price,
            "image": expensive_card.image_small
        }

    # 8. Top 5 Most Popular Cards
    top_cards_stmt = (
        select(models.Card.name, models.Card.set_code, models.Card.number, models.Card.price, models.Card.image_small, func.count(models.CollectionEntry.id).label("count"))
        .join(models.CollectionEntry)
        .group_by(models.Card.id)
        .order_by(desc("count"))
        .limit(5)
    )
    top_cards_rows = session.exec(top_cards_stmt).all()
    
    top_cards = None
    if top_cards_rows:
        top_cards = [
            {
                "name": card[0],
                "set_code": card[1],
                "number": card[2],
                "price": card[3] or 0.0,
                "image": card[4],
                "count": card[5]
            }
            for card in top_cards_rows
        ]

    # 9. System Status
    system_status = "healthy"  # Could be based on sync status in future
    
    # 10. Last Sync Time (from latest CardRecord update)
    last_sync_result = session.exec(
        select(func.max(models.CardRecord.updated_at))
    ).first()
    last_sync = last_sync_result if last_sync_result else None

    return {
        "total_users": total_users,
        "total_collections": total_collections,
        "online_users": 1,  # Placeholder
        "shop_clicks": 42,  # Placeholder
        "total_cards": total_cards,
        "total_products": total_products,
        "average_card_price": average_card_price,
        "last_sync": last_sync,
        "system_status": system_status,
        "most_popular_card": popular_card_data,
        "most_valuable_card": expensive_card_data,
        "top_cards": top_cards
    }
