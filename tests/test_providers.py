"""Tests de la couche IA : garde-fous, consentement, budget, journal, adaptateurs (sans appel réseau)."""

from types import SimpleNamespace

import pytest
from mcp import Client

from academic_writer.core.config import Settings
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentType, Language
from academic_writer.providers import secrets
from academic_writer.providers.base import GenerationRequest, ProviderError
from academic_writer.providers.manager import ProviderManager
from academic_writer.providers.mock import MockProvider
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

REQUEST = GenerationRequest(task="test", system="Système", prompt="Bonjour")
PHRASE = "J'autorise l'envoi externe"


@pytest.fixture
def mock() -> MockProvider:
    return MockProvider(["Texte généré."])


@pytest.fixture
def connected(services: Services, mock: MockProvider) -> ProviderManager:
    services.settings.mode = "connected"
    manager = ProviderManager(services.db, services.settings, services.projects, factory=lambda name: mock)
    services.ai = manager
    return manager


@pytest.fixture
def project(services: Services):
    return services.projects.create("Mémoire", DocumentType.MEMOIRE_MASTER, Language.FR)


def test_local_mode_blocks_everything(services: Services, project) -> None:
    services.ai = ProviderManager(services.db, services.settings, services.projects,
                                  factory=lambda name: MockProvider())
    with pytest.raises(ProviderError) as exc:
        services.ai.generate(project.id, REQUEST)
    assert exc.value.kind == "consent" and "mode = 'connected'" in str(exc.value)
    with pytest.raises(ProviderError):
        services.ai.test_provider("anthropic")


def test_consent_required_and_phrase_checked(connected: ProviderManager, project, mock: MockProvider) -> None:
    with pytest.raises(ProviderError) as exc:
        connected.generate(project.id, REQUEST)
    assert exc.value.kind == "consent" and mock.requests == []
    with pytest.raises(ValidationFailed):
        connected.set_consent(project.id, True, confirmation="oui")
    consent = connected.set_consent(project.id, True, confirmation="  j’autorise l’envoi externe. ")
    assert consent.scope == "all"
    result = connected.generate(project.id, REQUEST)
    assert result.text == "Texte généré." and len(mock.requests) == 1


def test_consent_scope_and_revocation(connected: ProviderManager, project) -> None:
    connected.set_consent(project.id, True, scope="openai", confirmation=PHRASE)
    with pytest.raises(ProviderError):
        connected.generate(project.id, REQUEST, provider="anthropic")
    connected.generate(project.id, REQUEST, provider="openai")
    assert connected.set_consent(project.id, False) is None
    with pytest.raises(ProviderError):
        connected.generate(project.id, REQUEST, provider="openai")


def test_consent_phrases_ru_en(connected: ProviderManager, project) -> None:
    assert connected.set_consent(project.id, True, confirmation="Я разрешаю внешнюю отправку")
    assert connected.set_consent(project.id, True, confirmation="I authorize external processing!")


def test_usage_recorded_without_content(connected: ProviderManager, project, services: Services) -> None:
    connected.set_consent(project.id, True, confirmation=PHRASE)
    connected.generate(project.id, REQUEST.model_copy(update={"prompt": "Données confidentielles"}))
    with services.db.read() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM ai_usage")]
    assert len(rows) == 1 and rows[0]["status"] == "ok" and rows[0]["cost_estimate"] is None
    assert "confidentielles" not in str(rows)
    assert connected.month_tokens() == rows[0]["input_tokens"] + rows[0]["output_tokens"]


def test_errors_and_refusals_recorded(connected: ProviderManager, project, mock: MockProvider, services: Services) -> None:
    connected.set_consent(project.id, True, confirmation=PHRASE)
    mock.fail_with = ProviderError("refusal", "refusé")
    with pytest.raises(ProviderError):
        connected.generate(project.id, REQUEST)
    mock.fail_with = ProviderError("rate_limit", "limite", retryable=True)
    with pytest.raises(ProviderError):
        connected.generate(project.id, REQUEST)
    with services.db.read() as conn:
        statuses = [(r[0], r[1]) for r in conn.execute("SELECT status, error_kind FROM ai_usage ORDER BY id")]
    assert statuses == [("refused", "refusal"), ("error", "rate_limit")]


def test_budget_blocks_calls(connected: ProviderManager, project, mock: MockProvider) -> None:
    connected.settings.ai_monthly_token_budget = 1000
    connected.set_consent(project.id, True, confirmation=PHRASE)
    mock.responses.extend(["x" * 8000])
    connected.generate(project.id, REQUEST)  # dépasse le budget
    connected.generate(project.id, REQUEST)
    with pytest.raises(ProviderError) as exc:
        connected.generate(project.id, REQUEST)
    assert exc.value.kind == "budget"


def test_cost_only_with_user_prices(connected: ProviderManager, project, services: Services) -> None:
    connected.settings.ai_prices_per_million = {"mock-1": {"input": 4.0, "output": 20.0}}
    connected.set_consent(project.id, True, confirmation=PHRASE)
    connected.generate(project.id, REQUEST)
    assert connected.month_cost() > 0
    assert connected.estimate_cost("autre-modele", 1000, 1000) is None


def test_max_tokens_capped_by_settings(connected: ProviderManager, project, mock: MockProvider) -> None:
    connected.settings.ai_max_output_tokens = 500
    connected.set_consent(project.id, True, confirmation=PHRASE)
    connected.generate(project.id, REQUEST.model_copy(update={"max_output_tokens": 9000}))
    assert mock.requests[-1].max_output_tokens == 500


