from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.rag import RAGEngine


class TestRAGEngine:
    @pytest.mark.asyncio
    async def test_retrieve_no_db(self) -> None:
        engine = RAGEngine(vector_db=None)
        result = await engine.retrieve("test query", "tenant1")
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_with_results(self) -> None:
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(
            return_value={
                "matches": [
                    {"id": "1", "score": 0.9, "metadata": {"chunk": "Relevant info 1"}},
                    {"id": "2", "score": 0.8, "metadata": {"chunk": "Relevant info 2"}},
                    {"id": "3", "score": 0.5, "metadata": {"chunk": "Low score"}},
                ]
            }
        )

        mock_embed_resp = MagicMock()
        mock_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]

        with patch("app.core.rag.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_embed_resp
            mock_openai.return_value = mock_client
            engine = RAGEngine(vector_db=mock_db)
            result = await engine.retrieve("test query", "tenant1", top_k=5, score_threshold=0.72)

        assert len(result) == 2
        assert "Relevant info 1" in result
        assert "Relevant info 2" in result
        assert "Low score" not in result

    @pytest.mark.asyncio
    async def test_retrieve_empty_results(self) -> None:
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value={"matches": []})

        mock_embed_resp = MagicMock()
        mock_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]

        with patch("app.core.rag.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_embed_resp
            mock_openai.return_value = mock_client
            engine = RAGEngine(vector_db=mock_db)
            result = await engine.retrieve("test query", "tenant1")

        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_all_below_threshold(self) -> None:
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(
            return_value={
                "matches": [
                    {"id": "1", "score": 0.5, "metadata": {"chunk": "Low score 1"}},
                    {"id": "2", "score": 0.3, "metadata": {"chunk": "Low score 2"}},
                ]
            }
        )

        mock_embed_resp = MagicMock()
        mock_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]

        with patch("app.core.rag.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_embed_resp
            mock_openai.return_value = mock_client
            engine = RAGEngine(vector_db=mock_db)
            result = await engine.retrieve("test", "tenant1")

        assert result == []
