"""Tests for Google Gemini AI workflow and FactGuard verification."""

from fastapi.testclient import TestClient
from app.main import app
from app.gemini_service import gemini_service
from app.humanizer import humanizer_service

client = TestClient(app)


def test_health_endpoint_gemini_metadata():
    """Verify health endpoint includes Gemini cloud metadata."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "workflow" in data
    assert data["workflow"] == "gemini_cloud"
    assert "gemini_configured" in data
    assert "gemini_model" in data
    assert "active_provider" in data
    assert data["active_provider"] == "gemini"


def test_config_endpoint_gemini_metadata():
    """Verify config endpoint includes Gemini model and primary provider."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "gemini_model" in data
    assert data["workflow"] == "gemini_cloud"
    assert data["primary_provider"] == "gemini"


def test_workflow_gemini_primary_success(monkeypatch):
    """When Gemini succeeds, it should be the provider with fallback_used=False."""
    def mock_generate(text, system_prompt, temperature=0.7):
        return True, "In today's recruitment landscape, we need to utilize innovative methodologies.", None, False

    monkeypatch.setattr(gemini_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service, "is_currently_rate_limited", lambda: False)
    monkeypatch.setattr(gemini_service, "generate_rewrite", mock_generate)

    payload = {
        "text": "In the contemporary recruitment landscape, it is imperative that we utilize innovative methodologies.",
        "context": "General Communication",
        "tone": "Professional",
    }
    response = client.post("/api/humanize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "gemini"
    assert data["fallback_used"] is False
    assert data["fallback_reason"] is None
    assert "In today's recruitment landscape" in data["rewritten_text"]


def test_workflow_gemini_rate_limit_fallback_to_rules(monkeypatch):
    """When Gemini reaches rate limits (429 / ResourceExhausted), FactGuard rule engine provides safe fallback."""
    def mock_generate_429(text, system_prompt, temperature=0.7):
        return False, "", "Rate limit reached (429): Quota exceeded for metric GenerateContentRequestsPerMinute", True

    monkeypatch.setattr(gemini_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service, "is_currently_rate_limited", lambda: False)
    monkeypatch.setattr(gemini_service, "generate_rewrite", mock_generate_429)

    payload = {
        "text": "In the contemporary recruitment landscape, it is imperative that we utilize innovative methodologies.",
        "context": "General Communication",
        "tone": "Professional",
    }
    response = client.post("/api/humanize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "rule_engine"
    assert data["fallback_used"] is True
    assert "rate limit" in data["fallback_reason"].lower()
    assert data["rewritten_text"] != ""


def test_workflow_gemini_error_fallback_to_rules(monkeypatch):
    """When Gemini encounters a network or server error, FactGuard rule engine provides safe fallback."""
    def mock_generate_error(text, system_prompt, temperature=0.7):
        return False, "", "Gemini API error: 503 Service Unavailable", False

    monkeypatch.setattr(gemini_service, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_service, "is_currently_rate_limited", lambda: False)
    monkeypatch.setattr(gemini_service, "generate_rewrite", mock_generate_error)

    payload = {
        "text": "Please do not hesitate to contact me if you require further assistance.",
        "context": "Candidate Communication",
        "tone": "Professional",
    }
    response = client.post("/api/humanize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "rule_engine"
    assert data["fallback_used"] is True
    assert "gemini rewrite failed" in data["fallback_reason"].lower()


def test_offline_autonomous_factguard_workflow(monkeypatch):
    """When Gemini is disabled (offline mode), FactGuard operates as the primary engine with zero API calls and no fallback banner."""
    from app.config import settings
    monkeypatch.setattr(settings, "enable_gemini", False)
    monkeypatch.setattr(gemini_service, "is_configured", lambda: False)

    gutenberg_text = (
        "Invented by Johannes Gutenberg around 1440, the movable type printing press revolutionized human "
        "communication, sparking the Information Age. Before its invention, books were painstakingly copied by "
        "hand—a costly, time-consuming process that reserved knowledge for religious elites and wealthy scholars. "
        "Gutenberg's key innovation combined durable metal alloy type with an oil-based ink and an adapted wooden "
        "wine press, enabling rapid mass production of standardized texts. The immediate impact was profound: the "
        "cost of publishing plummeted, literacy rates soared across Europe, and ideas spread with unprecedented "
        "speed. The press fueled the Renaissance, accelerated the Protestant Reformation, and laid the foundation "
        "for the Scientific Revolution. By democratizing access to information, Gutenberg's invention transformed "
        "how societies preserve memory, exchange knowledge, and foster free thought, making it one of the most "
        "transformative technological achievements in human history."
    )

    payload = {
        "text": gutenberg_text,
        "context": "General Communication",
        "tone": "Professional",
    }
    response = client.post("/api/humanize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "rule_engine"
    assert data["fallback_used"] is False
    assert data["fallback_reason"] is None
    assert data["rewritten_text"].strip().lower() != gutenberg_text.strip().lower()
    assert data["validation"]["passed"] is True
    # Verify entity preservation
    assert "1440" in data["rewritten_text"]
    assert "Johannes Gutenberg" in data["rewritten_text"] or "Gutenberg" in data["rewritten_text"]
    assert "Europe" in data["rewritten_text"]

