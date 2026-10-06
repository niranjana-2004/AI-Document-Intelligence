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