import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ai_classifier import IntentClassificationResult


@pytest.mark.asyncio
async def test_health_llm_wrong_secret() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health/llm?secret=not-the-test-secret")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_health_llm_ok_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClassifier:
        async def classify_full(self, text: str) -> IntentClassificationResult:
            _ = text
            return IntentClassificationResult(
                intent="PRICE",
                raw_text="PRICE",
                model="gemini-test",
                error=None,
            )

    monkeypatch.setattr("app.routers.health.AIClassifier", FakeClassifier)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health/llm?secret=test-reply-secret")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["intent"] == "PRICE"
    assert data["raw_text"] == "PRICE"
    assert data["error"] is None
