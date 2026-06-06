from app.core.session import CallSession


class TestCallSession:
    def test_create_session(self) -> None:
        session = CallSession(tenant_id="t1")
        assert session.tenant_id == "t1"
        assert session.call_id.startswith("call_")
        assert session.messages == []
        assert session.turn_count == 0

    def test_add_turns(self) -> None:
        session = CallSession(tenant_id="t1")
        session.add_turn("user", "Hello")
        session.add_turn("assistant", "Hi there!")
        assert len(session.messages) == 2
        assert session.turn_count == 2
        assert session.messages[0] == {"role": "user", "content": "Hello"}
        assert session.messages[1] == {"role": "assistant", "content": "Hi there!"}

    def test_update_entities(self) -> None:
        session = CallSession(tenant_id="t1")
        session.update_entities({"name": "Ahmed"})
        session.update_entities({"order_id": "ORD-123"})
        assert session.entities == {"name": "Ahmed", "order_id": "ORD-123"}

    def test_update_entities_overwrites(self) -> None:
        session = CallSession(tenant_id="t1")
        session.update_entities({"name": "Ahmed"})
        session.update_entities({"name": "Ali"})
        assert session.entities["name"] == "Ali"

    def test_get_transcript(self) -> None:
        session = CallSession(tenant_id="t1")
        session.add_turn("user", "I need help with my order")
        session.add_turn("assistant", "Sure, what's your order ID?")
        session.add_turn("user", "ORD-123")
        transcript = session.get_transcript()
        assert "USER: I need help with my order" in transcript
        assert "ASSISTANT: Sure, what's your order ID?" in transcript
        assert "USER: ORD-123" in transcript
