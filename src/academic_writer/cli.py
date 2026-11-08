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
        for provider in secrets.PROVIDERS:
            source = secrets.key_source(provider)
            print(f"{provider:10} : {'configurée (' + source + ')' if source else 'non configurée'}")
        return 0
    if args.provider is None:
        print("Précisez le fournisseur : anthropic ou openai", file=sys.stderr)
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
    sec = sub.add_parser("secrets", help="Gérer les clés API des fournisseurs d'IA")
    sec.add_argument("action", choices=["set", "status", "delete"])
    sec.add_argument("provider", nargs="?", choices=list(secrets.PROVIDERS))
    args = parser.parse_args(argv)
    if args.command == "secrets":
        return _secrets(args)
    return 2
