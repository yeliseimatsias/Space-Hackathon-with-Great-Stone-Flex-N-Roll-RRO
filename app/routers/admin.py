from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import EmployeeNotFoundError
from app.models.employee import Employee
from app.schemas.admin import EmployeeResponse, KnowledgeAddRequest, RatingUpdate
from app.services.employee import EmployeeService
from app.services.knowledge import KnowledgeService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/employees", response_model=list[EmployeeResponse])
async def list_employees(db: AsyncSession = Depends(get_db)) -> list[Employee]:
    result = await db.execute(select(Employee))
    return list(result.scalars().all())


@router.patch(
    "/employees/{employee_id}/toggle-availability",
    response_model=EmployeeResponse,
)
async def toggle_employee_availability(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    svc = EmployeeService(db)
    try:
        emp = await svc.toggle_availability(employee_id)
        await db.commit()
        return emp
    except EmployeeNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/employees/{employee_id}/rating", response_model=EmployeeResponse)
async def update_employee_rating(
    employee_id: UUID,
    body: RatingUpdate,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    svc = EmployeeService(db)
    try:
        emp = await svc.update_rating(employee_id, body.delta)
        await db.commit()
        return emp
    except EmployeeNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/knowledge")
async def add_knowledge(
    body: KnowledgeAddRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = KnowledgeService(db)
    try:
        item = await svc.add_entry(
            question=body.question,
            answer=body.answer,
            expert_id=body.expert_id,
            role=body.role,
        )
        await db.commit()
        return {"id": str(item.id)}
    except EmployeeNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        log.exception("admin_knowledge_add_failed", error=str(exc))
        raise HTTPException(status_code=400, detail="Failed to add knowledge") from exc
