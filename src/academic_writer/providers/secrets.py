"""Stockage des clés API dans le Gestionnaire d'identification de Windows (via ``keyring``).

Les clés ne sont jamais écrites en clair dans un fichier, jamais journalisées, jamais
renvoyées par un outil MCP. Repli : variables d'environnement ``ANTHROPIC_API_KEY`` /
``OPENAI_API_KEY`` (pour les environnements sans coffre de secrets).
"""

from __future__ import annotations

import os

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "academic-writer"
ENV_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
PROVIDERS = tuple(ENV_VARS)


def _check(provider: str) -> None:
    if provider not in ENV_VARS:
        raise ValueError(f"Fournisseur inconnu : {provider} (attendu : {', '.join(PROVIDERS)})")


def set_key(provider: str, key: str) -> None:
    _check(provider)
    key = key.strip()
    if len(key) < 20 or any(ch.isspace() for ch in key):
        raise ValueError("Clé API manifestement invalide (trop courte ou contenant des espaces).")
    keyring.set_password(SERVICE, provider, key)


def get_key(provider: str) -> str | None:
    _check(provider)
    try:
        stored = keyring.get_password(SERVICE, provider)
    except KeyringError:
        stored = None
    return stored or os.environ.get(ENV_VARS[provider]) or None


def key_source(provider: str) -> str | None:
    """Origine de la clé : 'coffre Windows', 'variable d'environnement' ou None (sans révéler la clé)."""
    _check(provider)
    try:
        if keyring.get_password(SERVICE, provider):
            return "coffre Windows"
    except KeyringError:
        pass
    return "variable d'environnement" if os.environ.get(ENV_VARS[provider]) else None


def delete_key(provider: str) -> bool:
    _check(provider)
    try:
        keyring.delete_password(SERVICE, provider)
        return True
    except PasswordDeleteError:
        return False


def mask(key: str) -> str:
    return key[:7] + "…" + key[-4:] if len(key) > 12 else "…"
