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
    manager = ProviderManager(services.db, services.settings, services.projects, factory=lambda name: mock,
                              ollama_probe=lambda: None)
    services.ai = manager
    return manager


@pytest.fixture
def project(services: Services):
    return services.projects.create("Mémoire", DocumentType.MEMOIRE_MASTER, Language.FR)


def test_local_mode_blocks_everything(services: Services, project) -> None:
    services.ai = ProviderManager(services.db, services.settings, services.projects,
                                  factory=lambda name: MockProvider(), ollama_probe=lambda: None)
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
    manager = ProviderManager(services.db, services.settings, services.projects, ollama_probe=lambda: None)
    with pytest.raises(ProviderError) as exc:
        manager.test_provider("openai")
    assert exc.value.kind == "config" and "secrets set openai" in str(exc.value)


def test_status_lists_steps(services: Services, project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "key_source", lambda provider: None)
    status = services.ai.status(project.id)
    assert status.mode == "local" and not status.connected
    assert len(status.how_to_enable) == 5  # mode + 2 clés + consentement + modèle local
    assert status.auto_choice.engine == "assistant"
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


# --- choix du moteur et modèle local (Ollama) ---------------------------------

def _manager(services: Services, installed=None, mock: MockProvider | None = None) -> ProviderManager:
    mock = mock or MockProvider(["Texte local."])
    return ProviderManager(services.db, services.settings, services.projects,
                           factory=lambda name: mock, ollama_probe=lambda: installed)


def test_auto_engine_falls_back_to_assistant(services: Services, project) -> None:
    choice = _manager(services).resolve_engine(project.id)
    assert choice.engine == "assistant" and choice.local
    reasons = {e.engine: e.reason for e in choice.engines}
    assert "mode local" in reasons["anthropic"] and "ne répond pas" in reasons["ollama"]


def test_auto_engine_prefers_local_model_when_installed(services: Services, project) -> None:
    choice = _manager(services, installed=["qwen3.5:4b"]).resolve_engine(project.id)
    assert choice.engine == "ollama" and choice.local and choice.model == "qwen3.5:4b"
    missing = _manager(services, installed=["autre:7b"]).resolve_engine(project.id)
    assert missing.engine == "assistant"
    assert "ollama pull qwen3.5:4b" in next(e.reason for e in missing.engines if e.engine == "ollama")


def test_auto_engine_prefers_authorized_cloud(services: Services, project, monkeypatch: pytest.MonkeyPatch) -> None:
    services.settings.mode = "connected"
    monkeypatch.setattr(secrets, "key_source", lambda provider: "coffre Windows" if provider == "openai" else None)
    manager = _manager(services, installed=["qwen3.5:4b"])
    assert manager.resolve_engine(project.id).engine == "ollama"  # pas encore de consentement
    manager.set_consent(project.id, True, confirmation=PHRASE)
    choice = manager.resolve_engine(project.id)
    assert choice.engine == "openai" and not choice.local  # anthropic sans clé → openai


def test_requested_engine_must_be_available(services: Services, project) -> None:
    manager = _manager(services)
    with pytest.raises(ProviderError) as exc:
        manager.resolve_engine(project.id, "ollama")
    assert "indisponible" in str(exc.value)
    assert manager.resolve_engine(project.id, "assistant").engine == "assistant"


def test_local_model_needs_no_consent_and_is_logged(services: Services, project) -> None:
    manager = _manager(services, installed=["qwen3.5:4b"])
    result = manager.generate(project.id, REQUEST, provider="ollama")  # mode local, sans consentement
    assert result.text == "Texte local."
    with services.db.read() as conn:
        assert conn.execute("SELECT provider, status FROM ai_usage").fetchone()[:] == ("ollama", "ok")
    with pytest.raises(ProviderError):
        manager.generate(project.id, REQUEST, provider="assistant")


def test_ollama_adapter_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from academic_writer.providers.ollama_provider import OllamaProvider
    provider = OllamaProvider("http://localhost:11434", "qwen3.5:4b", 8192, False, 30)
    sent = {}

    def fake_post(path, payload):
        sent.update(payload)
        return {"model": "qwen3.5:4b", "message": {"content": "Привет"}, "prompt_eval_count": 12,
                "eval_count": 4, "done_reason": "length"}

    monkeypatch.setattr(provider, "_post", fake_post)
    result = provider.generate(REQUEST)
    assert result.text == "Привет" and result.input_tokens == 12 and result.truncated
    assert sent["stream"] is False and sent["options"] == {"num_predict": 8000, "num_ctx": 8192}
    assert sent["messages"][0] == {"role": "system", "content": "Système"}


def test_ollama_adapter_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error
    import urllib.request

    from academic_writer.providers.ollama_provider import OllamaProvider, installed_models
    provider = OllamaProvider("http://localhost:11434", "qwen3.5:4b", 8192, False, 30)

    def not_found(*args, **kwargs):
        raise urllib.error.HTTPError("http://localhost:11434/api/chat", 404, "Not Found", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(urllib.request, "urlopen", not_found)
    with pytest.raises(ProviderError) as exc:
        provider.generate(REQUEST)
    assert exc.value.kind == "config" and "ollama pull qwen3.5:4b" in str(exc.value)

    def refused(*args, **kwargs):
        raise urllib.error.URLError("connexion refusée")

    monkeypatch.setattr(urllib.request, "urlopen", refused)
    with pytest.raises(ProviderError) as exc:
        provider.generate(REQUEST)
    assert exc.value.kind == "network"
    assert installed_models("http://localhost:11434") is None


def test_ollama_url_must_be_local(tmp_path) -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(data_dir=tmp_path, ollama_url="http://example.com:11434")
