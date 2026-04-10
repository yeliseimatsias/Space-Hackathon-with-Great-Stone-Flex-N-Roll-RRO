import uuid

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EmployeeNotFoundError
from app.models.employee import Employee

log = structlog.get_logger(__name__)


class EmployeeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_available_expert(self, role: str) -> Employee | None:
        result = await self.session.execute(
            select(Employee)
            .where(Employee.role == role, Employee.is_available.is_(True))
            .order_by(Employee.rating.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_rating(self, employee_id: uuid.UUID, delta: float) -> Employee:
        stmt = (
            update(Employee)
            .where(Employee.id == employee_id)
            .values(rating=Employee.rating + delta)
            .returning(Employee)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise EmployeeNotFoundError(str(employee_id))
        log.info("employee_rating_updated", employee_id=str(employee_id), delta=delta)
        return row

    async def toggle_availability(self, employee_id: uuid.UUID) -> Employee:
        res = await self.session.execute(select(Employee).where(Employee.id == employee_id))
        employee = res.scalar_one_or_none()
        if employee is None:
            raise EmployeeNotFoundError(str(employee_id))
        employee.is_available = not employee.is_available
        await self.session.flush()
        await self.session.refresh(employee)
        log.info(
            "employee_availability_toggled",
            employee_id=str(employee_id),
            is_available=employee.is_available,
        )
        return employee
