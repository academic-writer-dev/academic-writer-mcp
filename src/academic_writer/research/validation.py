"""Vérification LOCALE des métadonnées : champs obligatoires, identifiants, cohérence.

Une source « bien formée » est complète et ses identifiants sont valides ; cela ne prouve PAS
qu'elle existe : seule une vérification en ligne (ou par l'utilisateur) le confirme.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from academic_writer.research.models import Finding, SourceData

REQUIRED: dict[str, list[str]] = {
    "book": ["authors|editors", "title", "publisher", "year"],
    "article": ["authors", "title", "container", "year", "pages"],
    "chapter": ["authors", "title", "container", "publisher", "year", "pages"],
    "conference": ["authors", "title", "container", "year"],
    "thesis": ["authors", "title", "publisher", "year"],
    "standard": ["standard_number", "title", "year"],
    "web": ["title", "url", "accessed"],
    "report": ["title", "publisher", "year"],
    "patent": ["authors", "title", "year"],
    "other": ["title"],
}
RECOMMENDED: dict[str, list[str]] = {
    "book": ["place", "isbn", "pages"],
    "article": ["volume|issue", "doi"],
    "chapter": ["editors", "place"],
    "conference": ["publisher", "pages"],
    "thesis": ["place"],
    "standard": ["publisher", "place"],
    "report": ["authors", "place"],
}
DOI = re.compile(r"^10\.\d{4,9}/\S+$")
FIELD_NAMES = {
    "authors": "auteurs", "editors": "éditeurs scientifiques", "title": "titre", "container": "revue / ouvrage",
    "publisher": "éditeur / établissement", "place": "ville", "year": "année", "pages": "pages", "doi": "DOI",
    "isbn": "ISBN", "volume": "volume", "issue": "numéro", "url": "URL", "accessed": "date de consultation",
    "standard_number": "numéro de norme",
}


def normalize_doi(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    return re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)


def isbn_valid(value: str) -> bool:
    digits = re.sub(r"[\s-]", "", value).upper()
    if len(digits) == 10 and re.fullmatch(r"\d{9}[\dX]", digits):
        total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(digits))
        return total % 11 == 0
    if len(digits) == 13 and digits.isdigit():
        total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(digits))
        return total % 10 == 0
    return False


def issn_valid(value: str) -> bool:
    digits = re.sub(r"[\s-]", "", value).upper()
    if not re.fullmatch(r"\d{7}[\dX]", digits):
        return False
    total = sum((8 - i) * int(ch) for i, ch in enumerate(digits[:7]))
    check = (11 - total % 11) % 11
    return digits[7] == ("X" if check == 10 else str(check))


def _filled(data: SourceData, field: str) -> bool:
    value = getattr(data, field)
    return bool(value) if not isinstance(value, str) else bool(value.strip())


def check_source(source_type: str, data: SourceData) -> tuple[str, list[Finding]]:
    """Renvoie (statut local, constats) : incomplete, suspicious ou well_formed."""
    findings: list[Finding] = []
    missing = []
    for spec in REQUIRED.get(source_type, ["title"]):
        options = spec.split("|")
        if not any(_filled(data, option) for option in options):
            missing.append(" ou ".join(FIELD_NAMES.get(o, o) for o in options))
    for name in missing:
        findings.append(Finding(severity="error", field=name, message=f"Champ obligatoire manquant : {name}."))
    for spec in RECOMMENDED.get(source_type, []):
        options = spec.split("|")
        if not any(_filled(data, option) for option in options):
            findings.append(Finding(severity="info", field=options[0],
                                    message=f"Champ recommandé absent : {' ou '.join(FIELD_NAMES.get(o, o) for o in options)}."))

    suspicious = False
    current_year = datetime.now(UTC).year
    if data.year is not None and not (1450 <= data.year <= current_year + 1):
        suspicious = True
        findings.append(Finding(severity="error", field="year", message=f"Année impossible : {data.year}."))
    if data.doi:
        if not DOI.match(normalize_doi(data.doi)):
            suspicious = True
            findings.append(Finding(severity="error", field="doi", message=f"DOI mal formé : {data.doi}."))
    if data.isbn and not isbn_valid(data.isbn):
        suspicious = True
        findings.append(Finding(severity="error", field="isbn",
                                message=f"ISBN invalide (somme de contrôle incorrecte) : {data.isbn}."))
    if data.issn and not issn_valid(data.issn):
        suspicious = True
        findings.append(Finding(severity="error", field="issn", message=f"ISSN invalide : {data.issn}."))
    if data.url and not re.match(r"^https?://[^\s/]+\.[^\s]+", data.url):
        findings.append(Finding(severity="warning", field="url", message=f"URL mal formée : {data.url}."))
    if data.accessed and not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}", data.accessed):
        findings.append(Finding(severity="warning", field="accessed",
                                message="Date de consultation attendue au format JJ.MM.AAAA."))
    if data.pages and not re.fullmatch(r"\d+(?:\s*[–—-]\s*\d+)?|[IVXLCDM]+(?:\s*[–—-]\s*[IVXLCDM]+)?",
                                       data.pages.strip(), re.IGNORECASE):
        findings.append(Finding(severity="warning", field="pages", message=f"Pages : format inhabituel « {data.pages} »."))
    if any(re.fullmatch(r"(?:et al\.?|и др\.?|\.\.\.)", (p.family or "").strip(), re.IGNORECASE) for p in data.authors):
        findings.append(Finding(severity="warning", field="authors",
                                message="Auteur « et al. / и др. » : indiquez les noms réels des auteurs."))
    identifiable = any(_filled(data, f) for f in ("doi", "isbn", "url", "standard_number", "issn")) or \
        (_filled(data, "publisher") and _filled(data, "year"))
    if not identifiable:
        findings.append(Finding(severity="warning", field=None,
                                message="Aucun identifiant ni éditeur : source impossible à vérifier telle quelle."))

    if suspicious:
        return "suspicious", findings
    if missing:
        return "incomplete", findings
    return "well_formed", findings


def make_key(data: SourceData, existing: set[str]) -> str:
    """Clé de citation lisible et unique : nomAnnée (translittération simple du cyrillique)."""
    base = data.authors[0].family if data.authors else (data.standard_number or data.title or "source")
    base = transliterate(base).lower()
    base = re.sub(r"[^a-z0-9]+", "", base)[:20] or "source"
    key = f"{base}{data.year or ''}"
    candidate, suffix = key, ord("a")
    while candidate in existing:
        candidate = f"{key}{chr(suffix)}"
        suffix += 1
    return candidate


_TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                     ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
                      "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))


def transliterate(text: str) -> str:
    return "".join(_TRANSLIT.get(ch, _TRANSLIT.get(ch.lower(), ch)) for ch in text.lower())
