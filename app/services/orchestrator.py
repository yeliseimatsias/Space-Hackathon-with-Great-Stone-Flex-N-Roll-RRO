from datetime import UTC, datetime
from urllib.parse import quote

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BitrixAPIError
from app.models.conversation import Conversation
from app.models.employee import Employee
from app.services.ai_classifier import AIClassifier
from app.services.bitrix import BitrixService
from app.services.employee import EmployeeService
from app.services.intent import IntentService
from app.services.knowledge import KnowledgeService
from app.services.telegram import TelegramService

log = structlog.get_logger(__name__)

_INTENT_TO_DB_ROLE = {
    "TECH": "technologist",
    "PRICE": "economist",
    "STATUS": "dispatcher",
    "COMPLAINT": "manager",
    "SALES": "sales",
}


def _lead_id_value(lead: dict) -> int:
    raw = lead.get("ID", lead.get("id"))
    return int(raw) if raw is not None else 0


def _operator_reply_url(chat_id: str) -> str:
    """Ссылка на форму с подставленными chat_id и secret (менеджеру остаётся ввести только текст)."""
    base = settings.BASE_URL.rstrip("/")
    secret = (settings.BITRIX_REPLY_WEBHOOK_SECRET or "").strip()
    q = f"telegram_chat_id={quote(str(chat_id), safe='')}"
    if secret:
        q += f"&secret={quote(secret, safe='')}"
    return f"{base}/operator/reply?{q}"


def _im_notify_target(expert: Employee) -> int:
    """Кому слать im: либо единый диспетчер, либо bitrix_user_id ответственного эксперта."""
    if settings.BITRIX_IM_OPERATOR_USER_ID is not None:
        return settings.BITRIX_IM_OPERATOR_USER_ID
    return expert.bitrix_user_id


class OrchestratorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_telegram_message(
        self,
        chat_id: str,
        text: str | None,
        phone: str | None = None,
    ) -> None:
        message_text = text or ""
        try:
            await self._process(chat_id, message_text, phone)
        except Exception as exc:
            await self.session.rollback()
            log.exception("orchestrator_failed", chat_id=chat_id, error=str(exc))
            try:
                tg = TelegramService()
                await tg.send_message(
                    chat_id,
                    "Произошла ошибка. Пожалуйста, попробуйте позже.",
                )
            except Exception as send_exc:
                log.exception("orchestrator_error_notify_failed", error=str(send_exc))

    async def _process(self, chat_id: str, text: str, phone: str | None) -> None:
        bitrix = BitrixService()
        intent_svc = IntentService(AIClassifier())
        knowledge_svc = KnowledgeService(self.session)
        employee_svc = EmployeeService(self.session)
        telegram = TelegramService()

        conv_row = await self.session.execute(
            select(Conversation).where(Conversation.telegram_chat_id == chat_id)
        )
        conversation = conv_row.scalar_one_or_none()

        lead_id: int | None = None
        if conversation is not None and conversation.bitrix_lead_id is not None:
            lead_id = int(conversation.bitrix_lead_id)
        else:
            lead: dict | None = None
            if phone:
                try:
                    lead = await bitrix.find_lead_by_phone(phone)
                except BitrixAPIError as exc:
                    log.warning("bitrix_find_phone_failed", error=str(exc))
            if lead is None:
                try:
                    lead = await bitrix.find_lead_by_chat_id(chat_id)
                except BitrixAPIError as exc:
                    log.warning("bitrix_find_chat_failed", error=str(exc))
            if lead is None:
                try:
                    lead_id = await bitrix.create_lead(
                        f"Telegram Client {chat_id}", chat_id, phone
                    )
                except BitrixAPIError as exc:
                    log.exception("bitrix_create_lead_failed", error=str(exc))
                    raise
            else:
                lead_id = _lead_id_value(lead)

            now = datetime.now(UTC)
            if conversation is None:
                conversation = Conversation(
                    telegram_chat_id=chat_id,
                    bitrix_lead_id=lead_id,
                    phone=phone,
                    last_message_at=now,
                )
                self.session.add(conversation)
            else:
                conversation.bitrix_lead_id = lead_id
                if phone is not None:
                    conversation.phone = phone
                conversation.last_message_at = now
            await self.session.flush()

        if lead_id is None:
            log.error("orchestrator_no_lead", chat_id=chat_id)
            return

        if conversation is not None:
            conversation.last_message_at = datetime.now(UTC)
            if phone is not None:
                conversation.phone = phone
            await self.session.flush()

        async with telegram.keep_typing(chat_id):
            classification = await intent_svc.classify(text)
            db_role = _INTENT_TO_DB_ROLE.get(classification, "sales")

            if classification in ("TECH", "PRICE"):
                kb_role = _INTENT_TO_DB_ROLE[classification]
                answer_data = await knowledge_svc.search(text, kb_role)
                if answer_data is not None:
                    await telegram.send_message(chat_id, answer_data["answer"])
                    try:
                        await bitrix.add_comment_to_lead(
                            lead_id, f"Бот: {answer_data['answer']}"
                        )
                    except BitrixAPIError as exc:
                        log.warning("bitrix_comment_failed", error=str(exc))
                    # Уведомление в im не шлём: клиент уже получил ответ в Telegram.
                    await self.session.commit()
                    return

            expert = await employee_svc.get_available_expert(db_role)
            if expert is None:
                expert = await employee_svc.get_available_expert("sales")
            if expert is None:
                await telegram.send_message(
                    chat_id,
                    "Сейчас нет доступных специалистов. Попробуйте позже или напишите ещё раз.",
                )
                await self.session.commit()
                return

            if settings.PRIMARY_BITRIX_USER_ID is not None:
                apply_primary = (
                    not settings.BITRIX_PRIMARY_USER_ID_SALES_ONLY or db_role == "sales"
                )
                if apply_primary:
                    primary_row = await self.session.execute(
                        select(Employee).where(
                            Employee.bitrix_user_id == settings.PRIMARY_BITRIX_USER_ID
                        )
                    )
                    primary_expert = primary_row.scalar_one_or_none()
                    if primary_expert is not None:
                        expert = primary_expert
                        log.info(
                            "orchestrator_primary_bitrix_assignee",
                            bitrix_user_id=settings.PRIMARY_BITRIX_USER_ID,
                        )

            reply_url = _operator_reply_url(chat_id)
            if settings.BITRIX_SEND_CLIENT_MESSAGES_TO_IM:
                im_body = (
                    "[B]Входящее из Telegram[/B]\n"
                    f"Классификация: {classification} → роль в БД: {db_role}\n"
                    f"Ответственный (задача): {expert.name} ({expert.role}), Bitrix USER_ID {expert.bitrix_user_id}\n"
                    f"Лид CRM: {lead_id}\n"
                    f"Telegram chat_id: {chat_id}\n"
                    f"Текст клиента:\n{text}\n\n"
                    f"[URL={reply_url}]Ответить клиенту (форма)[/URL]"
                )
                try:
                    await bitrix.send_operator_alert(
                        _im_notify_target(expert), im_body
                    )
                except BitrixAPIError as exc:
                    log.warning(
                        "bitrix_operator_alert_failed",
                        error=str(exc),
                        hint="Проверьте права вебхука на «Чат и уведомления (im)»",
                    )

            if settings.BITRIX_CREATE_TASK_ON_ROUTING:
                try:
                    await bitrix.create_task(
                        expert.bitrix_user_id,
                        f"Ответ клиенту {lead_id}",
                        f"Клиент спрашивает: {text}\nОтветить в Telegram чат {chat_id}",
                        lead_id,
                    )
                except BitrixAPIError as exc:
                    # Не роняем весь сценарий: клиент уже увидит подтверждение; im ушёл (если не упал).
                    log.warning(
                        "bitrix_create_task_failed",
                        error=str(exc),
                        lead_id=lead_id,
                        responsible_bitrix_id=expert.bitrix_user_id,
                        hint="Проверьте права вебхука на tasks и поля CRM у задачи",
                    )

            if conversation is not None:
                conversation.assigned_employee_id = expert.id
                conversation.last_message_at = datetime.now(UTC)
                await self.session.flush()

            await telegram.send_message(
                chat_id,
                f"Ваш запрос передан {expert.name} ({expert.role}). Ожидайте ответа.",
            )
            await self.session.commit()
