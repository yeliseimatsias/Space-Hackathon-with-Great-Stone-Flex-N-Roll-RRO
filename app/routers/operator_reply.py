"""HTML-форма: ответ оператора клиенту в Telegram (секрет = BITRIX_REPLY_WEBHOOK_SECRET)."""

from __future__ import annotations

import html
import structlog
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from telegram.error import TelegramError

from app.core.config import settings
from app.services.telegram import TelegramService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/operator", tags=["operator"])


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:2rem auto;padding:0 1rem;}} label{{display:block;margin:.75rem 0 .25rem;}} input,textarea{{width:100%;box-sizing:border-box;padding:.5rem;}} button{{margin-top:1rem;padding:.6rem 1rem;cursor:pointer;}} .hint{{color:#666;font-size:.9rem;}}</style>
</head><body>
<h1>{html.escape(title)}</h1>
{body}
</body></html>"""
    )


@router.get("/reply", response_class=HTMLResponse)
async def operator_reply_form(request: Request) -> HTMLResponse:
    if not (settings.BITRIX_REPLY_WEBHOOK_SECRET or "").strip():
        return _page(
            "Ответ клиенту",
            "<p>Секрет не задан. Добавьте в <code>.env</code> строку <code>BITRIX_REPLY_WEBHOOK_SECRET=...</code> "
            "и перезапустите приложение.</p>"
            "<p class='hint'>Ссылку с подстановкой можно взять из уведомления Bitrix.</p>",
        )

    q = request.query_params
    pref_chat = (q.get("telegram_chat_id") or q.get("chat_id") or "").strip()
    pref_secret = (q.get("secret") or "").strip()
    expected = (settings.BITRIX_REPLY_WEBHOOK_SECRET or "").strip()

    esc_chat = html.escape(pref_chat)
    esc_secret = html.escape(pref_secret)

    compact = bool(
        pref_chat and pref_secret and pref_secret.strip() == expected
    )

    if compact:
        body = (
            "<p class='hint'>Осталось ввести сообщение для клиента.</p>"
            '<form method="post" accept-charset="utf-8">'
            f'<input type="hidden" name="secret" value="{esc_secret}">'
            f'<input type="hidden" name="telegram_chat_id" value="{esc_chat}">'
            "<label>Текст клиенту</label>"
            '<textarea name="text" rows="6" required placeholder="Ваш ответ…"></textarea>'
            "<button type=\"submit\">Отправить в Telegram</button>"
            "</form>"
        )
        return _page("Ответ клиенту в Telegram", body)

    # Полная форма (частичное автозаполнение из query)
    body = (
        "<p class='hint'>Параметры <code>?telegram_chat_id=…&amp;secret=…</code> в ссылке заполняют поля; "
        "секрет должен совпадать с <code>BITRIX_REPLY_WEBHOOK_SECRET</code>.</p>"
        '<form method="post" accept-charset="utf-8">'
        "<label>Секрет</label>"
        f'<input type="password" name="secret" required autocomplete="off" value="{esc_secret}">'
        "<label>Telegram chat_id</label>"
        f'<input type="text" name="telegram_chat_id" required placeholder="например 123456789" inputmode="numeric" value="{esc_chat}">'
        "<label>Текст клиенту</label>"
        '<textarea name="text" rows="5" required placeholder="Ваш ответ…"></textarea>'
        "<button type=\"submit\">Отправить</button>"
        "</form>"
    )
    return _page("Ответ клиенту в Telegram", body)


@router.post("/reply", response_model=None)
async def operator_reply_submit(
    secret: str = Form(...),
    telegram_chat_id: str = Form(...),
    text: str = Form(...),
) -> HTMLResponse:
    expected = (settings.BITRIX_REPLY_WEBHOOK_SECRET or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="BITRIX_REPLY_WEBHOOK_SECRET is not configured")
    if secret.strip() != expected:
        log.warning("operator_reply_bad_secret")
        return _page(
            "Неверный секрет",
            "<p style='color:#c00'>Секрет не совпадает с <code>BITRIX_REPLY_WEBHOOK_SECRET</code> в .env.</p>"
            "<p><a href='/operator/reply'>Назад</a></p>",
        )

    cid = telegram_chat_id.strip()
    body = text.strip()
    if not cid or not body:
        return _page(
            "Пустые поля",
            "<p>Укажите chat_id и текст.</p><p><a href='/operator/reply'>Назад</a></p>",
        )

    tg = TelegramService()
    try:
        await tg.send_message(cid, body)
    except TelegramError as exc:
        log.warning("operator_reply_telegram_failed", error=str(exc), chat_id=cid)
        err = html.escape(str(exc))
        return _page(
            "Telegram не принял сообщение",
            f"<p style='color:#c00'>Ошибка Telegram API:</p><pre style='white-space:pre-wrap;word-break:break-all;'>{err}</pre>"
            "<p class='hint'>Частые причины: неверный chat_id, клиент не писал боту.</p>"
            "<p><a href='/operator/reply'>Назад</a></p>",
        )

    log.info("operator_reply_sent", chat_id=cid)
    return _page(
        "Готово",
        "<p style='color:#0a0'>Сообщение отправлено в Telegram.</p>"
        "<p><a href='/operator/reply'>Отправить ещё</a> · <a href='/docs'>API</a></p>",
    )
