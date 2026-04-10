from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_telegram(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    send = AsyncMock()

    def _factory() -> MagicMock:
        m = MagicMock()
        m.send_message = send
        return m

    monkeypatch.setattr("app.routers.operator_reply.TelegramService", _factory)
    return send


def test_operator_reply_post_ok(mock_telegram: AsyncMock) -> None:
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/operator/reply",
        data={
            "secret": "test-reply-secret",
            "telegram_chat_id": "999",
            "text": "Привет",
        },
    )
    assert r.status_code == 200
    assert "отправлено" in r.text.lower() or "Готово" in r.text
    mock_telegram.assert_awaited_once_with("999", "Привет")
