from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=150
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )


class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
        max_length=128
    )


class OTPVerifyRequest(BaseModel):
    email: EmailStr

    otp: str = Field(
        ...,
        min_length=6,
        max_length=6
    )


class ResendOTPRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr

    otp: str = Field(
        ...,
        min_length=6,
        max_length=6
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )