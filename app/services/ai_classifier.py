import asyncio
import re
from dataclasses import dataclass

import google.generativeai as genai
import structlog
from google.api_core import exceptions as google_api_exceptions
from google.generativeai import GenerativeModel

from app.core.config import settings

log = structlog.get_logger(__name__)

# Короткий ответ без «рассуждений»; снижает шум в ответе модели
_CLASSIFY_GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=0.2,
    max_output_tokens=24,
)

_ALLOWED = frozenset({"TECH", "PRICE", "STATUS", "COMPLAINT", "SALES"})
_LABEL_ORDER = ("TECH", "PRICE", "STATUS", "COMPLAINT", "SALES")

_DEFAULT_CLASSIFY_PROMPT = (
    "Ты — классификатор запросов клиентов в B2B-полиграфии. Определи, к какой категории "
    "относится следующее сообщение. Категории: TECH (технические вопросы о материалах, "
    "печати, макетах), PRICE (расчёт стоимости, скидки, КП), STATUS (статус заказа, сроки, "
    "доставка), COMPLAINT (претензия, брак, жалоба), SALES (общие вопросы, знакомство, "
    "не подходит под остальное).\n"
    "Ответь строго одним словом латиницей без пояснений: TECH, PRICE, STATUS, COMPLAINT или SALES.\n\n"
    "Сообщение клиента: {text}"
)


def _safe_generate_content_text(response: object) -> str:
    """
    `response.text` в google-generativeai может кинуть ValueError (пустые parts, safety и т.д.).
    Тогда классификатор молча падал в SALES — как будто LLM «не вызывался».
    """
    try:
        t = response.text
        if t and str(t).strip():
            return str(t).strip()
    except (ValueError, AttributeError):
        pass
    try:
        cands = getattr(response, "candidates", None) or []
        if not cands:
            return ""
        parts = getattr(cands[0].content, "parts", None) or []
        chunks: list[str] = []
        for p in parts:
            chunk = getattr(p, "text", None)
            if chunk:
                chunks.append(chunk)
        return "".join(chunks).strip()
    except (IndexError, AttributeError, TypeError):
        return ""


def _intent_from_russian_model_line(raw: str) -> str | None:
    """Если модель вернула короткий ответ по-русски без латинских меток."""
    line = raw.strip().split("\n")[0].strip().lower()
    if not line:
        return None
    # Порядок: сначала узкие формулировки
    if re.match(r"^(претенз|жалоб|брак|рекламац)", line):
        return "COMPLAINT"
    if re.match(r"^(статус|доставк)", line) or re.search(
        r"^(когда|где)\s+(заказ|поставк)", line
    ):
        return "STATUS"
    if re.match(r"^(цен|стоим|скидк|кп|тариф|расч)", line):
        return "PRICE"
    if re.match(r"^(технич|макет|печат|офсет|цифр)", line):
        return "TECH"
    if re.match(r"^(общ|продаж|знаком)", line):
        return "SALES"
    return None


def _intent_token_from_model_text(raw: str) -> str:
    """Достаём метку TECH/PRICE/... даже если модель ответила фразой, а не одним словом."""
    raw = raw.strip()
    if not raw:
        return "SALES"
    upper = raw.upper()
    for label in _LABEL_ORDER:
        if re.search(rf"\b{re.escape(label)}\b", upper):
            return label
    # Второй проход: ответ вроде "Категория:TECH" без пробела после двоеточия
    for label in _LABEL_ORDER:
        if label in upper and len(raw) <= 120:
            if re.search(rf"(^|[^A-Z]){re.escape(label)}([^A-Z]|$)", upper):
                return label
    first = re.sub(r"\s+", " ", raw.strip()).split(" ")[0].upper()
    latin_only = re.sub(r"[^A-Z]", "", first)
    if not latin_only:
        ru = _intent_from_russian_model_line(raw)
        return ru if ru is not None else "SALES"
    token = latin_only
    if token not in _ALLOWED:
        ru = _intent_from_russian_model_line(raw)
        if ru is not None:
            return ru
        return "SALES"
    return token


