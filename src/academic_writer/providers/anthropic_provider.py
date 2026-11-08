"""Adaptateur Anthropic (SDK officiel ``anthropic``).

- Modèle par défaut : ``claude-opus-5-5`` ; effort réglé explicitement (``output_config``).
- Repli serveur en cas de refus : ``fallbacks="default"`` (bêta ``server-side-fallback-2026-07-01``),
  désactivable par ``anthropic_refusal_fallback = false``.
- Les nouvelles tentatives (429, 5xx, réseau) sont gérées par le SDK (``max_retries``).
"""

from __future__ import annotations

import anthropic

from academic_writer.providers.base import GenerationRequest, GenerationResult, ProviderError

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, effort: str, refusal_fallback: bool, timeout: float) -> None:
        self.model = model
        self.effort = effort
        self.refusal_fallback = refusal_fallback
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        kwargs = dict(
            model=self.model,
            max_tokens=request.max_output_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.prompt}],
            output_config={"effort": self.effort},
        )
        try:
            if self.refusal_fallback:
                response = self.client.beta.messages.create(betas=[_FALLBACK_BETA], fallbacks="default", **kwargs)
            else:
                response = self.client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise ProviderError("auth", "Clé API Anthropic refusée (invalide ou révoquée).") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ProviderError("permission", "La clé API Anthropic n'a pas accès à ce modèle ou à cette fonction.") from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError("config", f"Modèle Anthropic introuvable : {self.model}.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("rate_limit", "Limite de débit Anthropic atteinte : réessayez plus tard.", retryable=True) from exc
        except anthropic.BadRequestError as exc:
            raise ProviderError("bad_request", f"Requête refusée par Anthropic : {exc.message}") from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderError("timeout", "Délai dépassé lors de l'appel à Anthropic.", retryable=True) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("network", "Connexion à Anthropic impossible (réseau).", retryable=True) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderError("server", f"Erreur serveur Anthropic ({exc.status_code}).", retryable=True) from exc
            raise ProviderError("bad_request", f"Erreur Anthropic ({exc.status_code}) : {exc.message}") from exc

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise ProviderError("refusal", "Le modèle a refusé la demande"
                                + (f" (catégorie : {category})." if category else "."))
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        if not text.strip():
            raise ProviderError("empty", "Réponse vide du modèle (aucun texte produit).")
        usage = response.usage
        input_tokens = (usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        return GenerationResult(
            text=text, provider=self.name, model=self.model,
            input_tokens=input_tokens, output_tokens=usage.output_tokens or 0,
            stop_reason=response.stop_reason, truncated=response.stop_reason == "max_tokens",
            request_id=getattr(response, "_request_id", None), served_by=getattr(response, "model", None),
        )
