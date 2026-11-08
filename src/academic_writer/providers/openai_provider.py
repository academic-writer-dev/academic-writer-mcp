"""Adaptateur OpenAI (SDK officiel ``openai``, API Responses).

- Modèle par défaut : ``gpt-5.5`` (modifiable par ``openai_model``).
- ``store=False`` : OpenAI ne conserve pas la réponse pour une récupération ultérieure.
- Les nouvelles tentatives (429, 5xx, réseau) sont gérées par le SDK (``max_retries``).
"""

from __future__ import annotations

import openai

from academic_writer.providers.base import GenerationRequest, GenerationResult, ProviderError


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self.model = model
        self.client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=2)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=request.system,
                input=request.prompt,
                max_output_tokens=request.max_output_tokens,
                store=False,
            )
        except openai.AuthenticationError as exc:
            raise ProviderError("auth", "Clé API OpenAI refusée (invalide ou révoquée).") from exc
        except openai.PermissionDeniedError as exc:
            raise ProviderError("permission", "La clé API OpenAI n'a pas accès à ce modèle.") from exc
        except openai.NotFoundError as exc:
            raise ProviderError("config", f"Modèle OpenAI introuvable : {self.model}.") from exc
        except openai.RateLimitError as exc:
            raise ProviderError("rate_limit", "Limite de débit ou de crédit OpenAI atteinte.", retryable=True) from exc
        except openai.BadRequestError as exc:
            raise ProviderError("bad_request", f"Requête refusée par OpenAI : {exc.message}") from exc
        except openai.APITimeoutError as exc:
            raise ProviderError("timeout", "Délai dépassé lors de l'appel à OpenAI.", retryable=True) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("network", "Connexion à OpenAI impossible (réseau).", retryable=True) from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderError("server", f"Erreur serveur OpenAI ({exc.status_code}).", retryable=True) from exc
            raise ProviderError("bad_request", f"Erreur OpenAI ({exc.status_code}) : {exc.message}") from exc

        for item in getattr(response, "output", None) or []:
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "refusal":
                    raise ProviderError("refusal", "Le modèle a refusé la demande : "
                                        + (getattr(part, "refusal", "") or "")[:300])
        text = response.output_text or ""
        if not text.strip():
            raise ProviderError("empty", "Réponse vide du modèle (aucun texte produit).")
        incomplete = getattr(response, "incomplete_details", None)
        truncated = getattr(response, "status", None) == "incomplete" and \
            getattr(incomplete, "reason", None) == "max_output_tokens"
        usage = response.usage
        return GenerationResult(
            text=text, provider=self.name, model=self.model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            stop_reason=getattr(response, "status", None), truncated=truncated,
            request_id=getattr(response, "_request_id", None), served_by=getattr(response, "model", None),
        )