def _intent_from_user_message(text: str) -> str | None:
    """
    Резервная маршрутизация по самому сообщению клиента, если LLM недоступен или вернул SALES.
    Не заменяет уверенные ответы модели (см. classify_full).
    """
    t = text.strip().lower()
    if len(t) < 2:
        return None
    if any(
        x in t
        for x in (
            "претенз",
            "брак",
            "жалоб",
            "рекламац",
            "верните деньги",
            "не соответств",
            "бракован",
            "вернуть деньги",
        )
    ):
        return "COMPLAINT"
    if any(
        x in t
        for x in (
            "статус заказ",
            "где заказ",
            "мой заказ",
            "заказ номер",
            "когда привез",
            "когда приедет",
            "срок достав",
            "отследить",
            "номер заказ",
            "track order",
        )
    ):
        return "STATUS"
    if any(
        x in t
        for x in (
            "сколько стоит",
            "какая цена",
            "цена за",
            " стоим",
            "скидк",
            "тираж",
            "калькуля",
            "дешевле",
            "тариф",
            "квоти",
            " quote",
            "кп ",
            "кп?",
            "кп,",
            "кп.",
        )
    ):
        return "PRICE"
    if any(
        x in t
        for x in (
            "макет",
            "печат",
            "ламин",
            "бумаг",
            "офсет",
            "цифров",
            "flex",
            "флекс",
            "высечк",
            "вылет",
            "dpi",
            "разреш",
            "цветопроф",
            "ризограф",
            " uv",
            "уф-",
            "лакиров",
        )
    ):
        return "TECH"
    return None


def _apply_user_fallback_if_sales(intent: str, user_text: str) -> str:
    if intent != "SALES":
        return intent
    fb = _intent_from_user_message(user_text)
    if fb is not None:
        log.info("intent_user_fallback", intent=fb)
        return fb
    return "SALES"


def _block_reason_str(pf: object | None) -> str | None:
    if pf is None:
        return None
    br = getattr(pf, "block_reason", None)
    if br is None:
        return None
    # 0 / UNSPECIFIED — промпт не заблокирован
    if br == 0:
        return None
    name = getattr(br, "name", None)
    if name in (None, "BLOCK_REASON_UNSPECIFIED"):
        return None
    return str(br)


@dataclass(frozen=True)
class IntentClassificationResult:
    """Результат вызова Gemini для диагностики и продакшена."""

    intent: str
    raw_text: str
    model: str
    error: str | None = None
    block_reason: str | None = None


class AIClassifier:
    def __init__(self) -> None:
        genai.configure(api_key=settings.LLM_API_KEY)
        self._model: GenerativeModel = GenerativeModel(settings.LLM_MODEL)

    async def classify_full(self, text: str) -> IntentClassificationResult:
        """Полный ответ модели + распознанный intent (для /health/llm и отладки)."""
        prompt = _DEFAULT_CLASSIFY_PROMPT.format(text=text)
        model_name = settings.LLM_MODEL
        try:
            response = await asyncio.to_thread(
                lambda: self._model.generate_content(
                    prompt,
                    generation_config=_CLASSIFY_GENERATION_CONFIG,
                )
            )
            pf = getattr(response, "prompt_feedback", None)
            br_str = _block_reason_str(pf)
            if br_str:
                log.warning("intent_prompt_feedback", block_reason=br_str)

            raw = _safe_generate_content_text(response)
            if not raw:
                log.warning(
                    "intent_empty_model_text",
                    hint="Проверьте LLM_API_KEY, LLM_MODEL и логи Gemini (safety/blocked).",
                )
                intent = _apply_user_fallback_if_sales("SALES", text)
                return IntentClassificationResult(
                    intent=intent,
                    raw_text="",
                    model=model_name,
                    error="empty_model_text" if intent == "SALES" else None,
                    block_reason=br_str,
                )

            token = _intent_token_from_model_text(raw)
            token = _apply_user_fallback_if_sales(token, text)
            log.info("intent_classified", intent=token, raw_preview=raw[:120])
            return IntentClassificationResult(
                intent=token,
                raw_text=raw,
                model=model_name,
                error=None,
                block_reason=br_str,
            )
        except google_api_exceptions.NotFound as exc:
            log.error(
                "intent_gemini_model_not_found",
                model=model_name,
                error=str(exc),
                hint="Укажите актуальную модель в LLM_MODEL (например gemini-2.5-flash).",
            )
            fb = _intent_from_user_message(text)
            return IntentClassificationResult(
                intent=fb if fb is not None else "SALES",
                raw_text="",
                model=model_name,
                error=f"model_not_found: {exc}",
                block_reason=None,
            )
        except Exception as exc:
            log.exception("intent_classification_failed", error=str(exc))
            fb = _intent_from_user_message(text)
            return IntentClassificationResult(
                intent=fb if fb is not None else "SALES",
                raw_text="",
                model=model_name,
                error=str(exc),
                block_reason=None,
            )

    async def classify_intent(self, text: str) -> str:
        return (await self.classify_full(text)).intent
