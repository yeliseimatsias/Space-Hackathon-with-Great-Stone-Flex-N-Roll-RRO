import asyncio
import uuid

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import EmployeeNotFoundError
from app.models.employee import Employee
from app.models.knowledge import KnowledgeItem
from app.utils.embeddings import get_embedding_model

log = structlog.get_logger(__name__)


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_entry(
        self, question: str, answer: str, expert_id: uuid.UUID, role: str
    ) -> KnowledgeItem:
        result = await self.session.execute(select(Employee).where(Employee.id == expert_id))
        employee = result.scalar_one_or_none()
        if employee is None:
            raise EmployeeNotFoundError(str(expert_id))

        model = get_embedding_model()
        emb = await asyncio.to_thread(model.encode, question)
        vec = emb.tolist() if hasattr(emb, "tolist") else list(emb)

        item = KnowledgeItem(
            question=question,
            answer=answer,
            embedding=vec,
            role=role,
            expert_id=expert_id,
            expert_rating_at_time=employee.rating,
            similarity_threshold=settings.KNOWLEDGE_THRESHOLD,
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        log.info("knowledge_entry_added", knowledge_id=str(item.id), role=role)
        return item

    async def search(self, query: str, role: str) -> dict | None:
        model = get_embedding_model()
        emb = await asyncio.to_thread(model.encode, query)
        vec = emb.tolist() if hasattr(emb, "tolist") else list(emb)
        vec_literal = "[" + ",".join(str(float(x)) for x in vec) + "]"
        threshold = settings.KNOWLEDGE_THRESHOLD

        sql = text(
            """
            SELECT id, answer, expert_rating_at_time, use_count,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM knowledge_items
            WHERE role = :role
              AND 1 - (embedding <=> CAST(:embedding AS vector)) > :threshold
            ORDER BY (1 - (embedding <=> CAST(:embedding AS vector)))
                     * (expert_rating_at_time / 100.0) DESC
            LIMIT 1
            """
        )
        row = (
            await self.session.execute(
                sql,
                {
                    "embedding": vec_literal,
                    "role": role,
                    "threshold": threshold,
                },
            )
        ).mappings().first()

        if row is None:
            return None

        kid = row["id"]
        answer = row["answer"]
        similarity = float(row["similarity"])

        await self.session.execute(
            update(KnowledgeItem)
            .where(KnowledgeItem.id == kid)
            .values(use_count=KnowledgeItem.use_count + 1)
        )
        await self.session.flush()
        log.info(
            "knowledge_hit",
            knowledge_id=str(kid),
            similarity=similarity,
            role=role,
        )
        return {"answer": answer, "similarity": similarity}
