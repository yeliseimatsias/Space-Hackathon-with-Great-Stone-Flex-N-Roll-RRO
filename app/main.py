import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from telegram import Bot

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.init_db import init_demo_data
from app.routers import admin, health, operator_reply, webhooks


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _ = app
    log = structlog.get_logger(__name__)
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    webhook_url = f"{settings.BASE_URL.rstrip('/')}/webhook/telegram"
    try:
        await bot.set_webhook(url=webhook_url)
        log.info("telegram_webhook_set", url=webhook_url)
    except Exception as exc:
        log.warning("telegram_webhook_set_failed", error=str(exc), url=webhook_url)

    async with AsyncSessionLocal() as session:
        await init_demo_data(session)

    yield


app = FastAPI(
    title="Flex-n-Roll PRO AI Assistant",
    description="Telegram ↔ Bitrix24: лиды, задачи, база знаний, ответ оператора через вебхук.",
    lifespan=lifespan,
)

app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(health.router)
app.include_router(operator_reply.router)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "flex-n-roll-pro-ai",
        "docs": "/docs",
        "operator_reply": "/operator/reply",
    }
