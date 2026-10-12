import logging
import os
import smtplib
import socket
import time
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
SMTP_FROM_NAME = os.getenv(
    "SMTP_FROM_NAME",
    "AI Document Intelligence"
)
SMTP_TIMEOUT = float(os.getenv("SMTP_TIMEOUT", "10"))

if not SMTP_USERNAME:
    logger.warning("SMTP_USERNAME is not configured.")

if not SMTP_PASSWORD:
    logger.warning("SMTP_PASSWORD is not configured.")


def mask_email(email: str | None) -> str:
    """
    Mask an email address for sanitized logging (e.g. u***r@example.com).
    """
    if not email or "@" not in email:
        return "[REDACTED_EMAIL]"
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + "***"
    else:
        masked_local = local_part[0] + "***" + local_part[-1]
    return f"{masked_local}@{domain}"


def _sanitize_error_message(exc: Exception) -> str:
    """
    Sanitize exception details to avoid logging raw credentials or tokens.
    """
    msg = f"{type(exc).__name__}: {str(exc)}"
    if SMTP_PASSWORD and SMTP_PASSWORD in msg:
        msg = msg.replace(SMTP_PASSWORD, "[REDACTED_PASSWORD]")
    return msg


TRANSIENT_EXCEPTIONS = (
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPConnectError,
    socket.timeout,
    TimeoutError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    BrokenPipeError,
    OSError,
)

PERMANENT_EXCEPTIONS = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPDataError,
    smtplib.SMTPNotSupportedError,
    smtplib.SMTPHeloError,
)


def _is_transient_error(exc: Exception) -> bool:
    """
    Determine whether an SMTP exception represents a transient failure eligible for retry.
    """
    if isinstance(exc, PERMANENT_EXCEPTIONS):
        return False
    if isinstance(exc, (RuntimeError, ValueError)):
        return False
    if isinstance(exc, smtplib.SMTPConnectError):
        return True
    if isinstance(exc, smtplib.SMTPResponseException):
        return 400 <= exc.smtp_code < 500
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True
    return False


def _send_smtp_message_with_retries(
    message: EmailMessage,
    recipient_email: str,
    description: str = "email",
    max_retries: int = 2,
    initial_backoff: float = 1.0,
    backoff_multiplier: float = 2.0,
) -> None:
    """
    Send an EmailMessage via SMTP with timeout and bounded exponential backoff for transient errors.
    At most `max_retries` retries are attempted after the initial attempt (up to 3 total attempts).
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        raise RuntimeError("SMTP email configuration is missing.")

    total_attempts = 1 + max_retries
    sanitized_email = mask_email(recipient_email)
    delay = initial_backoff

    for attempt in range(1, total_attempts + 1):
        try:
            if SMTP_PORT == 465:
                with smtplib.SMTP_SSL(
                    SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT
                ) as server:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.send_message(message)
            else:
                with smtplib.SMTP(
                    SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT
                ) as server:
                    server.starttls()
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.send_message(message)

            logger.info(
                "SMTP %s dispatched successfully to %s (attempt %d/%d)",
                description,
                sanitized_email,
                attempt,
                total_attempts,
            )
            return

        except Exception as exc:
            sanitized_err = _sanitize_error_message(exc)

            if not _is_transient_error(exc):
                logger.error(
                    "Permanent failure sending %s to %s on attempt %d/%d: %s. Not retrying.",
                    description,
                    sanitized_email,
                    attempt,
                    total_attempts,
                    sanitized_err,
                )
                raise

            if attempt < total_attempts:
                logger.warning(
                    "Transient SMTP error sending %s to %s (attempt %d/%d): %s. Retrying in %.2fs...",
                    description,
                    sanitized_email,
                    attempt,
                    total_attempts,
                    sanitized_err,
                    delay,
                )
                time.sleep(delay)
                delay *= backoff_multiplier
            else:
                logger.error(
                    "Exhausted all %d attempts sending %s to %s. Final error: %s",
                    total_attempts,
                    description,
                    sanitized_email,
                    sanitized_err,
                )
                raise


def send_password_reset_email(
    recipient_email: str,
    recipient_name: str,
    reset_link: str,
) -> bool:
    """
    Send a password-reset email containing a secure reset link.
    Failures inside background tasks are caught and logged with sanitized details.
    """
    sanitized_email = mask_email(recipient_email)
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            logger.error(
                "SMTP email configuration is missing; cannot send reset email to %s",
                sanitized_email,
            )
            return False

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
            subtype="html",
        )

        _send_smtp_message_with_retries(
            message=message,
            recipient_email=recipient_email,
            description="password reset email",
        )
        return True

    except Exception as exc:
        logger.error(
            "Failed to send password reset email to %s: %s",
            sanitized_email,
            _sanitize_error_message(exc),
        )
        return False


def send_registration_otp_email(
    recipient_email: str,
    recipient_name: str,
    otp: str,
) -> None:
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
        subtype="html",
    )

    _send_smtp_message_with_retries(
        message=message,
        recipient_email=recipient_email,
        description="registration OTP email",
    )