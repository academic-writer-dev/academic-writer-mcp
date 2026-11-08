"""Adaptateur Ollama : modèle exécuté LOCALEMENT (aucun envoi externe, aucune clé, aucun coût).

API REST locale d'Ollama : ``POST /api/chat`` (``stream: false``) et ``GET /api/tags``.
Bibliothèque standard uniquement (urllib) ; le serveur doit être local.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from academic_writer.providers.base import GenerationRequest, GenerationResult, ProviderError


class OllamaProvider:
    name = "ollama"

    def __init__(self, url: str, model: str, num_ctx: int, think: bool | str, timeout: float) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.think = think
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.url + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (URL locale validée)
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code == 404:
                raise ProviderError("config", f"Modèle local « {self.model} » non téléchargé. "
                                    f"Dans PowerShell : ollama pull {self.model}") from exc
            raise ProviderError("server", f"Erreur d'Ollama ({exc.code}) : {body}") from exc
        except TimeoutError as exc:
            raise ProviderError("timeout", f"Le modèle local n'a pas répondu en {int(self.timeout)} s.") from exc
        except urllib.error.URLError as exc:
            raise ProviderError("network", "Ollama ne répond pas : lancez l'application Ollama "
                                "(ou « ollama serve » dans PowerShell).", retryable=True) from exc

    def generate(self, request: GenerationRequest) -> GenerationResult:
        data = self._post("/api/chat", {
            "model": self.model,
            "messages": [{"role": "system", "content": request.system},
                         {"role": "user", "content": request.prompt}],
            "stream": False,
            "think": self.think,
            "options": {"num_predict": request.max_output_tokens, "num_ctx": self.num_ctx},
        })
        text = (data.get("message") or {}).get("content", "") or ""
        if not text.strip():
            raise ProviderError("empty", "Réponse vide du modèle local.")
        done_reason = data.get("done_reason")
        return GenerationResult(
            text=text, provider=self.name, model=self.model,
            input_tokens=int(data.get("prompt_eval_count") or 0), output_tokens=int(data.get("eval_count") or 0),
            stop_reason=done_reason, truncated=done_reason == "length", served_by=data.get("model", self.model),
        )


def installed_models(url: str, timeout: float = 3.0) -> list[str] | None:
    """Modèles téléchargés, ou None si Ollama ne répond pas."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return [m.get("name", "") for m in data.get("models", [])]
