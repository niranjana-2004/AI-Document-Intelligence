import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User
from app.models.otp import OTPVerification
from app.core.security import hash_password, create_access_token


class TestEmailVerificationStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure in-memory SQLite database for isolated test run
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
        db = self.TestingSessionLocal()
        db.query(OTPVerification).delete()
        db.query(User).delete()
        db.commit()

        # 1. Verified user
        self.verified_user = User(
            full_name="Verified User",
            email="verified@example.com",
            phone="1234567890",
            password_hash=hash_password("StrongPassword123!"),
            is_verified=True,
        )
        db.add(self.verified_user)

        # 2. Unverified user
        self.unverified_user = User(
            full_name="Unverified User",
            email="unverified@example.com",
            phone="0987654321",
            password_hash=hash_password("StrongPassword123!"),
            is_verified=False,
        )
        db.add(self.unverified_user)
        db.commit()

        db.refresh(self.verified_user)
        db.refresh(self.unverified_user)
        self.verified_id = self.verified_user.id
        self.unverified_id = self.unverified_user.id
        db.close()

    def test_registration_creates_unverified_user(self):
        """New registration must create a user with is_verified=False in the database."""
        with patch("app.api.routes.auth.send_registration_otp_email"):
            resp = self.client.post(
                "/auth/register",
                json={
                    "full_name": "New Person",
                    "email": "newperson@example.com",
                    "password": "StrongPassword123!",
                },
            )
            self.assertEqual(resp.status_code, 200)

            db = self.TestingSessionLocal()
            created_user = (
                db.query(User)
                .filter(User.email == "newperson@example.com")
                .first()
            )
            self.assertIsNotNone(created_user)
            self.assertFalse(created_user.is_verified)
            db.close()

    def test_unverified_user_login_blocked(self):
        """Unverified user cannot log in and receives HTTP 403."""
        resp = self.client.post(
            "/auth/login",
            json={
                "email": "unverified@example.com",
                "password": "StrongPassword123!",
            },
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("verify your email before logging in", resp.json()["detail"])

    def test_verified_user_login_returns_is_verified_true(self):
        """Verified user can log in and response contains is_verified: True."""
        resp = self.client.post(
            "/auth/login",
            json={
                "email": "verified@example.com",
                "password": "StrongPassword123!",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertIn("user", data)
        user_info = data["user"]
        self.assertEqual(user_info["email"], "verified@example.com")
        self.assertTrue(user_info["is_verified"])
        self.assertEqual(user_info["phone"], "1234567890")

    def test_otp_verification_persists_status_in_database(self):
        """Valid OTP verification transitions user.is_verified to True in the database."""
        db = self.TestingSessionLocal()
        otp_hash = hash_password("654321")
        otp_record = OTPVerification(
            user_id=self.unverified_id,
            otp_hash=otp_hash,
            purpose="registration",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_used=False,
        )
        db.add(otp_record)
        db.commit()
        db.close()

        resp = self.client.post(
            "/auth/verify-otp",
            json={
                "email": "unverified@example.com",
                "otp": "654321",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("is_verified"))

        # Verify DB field is persisted
        db = self.TestingSessionLocal()
        updated_user = db.query(User).filter(User.id == self.unverified_id).first()
        self.assertTrue(updated_user.is_verified)
        db.close()

    def test_already_verified_user_otp_verification_rejected(self):
        """Attempting to verify OTP for an already verified user returns HTTP 400."""
        resp = self.client.post(
            "/auth/verify-otp",
            json={
                "email": "verified@example.com",
                "otp": "123456",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already verified", resp.json()["detail"])

    def test_get_profile_returns_verified_status(self):
        """GET /auth/profile returns is_verified: True for a verified user."""
        token = create_access_token(
            data={"sub": str(self.verified_id), "email": "verified@example.com"}
        )
        resp = self.client.get(
            "/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("user", data)
        self.assertTrue(data["user"]["is_verified"])
        self.assertEqual(data["user"]["email"], "verified@example.com")

    def test_get_profile_returns_unverified_status(self):
        """GET /auth/profile returns is_verified: False for an unverified user token."""
        token = create_access_token(
            data={"sub": str(self.unverified_id), "email": "unverified@example.com"}
        )
        resp = self.client.get(
            "/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("user", data)
        self.assertFalse(data["user"]["is_verified"])
        self.assertEqual(data["user"]["email"], "unverified@example.com")

    def test_get_profile_unauthenticated_returns_401(self):
        """GET /auth/profile without token returns HTTP 401."""
        resp = self.client.get("/auth/profile")
        self.assertEqual(resp.status_code, 401)

    def test_update_profile_preserves_verified_status(self):
        """PUT /auth/profile updates profile and preserves is_verified: True."""
        token = create_access_token(
            data={"sub": str(self.verified_id), "email": "verified@example.com"}
        )
        resp = self.client.put(
            "/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "full_name": "Updated Name",
                "phone": "9998887776",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user"]["full_name"], "Updated Name")
        self.assertEqual(data["user"]["phone"], "9998887776")
        self.assertTrue(data["user"]["is_verified"])
