"""Provenance : Content Credentials (C2PA), IPTC Digital Source Type, métadonnées PDF/XMP.

Détection par recherche de signatures dans les octets (fichier et médias incorporés). La signature
cryptographique d'un manifeste C2PA n'est PAS vérifiée localement (bibliothèque dédiée non installée) :
la présence d'un manifeste est signalée comme telle, sans en garantir l'authenticité.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from academic_writer.forensics.models import AI_TOOL, CORRECTION_TOOL, TRANSLATION_TOOL, ForensicFinding

AI_SOURCE_TYPES = {
    b"trainedAlgorithmicMedia": "média généré par IA (IPTC trainedAlgorithmicMedia)",
    b"compositeWithTrainedAlgorithmicMedia": "média composite incluant une génération par IA (IPTC)",
    b"algorithmicallyEnhanced": "média amélioré algorithmiquement (IPTC)",
}
_MAX_SCAN = 200 * 1024 * 1024


def _blobs(path: Path) -> list[tuple[str, bytes]]:
    """Le fichier et, pour une archive Office, ses médias incorporés."""
    blobs = [(path.name, path.read_bytes()[:_MAX_SCAN])]
    if path.suffix.lower() in (".docx", ".pptx", ".xlsx"):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if "/media/" in info.filename and info.file_size <= 50 * 1024 * 1024:
                    blobs.append((info.filename, archive.read(info.filename)))
    return blobs


def xmp_packets(data: bytes) -> list[str]:
    return [m.group(0).decode("utf-8", "replace")[:20000]
            for m in re.finditer(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.DOTALL)][:5]


def scan_provenance(path: Path, metadata_text: str = "") -> tuple[bool, list[str], list[str], list[ForensicFinding]]:
    """Renvoie (manifeste C2PA présent, médias déclarés IA, outils nommés, constats)."""
    findings: list[ForensicFinding] = []
    manifests: list[str] = []
    declared: list[str] = []
    tools: set[str] = set()
    xmp_text = ""
    for name, data in _blobs(path):
        if b"c2pa" in data and (b"jumb" in data or b"jumd" in data or b"c2pa.claim" in data):
            manifests.append(name)
        for marker, label in AI_SOURCE_TYPES.items():
            if marker in data:
                declared.append(f"{name} : {label}")
        for packet in xmp_packets(data):
            xmp_text += " " + packet
    scan = metadata_text + " " + xmp_text
    for pattern in (AI_TOOL, CORRECTION_TOOL, TRANSLATION_TOOL):
        tools |= {m.group(0) for m in re.finditer(pattern, scan, re.IGNORECASE)}
    if manifests:
        findings.append(ForensicFinding(
            category="provenance", severity="fort" if declared else "moyen",
            observation="Manifeste Content Credentials (C2PA) détecté ; signature NON vérifiée localement.",
            evidence=manifests[:10],
            explanations=["contenu produit ou modifié par un logiciel compatible C2PA (appareil photo, Adobe, "
                          "générateur d'images…)", "le manifeste peut concerner seulement une image incorporée"]))
    if declared:
        findings.append(ForensicFinding(
            category="provenance", severity="fort",
            observation="Des éléments sont DÉCLARÉS générés ou modifiés par IA dans leurs métadonnées.",
            evidence=declared[:10],
            explanations=["image d'illustration générée par IA (déclaration du générateur)",
                          "la déclaration porte sur le média, pas sur le texte du document"]))
    if tools:
        findings.append(ForensicFinding(
            category="provenance", severity="moyen", observation="Outils nommés dans les métadonnées XMP / propriétés.",
            evidence=sorted(tools), explanations=["usage déclaré d'un outil (rédaction, correction ou traduction)"]))
    return bool(manifests), declared, sorted(tools), findings
