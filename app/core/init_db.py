import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.services.knowledge import KnowledgeService

log = structlog.get_logger(__name__)


async def init_demo_data(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count()).select_from(Employee))
    if count and count > 0:
        return

    employees_spec = [
        ("Елисей Матяс", "sales", 90.0, 1),
        ("Анастасия Чернецкая", "technologist", 95.0, 2),
        ("Яна Демидович", "economist", 85.0, 3),
        ("Анна Дробышевская", "dispatcher", 80.0, 4),
        ("Галина Зиневич", "manager", 90.0, 5),
    ]
    for name, role, rating, bxid in employees_spec:
        session.add(
            Employee(
                name=name,
                role=role,
                rating=rating,
                bitrix_user_id=bxid,
            )
        )
    await session.flush()

    chernetskaya = (
        await session.execute(select(Employee).where(Employee.bitrix_user_id == 2))
    ).scalar_one()
    demidovich = (
        await session.execute(select(Employee).where(Employee.bitrix_user_id == 3))
    ).scalar_one()

    ks = KnowledgeService(session)
    await ks.add_entry(
        question="Какой материал для заморозки -18 градусов?",
        answer="Рекомендуем ПЭ с акриловым адгезивом.",
        expert_id=chernetskaya.id,
        role="technologist",
    )
    await ks.add_entry(
        question="Скидка на большой тираж?",
        answer="При тираже от 100 000 штук скидка 15%.",
        expert_id=demidovich.id,
        role="economist",
    )
    await session.commit()
    log.info("demo_data_initialized")
