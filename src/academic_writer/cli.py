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


def read_clipboard() -> str:
    """Texte du presse-papiers Windows (via PowerShell Get-Clipboard), sans l'afficher."""
    import subprocess

    try:
        completed = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],  # noqa: S603,S607
                                   capture_output=True, timeout=15, check=False, creationflags=0x08000000)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for encoding in ("utf-8", "cp866", "cp1252"):
        try:
            return completed.stdout.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return ""


def clear_clipboard() -> None:
    import subprocess

    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"],  # noqa: S603,S607
                   capture_output=True, timeout=15, check=False, creationflags=0x08000000)


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
        if getattr(args, "clipboard", False):
            # On lit le presse-papiers APRÈS l'appui sur Entrée : l'utilisateur a souvent copié la commande
            # elle-même juste avant de la lancer.
            print("1. Allez dans Google Cloud / le site du service et cliquez sur « Copier » à côté de la clé.")
            print("2. Revenez ici SANS rien coller, puis appuyez simplement sur Entrée.")
            try:
                input("   Appuyez sur Entrée quand la clé est copiée... ")
            except EOFError:
                pass
            key = read_clipboard()
            if not key:
                print("Presse-papiers vide ou illisible : copiez d'abord la clé (bouton « Copier »).", file=sys.stderr)
                return 1
            if " " in key or "academic-writer" in key or len(key) > 200:
                print("Le presse-papiers contient autre chose qu'une clé (sans doute la commande). "
                      "Relancez la commande, copiez la clé seulement à l'étape 1, puis Entrée.", file=sys.stderr)
                return 1
        else:
            key = getpass.getpass(f"Collez la clé API {args.provider} (saisie masquée), puis Entrée : ")
        try:
            secrets.set_key(args.provider, key)
        except ValueError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 1
        print(f"Clé {args.provider} enregistrée dans le Gestionnaire d'identification de Windows ({secrets.mask(key.strip())}).")
        if getattr(args, "clipboard", False):
            clear_clipboard()
            print("Presse-papiers vidé par précaution.")
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
    sec.add_argument("--clipboard", action="store_true",
                     help="Lire la clé dans le presse-papiers (si le collage ne marche pas dans la saisie masquée)")
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
