from app.core.flags import FlagResolver
from app.core.summariser import build_postcall_prompt


class TestPostCallPrompt:
    def test_basic_summary_only(self) -> None:
        flags = FlagResolver(
            tenant_id="t1",
            overrides={
                "FLAG_POSTCALL_KEYPOINTS_EXTRACT": False,
                "FLAG_POSTCALL_SENTIMENT_REPORT": False,
                "FLAG_POSTCALL_ESCALATION_DETECT": False,
            },
        )
        prompt = build_postcall_prompt("Hello, how are you?", flags)
        assert "summary" in prompt.lower()
        assert "TRANSCRIPT:" in prompt
        assert "Hello, how are you?" in prompt

    def test_all_features_enabled(self) -> None:
        flags = FlagResolver(
            tenant_id="t1",
            overrides={
                "FLAG_POSTCALL_KEYPOINTS_EXTRACT": True,
                "FLAG_POSTCALL_ACTION_ITEMS": True,
                "FLAG_POSTCALL_SENTIMENT_REPORT": True,
                "FLAG_POSTCALL_ESCALATION_DETECT": True,
                "FLAG_POSTCALL_NER_SUMMARY": True,
            },
        )
        prompt = build_postcall_prompt("Test transcript", flags)
        assert "bullet points" in prompt
        assert "action items" in prompt.lower()
        assert "sentiment" in prompt.lower()
        assert "escalation" in prompt.lower()
        assert "customer name" in prompt.lower()

    def test_partial_features(self) -> None:
        flags = FlagResolver(
            tenant_id="t1",
            overrides={
                "FLAG_POSTCALL_KEYPOINTS_EXTRACT": True,
                "FLAG_POSTCALL_SENTIMENT_REPORT": True,
            },
        )
        prompt = build_postcall_prompt("Some transcript", flags)
        assert "bullet points" in prompt
        assert "sentiment" in prompt.lower()
        assert "Was escalation to a human requested" not in prompt

    def test_prompt_contains_json_instructions(self) -> None:
        flags = FlagResolver(tenant_id="t1", overrides={})
        prompt = build_postcall_prompt("Test", flags)
        assert "JSON" in prompt
