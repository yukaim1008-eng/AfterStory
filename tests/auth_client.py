"""Existing business tests enter through the real login endpoint."""

from fastapi.testclient import TestClient as FastAPITestClient


class TestClient(FastAPITestClient):
    def __enter__(self):
        super().__enter__()
        response = self.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alice-test-password-123"},
        )
        assert response.status_code == 200, response.text
        self.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return self
