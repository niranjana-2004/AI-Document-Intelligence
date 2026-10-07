import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
SMTP_FROM_NAME = os.getenv(
    "SMTP_FROM_NAME",
    "AI Document Intelligence"
)

if not SMTP_USERNAME:
    raise RuntimeError("SMTP_USERNAME is not configured.")

if not SMTP_PASSWORD:
    raise RuntimeError("SMTP_PASSWORD is not configured.")

def send_password_reset_email(
    recipient_email: str,
    recipient_name: str,
    reset_link: str,
) -> None:
    """
    Send a password-reset email containing a secure reset link.
    """

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        raise RuntimeError(
            "SMTP email configuration is missing."
        )

    message = EmailMessage()

    message["Subject"] = "Reset your AI Document Intelligence password"
    message["From"] = (
        f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    )
    message["To"] = recipient_email

    message.set_content(
        f"""Hi {recipient_name},

We received a request to reset the password for your "
AI Document Intelligence account.

Use the link below to create a new password:

{reset_link}

This link will expire soon and can only be used once.

If you did not request a password reset, you can safely "
ignore this email. Your password will not be changed.

Regards,
AI Document Intelligence
"""
    )

    message.add_alternative(
    f"""
    <html>
        <body style="
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #12363d;
        ">
            <h2>Reset your password</h2>

            <p>Hi <strong>{recipient_name}</strong>,</p>

            <p>
                We received a request to reset the password
                for your AI Document Intelligence account.
            </p>

            <p>
                Click the button below to create a new password:
            </p>

            <p>
                <a href="{reset_link}"
                   style="
                       display: inline-block;
                       padding: 12px 20px;
                       background-color: #13b8a6;
                       color: white;
                       text-decoration: none;
                       border-radius: 8px;
                       font-weight: 600;
                   ">
                    Reset Password
                </a>
            </p>

            <p>
                This link will expire soon and can only be
                used once.
            </p>

            <p>
                If you did not request a password reset,
                you can safely ignore this email.
            </p>

            <p>
                Regards,<br>
                <strong>AI Document Intelligence</strong>
            </p>
        </body>
    </html>
    """,
    subtype="html"
)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)

def send_registration_otp_email(
    recipient_email: str,
    recipient_name: str,
    otp: str
):
    """
    Send the registration verification OTP by email.
    """

    message = EmailMessage()

    message["Subject"] = "Verify your AI Document Intelligence account"
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email

    message.set_content(
        f"""Hi {recipient_name},

Welcome to AI Document Intelligence!

Your email verification OTP is:

{otp}

This OTP will expire in 5 minutes.

If you did not create an account, you can safely ignore this email.

Regards,
AI Document Intelligence
"""
    )

    message.add_alternative(
        f"""
        <html>
            <body style="
                margin: 0;
                padding: 0;
                background-color: #f8fafc;
                font-family: Arial, sans-serif;
                color: #0f172a;
            ">
                <div style="
                    max-width: 520px;
                    margin: 40px auto;
                    background-color: #ffffff;
                    border-radius: 16px;
                    padding: 32px;
                    box-shadow: 0 8px 30px rgba(15, 23, 42, 0.08);
                ">

                    <h2 style="
                        margin-top: 0;
                        color: #0f766e;
                    ">
                        Verify your account
                    </h2>

                    <p>
                        Hi {recipient_name},
                    </p>

                    <p>
                        Welcome to
                        <strong>AI Document Intelligence</strong>!
                    </p>

                    <p>
                        Use the verification code below to verify
                        your email address:
                    </p>

                    <div style="
                        margin: 24px 0;
                        padding: 18px;
                        background-color: #f0fdfa;
                        border-radius: 12px;
                        text-align: center;
                        font-size: 32px;
                        font-weight: bold;
                        letter-spacing: 8px;
                        color: #0f766e;
                    ">
                        {otp}
                    </div>

                    <p>
                        This OTP will expire in
                        <strong>5 minutes</strong>.
                    </p>

                    <p style="
                        color: #64748b;
                        font-size: 14px;
                    ">
                        If you did not create an account, you can
                        safely ignore this email.
                    </p>

                    <p>
                        Regards,<br>
                        <strong>AI Document Intelligence</strong>
                    </p>

                </div>
            </body>
        </html>
        """,
        subtype="html"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)