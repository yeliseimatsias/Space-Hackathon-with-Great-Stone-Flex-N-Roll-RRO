import asyncio
from contextlib import asynccontextmanager

import structlog
from telegram import Bot
from telegram.constants import ChatAction

from app.core.config import settings

log = structlog.get_logger(__name__)


class TelegramService:
    def __init__(self) -> None:
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    async def send_message(self, chat_id: str, text: str) -> None:
        await self.bot.send_message(chat_id=chat_id, text=text)

    async def send_typing(self, chat_id: str) -> None:
        try:
            await self.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception as exc:
            # Не роняем маршрутизацию из‑за лимитов/сети Telegram
            log.warning("telegram_send_chat_action_failed", error=str(exc))

    async def _typing_refresh_loop(self, chat_id: str) -> None:
        """Повторять typing: клиентский индикатор гаснет ~за 5 с."""
        try:
            while True:
                await asyncio.sleep(4.0)
                await self.send_typing(chat_id)
        except asyncio.CancelledError:
            raise

    @asynccontextmanager
    async def keep_typing(self, chat_id: str):
        await self.send_typing(chat_id)
        task = asyncio.create_task(self._typing_refresh_loop(chat_id))
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
