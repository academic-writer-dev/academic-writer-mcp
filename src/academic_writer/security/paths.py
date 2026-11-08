"""Contrôle des chemins d'accès.

Les chemins fournis par l'assistant IA sont considérés comme non fiables :
ils peuvent provenir d'une injection de prompt contenue dans un document.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from academic_writer.core.errors import NotFoundError, SecurityViolation, ValidationFailed


def resolve_user_file(raw: str) -> Path:
    """Valide un chemin de fichier fourni par l'utilisateur et le résout (liens, '..')."""
    if raw is None or not str(raw).strip():
        raise ValidationFailed("Chemin de fichier vide.")
    text = str(raw).strip().strip('"').strip("'")
    if "\x00" in text:
        raise SecurityViolation("Chemin refusé : caractère nul.")
    if text.startswith(("\\\\?\\", "\\\\.\\", "//?/", "//./")):
        raise SecurityViolation("Chemin refusé : chemins de périphérique Windows non autorisés.")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise ValidationFailed(f"Le chemin doit être absolu (ex. D:\\Dossier\\fichier.docx) : {text}")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise NotFoundError(f"Fichier introuvable : {text}") from exc
    except OSError as exc:
        raise ValidationFailed(f"Chemin inaccessible : {text} ({exc.strerror})") from exc
    if not resolved.is_file():
        raise ValidationFailed(f"Ce chemin n'est pas un fichier : {text}")
    return resolved


def is_within(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def ensure_within(path: Path, roots: Iterable[Path]) -> None:
    """Refuse un chemin situé hors des dossiers autorisés."""
    roots = list(roots)
    if not any(is_within(path, root) for root in roots):
        allowed = ", ".join(str(r) for r in roots) or "(aucun)"
        raise SecurityViolation(
            f"Accès refusé : le fichier est hors des dossiers autorisés ({allowed}). "
            "Modifiez 'allowed_import_dirs' dans la configuration si nécessaire."
        )


def ensure_outside(path: Path, forbidden: Path, reason: str) -> None:
    if is_within(path, forbidden):
        raise SecurityViolation(reason)


def safe_child(base: Path, *parts: str) -> Path:
    """Construit un chemin sous ``base`` en garantissant qu'il n'en sort pas."""
    candidate = base.joinpath(*parts)
    if not is_within(candidate, base):
        raise SecurityViolation("Chemin interne refusé (sortie du dossier de base).")
    return candidate
