import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import EmployeeNotFoundError
from app.models.employee import Employee
from app.services.employee import EmployeeService
from sqlalchemy.engine import Result


@pytest.mark.asyncio
async def test_get_available_expert_orders_by_rating() -> None:
    session = MagicMock()
    expert = Employee(
        bitrix_user_id=1,
        name="A",
        role="sales",
        rating=99.0,
    )
    result_mock = MagicMock(spec=Result)
    result_mock.scalar_one_or_none = MagicMock(return_value=expert)
    session.execute = AsyncMock(return_value=result_mock)

    svc = EmployeeService(session)
    out = await svc.get_available_expert("sales")
    assert out is expert
    session.execute.assert_awaited()


@pytest.mark.asyncio
async def test_update_rating_raises_when_missing() -> None:
    session = MagicMock()
    result_mock = MagicMock(spec=Result)
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_mock)

    svc = EmployeeService(session)
    eid = uuid.uuid4()
    with pytest.raises(EmployeeNotFoundError):
        await svc.update_rating(eid, 1.0)


@pytest.mark.asyncio
async def test_toggle_availability_flips_flag() -> None:
    eid = uuid.uuid4()
    emp = Employee(
        id=eid,
        bitrix_user_id=2,
        name="B",
        role="technologist",
        rating=80.0,
        is_available=True,
    )
    session = MagicMock()
    select_result = MagicMock(spec=Result)
    select_result.scalar_one_or_none = MagicMock(return_value=emp)
    session.execute = AsyncMock(return_value=select_result)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    svc = EmployeeService(session)
    updated = await svc.toggle_availability(eid)
    assert updated.is_available is False
    session.flush.assert_awaited()
