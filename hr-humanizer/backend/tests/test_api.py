"""Integration tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "ollama_reachable" in data
    assert "active_model" in data
    assert "available_models" in data


def test_config_endpoint():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "default_model" in data
    assert "communication_types" in data
    assert "tones" in data
    assert len(data["communication_types"]) >= 10
    assert len(data["tones"]) >= 6


def test_validate_endpoint_valid():
    payload = {
        "original_text": "The candidate scored 78/100. They may be suitable for the junior developer role, but they have not worked with Kubernetes.",
        "rewritten_text": "The candidate achieved 78/100. They may be suitable for the junior developer role, though they have not worked with Kubernetes.",
    }
    response = client.post("/api/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["requires_review"] is False
    assert len(data["warnings"]) == 0


def test_validate_endpoint_catches_failure():
    payload = {
        "original_text": "The candidate scored 78/100. They may be suitable for the junior developer role, but they have not worked with Kubernetes.",
        "rewritten_text": "The candidate scored 78/100. They are a good fit for the junior developer role, but their lack of Kubernetes is a red flag.",
    }
    response = client.post("/api/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False
    assert data["requires_review"] is True
    assert "red flag" in data["details"]["unsupported_judgments"]


def test_humanize_endpoint_empty_input():
    payload = {
        "text": "   ",
        "communication_type": "general_hr",
        "tone": "professional",
    }
    response = client.post("/api/humanize", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_humanize_endpoint_exceeds_length():
    payload = {
        "text": "A" * 5000,
        "communication_type": "general_hr",
        "tone": "professional",
    }
    response = client.post("/api/humanize", json=payload)
    assert response.status_code in (400, 422)

