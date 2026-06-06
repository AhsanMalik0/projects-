# AI Voice Call Agent Platform

A multi-tenant AI voice call agent platform built with Python, FastAPI, Google Gemini / Anthropic Claude, PostgreSQL, and Pinecone.

## What It Does

- Business clients register and configure AI voice agents for their use case (customer support, sales, bookings, etc.)
- The platform provisions API keys and webhooks for integration
- When a call arrives, the AI voice agent handles the conversation: **STT → NLU → RAG → LLM → TTS**
- Real-time voice streaming via WebSocket (`/api/v1/voice/stream`)
- After the call, the system generates summaries, key points, sentiment scores, and pushes results via webhooks
- All behaviour is controlled via feature flags on a per-tenant basis

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| API Framework | FastAPI + Uvicorn |
| LLM | Google Gemini (free) / Anthropic Claude |
| STT | Deepgram SDK / OpenAI Whisper |
| TTS | ElevenLabs / OpenAI TTS |
| Vector DB | Pinecone / Qdrant |
| Relational DB | PostgreSQL + asyncpg |
| Cache / Queue | Redis + Celery |
| Embeddings | OpenAI text-embedding-3-small |
| Auth | JWT + API key (HMAC-SHA256) |
| Telephony | Twilio (optional) |
| Infra | Docker + docker-compose |
| Observability | Prometheus + Sentry + structlog |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Poetry

### Setup

```bash
# Clone the repo
git clone https://github.com/conninieves-web/voice-agent.git
cd voice-agent/voice-agent-platform

# Install dependencies
poetry install

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and database URL

# For Gemini (free), set in .env:
#   LLM_PROVIDER=gemini
#   LLM_MODEL=gemini-2.0-flash
#   GEMINI_API_KEY=your-key-here
# Get your free key at: https://aistudio.google.com/apikey

# Run with Docker
make build
make up
```

### Development

```bash
# Run tests
make test

# Lint and format
make lint
make format

# Run API server locally
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/api/v1/onboarding/register` | Register a new business tenant |
| POST | `/api/v1/onboarding/configure` | Set use-case, persona, business hours |
| GET | `/api/v1/onboarding/status` | Get onboarding and sandbox status |
| POST | `/api/v1/onboarding/rotate-key` | Rotate API key |
| POST | `/api/v1/calls/initiate` | Start an outbound AI voice call |
| GET | `/api/v1/calls/{call_id}` | Get call status and metadata |
| PATCH | `/api/v1/calls/{call_id}/status` | Update call status (with transcript) |
| GET | `/api/v1/calls/{call_id}/transcript` | Retrieve full call transcript |
| GET | `/api/v1/calls/{call_id}/summary` | Retrieve post-call summary JSON |
| GET | `/api/v1/calls` | List calls with filtering and pagination |
| GET | `/api/v1/knowledge` | List knowledge base documents |
| POST | `/api/v1/knowledge/upload` | Upload a document to the knowledge base |
| DELETE | `/api/v1/knowledge/{doc_id}` | Remove a document from the KB |
| GET | `/api/v1/webhooks` | List registered webhooks |
| POST | `/api/v1/webhooks/register` | Register a webhook URL for callbacks |
| DELETE | `/api/v1/webhooks/{id}` | Remove a webhook registration |
| GET | `/api/v1/admin/flags` | List all feature flags for the tenant |
| PATCH | `/api/v1/admin/flags/{flag}` | Update a feature flag value |
| WS | `/api/v1/voice/stream` | Real-time voice streaming via WebSocket |

## Architecture

```
Call arrives → STT (Deepgram/Whisper)
            → Guardrails check
            → NLU (intent + entity extraction)
            → RAG (knowledge retrieval from Pinecone/Qdrant)
            → LLM (Gemini/Claude response generation)
            → TTS (ElevenLabs/OpenAI)
            → Audio response sent back

Post-call   → Summary generation
            → Key point extraction
            → Sentiment analysis
            → Webhook delivery to client
            → CRM sync (optional)
```

## Feature Flags

All features are flag-gated per tenant. See `app/core/flags.py` for the full list of defaults. Flags can be managed via the admin API.

Key flags include:
- `FLAG_RAG_ENABLED` — Enable knowledge base retrieval
- `FLAG_LLM_GUARDRAILS` — Enable prompt injection protection
- `FLAG_NLU_ENTITY_EXTRACTION` — Enable intent/entity extraction
- `FLAG_POSTCALL_SUMMARY_ENABLED` — Enable post-call AI summary
- `FLAG_DATA_TRANSCRIPT_ENCRYPTION` — Encrypt transcripts at rest
- `FLAG_DATA_GDPR_REDACTION` — Redact PII from transcripts

## Using Gemini (Free API)

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Set in your `.env`:
   ```
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-2.0-flash
   GEMINI_API_KEY=your-key-here
   ```
3. The platform will use Gemini for all LLM operations (NLU, summarisation, etc.)

## License

MIT
