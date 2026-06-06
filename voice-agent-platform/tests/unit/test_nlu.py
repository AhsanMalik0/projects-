import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.nlu import NLUProcessor, NLUResult


class TestNLUResult:
    def test_create_result(self) -> None:
        result = NLUResult(intent="order_status", confidence=0.95, entities={"order_id": "ORD-123"})
        assert result.intent == "order_status"
        assert result.confidence == 0.95
        assert result.entities == {"order_id": "ORD-123"}

    def test_default_entities(self) -> None:
        result = NLUResult(intent="greeting", confidence=0.8)
        assert result.entities == {}


class TestNLUProcessor:
    @pytest.mark.asyncio
    async def test_process_happy_path(self) -> None:
        llm_response = json.dumps(
            {
                "intent": "order_status",
                "confidence": 0.92,
                "entities": {"order_id": "ORD-123"},
            }
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=llm_response)

        with patch("app.services.llm.base.get_llm_provider", return_value=mock_llm):
            processor = NLUProcessor()
            result = await processor.process("What's the status of order ORD-123?")

        assert result.intent == "order_status"
        assert result.confidence == 0.92
        assert result.entities["order_id"] == "ORD-123"

    @pytest.mark.asyncio
    async def test_process_low_confidence(self) -> None:
        llm_response = json.dumps(
            {
                "intent": "unclear",
                "confidence": 0.3,
                "entities": {},
            }
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=llm_response)

        with patch("app.services.llm.base.get_llm_provider", return_value=mock_llm):
            processor = NLUProcessor()
            result = await processor.process("hmm maybe")

        assert result.intent == "unclear"
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_process_invalid_json(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="This is not JSON")

        with patch("app.services.llm.base.get_llm_provider", return_value=mock_llm):
            processor = NLUProcessor()
            result = await processor.process("test")

        assert result.intent == "unclear"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_custom_entity_types(self) -> None:
        llm_response = json.dumps(
            {
                "intent": "booking",
                "confidence": 0.88,
                "entities": {"room_type": "deluxe"},
            }
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=llm_response)

        with patch("app.services.llm.base.get_llm_provider", return_value=mock_llm):
            processor = NLUProcessor(custom_entity_types=["room_type", "check_in_date"])
            result = await processor.process("I want to book a deluxe room")

        assert result.intent == "booking"
        assert result.entities["room_type"] == "deluxe"
