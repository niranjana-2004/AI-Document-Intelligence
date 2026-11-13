from __future__ import annotations

import unittest
from starlette.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token

class TestAPIContractAndLargeDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # User 4 (Niveda V) owns docs 3, 5, 12, 14, 16
        cls.user_4_token = create_access_token({"sub": "4"})
        # User 5 owns doc 9
        cls.user_5_token = create_access_token({"sub": "5"})

    def test_api_unauthorized_access(self):
        # 1. Query without auth
        res = self.client.post("/documents/knowledge-intelligence/query", json={"query": "TCP"})
        self.assertEqual(res.status_code, 401)

        # 2. Entity drilldown without auth
        res = self.client.get("/documents/knowledge-intelligence/entity/ent_tcp")
        self.assertEqual(res.status_code, 401)

        # 3. Cache delete without auth
        res = self.client.delete("/documents/knowledge-intelligence/cache")
        self.assertEqual(res.status_code, 401)

    def test_api_validation_errors(self):
        headers = {"Authorization": f"Bearer {self.user_4_token}"}

        # Empty body
        res = self.client.post("/documents/knowledge-intelligence/query", json={}, headers=headers)
        self.assertIn(res.status_code, [400, 422])

        # Whitespace-only query
        res = self.client.post("/documents/knowledge-intelligence/query", json={"query": "   "}, headers=headers)
        self.assertEqual(res.status_code, 400)

        # Single character query (violates min_length=2)
        res = self.client.post("/documents/knowledge-intelligence/query", json={"query": "a"}, headers=headers)
        self.assertEqual(res.status_code, 422)

    def test_api_cross_tenant_document_rejection(self):
        # User 5 attempts to query User 4's document 14
        headers_user_5 = {"Authorization": f"Bearer {self.user_5_token}"}
        res = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={"query": "What is TCP?", "document_ids": [14]},
            headers=headers_user_5,
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("not exist or are not owned", res.json().get("detail", ""))

    def test_api_successful_query_and_drilldown(self):
        headers = {"Authorization": f"Bearer {self.user_4_token}"}
        res = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={"query": "What is TCP?", "document_ids": [12, 14], "skip_llm": True},
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["direct_answer"]["grounding_status"], "grounded")
        self.assertTrue(len(data["evidence"]) > 0)

        # Test drilldown endpoint
        res_dd = self.client.get(
            "/documents/knowledge-intelligence/entity/ent_tcp?document_ids=12,14",
            headers=headers,
        )
        self.assertEqual(res_dd.status_code, 200)
        dd_data = res_dd.json()
        self.assertIn("direct_answer", dd_data)
        self.assertIn("evidence", dd_data)

    def test_api_cache_clearance(self):
        headers = {"Authorization": f"Bearer {self.user_4_token}"}
        res = self.client.delete("/documents/knowledge-intelligence/cache", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("deleted_cache_entries", data)

    def test_large_academic_thesis_queries(self):
        # Doc 5 (107-page doctoral thesis)
        headers = {"Authorization": f"Bearer {self.user_4_token}"}

        # 1. Broad academic query
        res_broad = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={"query": "network security and privacy", "document_ids": [5], "skip_llm": True},
            headers=headers,
        )
        self.assertEqual(res_broad.status_code, 200)
        data_broad = res_broad.json()
        self.assertEqual(data_broad["direct_answer"]["grounding_status"], "grounded")
        self.assertTrue(len(data_broad["evidence"]) > 0)
        for ev in data_broad["evidence"]:
            self.assertEqual(ev["document_id"], 5)
            self.assertTrue(ev["page_number"] >= 1)

        # 2. Unknown concept on thesis
        res_unk = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={"query": "Quantum Teleportation Superluminal", "document_ids": [5], "skip_llm": True},
            headers=headers,
        )
        self.assertEqual(res_unk.status_code, 200)
        data_unk = res_unk.json()
        self.assertEqual(data_unk["direct_answer"]["grounding_status"], "insufficient_evidence")

if __name__ == "__main__":
    unittest.main()