def test_missing_key_message(services: Services, monkeypatch: pytest.MonkeyPatch) -> None:
    services.settings.mode = "connected"
    monkeypatch.setattr(secrets, "get_key", lambda provider: None)
    manager = ProviderManager(services.db, services.settings, services.projects)
    with pytest.raises(ProviderError) as exc:
        manager.test_provider("openai")
    assert exc.value.kind == "config" and "secrets set openai" in str(exc.value)


def test_status_lists_steps(services: Services, project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "key_source", lambda provider: None)
    status = services.ai.status(project.id)
    assert status.mode == "local" and not status.connected
    assert len(status.how_to_enable) == 4  # mode + 2 clés + consentement
    assert all(not p.key_configured for p in status.providers)


def test_secrets_validation_and_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        secrets.set_key("anthropic", "court")
    with pytest.raises(ValueError):
        secrets.get_key("inconnu")
    monkeypatch.setattr(secrets.keyring, "get_password", lambda service, name: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-0123456789abcdefghij")
    assert secrets.get_key("openai") == "sk-test-0123456789abcdefghij"
    assert secrets.key_source("openai") == "variable d'environnement"
    assert secrets.mask("sk-ant-0123456789abcdef") == "sk-ant-…cdef"


def test_languagetool_must_be_local(tmp_path) -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(data_dir=tmp_path, languagetool_url="https://api.languagetool.org")
    assert Settings(data_dir=tmp_path, languagetool_url="http://127.0.0.1:8081/").languagetool_url == "http://127.0.0.1:8081"


# --- adaptateurs : traduction des réponses et des erreurs des SDK (client simulé) -------------

def _anthropic_response(stop_reason="end_turn", text="Bonjour", category=None):
    return SimpleNamespace(
        stop_reason=stop_reason, stop_details=SimpleNamespace(category=category) if category else None,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=3,
                              cache_creation_input_tokens=0),
        model="claude-opus-5-5", _request_id="req_1",
    )


def test_anthropic_adapter_uses_fallback_and_effort() -> None:
    from academic_writer.providers.anthropic_provider import AnthropicProvider
    provider = AnthropicProvider("sk-ant-test-0123456789abcdef", "claude-opus-5-5", "high", True, 30)
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _anthropic_response()

    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)))
    result = provider.generate(REQUEST)
    assert result.text == "Bonjour" and result.input_tokens == 13 and result.output_tokens == 5
    assert captured["fallbacks"] == "default" and captured["betas"] == ["server-side-fallback-2026-07-01"]
    assert captured["output_config"] == {"effort": "high"} and captured["model"] == "claude-opus-5-5"
    assert "thinking" not in captured  # jamais désactivé : réglé par l'effort


def test_anthropic_adapter_refusal_and_truncation() -> None:
    from academic_writer.providers.anthropic_provider import AnthropicProvider
    provider = AnthropicProvider("sk-ant-test-0123456789abcdef", "claude-opus-5-5", "high", False, 30)
    provider.client = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: _anthropic_response("refusal", category="cyber")))
    with pytest.raises(ProviderError) as exc:
        provider.generate(REQUEST)
    assert exc.value.kind == "refusal" and "cyber" in str(exc.value)
    provider.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _anthropic_response("max_tokens")))
    assert provider.generate(REQUEST).truncated


def test_anthropic_adapter_maps_sdk_errors() -> None:
    import anthropic
    import httpx2
    from academic_writer.providers.anthropic_provider import AnthropicProvider
    provider = AnthropicProvider("sk-ant-test-0123456789abcdef", "claude-opus-5-5", "high", False, 30)
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    error_classes = {401: anthropic.AuthenticationError, 429: anthropic.RateLimitError,
                     529: anthropic.InternalServerError}

    def raising(status):
        def create(**kwargs):
            response = httpx2.Response(status, request=request, json={"error": {"message": "x"}})
            raise error_classes[status]("x", response=response, body=None)
        return create

    for status, kind in ((401, "auth"), (429, "rate_limit"), (529, "server")):
        provider.client = SimpleNamespace(messages=SimpleNamespace(create=raising(status)))
        with pytest.raises(ProviderError) as exc:
            provider.generate(REQUEST)
        assert exc.value.kind == kind


def test_openai_adapter_store_false_and_refusal() -> None:
    from academic_writer.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider("sk-test-0123456789abcdefghij", "gpt-5.5", 30)
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output=[], output_text="Réponse", status="completed", incomplete_details=None,
                               usage=SimpleNamespace(input_tokens=7, output_tokens=3), model="gpt-5.5", _request_id="r")

    provider.client = SimpleNamespace(responses=SimpleNamespace(create=fake_create))
    result = provider.generate(REQUEST)
    assert result.text == "Réponse" and captured["store"] is False and captured["instructions"] == "Système"
    refusal = SimpleNamespace(output=[SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="non")])],
                              output_text="", usage=None)
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: refusal))
    with pytest.raises(ProviderError) as exc:
        provider.generate(REQUEST)
    assert exc.value.kind == "refusal"


@pytest.mark.anyio
async def test_mcp_ai_tools(services: Services, project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "key_source", lambda provider: None)
    async with Client(mcp) as client:
        status = await client.call_tool("get_ai_status", {"project_id": project.id})
        assert status.structured_content["mode"] == "local"
        refused = await client.call_tool("set_project_ai_consent", {"project_id": project.id, "granted": True})
        assert refused.is_error and "phrase exacte" in refused.content[0].text
        granted = await client.call_tool("set_project_ai_consent", {
            "project_id": project.id, "granted": True, "user_confirmation": PHRASE})
        assert granted.structured_content["consent"]["scope"] == "all"
        test = await client.call_tool("test_ai_provider", {"provider": "anthropic"})
        assert test.is_error and "Mode local" in test.content[0].text
