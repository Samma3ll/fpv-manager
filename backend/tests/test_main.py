from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint_returns_status():
    with patch("app.main.init_db", new=AsyncMock()):
        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint_returns_api_metadata():
    with patch("app.main.init_db", new=AsyncMock()):
        with TestClient(app) as client:
            response = client.get("/api/v1/")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "FPV Manager API"
    assert body["docs"] == "/docs"
