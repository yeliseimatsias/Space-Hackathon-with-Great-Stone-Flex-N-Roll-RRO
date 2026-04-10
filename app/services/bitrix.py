import re

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import BitrixAPIError

log = structlog.get_logger(__name__)

_WEBHOOK_USER_ID_RE = re.compile(r"/rest/(\d+)/", re.IGNORECASE)


def _webhook_owner_user_id_from_url(url: str) -> int | None:
    m = _WEBHOOK_USER_ID_RE.search(url)
    if m:
        return int(m.group(1))
    return None


class BitrixService:
    """REST Bitrix24 через входящий вебхук."""

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=30.0)

    def _webhook_base(self) -> str:
        return settings.BITRIX_WEBHOOK_URL.rstrip("/")

    async def _request(self, method: str, params: dict) -> dict:
        url = f"{self._webhook_base()}/{method}"
        log.info("bitrix_request", method=method, url=url)
        try:
            response = await self.client.post(url, json=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.exception("bitrix_http_error", method=method, error=str(exc))
            raise BitrixAPIError(str(exc)) from exc

        try:
            data = response.json()
        except ValueError as exc:
            log.exception("bitrix_invalid_json", method=method)
            raise BitrixAPIError("Invalid JSON from Bitrix") from exc

        if isinstance(data, dict) and data.get("error"):
            log.error("bitrix_api_error", method=method, response=data)
            raise BitrixAPIError(str(data.get("error_description", data.get("error"))))
        return data

    async def find_lead_by_phone(self, phone: str) -> dict | None:
        data = await self._request(
            "crm.lead.list",
            {
                "filter": {"PHONE": phone},
                "select": ["ID", "NAME", "PHONE"],
            },
        )
        result = data.get("result") or []
        return result[0] if result else None

    async def find_lead_by_chat_id(self, chat_id: str) -> dict | None:
        data = await self._request(
            "crm.lead.list",
            {
                "filter": {"UF_CRM_TELEGRAM_CHAT_ID": chat_id},
                "select": ["ID", "NAME"],
            },
        )
        result = data.get("result") or []
        return result[0] if result else None

    async def create_lead(self, name: str, chat_id: str, phone: str | None = None) -> int:
        fields: dict = {
            "NAME": name,
            "UF_CRM_TELEGRAM_CHAT_ID": chat_id,
        }
        if phone is not None:
            fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"}]
        data = await self._request("crm.lead.add", {"fields": fields})
        raw = data.get("result")
        if raw is None:
            raise BitrixAPIError("crm.lead.add returned no result")
        return int(raw)

    async def add_comment_to_lead(self, lead_id: int, text: str) -> None:
        await self._request(
            "crm.timeline.comment.add",
            {
                "fields": {
                    "ENTITY_ID": lead_id,
                    "ENTITY_TYPE": "lead",
                    "COMMENT": text,
                }
            },
        )

    async def create_task(
        self, responsible_id: int, title: str, description: str, lead_id: int
    ) -> int:
        data = await self._request(
            "tasks.task.add",
            {
                "fields": {
                    "TITLE": title,
                    "DESCRIPTION": description,
                    "RESPONSIBLE_ID": responsible_id,
                    "UF_CRM_TASK": [f"L_{lead_id}"],
                }
            },
        )
        result = data.get("result")
        if not result or "task" not in result:
            raise BitrixAPIError("tasks.task.add returned unexpected payload")
        task = result["task"]
        tid = task.get("id") if isinstance(task, dict) else None
        if tid is None:
            raise BitrixAPIError("tasks.task.add missing task id")
        return int(tid)

    async def send_im_message_to_user(self, user_id: int, message: str) -> None:
        await self._request(
            "im.message.add",
            {
                "DIALOG_ID": str(user_id),
                "MESSAGE": message,
            },
        )

    async def send_personal_notification(self, user_id: int, message: str) -> None:
        await self._request(
            "im.notify.personal.add",
            {
                "USER_ID": user_id,
                "MESSAGE": message,
            },
        )

    async def send_operator_alert(self, operator_user_id: int, message: str) -> None:
        """Уведомить оператора о сообщении из Telegram."""
        owner = _webhook_owner_user_id_from_url(settings.BITRIX_WEBHOOK_URL)
        if owner is not None and operator_user_id == owner:
            try:
                await self.send_personal_notification(operator_user_id, message)
                log.info("bitrix_operator_alert_notify", user_id=operator_user_id)
                return
            except BitrixAPIError as exc:
                log.warning("bitrix_notify_failed_try_im", error=str(exc))

        await self.send_im_message_to_user(operator_user_id, message)
        log.info("bitrix_operator_alert_im", user_id=operator_user_id)
