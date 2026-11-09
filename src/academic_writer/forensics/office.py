"""Métadonnées et historique des fichiers Office (DOCX, PPTX, XLSX).

Lecture directe de l'archive (aucune macro exécutée, XML analysé sans entités externes) :
propriétés, durée d'édition, sessions d'édition (rsid), modifications suivies, commentaires,
texte masqué (attribut « caché », texte blanc, taille ≤ 2 pt).
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path

from lxml import etree

from academic_writer.forensics.models import (
    AI_TOOL,
    CORRECTION_TOOL,
    TRANSLATION_TOOL,
    Comment,
    ForensicFinding,
    TrackedChanges,
)

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MAX_XML = 50 * 1024 * 1024


def _xml(archive: zipfile.ZipFile, name: str):
    if name not in archive.namelist():
        return None
    if archive.getinfo(name).file_size > _MAX_XML:
        return None
    return etree.fromstring(archive.read(name), _PARSER)


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        for part, prefix in (("docProps/core.xml", ""), ("docProps/app.xml", "app_"), ("docProps/custom.xml", "custom_")):
            root = _xml(archive, part)
            if root is None:
                continue
            for element in root.iter():
                tag = etree.QName(element).localname
                if part.endswith("custom.xml") and tag == "property":
                    value = " ".join(element.itertext()).strip()
                    if value:
                        props[f"custom_{element.get('name', '?')}"] = value[:300]
                elif len(element) == 0 and element.text and element.text.strip():
                    props[f"{prefix}{tag}"] = element.text.strip()[:300]
    return props


def analyze_office(path: Path, words: int) -> tuple[dict[str, str], int | None, TrackedChanges | None,
                                                    list[Comment], list[str], list[ForensicFinding]]:
    """Renvoie (propriétés, sessions, modifications suivies, commentaires, texte masqué, constats)."""
    props = read_properties(path)
    findings: list[ForensicFinding] = []
    sessions: int | None = None
    tracked: TrackedChanges | None = None
    comments: list[Comment] = []
    hidden: list[str] = []
    with zipfile.ZipFile(path) as archive:
        settings = _xml(archive, "word/settings.xml")
        if settings is not None:
            sessions = len({e.get(f"{W}val") for e in settings.iter(f"{W}rsid")}) or None
        document = _xml(archive, "word/document.xml")
        if document is not None:
            tracked = TrackedChanges()
            dates: list[str] = []
            for tag, field in ((f"{W}ins", "insertions"), (f"{W}del", "deletions")):
                for element in document.iter(tag):
                    setattr(tracked, field, getattr(tracked, field) + 1)
                    author = element.get(f"{W}author") or "?"
                    tracked.authors[author] = tracked.authors.get(author, 0) + 1
                    if element.get(f"{W}date"):
                        dates.append(element.get(f"{W}date"))
            if dates:
                tracked.first_date, tracked.last_date = min(dates), max(dates)
            for run in document.iter(f"{W}r"):
                rpr = run.find(f"{W}rPr")
                if rpr is None:
                    continue
                color = rpr.find(f"{W}color")
                size = rpr.find(f"{W}sz")
                is_hidden = rpr.find(f"{W}vanish") is not None
                is_white = color is not None and (color.get(f"{W}val") or "").upper() in ("FFFFFF", "FFFFFE")
                is_tiny = size is not None and (size.get(f"{W}val") or "99").isdigit() and int(size.get(f"{W}val")) <= 4
                if is_hidden or is_white or is_tiny:
                    text = "".join(t.text or "" for t in run.iter(f"{W}t")).strip()
                    if text:
                        kind = "caché" if is_hidden else "blanc" if is_white else "≤ 2 pt"
                        hidden.append(f"[{kind}] {text[:200]}")
        comments_root = _xml(archive, "word/comments.xml")
        if comments_root is not None:
            for comment in comments_root.iter(f"{W}comment"):
                text = " ".join("".join(t.text or "" for t in comment.iter(f"{W}t")).split())
                comments.append(Comment(author=comment.get(f"{W}author"), date=comment.get(f"{W}date"), text=text[:300]))

    created, modified = _date(props.get("created")), _date(props.get("modified"))
    if created and modified and modified < created:
        findings.append(ForensicFinding(
            category="metadata", severity="moyen", observation="Date de modification antérieure à la date de création.",
            evidence=[f"créé : {props.get('created')}", f"modifié : {props.get('modified')}"],
            explanations=["horloge de l'ordinateur déréglée", "propriétés modifiées par un outil", "copie de fichier"]))
    total_minutes = int(props["app_TotalTime"]) if props.get("app_TotalTime", "").isdigit() else None
    if total_minutes is not None and words >= 1000 and words / max(total_minutes, 1) > 150:
        findings.append(ForensicFinding(
            category="history", severity="moyen",
            observation=f"Durée d'édition enregistrée très courte ({total_minutes} min) pour {words} mots.",
            evidence=[f"TotalTime = {total_minutes} min", f"{words} mots"],
            explanations=["texte rédigé ailleurs puis collé (autre logiciel, autre fichier)", "fichier créé par "
                          "« Enregistrer sous » ou par conversion", "texte généré puis collé"]))
    revision = int(props["revision"]) if props.get("revision", "").isdigit() else None
    if revision is not None and revision <= 2 and words >= 2000:
        findings.append(ForensicFinding(
            category="history", severity="faible",
            observation=f"Numéro de révision très bas ({revision}) pour un document de {words} mots.",
            evidence=[f"revision = {revision}"],
            explanations=["document copié dans un nouveau fichier", "conversion depuis un autre format", "texte collé"]))
    if sessions is not None and sessions <= 2 and words >= 2000:
        findings.append(ForensicFinding(
            category="history", severity="faible",
            observation=f"Seulement {sessions} session(s) d'édition enregistrée(s) pour {words} mots.",
            evidence=[f"rsid : {sessions}"],
            explanations=["contenu collé en une fois depuis une autre source", "document reconstruit ou converti"]))
    if props.get("creator") and props.get("lastModifiedBy") and props["creator"] != props["lastModifiedBy"]:
        findings.append(ForensicFinding(
            category="metadata", severity="info", observation="Auteur et dernier modificateur différents.",
            evidence=[f"auteur : {props['creator']}", f"modifié par : {props['lastModifiedBy']}"],
            explanations=["modèle fourni par l'enseignant", "travail à plusieurs", "ordinateur partagé"]))
    if hidden:
        findings.append(ForensicFinding(
            category="hidden_text", severity="fort",
            observation=f"{len(hidden)} passage(s) de texte masqué (caché, blanc ou minuscule).", evidence=hidden[:10],
            explanations=["notes oubliées", "texte de modèle", "tentative de manipulation d'un correcteur ou d'une IA "
                          "(instructions cachées)"]))
    scan = " ".join([*props.values(), *(tracked.authors if tracked else {}), *(c.author or "" for c in comments)])
    for pattern, label, severity in ((AI_TOOL, "assistant d'IA", "fort"), (CORRECTION_TOOL, "outil de correction", "moyen"),
                                     (TRANSLATION_TOOL, "outil de traduction", "moyen")):
        names = sorted({m.group(0) for m in re.finditer(pattern, scan, re.IGNORECASE)})
        if names:
            findings.append(ForensicFinding(
                category="provenance", severity=severity,
                observation=f"Un {label} est nommé dans les métadonnées, commentaires ou modifications suivies.",
                evidence=names, explanations=["usage déclaré de l'outil (pas nécessairement pour rédiger)",
                                              "nom d'utilisateur ou d'appareil"]))
    return props, sessions, tracked, comments, hidden, findings
