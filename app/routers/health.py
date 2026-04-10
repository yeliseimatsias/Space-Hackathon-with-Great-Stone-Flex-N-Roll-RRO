from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.ai_classifier import AIClassifier

router = APIRouter(tags=["health"])

_DEFAULT_LLM_PROBE = (
    "Сколько будет стоить тираж 1000 визиток на мелованном картоне?"
)


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "database": str(exc)},
        ) from exc


@router.get("/health/llm")
async def health_llm(
    secret: str = Query(..., description="Должен совпадать с BITRIX_REPLY_WEBHOOK_SECRET"),
    message: str | None = Query(
        None,
        max_length=2000,
        description="Текст «клиента» для классификации; по умолчанию фиксированный пример (ожидается PRICE)",
    ),
) -> dict:
    """
    Проверка, что Gemini отвечает и что парсер выдаёт ожидаемую метку.
    Защита: тот же секрет, что и для формы ответа оператора.
    """
    expected = (settings.BITRIX_REPLY_WEBHOOK_SECRET or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Задайте BITRIX_REPLY_WEBHOOK_SECRET в .env, чтобы включить /health/llm",
        )
    if secret.strip() != expected:
        raise HTTPException(status_code=403, detail="Invalid secret")

    probe = (message or "").strip() or _DEFAULT_LLM_PROBE
    result = await AIClassifier().classify_full(probe)
    return {
        "ok": result.error is None,
        "model": result.model,
        "intent": result.intent,
        "raw_text": result.raw_text,
        "error": result.error,
        "block_reason": result.block_reason,
        "message_used": probe,
    }
