"""Fournisseur simulé : tests et démonstration sans clé API ni envoi externe."""

from __future__ import annotations

from collections import deque

from academic_writer.providers.base import GenerationRequest, GenerationResult, ProviderError


class MockProvider:
    name = "mock"

    def __init__(self, responses: list[str] | None = None, model: str = "mock-1") -> None:
        self.model = model
        self.responses: deque[str] = deque(responses or [])
        self.requests: list[GenerationRequest] = []
        self.fail_with: ProviderError | None = None

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        text = self.responses.popleft() if self.responses else f"[réponse simulée pour : {request.task}]"
        return GenerationResult(
            text=text, provider=self.name, model=self.model,
            input_tokens=max(1, (len(request.system) + len(request.prompt)) // 4),
            output_tokens=max(1, len(text) // 4), stop_reason="end_turn", served_by=self.model,
        )
