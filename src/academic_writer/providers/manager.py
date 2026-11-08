"""Gestionnaire des fournisseurs d'IA : garde-fous, consentement, budget, journal d'usage.

Ordre des contrôles avant tout envoi externe :
1. mode ``connected`` dans la configuration (réglé par l'utilisateur, pas par l'assistant) ;
2. consentement actif pour le projet et le fournisseur ;
3. budget mensuel de tokens non dépassé ;
4. clé API disponible.
Chaque appel (réussi, refusé ou en erreur) est journalisé SANS son contenu.
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from academic_writer.core.config import Settings
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.history import record_event
from academic_writer.core.models import utc_now
from academic_writer.core.projects import ProjectService
from academic_writer.providers import secrets
from academic_writer.providers.base import AIProvider, GenerationRequest, GenerationResult, ProviderError
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.ai")

CONSENT_PHRASES = (
    "j'autorise l'envoi externe",
    "я разрешаю внешнюю отправку",
    "i authorize external processing",
)
DATA_NOTICE = (
    "En mode connecté, les extraits nécessaires à la tâche (dossier de section, texte à corriger ou à "
    "traduire) sont transmis au fournisseur choisi (Anthropic ou OpenAI) et traités sur ses serveurs, "
    "selon ses conditions. Les documents complets ne sont jamais envoyés. Le consentement est révocable."
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'").strip().rstrip(".!")
    return " ".join(text.split())


LOCAL_PROVIDERS = frozenset({"ollama"})
CLOUD_PROVIDERS = ("anthropic", "openai")


class ProviderStatus(BaseModel):
    provider: str
    model: str
    key_configured: bool
    key_source: str | None


class EngineAvailability(BaseModel):
    engine: str
    available: bool
    local: bool = Field(description="Vrai si aucune donnée ne quitte l'ordinateur.")
    model: str | None = None
    reason: str


class EngineChoice(BaseModel):
    engine: str = Field(description="assistant, ollama, anthropic ou openai")
    model: str | None = None
    local: bool
    reason: str
    engines: list[EngineAvailability]


class ConsentInfo(BaseModel):
    project_id: str
    scope: str
    granted_at: str


class AIStatus(BaseModel):
    mode: str
    connected: bool
    default_provider: str
    providers: list[ProviderStatus]
    project_consent: ConsentInfo | None = None
    month_tokens_used: int
    month_budget: int | None
    month_cost_estimate: float | None = Field(description="Uniquement si des tarifs ont été saisis.")
    writing_engine_setting: str
    auto_choice: EngineChoice
    data_notice: str = DATA_NOTICE
    how_to_enable: list[str]


class ProviderManager:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService,
                 factory: Callable[[str], AIProvider] | None = None,
                 ollama_probe: Callable[[], list[str] | None] | None = None) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self._factory = factory or self._build_provider
        self._ollama_probe = ollama_probe or self._probe_ollama

    # --- construction ------------------------------------------------------
    def _probe_ollama(self) -> list[str] | None:
        from academic_writer.providers.ollama_provider import installed_models
        return installed_models(self.settings.ollama_url)

    def _build_provider(self, provider: str) -> AIProvider:
        if provider == "ollama":
            from academic_writer.providers.ollama_provider import OllamaProvider
            return OllamaProvider(self.settings.ollama_url, self.settings.ollama_model, self.settings.ollama_num_ctx,
                                  self.settings.ollama_think, float(self.settings.ollama_timeout_seconds))
        key = secrets.get_key(provider)
        if not key:
            raise ProviderError("config", f"Aucune clé API {provider} configurée. Dans PowerShell : "
                                f"cd D:\\MCP\\academic-writer-mcp ; uv run academic-writer secrets set {provider}")
        timeout = float(self.settings.ai_timeout_seconds)
        if provider == "anthropic":
            from academic_writer.providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(key, self.settings.anthropic_model, self.settings.anthropic_effort,
                                     self.settings.anthropic_refusal_fallback, timeout)
        if provider == "openai":
            from academic_writer.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(key, self.settings.openai_model, timeout)
        raise ProviderError("config", f"Fournisseur inconnu : {provider}")

    def model_of(self, provider: str) -> str:
        return {"anthropic": self.settings.anthropic_model, "openai": self.settings.openai_model,
                "ollama": self.settings.ollama_model}.get(provider, provider)

    # --- choix du moteur -------------------------------------------------------
    def engines(self, project_id: str | None = None) -> list[EngineAvailability]:
        result: list[EngineAvailability] = []
        consent = self.active_consent(project_id) if project_id else None
        for name in CLOUD_PROVIDERS:
            if self.settings.mode != "connected":
                available, reason = False, "mode local (aucun envoi externe autorisé)"
            elif secrets.key_source(name) is None:
                available, reason = False, "aucune clé API configurée"
            elif project_id is None:
                available, reason = True, "clé configurée ; consentement requis par projet"
            elif consent is None or consent.scope not in ("all", name):
                available, reason = False, "pas de consentement pour ce projet"
            else:
                available, reason = True, "mode connecté, clé et consentement présents"
            result.append(EngineAvailability(engine=name, available=available, local=False,
                                             model=self.model_of(name), reason=reason))
        installed = self._ollama_probe()
        wanted = self.settings.ollama_model
        if installed is None:
            available, reason = False, "Ollama ne répond pas (non installé ou non lancé)"
        elif wanted in installed or f"{wanted}:latest" in installed:
            available, reason = True, "modèle local prêt (aucun envoi externe)"
        else:
            available, reason = False, f"modèle « {wanted} » non téléchargé (ollama pull {wanted})"
        result.append(EngineAvailability(engine="ollama", available=available, local=True, model=wanted, reason=reason))
        result.append(EngineAvailability(engine="assistant", available=True, local=True, model=None,
                                         reason="l'assistant MCP rédige à partir du dossier préparé par le serveur"))
        return result

    def resolve_engine(self, project_id: str | None = None, requested: str | None = None) -> EngineChoice:
        """Choisit le moteur : demandé explicitement, sinon réglage, sinon meilleur disponible."""
        engines = self.engines(project_id)
        by_name = {e.engine: e for e in engines}
        wanted = requested or self.settings.writing_engine
        if wanted != "auto":
            engine = by_name.get(wanted)
            if engine is None:
                raise ValidationFailed(f"Moteur inconnu : {wanted}")
            if not engine.available:
                raise ProviderError("config", f"Moteur « {wanted} » indisponible : {engine.reason}.")
            return EngineChoice(engine=wanted, model=engine.model, local=engine.local,
                                reason=f"moteur demandé ({engine.reason})", engines=engines)
        order = [self.settings.ai_default_provider] + [p for p in CLOUD_PROVIDERS if p != self.settings.ai_default_provider]
        for name in order + ["ollama", "assistant"]:
            engine = by_name[name]
            if engine.available and (name not in CLOUD_PROVIDERS or project_id is not None):
                return EngineChoice(engine=name, model=engine.model, local=engine.local,
                                    reason=f"choix automatique : {engine.reason}", engines=engines)
        raise AssertionError("le moteur assistant est toujours disponible")

    # --- consentement ------------------------------------------------------
    def active_consent(self, project_id: str) -> ConsentInfo | None:
        with self.db.read() as conn:
            row = conn.execute("SELECT project_id, scope, granted_at FROM ai_consents WHERE project_id = ? "
                               "AND revoked_at IS NULL ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
        return ConsentInfo(**dict(row)) if row else None

    def set_consent(self, project_id: str, granted: bool, scope: str = "all", confirmation: str = "",
                    note: str = "") -> ConsentInfo | None:
        self.projects.get(project_id)
        now = utc_now()
        if granted:
            if scope not in ("all", "anthropic", "openai"):
                raise ValidationFailed("Portée inconnue : all, anthropic ou openai.")
            if _normalize(confirmation) not in CONSENT_PHRASES:
                raise ValidationFailed(
                    "Consentement non enregistré : l'utilisateur doit taper lui-même la phrase exacte "
                    "« J'autorise l'envoi externe » (ou « Я разрешаю внешнюю отправку », "
                    "« I authorize external processing »)."
                )
        with self.db.transaction() as conn:
            conn.execute("UPDATE ai_consents SET revoked_at = ? WHERE project_id = ? AND revoked_at IS NULL",
                         (now, project_id))
            if granted:
                conn.execute("INSERT INTO ai_consents (project_id, scope, granted_at, note) VALUES (?, ?, ?, ?)",
                             (project_id, scope, now, note[:500]))
            record_event(conn, project_id=project_id, entity_type="project", entity_id=project_id,
                         action="ai_consent_granted" if granted else "ai_consent_revoked", details={"scope": scope})
        logger.info("Consentement IA %s pour le projet %s", "accordé" if granted else "révoqué", project_id)
        return self.active_consent(project_id)

    # --- contrôles -----------------------------------------------------------
    def _check_connected(self) -> None:
        if self.settings.mode != "connected":
            raise ProviderError("consent", "Mode local : aucun envoi externe. Pour utiliser un fournisseur d'IA, "
                                "l'utilisateur doit lui-même mettre mode = 'connected' dans "
                                "%APPDATA%\\AcademicWriter\\config.toml puis redémarrer l'application.")

    def _check_consent(self, project_id: str, provider: str) -> None:
        consent = self.active_consent(project_id)
        if consent is None or consent.scope not in ("all", provider):
            raise ProviderError("consent", f"Aucun consentement actif pour envoyer des données de ce projet à {provider}. "
                                "Utilisez set_project_ai_consent après accord explicite de l'utilisateur.")

    def month_tokens(self) -> int:
        start = datetime.now(UTC).strftime("%Y-%m-01")
        with self.db.read() as conn:
            value = conn.execute("SELECT coalesce(sum(input_tokens + output_tokens), 0) FROM ai_usage "
                                 "WHERE created_at >= ?", (start,)).fetchone()[0]
        return int(value)

    def month_cost(self) -> float | None:
        if not self.settings.ai_prices_per_million:
            return None
        start = datetime.now(UTC).strftime("%Y-%m-01")
        with self.db.read() as conn:
            value = conn.execute("SELECT sum(cost_estimate) FROM ai_usage WHERE created_at >= ?", (start,)).fetchone()[0]
        return round(value, 4) if value is not None else 0.0

    def _check_budget(self) -> None:
        budget = self.settings.ai_monthly_token_budget
        if budget is not None and self.month_tokens() >= budget:
            raise ProviderError("budget", f"Budget mensuel de {budget} tokens atteint : appel bloqué. "
                                "Augmentez ai_monthly_token_budget dans la configuration si nécessaire.")

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        prices = self.settings.ai_prices_per_million.get(model)
        if not prices:
            return None
        return round(input_tokens / 1e6 * prices.get("input", 0) + output_tokens / 1e6 * prices.get("output", 0), 6)

    def _record(self, project_id: str | None, provider: str, model: str, task: str, status: str,
                result: GenerationResult | None = None, error_kind: str | None = None) -> None:
        tokens_in = result.input_tokens if result else 0
        tokens_out = result.output_tokens if result else 0
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO ai_usage (project_id, provider, model, task, input_tokens, output_tokens, cost_estimate, "
                "status, error_kind, request_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, provider, model, task, tokens_in, tokens_out,
                 self.estimate_cost(model, tokens_in, tokens_out), status, error_kind,
                 result.request_id if result else None, utc_now()),
            )

    # --- appel ---------------------------------------------------------------
    def generate(self, project_id: str | None, request: GenerationRequest, provider: str | None = None,
                 *, require_consent: bool = True) -> GenerationResult:
        provider = provider or self.settings.ai_default_provider
        if provider == "assistant":
            raise ProviderError("config", "Le moteur « assistant » ne génère pas côté serveur : "
                                "l'assistant MCP rédige lui-même à partir du dossier fourni.")
        if provider not in LOCAL_PROVIDERS:
            self._check_connected()
            if require_consent:
                if project_id is None:
                    raise ProviderError("consent", "Projet requis pour un envoi de données.")
                self._check_consent(project_id, provider)
        self._check_budget()
        request = request.model_copy(update={"max_output_tokens": min(request.max_output_tokens,
                                                                      self.settings.ai_max_output_tokens)})
        model = self.model_of(provider)
        try:
            client = self._factory(provider)
            model = client.model
            result = client.generate(request)
        except ProviderError as exc:
            self._record(project_id, provider, model, request.task,
                         "refused" if exc.kind == "refusal" else "error", error_kind=exc.kind)
            logger.warning("Appel IA %s/%s échoué (%s)", provider, request.task, exc.kind)
            raise
        self._record(project_id, provider, result.model, request.task, "ok", result)
        logger.info("Appel IA %s/%s : %d+%d tokens", provider, request.task, result.input_tokens, result.output_tokens)
        return result

    def test_provider(self, provider: str | None = None) -> GenerationResult:
        """Petit appel de vérification (aucune donnée de projet envoyée)."""
        request = GenerationRequest(task="test_connexion", system="Réponds en un seul mot.",
                                    prompt="Réponds simplement : OK", max_output_tokens=1024)
        return self.generate(None, request, provider, require_consent=False)

    # --- état ------------------------------------------------------------------
    def status(self, project_id: str | None = None) -> AIStatus:
        providers = [
            ProviderStatus(provider=name, model=self.model_of(name),
                           key_configured=secrets.key_source(name) is not None, key_source=secrets.key_source(name))
            for name in secrets.PROVIDERS
        ]
        steps: list[str] = []
        if self.settings.mode != "connected":
            steps.append("Mettre mode = 'connected' dans %APPDATA%\\AcademicWriter\\config.toml (par l'utilisateur), "
                         "puis redémarrer l'application.")
        for item in providers:
            if not item.key_configured:
                steps.append(f"Enregistrer la clé {item.provider} : uv run academic-writer secrets set {item.provider}")
        consent = self.active_consent(project_id) if project_id else None
        if project_id and consent is None:
            steps.append("Donner le consentement pour ce projet (phrase exacte : « J'autorise l'envoi externe »).")
        choice = self.resolve_engine(project_id, "auto")
        ollama = next(e for e in choice.engines if e.engine == "ollama")
        if not ollama.available:
            steps.append(f"Modèle local (sans envoi externe) : {ollama.reason}.")
        return AIStatus(
            mode=self.settings.mode, connected=self.settings.mode == "connected",
            default_provider=self.settings.ai_default_provider, providers=providers, project_consent=consent,
            month_tokens_used=self.month_tokens(), month_budget=self.settings.ai_monthly_token_budget,
            month_cost_estimate=self.month_cost(), writing_engine_setting=self.settings.writing_engine,
            auto_choice=choice, how_to_enable=steps,
        )
