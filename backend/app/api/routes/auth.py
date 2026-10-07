from app.core import database
import secrets
import os
from typing import cast
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.otp import OTPVerification
from app.models.document import Document
from app.models.activity import ActivityLog
from app.schemas.auth import (
    RegisterRequest,
    OTPVerifyRequest,
    LoginRequest,
    ResendOTPRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    ChangePasswordRequest,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from datetime import datetime, timedelta, timezone
from app.models.password_reset_token import PasswordResetToken
from app.services.email_service import (
    send_password_reset_email,
    send_registration_otp_email,
)
from app.core.security import (
    generate_password_reset_token,
    hash_password_reset_token,
)
from app.api.dependencies import get_current_user

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173"
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

    send_registration_otp_email(
        recipient_email=cast(str, user.email),
        recipient_name=cast(str, user.full_name),
        otp=otp
    )

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

@router.post("/resend-otp")
def resend_otp(
    request: ResendOTPRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == request.email.lower())
        .first()
    )

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

    otp = generate_otp()

    otp_hash = hash_password(otp)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=5)
    )

    otp_record = OTPVerification(
        user_id=user.id,
        otp_hash=otp_hash,
        purpose="registration",
        expires_at=expires_at,
        is_used=False
    )

    db.add(otp_record)
    db.commit()

    send_registration_otp_email(
    recipient_email=cast(str, user.email),
    recipient_name=cast(str, user.full_name),
    otp=otp
    )

    return {
    "message": "A new OTP has been sent to your email.",
    "email": user.email
    }

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == request.email.lower())
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email address."
        )

    # Generate a secure, random reset token
    reset_token = generate_password_reset_token()

    # Store only the hashed token in the database
    token_hash = hash_password_reset_token(reset_token)

    # Token expires after 30 minutes
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=30)
    )

    # Invalidate any previous unused reset tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False
    ).update(
        {"is_used": True},
        synchronize_session=False
    )

    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_used=False
    )

    db.add(reset_record)
    db.commit()

    # Create the link that will be sent by email
    reset_link = (
        f"{FRONTEND_URL}/reset-password"
        f"?token={reset_token}"
    )

    # Send the reset email
    send_password_reset_email(
        recipient_email=cast(str, user.email),
        recipient_name=cast(str, user.full_name),
        reset_link=reset_link
    )

    return {
        "message": "If an account exists with this email address, "
                   "a password reset link has been sent."
    }

@router.post("/resend-reset-otp")
def resend_reset_otp(
    request: ResendOTPRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == request.email.lower())
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email address."
        )

    otp = generate_otp()

    otp_hash = hash_password(otp)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=5)
    )

    otp_record = OTPVerification(
        user_id=user.id,
        otp_hash=otp_hash,
        purpose="password_reset",
        expires_at=expires_at,
        is_used=False
    )

    db.add(otp_record)
    db.commit()

    print(
        f"[DEV OTP] Resent password reset OTP "
        f"for {user.email}: {otp}"
    )

    return {
        "message": "A new password reset OTP has been generated.",
        "email": user.email
    }

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    # Hash the token received from the reset link
    token_hash = hash_password_reset_token(request.token)

    # Find the corresponding reset token
    reset_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used == False
        )
        .first()
    )

    if not reset_record:
        raise HTTPException(
            status_code=400,
            detail="Invalid or already used password reset link."
        )

    # Make the expiry timezone-aware if SQLite returned a naive datetime
    expires_at = reset_record.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    # Check whether the reset link has expired
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=400,
            detail="Password reset link has expired. Please request a new one."
        )

    # Find the user associated with this reset token
    user = (
        db.query(User)
        .filter(User.id == reset_record.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid password reset request."
        )

    # Update the password
    user.password_hash = hash_password(request.new_password)  # type: ignore[assignment]

    # Mark the reset token as used
    reset_record.is_used = True  # type: ignore[assignment]

    db.commit()

    return {
        "message": "Password reset successfully."
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

    # Record the latest successful login time
    user.last_login = datetime.now(timezone.utc)  # type: ignore[assignment]
    db.commit()

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

@router.put("/profile")
def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    setattr(current_user, "full_name", profile_data.full_name.strip())
    setattr(current_user, "phone", profile_data.phone)

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Profile updated successfully.",
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "is_verified": current_user.is_verified,
        },
    }

@router.put("/change-password")
def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify the current password
    if not verify_password(
        password_data.current_password,
        str(current_user.password_hash)
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect."
        )

    # Make sure the new password and confirmation match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="New passwords do not match."
        )

    # Prevent reusing the current password
    if verify_password(
        password_data.new_password,
        str(current_user.password_hash)
    ):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from your current password."
        )

    # Hash and save the new password
    current_user.password_hash = hash_password(password_data.new_password)  # type: ignore[assignment]

    db.commit()

    return {
        "message": "Password changed successfully."
    }

@router.get("/activity")
def get_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documents_count = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .count()
    )

    ai_questions_count = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.user_id == current_user.id,
            ActivityLog.activity_type == "ai_question"
        )
        .count()
    )

    searches_count = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.user_id == current_user.id,
            ActivityLog.activity_type == "search"
        )
        .count()
    )

    summaries_count = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.user_id == current_user.id,
            ActivityLog.activity_type == "summary"
        )
        .count()
    )

    return {
        "documents": documents_count,
        "ai_questions": ai_questions_count,
        "searches": searches_count,
        "summaries": summaries_count,
        "account_created": current_user.created_at,
        "last_login": current_user.last_login,
    }

@router.delete("/account")
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Remove activity history belonging to this account
    db.query(ActivityLog).filter(
        ActivityLog.user_id == current_user.id
    ).delete(synchronize_session=False)

    db.delete(current_user)
    db.commit()

    return {
        "message": "Account deleted successfully."
    }