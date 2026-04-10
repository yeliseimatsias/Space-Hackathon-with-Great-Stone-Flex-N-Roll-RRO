from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.intent import IntentService


@pytest.mark.asyncio
async def test_intent_classify_delegates_to_classifier() -> None:
    classifier = MagicMock()
    classifier.classify_intent = AsyncMock(return_value="TECH")
    svc = IntentService(classifier)
    result = await svc.classify("hello")
    assert result == "TECH"
    classifier.classify_intent.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_intent_classify_propagates_sales_default() -> None:
    classifier = MagicMock()
    classifier.classify_intent = AsyncMock(return_value="SALES")
    svc = IntentService(classifier)
    assert await svc.classify("x") == "SALES"
