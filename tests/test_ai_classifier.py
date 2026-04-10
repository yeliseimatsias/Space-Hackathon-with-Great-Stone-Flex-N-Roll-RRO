"""Тесты разбора ответа Gemini без реального API."""

import pytest

from app.services.ai_classifier import (
    _intent_from_user_message,
    _intent_token_from_model_text,
    _safe_generate_content_text,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TECH", "TECH"),
        ("The category is TECH", "TECH"),
        ("Ответ: PRICE.", "PRICE"),
        ("STATUS — подходит", "STATUS"),
        ("COMPLAINT", "COMPLAINT"),
        ("SALES", "SALES"),
        ("sales", "SALES"),
        ("цена", "PRICE"),
        ("Технический вопрос", "TECH"),
        ("статус заказа", "STATUS"),
    ],
)
def test_intent_token_from_model_text(raw: str, expected: str) -> None:
    assert _intent_token_from_model_text(raw) == expected


def test_safe_text_when_text_property_raises() -> None:
    class FakePart:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeContent:
        def __init__(self, parts: list) -> None:
            self.parts = parts

    class FakeCandidate:
        def __init__(self, parts: list) -> None:
            self.content = FakeContent(parts)

    class FakeResponse:
        @property
        def text(self) -> str:
            raise ValueError("simulated SDK: empty parts")

        def __init__(self) -> None:
            self.candidates = [FakeCandidate([FakePart("PRICE")])]

    assert _safe_generate_content_text(FakeResponse()) == "PRICE"


@pytest.mark.parametrize(
    ("user_msg", "expected"),
    [
        ("Сколько стоит тираж 5000?", "PRICE"),
        ("Где мой заказ номер 12?", "STATUS"),
        ("Претензия по качеству ламинации", "COMPLAINT"),
        ("Какой dpi для макета?", "TECH"),
        ("Привет", None),
    ],
)
def test_intent_from_user_message(user_msg: str, expected: str | None) -> None:
    assert _intent_from_user_message(user_msg) == expected
