from rank_bm25 import BM25Okapi

from app.core.flags import FlagResolver
from app.core.nlu import NLUProcessor
from app.core.rag import RAGEngine
from app.core.session import CallSession
from app.services.llm.base import LLMProvider
from app.services.stt.base import STTProvider
from app.services.tts.base import TTSProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

GUARDRAIL_BLOCK_PHRASES = [
    "ignore your instructions",
    "pretend you are",
    "act as if you",
    "disregard previous",
    "forget your rules",
]


class VoicePipeline:
    def __init__(
        self,
        flags: FlagResolver,
        session: CallSession,
        stt: STTProvider,
        tts: TTSProvider,
        llm: LLMProvider,
        rag: RAGEngine | None = None,
    ) -> None:
        self.flags = flags
        self.session = session
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.rag = rag

    async def process_audio_chunk(self, audio: bytes) -> bytes:
        """Full pipeline: audio in -> audio response out."""
        # 1. STT
        transcript = await self.stt.transcribe(audio)
        log.info("stt_result", text=transcript)

        # 2. Guardrails check (flag-gated)
        if self.flags.enabled("FLAG_LLM_GUARDRAILS"):
            lower = transcript.lower()
            for phrase in GUARDRAIL_BLOCK_PHRASES:
                if phrase in lower:
                    log.warning("guardrail_blocked", phrase=phrase)
                    refusal = "I'm sorry, I can only help with topics related to our services."
                    self.session.add_turn("user", transcript)
                    self.session.add_turn("assistant", refusal)
                    return await self.tts.synthesise(refusal)

        # 3. Max turns enforcement (flag-gated)
        max_turns = self.flags.get("FLAG_LLM_MAX_TURNS", 30)
        if self.session.turn_count >= max_turns:
            wrap_up = (
                "We've reached the end of our conversation time. "
                "Is there anything else I can quickly help with before we wrap up?"
            )
            self.session.add_turn("user", transcript)
            self.session.add_turn("assistant", wrap_up)
            return await self.tts.synthesise(wrap_up)

        # 4. NLU + NER (flag-gated)
        nlu_result = None
        if self.flags.enabled("FLAG_NLU_ENTITY_EXTRACTION"):
            custom_types = None
            if self.flags.enabled("FLAG_NLU_CUSTOM_ENTITIES"):
                custom_types = self.flags.get("FLAG_NLU_CUSTOM_ENTITIES_LIST", [])
                if not isinstance(custom_types, list):
                    custom_types = None
            nlu_result = await NLUProcessor(custom_entity_types=custom_types).process(transcript)
            threshold = self.flags.get("FLAG_NLU_CONFIDENCE_THRESHOLD", 0.75)
            if nlu_result.confidence >= threshold:
                self.session.update_entities(nlu_result.entities)
                log.info("nlu_result", intent=nlu_result.intent, conf=nlu_result.confidence)
            else:
                log.info("nlu_low_confidence", intent=nlu_result.intent, conf=nlu_result.confidence)

        # 5. RAG retrieval (flag-gated)
        context_chunks: list[str] = []
        if self.flags.enabled("FLAG_RAG_ENABLED") and self.rag:
            max_chunks = self.flags.get("FLAG_RAG_MAX_CHUNKS", 5)
            context_chunks = await self.rag.retrieve(
                query=transcript,
                tenant_id=self.session.tenant_id,
                top_k=max_chunks,
            )

            # BM25 keyword fallback
            if not context_chunks and self.flags.enabled("FLAG_RAG_KEYWORD_FALLBACK"):
                context_chunks = self._keyword_fallback(transcript)

            # Re-ranker: score-based re-sort (simple implementation)
            if context_chunks and self.flags.enabled("FLAG_RAG_RERANKER"):
                context_chunks = self._rerank(transcript, context_chunks)

        # 6. Build LLM messages
        self.session.add_turn("user", transcript)
        response_text = await self.llm.generate(
            messages=self.session.messages,
            system_prompt=self._build_system_prompt(context_chunks),
        )
        self.session.add_turn("assistant", response_text)

        # 7. Real-time sentiment (flag-gated)
        if self.flags.enabled("FLAG_NLU_SENTIMENT_REALTIME") and nlu_result:
            log.info(
                "realtime_sentiment",
                intent=nlu_result.intent,
                turn=self.session.turn_count,
            )

        # 8. TTS
        audio_response = await self.tts.synthesise(response_text)
        return audio_response

    def _build_system_prompt(self, chunks: list[str]) -> str:
        parts = [self.session.persona_prompt]
        if chunks:
            parts.append("\n\n## Relevant knowledge\n" + "\n---\n".join(chunks))
        if self.session.entities:
            parts.append(f"\n\n## Extracted so far\n{self.session.entities}")
        return "\n".join(parts)

    def _keyword_fallback(self, query: str) -> list[str]:
        """BM25-based keyword search as fallback when vector search returns nothing."""
        history_texts = [m["content"] for m in self.session.messages if m["role"] == "assistant"]
        if not history_texts:
            return []
        tokenised = [doc.lower().split() for doc in history_texts]
        bm25 = BM25Okapi(tokenised)
        scores = bm25.get_scores(query.lower().split())
        ranked = sorted(zip(history_texts, scores), key=lambda x: x[1], reverse=True)
        return [text for text, score in ranked[:3] if score > 0]

    def _rerank(self, query: str, chunks: list[str]) -> list[str]:
        """Simple BM25-based reranking of retrieved chunks."""
        tokenised = [c.lower().split() for c in chunks]
        bm25 = BM25Okapi(tokenised)
        scores = bm25.get_scores(query.lower().split())
        ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        return [c for c, _ in ranked]
