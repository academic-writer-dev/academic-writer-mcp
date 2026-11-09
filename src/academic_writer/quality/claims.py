"""Repérage des affirmations factuelles et de leur TRAÇABILITÉ (jamais de verdict vrai / faux).

Types d'affirmations : chiffre ou statistique, date, attribution (« selon X »), formulation absolue,
référence normative. Pour chacune : citation présente ? source enregistrée et vérifiée ? chiffres retrouvés
dans les documents du projet ? Les normes sont comparées aux éditions connues du profil disciplinaire.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.quality.models import QualityIssue, Segment, Severity, excerpt
from academic_writer.writing.checks import numbers_in

ClaimType = Literal["chiffre", "date", "attribution", "absolu", "norme"]
Support = Literal["source_verifiee", "source_non_verifiee", "cle_inconnue", "citation_numerique",
                  "documents_du_projet", "norme", "non_etaye"]
NOTICE = ("Repérage de la traçabilité : aucune affirmation n'est déclarée vraie ou fausse. Chaque affirmation non "
          "étayée doit être vérifiée par une personne dans une source fiable, puis citée.")

_SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЁ«\"(\[])")
_KEY_MARKER = re.compile(r"\[@([^\[\],;\s]+)")
_NUMERIC_CITATION = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*(?:,\s*[сcp]\.\s*\d+)?\]")
_AUTHOR_YEAR = re.compile(r"\([A-ZА-ЯЁ][\w\-]+(?: et al\.| и др\.| and [A-Z]\w+| et [A-Z]\w+)?,? \d{4}[a-z]?(?:, [сp]\. ?\d+)?\)")
_PERCENT = re.compile(r"\d\s?%|\bпроцент|\bpour ?cent|\bpercent")
_YEAR = re.compile(r"(?<![\d.,])(1[5-9]\d\d|20\d\d)(?![\d.,])")
_NUMBER_UNIT = re.compile(r"\d+(?:[.,]\d+)?\s?(?:мм|см|км|м|кг|т|МПа|ГПа|кН|Н|кВт|Вт|об/мин|рад/с|м/с|Гц|ч|руб|"
                          r"млн|млрд|тыс|раз|лет|mm|cm|km|kg|MPa|GPa|kN|kW|W|Hz|rpm|tr/min|€|\$|millions?|"
                          r"milliards?|billions?|ans|years|fois|times|°C)(?![\w/])")
_STANDARD = re.compile(r"\b(ГОСТ(?:\s?Р)?(?:\s?ИСО|\s?ISO)?|ОСТ|СНиП|СП|ISO|NF\s?EN(?:\s?ISO)?|EN(?:\s?ISO)?|IEC|МЭК|DIN)"
                       r"\s?([\d.]+(?:[-–]\d+)*)(?:[:\-–](\d{2,4}))?", re.UNICODE)
_ATTRIBUTION = {
    "fr": ["selon ", "d'après ", "d’après ", "comme l'a montré", "comme l’a montré", "a démontré", "ont montré",
           "a montré", "les études montrent", "les recherches montrent"],
    "ru": ["по данным", "согласно ", "по мнению", "как показал", "как показали", "исследования показывают",
           "доказал", "установил", "по оценкам"],
    "en": ["according to", "as shown by", "studies show", "research shows", "demonstrated", "has shown", "have shown"],
}
_ABSOLUTE = {
    "fr": ["toujours", "jamais", "tous les", "toutes les", "aucun", "aucune", "le plus", "la plus", "le meilleur",
           "la meilleure", "unique", "prouvé", "incontestable", "il est évident", "sans aucun doute", "systématiquement"],
    "ru": ["всегда", "никогда", "все ", "любой", "самый", "самая", "самое", "наилучш", "единственн", "доказано",
           "бесспорно", "очевидно", "несомненно", "абсолютно"],
    "en": ["always", "never", "all ", "none", "the most", "the best", "unique", "proven", "undoubtedly",
           "obviously", "clearly", "without doubt"],
}
_CROSS_REFERENCE = re.compile(r"(?i)(?<!\w)(?:рис|рисун\w*|табл\w*|fig\w*|tableau\w*|table|раздел\w*|section|"
                              r"глав\w*|chapitre|chapter|пункт\w*|п|приложени\w*|annexe|appendix|вариант\w*|№)"
                              r"\.?\s*\d+(?:\.\d+)*")
_REFERENCE_HEADINGS = ("список", "литератур", "источник", "bibliograph", "référence", "reference", "sources")


class Claim(BaseModel):
    text: str
    location: str | None
    types: list[ClaimType]
    support: Support
    evidence: list[str] = Field(default_factory=list, description="Ce qui étaye l'affirmation (clés, documents).")
    severity: Severity
    suggestion: str | None = None


class ClaimsReport(BaseModel):
    label: str
    claims_found: int
    by_support: dict[str, int]
    claims: list[Claim] = Field(description="Non étayées d'abord (au plus 120).")
    notice: str = NOTICE


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("ё", "е")


def _is_reference_section(section: str | None) -> bool:
    return bool(section) and any(word in _fold(section) for word in map(_fold, _REFERENCE_HEADINGS))


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def claim_types(sentence: str, language: str) -> list[ClaimType]:
    folded = " " + sentence.casefold() + " "
    found: list[ClaimType] = []
    without_markers = _CROSS_REFERENCE.sub(" ", _KEY_MARKER.sub(" ", _NUMERIC_CITATION.sub(" ", sentence)))
    # un simple numéro (« винт 14 », « вариант 4 ») n'est pas une affirmation : il faut un pourcentage,
    # une grandeur avec unité ou un ordre de grandeur (млн, milliards...)
    if "=" not in sentence and (_PERCENT.search(without_markers) or _NUMBER_UNIT.search(without_markers)):
        found.append("chiffre")
    if _YEAR.search(_AUTHOR_YEAR.sub(" ", without_markers)):
        found.append("date")
    langs = {language, "en"} if language != "en" else {"en"}
    if any(p in folded for lang in langs for p in _ATTRIBUTION.get(lang, [])):
        found.append("attribution")
    if any(re.search(r"(?<!\w)" + re.escape(p.strip()) + r"(?!\w)", folded) for lang in langs
           for p in _ABSOLUTE.get(lang, [])):
        found.append("absolu")
    if _STANDARD.search(sentence):
        found.append("norme")
    return found


def standard_references(text: str) -> list[tuple[str, str, str | None]]:
    """(code complet, base « ГОСТ 2.105 », année éventuelle) des normes citées."""
    result = []
    for match in _STANDARD.finditer(text):
        prefix = re.sub(r"\s+", " ", match.group(1)).strip()
        number = match.group(2)
        year = match.group(3)
        pieces = re.split(r"[-–]", number)
        if year is None and len(pieces) > 1 and len(pieces[-1]) in (2, 4):
            year, number = pieces[-1], "-".join(pieces[:-1])
        result.append((match.group(0).strip(), f"{prefix} {number}".strip(), year))
    return result


def _year4(year: str | None) -> int | None:
    if not year:
        return None
    value = int(year)
    if len(year) == 2:
        value += 1900 if value > 30 else 2000
    return value


def analyze_claims(label: str, segments: list[Segment], language: str, *, sources: dict[str, str],
                   project_texts: dict[str, str], known_standards: list[str]) -> ClaimsReport:
    """sources : {clé: statut} ; project_texts : {nom du document: texte} (autres documents du projet)."""
    trusted = {"verified_online", "verified_manual", "well_formed"}
    folded_docs = {name: text for name, text in project_texts.items()}
    doc_numbers = {name: numbers_in(text) for name, text in folded_docs.items()}
    standards_known: dict[str, set[int]] = {}
    for code in known_standards:
        for _, base, year in standard_references(code):
            standards_known.setdefault(_fold(base), set())
            if _year4(year):
                standards_known[_fold(base)].add(_year4(year))  # type: ignore[arg-type]
    claims: list[Claim] = []
    for segment in segments:
        if segment.kind in ("heading", "table") or _is_reference_section(segment.section):
            continue
        for sentence in sentences(segment.text):
            types = claim_types(sentence, language)
            if not types:
                continue
            evidence: list[str] = []
            keys = _KEY_MARKER.findall(sentence)
            suggestion = None
            if keys:
                unknown = [k for k in keys if k not in sources]
                untrusted = [k for k in keys if k in sources and sources[k] not in trusted]
                if unknown:
                    support: Support = "cle_inconnue"
                    evidence = [f"clé non enregistrée : {k}" for k in unknown]
                    suggestion = "Enregistrer la source (register_source) ou corriger la clé."
                elif untrusted:
                    support = "source_non_verifiee"
                    evidence = [f"{k} : {sources[k]}" for k in untrusted]
                    suggestion = "Vérifier la source (verify_source ou vérification manuelle)."
                else:
                    support = "source_verifiee"
                    evidence = [f"{k} : {sources[k]}" for k in keys]
            elif _NUMERIC_CITATION.search(sentence) or _AUTHOR_YEAR.search(sentence):
                support = "citation_numerique"
                evidence = ["citation présente (non reliée à une source enregistrée)"]
                suggestion = "Relier la citation à une source enregistrée ([@clé]) pour pouvoir la vérifier."
            else:
                numbers = numbers_in(_YEAR.sub(" ", _CROSS_REFERENCE.sub(" ", sentence)))
                matched = [name for name, found in doc_numbers.items() if numbers and numbers <= found]
                if matched:
                    support = "documents_du_projet"
                    evidence = [f"chiffres présents dans : {name}" for name in matched[:3]]
                    suggestion = "Citer le document d'origine (consignes, données de mesure...)."
                elif types == ["norme"]:
                    support = "norme"
                else:
                    support = "non_etaye"
                    suggestion = ("Trouver une source fiable et la citer, ou reformuler prudemment ; "
                                  "supprimer l'affirmation si elle ne peut pas être vérifiée.")
            if "norme" in types:
                for code, base, year in standard_references(sentence):
                    years = standards_known.get(_fold(base))
                    cited = _year4(year)
                    if years and cited and cited not in years:
                        evidence.append(f"{code} : édition {cited} ; édition connue du profil : "
                                        f"{', '.join(map(str, sorted(years)))}")
                        suggestion = "Vérifier l'édition en vigueur de la norme (elle a peut-être été remplacée)."
                    elif years is None:
                        evidence.append(f"{code} : absente du profil disciplinaire, existence et édition à vérifier")
            severity: Severity
            if support in ("cle_inconnue",):
                severity = "error"
            elif support == "non_etaye" and set(types) & {"chiffre", "attribution", "absolu"}:
                severity = "warning"
            elif support == "source_non_verifiee" or any("édition" in e for e in evidence):
                severity = "warning"
            else:
                severity = "info"
            claims.append(Claim(text=excerpt(sentence, 300), location=segment.location, types=types, support=support,
                                evidence=evidence, severity=severity, suggestion=suggestion))
    order = {"error": 0, "warning": 1, "info": 2}
    claims.sort(key=lambda c: order[c.severity])
    by_support: dict[str, int] = {}
    for claim in claims:
        by_support[claim.support] = by_support.get(claim.support, 0) + 1
    return ClaimsReport(label=label, claims_found=len(claims), by_support=by_support, claims=claims[:120])


def claim_issues(report: ClaimsReport) -> list[QualityIssue]:
    labels = {"cle_inconnue": "citation vers une clé inconnue", "source_non_verifiee": "source citée non vérifiée",
              "non_etaye": "affirmation non étayée"}
    issues = []
    for claim in report.claims:
        if claim.severity == "info":
            continue
        what = labels.get(claim.support, "norme à vérifier")
        issues.append(QualityIssue(category="affirmations", code=claim.support, severity=claim.severity,
                                   message=f"{what.capitalize()} ({', '.join(claim.types)})"
                                           + (f" — {'; '.join(claim.evidence)}" if claim.evidence else ""),
                                   location=claim.location, excerpt=claim.text, suggestion=claim.suggestion))
    return issues
