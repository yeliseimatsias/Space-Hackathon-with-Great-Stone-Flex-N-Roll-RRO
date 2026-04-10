import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from app.core.exceptions import EmployeeNotFoundError
from app.models.employee import Employee
from app.models.knowledge import KnowledgeItem
from app.services.knowledge import KnowledgeService
from sqlalchemy.engine import CursorResult, Result


@pytest.mark.asyncio
async def test_add_entry_raises_without_employee() -> None:
    session = MagicMock()
    result_mock = MagicMock(spec=Result)
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_mock)

    svc = KnowledgeService(session)
    with pytest.raises(EmployeeNotFoundError):
        await svc.add_entry("q", "a", uuid.uuid4(), "technologist")


@pytest.mark.asyncio
@patch("app.services.knowledge.get_embedding_model")
async def test_add_entry_creates_row(mock_get_model: MagicMock) -> None:
    eid = uuid.uuid4()
    emp = Employee(
        id=eid,
        bitrix_user_id=2,
        name="Expert",
        role="technologist",
        rating=90.0,
    )

    session = MagicMock()
    select_result = MagicMock(spec=Result)
    select_result.scalar_one_or_none = MagicMock(return_value=emp)

    mock_model = MagicMock()
    mock_model.encode = MagicMock(return_value=np.zeros(384, dtype=np.float32))
    mock_get_model.return_value = mock_model

    session.execute = AsyncMock(return_value=select_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    svc = KnowledgeService(session)
    item = await svc.add_entry("question", "answer", eid, "technologist")
    assert isinstance(item, KnowledgeItem)
    session.add.assert_called_once()
    mock_model.encode.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.knowledge.get_embedding_model")
async def test_search_returns_none_when_empty(mock_get_model: MagicMock) -> None:
    session = MagicMock()
    mappings = MagicMock()
    mappings.first = MagicMock(return_value=None)
    cursor = MagicMock(spec=CursorResult)
    cursor.mappings = MagicMock(return_value=mappings)
    session.execute = AsyncMock(return_value=cursor)

    mock_model = MagicMock()
    mock_model.encode = MagicMock(return_value=np.zeros(384, dtype=np.float32))
    mock_get_model.return_value = mock_model

    svc = KnowledgeService(session)
    assert await svc.search("q", "technologist") is None
