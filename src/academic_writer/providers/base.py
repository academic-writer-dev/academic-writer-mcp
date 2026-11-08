"""Interface commune des fournisseurs d'IA.

Le serveur MCP reste indépendant du modèle : chaque fournisseur est un adaptateur
qui transforme une ``GenerationRequest`` en ``GenerationResult``. Ajouter un
fournisseur = écrire un adaptateur, sans toucher au noyau.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from academic_writer.core.errors import AcademicWriterError

ProviderName = Literal["anthropic", "openai", "mock"]
ErrorKind = Literal["config", "auth", "permission", "rate_limit", "network", "timeout", "server",
                    "bad_request", "refusal", "budget", "consent", "empty"]


class GenerationRequest(BaseModel):
    task: str = Field(description="Nature de la tâche (journalisation sans contenu).")
    system: str
    prompt: str
    max_output_tokens: int = 8000


class GenerationResult(BaseModel):
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    truncated: bool = Field(default=False, description="Réponse coupée par la limite de tokens.")
    request_id: str | None = None
    served_by: str | None = Field(default=None, description="Modèle ayant réellement répondu (repli éventuel).")


class ProviderError(AcademicWriterError):
    """Erreur d'un fournisseur, avec une catégorie exploitable et un message en français."""

    def __init__(self, kind: ErrorKind, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


class AIProvider(Protocol):
    name: str
    model: str

    def generate(self, request: GenerationRequest) -> GenerationResult: ...
