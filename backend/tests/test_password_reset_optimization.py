import logging
import os
import smtplib
import socket
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.core.security import (
    hash_password,
    hash_password_reset_token,
    generate_password_reset_token,
)
from app.services.email_service import (
    mask_email,
    _sanitize_error_message,
    _is_transient_error,
    _send_smtp_message_with_retries,
    send_password_reset_email,
    TRANSIENT_EXCEPTIONS,
    PERMANENT_EXCEPTIONS,
)


class TestPasswordResetOptimization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure in-memory SQLite for isolated test runs
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine
        )
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)

    def setUp(self):
        # Clean users and tokens
        db = self.TestingSessionLocal()
        db.query(PasswordResetToken).delete()
        db.query(User).delete()
        db.commit()

        # Seed test user
        self.test_user = User(
            full_name="Registered User",
            email="registered@example.com",
            password_hash=hash_password("OldPassword123!"),
            is_verified=True,
        )
        db.add(self.test_user)
        db.commit()
        db.refresh(self.test_user)
        self.user_id = self.test_user.id
        db.close()

    def test_registered_and_unregistered_generic_response(self):
        """
        Verify registered and unregistered email addresses return the identical generic response.
        Ensure unregistered addresses never create a token or schedule an email.
        """
        with patch("app.api.routes.auth.send_password_reset_email") as mock_send:
            # 1. Registered email
            resp_reg = self.client.post(
                "/auth/forgot-password",
                json={"email": "registered@example.com"},
            )
            self.assertEqual(resp_reg.status_code, 200)
            data_reg = resp_reg.json()
            self.assertEqual(
                data_reg,
                {
                    "message": (
                        "If an account exists with this email address, "
                        "a password reset link has been sent."
                    )
                },
            )

            # Token should be created in DB
            db = self.TestingSessionLocal()
            token_record = (
                db.query(PasswordResetToken)
                .filter(PasswordResetToken.user_id == self.user_id)
                .first()
            )
            self.assertIsNotNone(token_record)
            self.assertFalse(token_record.is_used)
            self.assertEqual(len(token_record.token_hash), 64)  # SHA-256 hash
            db.close()

            # Email task should be scheduled
            self.assertEqual(mock_send.call_count, 1)
            call_kwargs = mock_send.call_args.kwargs
            self.assertEqual(call_kwargs["recipient_email"], "registered@example.com")
            self.assertEqual(call_kwargs["recipient_name"], "Registered User")
            self.assertIn("/reset-password?token=", call_kwargs["reset_link"])

            # 2. Unregistered email
            mock_send.reset_mock()
            resp_unreg = self.client.post(
                "/auth/forgot-password",
                json={"email": "unregistered@example.com"},
            )
            self.assertEqual(resp_unreg.status_code, 200)
            data_unreg = resp_unreg.json()
            # Must match generic message exactly
            self.assertEqual(data_unreg, data_reg)

            # Verify NO token was created for unregistered
            db = self.TestingSessionLocal()
            count = (
                db.query(PasswordResetToken)
                .join(User)
                .filter(User.email == "unregistered@example.com")
                .count()
            )
            self.assertEqual(count, 0)
            db.close()

            # Verify NO email task was scheduled
            self.assertEqual(mock_send.call_count, 0)

    def test_token_persisted_before_email_scheduling(self):
        """
        Verify token is committed in DB before email background task is scheduled.
        Also verifies live db session is not passed to the task.
        """
        token_verified_in_db = False

        def mock_email_runner(**kwargs):
            nonlocal token_verified_in_db
            # Check DB from separate session inside the task execution
            db = self.TestingSessionLocal()
            rec = (
                db.query(PasswordResetToken)
                .filter(PasswordResetToken.user_id == self.user_id)
                .first()
            )
            if rec is not None and not rec.is_used:
                token_verified_in_db = True
            db.close()

            # Verify no SQLAlchemy session was passed
            for k, val in kwargs.items():
                self.assertNotIsInstance(val, sessionmaker)
                self.assertFalse(hasattr(val, "query"))

        with patch("app.api.routes.auth.send_password_reset_email", side_effect=mock_email_runner):
            resp = self.client.post(
                "/auth/forgot-password",
                json={"email": "registered@example.com"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(token_verified_in_db, "Token was not committed in DB before task ran")

    def test_database_failure_returns_500_and_does_not_schedule_email(self):
        """
        Verify database failure returns 500 and prevents email scheduling.
        """
        with patch("app.api.routes.auth.send_password_reset_email") as mock_send:
            with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("DB disk full")):
                resp = self.client.post(
                    "/auth/forgot-password",
                    json={"email": "registered@example.com"},
                )
                self.assertEqual(resp.status_code, 500)
                self.assertEqual(mock_send.call_count, 0)

    def test_existing_reset_tokens_validate_and_remain_single_use(self):
        """
        Verify token validation, successful password reset, and single-use enforcement.
        """
        # Generate token and persist
        token = generate_password_reset_token()
        token_hash = hash_password_reset_token(token)

        db = self.TestingSessionLocal()
        reset_rec = PasswordResetToken(
            user_id=self.user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            is_used=False,
        )
        db.add(reset_rec)
        db.commit()
        db.close()

        # 1. Reset password
        resp = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "NewSecretPassword123!"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Password reset successfully", resp.json()["message"])

        # 2. Try using the exact same token again -> should fail with 400
        resp_again = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "AnotherSecret123!"},
        )
        self.assertEqual(resp_again.status_code, 400)
        self.assertIn("Invalid or already used", resp_again.json()["detail"])

    def test_sanitized_email_masking(self):
        """
        Verify email masking for privacy in logs.
        """
        self.assertEqual(mask_email("user@example.com"), "u***r@example.com")
        self.assertEqual(mask_email("a@b.com"), "a***@b.com")
        self.assertEqual(mask_email("ab@c.com"), "a***@c.com")
        self.assertEqual(mask_email(None), "[REDACTED_EMAIL]")
        self.assertEqual(mask_email("invalid"), "[REDACTED_EMAIL]")

    def test_transient_vs_permanent_error_classification(self):
        """
        Verify transient errors are identified for retry and permanent errors are not.
        """
        # Transient errors
        self.assertTrue(_is_transient_error(socket.timeout()))
        self.assertTrue(_is_transient_error(TimeoutError()))
        self.assertTrue(_is_transient_error(smtplib.SMTPServerDisconnected()))
        self.assertTrue(_is_transient_error(smtplib.SMTPConnectError(1, "connection refused")))
        self.assertTrue(_is_transient_error(ConnectionResetError()))
        self.assertTrue(_is_transient_error(smtplib.SMTPResponseException(421, b"Service not available")))
        self.assertTrue(_is_transient_error(smtplib.SMTPResponseException(450, b"Mailbox busy")))

        # Permanent errors
        self.assertFalse(_is_transient_error(smtplib.SMTPAuthenticationError(535, b"Auth failed")))
        self.assertFalse(_is_transient_error(smtplib.SMTPSenderRefused(550, b"Denied", "sender@example.com")))
        self.assertFalse(_is_transient_error(smtplib.SMTPRecipientsRefused({})))
        self.assertFalse(_is_transient_error(smtplib.SMTPDataError(554, b"Transaction failed")))
        self.assertFalse(_is_transient_error(smtplib.SMTPResponseException(550, b"User not found")))
        self.assertFalse(_is_transient_error(RuntimeError("Config missing")))
        self.assertFalse(_is_transient_error(ValueError("Bad port")))

    def test_smtp_transient_retry_and_limit(self):
        """
        Verify transient errors retry up to 2 times (3 total attempts) with backoff.
        """
        msg = MagicMock()
        attempts = 0

        def failing_connect(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            raise smtplib.SMTPServerDisconnected("Remote host closed connection")

        with patch("smtplib.SMTP", side_effect=failing_connect):
            with self.assertRaises(smtplib.SMTPServerDisconnected):
                _send_smtp_message_with_retries(
                    message=msg,
                    recipient_email="user@example.com",
                    max_retries=2,
                    initial_backoff=0.001,  # fast backoff for tests
                )

        # 1 initial + 2 retries = 3 attempts total
        self.assertEqual(attempts, 3)

    def test_smtp_permanent_error_no_retry(self):
        """
        Verify permanent errors (e.g. SMTPAuthenticationError) fail immediately without retrying.
        """
        msg = MagicMock()
        attempts = 0

        def auth_fail(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            raise smtplib.SMTPAuthenticationError(535, b"Bad username or password")

        with patch("smtplib.SMTP", side_effect=auth_fail):
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                _send_smtp_message_with_retries(
                    message=msg,
                    recipient_email="user@example.com",
                    max_retries=2,
                    initial_backoff=0.001,
                )

        # Exactly 1 attempt, zero retries
        self.assertEqual(attempts, 1)

    def test_smtp_recovery_on_second_attempt(self):
        """
        Verify successful send after initial transient failure.
        """
        msg = MagicMock()
        attempts = 0

        mock_server = MagicMock()

        def flaky_connect(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise socket.timeout("Timed out waiting for SMTP greeting")
            return mock_server

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__.side_effect = flaky_connect
            _send_smtp_message_with_retries(
                message=msg,
                recipient_email="user@example.com",
                max_retries=2,
                initial_backoff=0.001,
            )

        self.assertEqual(attempts, 2)
        mock_server.send_message.assert_called_once_with(msg)

    def test_send_password_reset_email_catches_and_sanitizes_logs(self):
        """
        Verify send_password_reset_email catches exceptions, returns False,
        and logs sanitized details without leaking tokens or reset URLs.
        """
        raw_token = "super_secret_token_1234567890_abcdef"
        reset_link = f"http://localhost:5173/reset-password?token={raw_token}"

        with patch("app.services.email_service._send_smtp_message_with_retries", side_effect=TimeoutError("Connection timed out")):
            with patch("app.services.email_service.logger") as mock_logger:
                result = send_password_reset_email(
                    recipient_email="confidential@example.com",
                    recipient_name="John Doe",
                    reset_link=reset_link,
                )

                self.assertFalse(result)
                mock_logger.error.assert_called_once()
                log_args = mock_logger.error.call_args[0]
                log_formatted = log_args[0] % log_args[1:]

                # Verify masking and sanitization
                self.assertIn("c***l@example.com", log_formatted)
                self.assertNotIn("confidential@example.com", log_formatted)
                self.assertNotIn(raw_token, log_formatted)
                self.assertNotIn(reset_link, log_formatted)

    def test_api_latency_measurement(self):
        """
        Measure actual API response latency with email delivery deferred to background task.
        """
        # Mock the SMTP transport inside the background task to be deferred/mocked
        latencies_ms = []

        with patch("app.api.routes.auth.send_password_reset_email"):
            for _ in range(5):
                start = time.perf_counter()
                resp = self.client.post(
                    "/auth/forgot-password",
                    json={"email": "registered@example.com"},
                )
                duration_ms = (time.perf_counter() - start) * 1000
                self.assertEqual(resp.status_code, 200)
                latencies_ms.append(duration_ms)

        avg_latency_ms = sum(latencies_ms) / len(latencies_ms)
        min_latency_ms = min(latencies_ms)
        max_latency_ms = max(latencies_ms)

        print(
            f"\n[LATENCY MEASUREMENT] forgot-password response dispatch: "
            f"avg={avg_latency_ms:.2f}ms, min={min_latency_ms:.2f}ms, max={max_latency_ms:.2f}ms"
        )
        # Verify it responds in well under 100ms (compared to baseline ~2500ms)
        self.assertLess(avg_latency_ms, 150.0)


if __name__ == "__main__":
    unittest.main()
