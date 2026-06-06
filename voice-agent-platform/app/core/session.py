import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CallSession:
    tenant_id: str
    call_id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    persona_prompt: str = "You are a helpful AI voice assistant."
    messages: list[dict[str, str]] = field(default_factory=list)
    entities: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    turn_count: int = 0

    def add_turn(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.turn_count += 1

    def update_entities(self, new_entities: dict[str, str]) -> None:
        self.entities.update(new_entities)

    def get_transcript(self) -> str:
        lines = []
        for msg in self.messages:
            role = msg["role"].upper()
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
