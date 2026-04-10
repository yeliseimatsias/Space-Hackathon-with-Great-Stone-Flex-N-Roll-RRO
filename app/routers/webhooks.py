from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.bitrix_webhook import BitrixReplyRequest
from app.schemas.telegram import TelegramUpdate
from app.services.orchestrator import OrchestratorService
from app.services.telegram import TelegramService

router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/telegram")
async def telegram_webhook(
    update: TelegramUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    if update.message is None:
        return {"ok": True}
    msg = update.message
    if msg.text is None and msg.contact is None:
        return {"ok": True}
    chat_id = str(msg.chat.id)
    text = msg.text
    phone = msg.contact.phone_number if msg.contact else None
    await OrchestratorService(db).process_telegram_message(chat_id, text, phone)
    return {"ok": True}


@router.post("/bitrix")
async def bitrix_webhook_stub() -> dict[str, bool]:
    """Заглушка для исходящих событий Bitrix24 (при необходимости укажите URL здесь)."""
    return {"ok": True}


@router.post("/bitrix/reply")
async def bitrix_reply_to_telegram(body: BitrixReplyRequest) -> dict[str, bool]:
    """Ответ оператора клиенту в Telegram (JSON API; в браузере — GET /operator/reply)."""
    if not settings.BITRIX_REPLY_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=503,
            detail="BITRIX_REPLY_WEBHOOK_SECRET is not configured",
        )
    if body.secret != settings.BITRIX_REPLY_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    tg = TelegramService()
    await tg.send_message(body.telegram_chat_id, body.text)
    return {"ok": True}
