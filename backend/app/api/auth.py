from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.schemas.auth import AuthResponse, AuthUser, LoginRequest, RegisterRequest
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    get_user_by_email,
    serialize_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = await create_user(db, name=payload.name, email=payload.email, password=payload.password)
    await db.commit()
    token = create_access_token(str(user.id))
    return AuthResponse(access_token=token, user=AuthUser(**serialize_user(user)))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, email=payload.email, password=payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(str(user.id))
    return AuthResponse(access_token=token, user=AuthUser(**serialize_user(user)))


@router.get("/me", response_model=AuthUser)
async def me(current_user=Depends(get_current_user)):
    return AuthUser(**serialize_user(current_user))
