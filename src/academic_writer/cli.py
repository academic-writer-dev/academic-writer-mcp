"""Ligne de commande d'Academic Writer.

    academic-writer                         lance le serveur MCP (stdio) — usage par les clients
    academic-writer secrets set anthropic   enregistre une clé API (saisie masquée)
    academic-writer secrets status          indique quelles clés sont configurées (sans les afficher)
    academic-writer secrets delete openai   supprime une clé
"""

from __future__ import annotations

import argparse
import getpass
import sys

from academic_writer.providers import secrets


def _secrets(args: argparse.Namespace) -> int:
    if args.action == "status":
        for provider in secrets.ALL_SERVICES:
            source = secrets.key_source(provider)
            print(f"{provider:10} : {'configurée (' + source + ')' if source else 'non configurée'}")
        return 0
    if args.provider is None:
        print("Précisez le service : anthropic, openai, google_books ou openalex", file=sys.stderr)
        return 2
    if args.action == "set":
        key = getpass.getpass(f"Collez la clé API {args.provider} (saisie masquée), puis Entrée : ")
        try:
            secrets.set_key(args.provider, key)
        except ValueError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 1
        print(f"Clé {args.provider} enregistrée dans le Gestionnaire d'identification de Windows ({secrets.mask(key.strip())}).")
        return 0
    if args.action == "delete":
        print("Clé supprimée." if secrets.delete_key(args.provider) else "Aucune clé enregistrée pour ce fournisseur.")
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from academic_writer.server.app import run
        run()
        return 0
    parser = argparse.ArgumentParser(prog="academic-writer", description="Academic Writer MCP")
    sub = parser.add_subparsers(dest="command", required=True)
    sec = sub.add_parser("secrets", help="Gérer les clés API (IA : anthropic, openai ; sources : google_books, openalex)")
    sec.add_argument("action", choices=["set", "status", "delete"])
    sec.add_argument("provider", nargs="?", choices=list(secrets.ALL_SERVICES))
    ev = sub.add_parser("evaluate-indicators", help="Mesurer les indices IA sur un corpus annoté (humain/ et ia/)")
    ev.add_argument("folder")
    ev.add_argument("--language", choices=["fr", "ru", "en"], default="ru")
    args = parser.parse_args(argv)
    if args.command == "secrets":
        return _secrets(args)
    if args.command == "evaluate-indicators":
        from pathlib import Path

        from academic_writer.ai_detection.evaluation import evaluate

        result = evaluate(Path(args.folder), args.language)
        print(f"Corpus : {result.human_texts} textes humains, {result.ai_texts} textes IA "
              f"({result.skipped_short} trop courts ignorés), langue {result.language}")
        print(f"{'Indice':28} {'humains':>8} {'IA':>8}")
        for item in result.rates:
            print(f"{item.indicator:28} {item.human_rate:>8.1%} {item.ai_rate:>8.1%}")
        print(f"{'au moins un indice':28} {result.any_indicator_human_rate:>8.1%} {result.any_indicator_ai_rate:>8.1%}")
        print(result.warning)
        return 0
    return 2
