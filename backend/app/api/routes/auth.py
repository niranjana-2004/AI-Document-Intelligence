from app.core import database
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.otp import OTPVerification
from app.schemas.auth import (
    RegisterRequest,
    OTPVerifyRequest,
    LoginRequest,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == request.email.lower()
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists."
        )

    password_hash = hash_password(request.password)

    user = User(
        full_name=request.full_name.strip(),
        email=request.email.lower(),
        password_hash=password_hash,
        is_verified=False
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    otp = generate_otp()
    otp_hash = hash_password(otp)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    otp_record = OTPVerification(
        user_id=user.id,
        otp_hash=otp_hash,
        purpose="registration",
        expires_at=expires_at,
        is_used=False
    )

    db.add(otp_record)
    db.commit()

    print(f"[DEV OTP] Registration OTP for {user.email}: {otp}")

    return {
        "message": "Registration successful. Please verify your email with the OTP.",
        "user_id": user.id,
        "email": user.email
    }


@router.post("/verify-otp")
def verify_otp(
    request: OTPVerifyRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == request.email.lower()
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    if user.is_verified:
        raise HTTPException(
            status_code=400,
            detail="This account is already verified."
        )

    otp_record = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.user_id == user.id,
            OTPVerification.purpose == "registration",
            OTPVerification.is_used == False
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="No valid OTP found. Please request a new OTP."
        )

    # SQLite may return timezone-naive datetime values.
    expires_at = otp_record.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP has expired. Please request a new OTP."
        )

    if not verify_password(request.otp, str(otp_record.otp_hash)):
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP."
        )

    user.is_verified = True  # type: ignore[assignment]
    otp_record.is_used = True  # type: ignore[assignment]

    db.commit()

    return {
        "message": "Email verified successfully.",
        "email": user.email
    }
@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == request.email.lower()
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    if not verify_password(
        request.password,
        str(user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in."
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email
        }
    )

    return {
        "message": "Login successful.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        }
    }