from telegram import Bot

from app.core.config import settings


class TelegramService:
    def __init__(self) -> None:
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    async def send_message(self, chat_id: str, text: str) -> None:
        await self.bot.send_message(chat_id=chat_id, text=text)
