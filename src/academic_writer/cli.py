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


_ICONS = {"ok": "[OK]", "attention": "[!!]", "absent": "[--]", "erreur": "[XX]"}


def _maintenance(args: argparse.Namespace) -> int:
    from pathlib import Path

    from academic_writer.core import maintenance
    from academic_writer.core.errors import AcademicWriterError

    if args.command == "setup-desktop":
        result = maintenance.setup_desktop(apply=args.apply)
        print(f"Claude Desktop : {result.status} — {result.detail}")
        if result.config_path:
            print(f"Fichier : {result.config_path}")
        if result.backup_path:
            print(f"Copie de sauvegarde : {result.backup_path}")
        print("\nClaude Code (VS Code), commande équivalente :")
        print("  " + maintenance.claude_code_command())
        return 0 if result.status != "introuvable" else 1
    from academic_writer.server.services import build_services

    services = build_services()
    try:
        if args.command == "doctor":
            diagnosis = maintenance.diagnose(services)
            print(f"Academic Writer {diagnosis.version} — {diagnosis.summary}\n")
            for check in diagnosis.checks:
                print(f"{_ICONS[check.status]} {check.component:34} {check.detail}")
                if check.fix and check.status != "ok":
                    print(f"{'':39}→ {check.fix}")
            return 0 if diagnosis.ready else 1
        if args.command == "backup":
            info = maintenance.create_backup(services.settings, services.db, complete=not args.db_only)
            print(f"Sauvegarde {info.kind} créée : {info.path} ({info.size_mb} Mo)")
            return 0
        if args.command == "backups":
            listing = maintenance.list_backups(services.settings)
            print(f"Dossier : {listing.folder}")
            for item in listing.backups:
                print(f"  {item.created_at}  {item.kind:9} {item.size_mb:>8} Mo  {Path(item.path).name}")
            return 0
        if args.command == "restore":
            if not args.yes:
                print("La restauration REMPLACE la base et les dossiers des projets actuels (une sauvegarde de "
                      "sécurité est faite avant).\nFermez Claude Desktop et VS Code, puis relancez avec --yes.")
                return 2
            result = maintenance.restore_backup(services.settings, services.db, Path(args.archive))
            print(f"Restauré depuis {result.restored_from} : {result.projects_restored} projet(s), "
                  f"schéma v{result.schema_version}.")
            for message in result.messages:
                print("  " + message)
            return 0
    except AcademicWriterError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from academic_writer.server.app import run
        run()
        return 0
    for stream in (sys.stdout, sys.stderr):  # console redirigée en cp1251 : pas de plantage sur « — », « → »…
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser =argparse.ArgumentParser(prog="academic-writer", description="Academic Writer MCP")
    sub = parser.add_subparsers(dest="command", required=True)
    sec = sub.add_parser("secrets", help="Gérer les clés API (IA : anthropic, openai ; sources : google_books, openalex)")
    sec.add_argument("action", choices=["set", "status", "delete"])
    sec.add_argument("provider", nargs="?", choices=list(secrets.ALL_SERVICES))
    sec.add_argument("--clipboard", action="store_true",
                     help="Lire la clé dans le presse-papiers (si le collage ne marche pas dans la saisie masquée)")
    ev = sub.add_parser("evaluate-indicators", help="Mesurer les indices IA sur un corpus annoté (humain/ et ia/)")
    ev.add_argument("folder")
    ev.add_argument("--language", choices=["fr", "ru", "en"], default="ru")
    sub.add_parser("doctor", help="Diagnostic complet de l'installation")
    bk = sub.add_parser("backup", help="Créer une sauvegarde (complète par défaut)")
    bk.add_argument("--db-only", action="store_true", help="Base de données seule")
    sub.add_parser("backups", help="Lister les sauvegardes")
    rs = sub.add_parser("restore", help="Restaurer une sauvegarde complète (.zip) — fermer Claude avant")
    rs.add_argument("archive")
    rs.add_argument("--yes", action="store_true", help="Confirmer le remplacement des données actuelles")
    sd = sub.add_parser("setup-desktop", help="Déclarer le serveur dans Claude Desktop")
    sd.add_argument("--apply", action="store_true", help="Écrire la configuration (sinon : simple vérification)")
    args = parser.parse_args(argv)
    if args.command == "secrets":
        return _secrets(args)
    if args.command in ("doctor", "backup", "backups", "restore", "setup-desktop"):
        return _maintenance(args)
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
