import json
import os
import unittest


class TestVerificationFlowOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DINQ_AUTH_BYPASS", "true")
        os.environ.setdefault("DINQ_EMAIL_BACKEND", "file")
        os.environ.setdefault("DINQ_TEST_EMAIL_OUTBOX_PATH", "./.test_outbox/emails.jsonl")

        from src.utils.db_utils import create_tables

        assert create_tables()

        from server.app import app as flask_app

        cls.app = flask_app

    def setUp(self):
        self.client = self.app.test_client()
        self.user_id = "offline_verification_user"

        outbox = os.getenv("DINQ_TEST_EMAIL_OUTBOX_PATH")
        if outbox:
            os.makedirs(os.path.dirname(os.path.abspath(outbox)) or ".", exist_ok=True)
            try:
                os.remove(outbox)
            except FileNotFoundError:
                pass

        # Clean any existing records for deterministic runs.
        from src.models.user_verification import EmailVerification, UserVerification
        from src.utils.db_utils import get_db_session

        with get_db_session() as session:
            session.query(EmailVerification).filter(EmailVerification.user_id == self.user_id).delete()
            session.query(UserVerification).filter(UserVerification.user_id == self.user_id).delete()

    def _headers(self):
        return {"Userid": self.user_id}

    def _read_outbox(self) -> list:
        path = os.getenv("DINQ_TEST_EMAIL_OUTBOX_PATH")
        if not path or not os.path.exists(path):
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        return entries

    def test_end_to_end_verification_flow_offline(self):
        # 1) Start verification
        resp = self.client.post("/api/verification/start", json={"user_type": "job_seeker"}, headers=self._headers())
        self.assertIn(resp.status_code, (200, 201), resp.get_data(as_text=True))
        payload = resp.get_json()
        self.assertTrue(payload.get("success"))

        # 2) Update basic info
        resp = self.client.post(
            "/api/verification/update-step",
            json={
                "step": "basic_info",
                "data": {"full_name": "Test User", "user_current_role": "Engineer", "current_title": "IC"},
                "advance_to_next": True,
            },
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json().get("success"))

        # 3) Update education info (sets edu_email)
        test_email = "offline_test@example.com"
        resp = self.client.post(
            "/api/verification/update-step",
            json={
                "step": "education",
                "data": {
                    "university_name": "Test University",
                    "degree_level": "PhD",
                    "department_major": "CS",
                    "edu_email": test_email,
                },
                "advance_to_next": False,
            },
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json().get("success"))

        # 4) Send verification email (offline: writes outbox)
        resp = self.client.post(
            "/api/verification/send-email-verification",
            json={"email": test_email, "email_type": "edu_email"},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json().get("success"))

        outbox_entries = self._read_outbox()
        self.assertTrue(outbox_entries, "Expected outbox entries")
        verification_entries = [e for e in outbox_entries if e.get("kind") == "verification" and e.get("to") == test_email]
        self.assertTrue(verification_entries, "Expected verification email in outbox")
        verification_code = verification_entries[-1].get("verification_code")
        self.assertTrue(verification_code)

        # 5) Verify email with the code
        resp = self.client.post(
            "/api/verification/verify-email",
            json={"email": test_email, "email_type": "edu_email", "verification_code": verification_code},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json().get("success"))

        # 6) Complete verification -> should emit welcome email (offline outbox)
        resp = self.client.post("/api/verification/complete", json={}, headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json().get("success"))

        outbox_entries = self._read_outbox()
        welcome_entries = [e for e in outbox_entries if e.get("kind") == "welcome" and e.get("to") == test_email]
        self.assertTrue(welcome_entries, "Expected welcome email in outbox")


if __name__ == "__main__":
    unittest.main()

