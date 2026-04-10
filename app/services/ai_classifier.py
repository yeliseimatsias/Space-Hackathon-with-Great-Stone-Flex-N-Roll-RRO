import asyncio
import re

import google.generativeai as genai
import structlog
from google.generativeai import GenerativeModel

from app.core.config import settings

log = structlog.get_logger(__name__)

_ALLOWED = frozenset({"TECH", "PRICE", "STATUS", "COMPLAINT", "SALES"})


class AIClassifier:
    def __init__(self) -> None:
        genai.configure(api_key=settings.LLM_API_KEY)
        self._model: GenerativeModel = genai.GenerativeModel(settings.LLM_MODEL)

    async def classify_intent(self, text: str) -> str:
        prompt = (
            "Ты — классификатор запросов клиентов в B2B-полиграфии. Определи, к какой категории "
            "относится следующее сообщение. Категории: TECH (технические вопросы о материалах, "
            "печати, макетах), PRICE (расчёт стоимости, скидки, КП), STATUS (статус заказа, сроки, "
            "доставка), COMPLAINT (претензия, брак, жалоба), SALES (общие вопросы, знакомство, "
            "не подходит под остальное). Ответь только одним словом — названием категории "
            f"(TECH, PRICE, STATUS, COMPLAINT или SALES).\n\nСообщение клиента: {text}"
        )
        try:
            response = await asyncio.to_thread(self._model.generate_content, prompt)
            raw = getattr(response, "text", None) or ""
            token = re.sub(r"\s+", " ", raw.strip()).split(" ")[0].upper()
            token = re.sub(r"[^A-Z]", "", token) or "SALES"
            if token not in _ALLOWED:
                token = "SALES"
            log.info("intent_classified", intent=token)
            return token
        except Exception as exc:
            log.exception("intent_classification_failed", error=str(exc))
            return "SALES"
