import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BASE_URL", "http://localhost")
os.environ.setdefault("BITRIX_WEBHOOK_URL", "http://bitrix.test/rest/1/test/")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")
os.environ.setdefault("LLM_API_KEY", "test-llm-key")
os.environ.setdefault("BITRIX_REPLY_WEBHOOK_SECRET", "test-reply-secret")

import pytest
from app.core.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_db_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
async def client(
    mock_db_session: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def mock_bitrix_service(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    svc = MagicMock()
    svc.find_lead_by_phone = AsyncMock(return_value=None)
    svc.find_lead_by_chat_id = AsyncMock(return_value=None)
    svc.create_lead = AsyncMock(return_value=1)
    svc.add_comment_to_lead = AsyncMock()
    svc.create_task = AsyncMock(return_value=42)
    monkeypatch.setattr(
        "app.services.orchestrator.BitrixService",
        lambda: svc,
    )
    return svc


@pytest.fixture
def mock_classifier(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    clf = MagicMock()
    clf.classify_intent = AsyncMock(return_value="SALES")
    monkeypatch.setattr(
        "app.services.orchestrator.AIClassifier",
        lambda: clf,
    )
    return clf


@pytest.fixture
def mock_knowledge(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    ks = MagicMock()
    ks.search = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.orchestrator.KnowledgeService",
        lambda session: ks,
    )
    return ks
