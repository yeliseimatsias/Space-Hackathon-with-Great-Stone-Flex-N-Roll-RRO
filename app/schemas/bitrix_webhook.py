from pydantic import BaseModel, Field


class BitrixReplyRequest(BaseModel):
    """Ответ оператора клиенту в Telegram (ручной вызов или автоматизация Bitrix)."""

    secret: str = Field(
        ...,
        min_length=1,
        description="Совпадает с BITRIX_REPLY_WEBHOOK_SECRET в .env",
    )
    telegram_chat_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, description="Текст, который увидит клиент в Telegram")
