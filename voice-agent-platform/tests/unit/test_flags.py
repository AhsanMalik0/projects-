from app.core.flags import DEFAULTS, FlagResolver


class TestFlagResolver:
    def test_get_default_value(self) -> None:
        resolver = FlagResolver(tenant_id="t1", overrides={})
        assert resolver.get("FLAG_RAG_ENABLED") is False
        assert resolver.get("FLAG_RAG_MAX_CHUNKS") == 5

    def test_get_override_value(self) -> None:
        resolver = FlagResolver(
            tenant_id="t1",
            overrides={"FLAG_RAG_ENABLED": True, "FLAG_RAG_MAX_CHUNKS": 10},
        )
        assert resolver.get("FLAG_RAG_ENABLED") is True
        assert resolver.get("FLAG_RAG_MAX_CHUNKS") == 10

    def test_get_unknown_flag_returns_default_param(self) -> None:
        resolver = FlagResolver(tenant_id="t1", overrides={})
        assert resolver.get("NONEXISTENT_FLAG") is None
        assert resolver.get("NONEXISTENT_FLAG", "fallback") == "fallback"

    def test_enabled_returns_bool(self) -> None:
        resolver = FlagResolver(
            tenant_id="t1",
            overrides={"FLAG_RAG_ENABLED": True},
        )
        assert resolver.enabled("FLAG_RAG_ENABLED") is True
        assert resolver.enabled("FLAG_NLU_SENTIMENT_REALTIME") is False

    def test_enabled_with_non_bool_value(self) -> None:
        resolver = FlagResolver(
            tenant_id="t1",
            overrides={"FLAG_RAG_MAX_CHUNKS": 5},
        )
        assert resolver.enabled("FLAG_RAG_MAX_CHUNKS") is True

    def test_enabled_false_for_zero(self) -> None:
        resolver = FlagResolver(
            tenant_id="t1",
            overrides={"FLAG_RAG_MAX_CHUNKS": 0},
        )
        assert resolver.enabled("FLAG_RAG_MAX_CHUNKS") is False

    def test_all_defaults_have_values(self) -> None:
        for key, value in DEFAULTS.items():
            assert key.startswith("FLAG_"), f"Flag {key} should start with FLAG_"
            assert value is not None or key in DEFAULTS

    def test_tenant_id_stored(self) -> None:
        resolver = FlagResolver(tenant_id="tenant_abc", overrides={})
        assert resolver.tenant_id == "tenant_abc"
