"""Contrôle des normes internationales de présentation des documents académiques (fr / ru / en).

Règles contrôlées (formulées d'après les normes ; les consignes de l'enseignant et de l'établissement priment) :
- ISO 7144 (présentation des thèses et documents analogues) et ANSI/NISO Z39.18 (rapports scientifiques et
  techniques) : éléments attendus selon le type de document (page de titre, résumé, mots-clés, sommaire,
  introduction, conclusion, références) ;
- ISO 214 (résumés) : longueur du résumé ;
- ISO 2145 (numérotation des divisions) : numéros 1, 1.1, 1.1.1 sans saut, profondeur limitée, présentation homogène ;
- figures et tableaux (ISO 7144, ГОСТ 7.32) : numérotation continue, chaque figure / tableau appelé dans le texte ;
- ISO 80000-1 / SI : espace entre la valeur et l'unité, symboles d'unités corrects, séparateur décimal homogène ;
- ISO 8601 : dates numériques ambiguës ;
- sigles : définis à leur première occurrence ou dans une liste des abréviations.
Ce sont des contrôles automatiques et indicatifs : ils signalent, ils ne corrigent rien.
"""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, Field

from academic_writer.quality.models import QualityIssue, Segment, Target, excerpt

_I = re.IGNORECASE

THESES = {"memoire_licence", "memoire_master", "these_doctorat"}
ADVANCED = {"memoire_master", "these_doctorat"}
REPORTS = {"rapport_technique", "rapport_de_stage", "projet_recherche", "projet_technique", "etude_technique",
           "projet_universitaire", "synthese_bibliographique"}
LAB = {"tp", "compte_rendu_tp", "rapport_laboratoire"}

ELEMENTS = {
    "title_page": re.compile(r"page de (?:garde|titre)|титульн\w*|title page", _I),
    "abstract": re.compile(r"^(?:résumé|abstract|реферат|аннотаци\w*|summary|executive summary|синопсис)\b", _I),
    "keywords": re.compile(r"mots[- ]cl[ée]s|ключев\w* слов\w*|key ?words", _I),
    "contents": re.compile(r"sommaire|table des matières|содержание|оглавление|contents", _I),
    "introduction": re.compile(r"^(?:\d[\d.]*\s*)?(?:introduction|введение)\b", _I),
    "conclusion": re.compile(r"^(?:\d[\d.]*\s*)?(?:conclusions?(?: générale)?|заключение|выводы|"
                             r"conclusions? and recommendations|general conclusion)\b", _I),
    "references": re.compile(r"r[ée]f[ée]rences|bibliograph\w*|список\s+(?:использованн\w*\s+)?(?:источник|литератур)\w*|"
                             r"литература|works cited|sources", _I),
    "objective": re.compile(r"objectif|but (?:du|de la)|цель|aim|objective|purpose", _I),
    "method": re.compile(r"m[ée]thod\w*|mode opératoire|protocole|matériel|manipulation|ход работы|методик\w*|"
                         r"порядок выполнения|оборудование|procedure|materials|apparatus", _I),
    "results": re.compile(r"r[ée]sultats?|mesures|результат\w*|расч[её]т\w*|results?|measurements|calculations?", _I),
    "discussion": re.compile(r"discussion|analyse|interpr[ée]tation|обсуждени\w*|анализ\w*|analysis|interpretation", _I),
}
_ELEMENT_LABELS = {
    "title_page": "page de titre", "abstract": "résumé", "keywords": "mots-clés", "contents": "sommaire",
    "introduction": "introduction", "conclusion": "conclusion", "references": "liste des références",
    "objective": "objectif du travail", "method": "matériel et méthode", "results": "résultats",
    "discussion": "analyse / discussion des résultats",
}


class NormCheck(BaseModel):
    norm: str
    rule: str
    status: str = Field(description="conforme, non_conforme ou a_verifier")
    detail: str


class NormsReport(BaseModel):
    label: str
    document_type: str | None
    checks: list[NormCheck]
    issues: list[QualityIssue]
    summary: str
    notice: str = ("Contrôles indicatifs d'après les normes internationales (ISO 7144, ISO 214, ISO 2145, ISO 80000, "
                   "ISO 8601) ; les consignes de l'enseignant et de l'établissement priment toujours.")


def _issue(code: str, severity: str, message: str, suggestion: str | None = None, segment: Segment | None = None,
           text: str | None = None) -> QualityIssue:
    return QualityIssue(category="normes", code=code, severity=severity, message=message, suggestion=suggestion,
                        location=segment.location if segment else None, excerpt=excerpt(text) if text else None)


def _expected(document_type: str | None) -> tuple[list[str], str]:
    if document_type in THESES:
        return (["title_page", "abstract", "keywords", "contents", "introduction", "conclusion", "references"],
                "ISO 7144 (thèses)")
    if document_type in REPORTS or document_type == "article_scientifique":
        return ["abstract", "introduction", "conclusion", "references"], "ANSI/NISO Z39.18 (rapports) / ISO 7144"
    if document_type in LAB:
        return ["objective", "method", "results", "discussion", "conclusion"], "usage des comptes rendus de TP"
    return [], ""


# --- éléments et résumé --------------------------------------------------------------------------------

def _elements(target: Target, document_type: str | None, checks: list[NormCheck], issues: list[QualityIssue]) -> None:
    expected, norm = _expected(document_type)
    if not expected:
        return
    headings = [s.text.strip() for s in target.segments if s.kind == "heading"]
    first_lines = [s.text for s in target.segments[:40]]
    missing = []
    for element in expected:
        pattern = ELEMENTS[element]
        found = any(pattern.search(h) for h in headings)
        if not found and element in ("title_page", "keywords"):
            found = any(pattern.search(t) for t in first_lines) or any(pattern.search(s.text[:80])
                                                                       for s in target.segments)
        if not found:
            missing.append(_ELEMENT_LABELS[element])
    checks.append(NormCheck(norm=norm, rule="éléments attendus pour ce type de document",
                            status="conforme" if not missing else "non_conforme",
                            detail="tous présents" if not missing else "absents : " + ", ".join(missing)))
    for label in missing:
        issues.append(_issue("norm_missing_element", "warning", f"Élément attendu absent ({norm}) : {label}.",
                             "Ajouter cet élément, sauf si les consignes de l'enseignant l'excluent."))
    if document_type in ADVANCED:
        abstracts = [h for h in headings if ELEMENTS["abstract"].search(h)]
        if len(abstracts) < 2:
            checks.append(NormCheck(norm="usage universitaire (master, doctorat)", rule="résumé dans deux langues",
                                    status="a_verifier", detail=f"{len(abstracts)} résumé(s) trouvé(s)"))
            issues.append(_issue("norm_bilingual_abstract", "info",
                                 "Un seul résumé trouvé : mémoires de master et thèses en demandent souvent deux "
                                 "(langue du document + anglais).", "Vérifier les consignes de l'établissement."))


def _abstract_length(target: Target, document_type: str | None, checks: list[NormCheck],
                     issues: list[QualityIssue]) -> None:
    limit = 500 if document_type in THESES | REPORTS else 250
    current = None
    words: Counter[str] = Counter()
    for segment in target.segments:
        if segment.kind == "heading":
            current = segment.text if ELEMENTS["abstract"].search(segment.text.strip()) else None
            continue
        if current:
            words[current] += len(re.findall(r"\w+", segment.text))
    for title, count in words.items():
        ok = 60 <= count <= limit
        checks.append(NormCheck(norm="ISO 214", rule=f"longueur du résumé (≤ {limit} mots)",
                                status="conforme" if ok else "non_conforme", detail=f"« {title[:40]} » : {count} mots"))
        if count > limit:
            issues.append(_issue("norm_abstract_long", "warning",
                                 f"Résumé « {title[:40]} » de {count} mots : ISO 214 recommande au plus {limit} mots "
                                 "pour ce type de document.", "Resserrer : objectif, méthode, résultats, conclusion."))
        elif count < 60:
            issues.append(_issue("norm_abstract_short", "info",
                                 f"Résumé « {title[:40]} » très court ({count} mots) : ISO 214 attend objectif, méthode, "
                                 "résultats et conclusions.", None))


# --- numérotation des titres (ISO 2145) ----------------------------------------------------------------

_HEADING_NUMBER = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,5})(\.?)\s+\S")


def _numbering(target: Target, checks: list[NormCheck], issues: list[QualityIssue]) -> None:
    numbered = [(s, m) for s in target.segments if s.kind == "heading" and (m := _HEADING_NUMBER.match(s.text))]
    if len(numbered) < 3:
        return
    problems = 0
    previous: list[int] = []
    for segment, match in numbered:
        parts = [int(p) for p in match.group(1).split(".")]
        if previous:
            depth = len(parts)
            expected_same = previous[:depth - 1] + [previous[depth - 1] + 1] if depth <= len(previous) else None
            expected_child = previous + [1] if depth == len(previous) + 1 else None
            if parts not in (expected_same, expected_child) and not (depth == 1 and parts[0] == previous[0] + 1):
                problems += 1
                if problems <= 5:
                    issues.append(_issue("norm_heading_sequence", "warning",
                                         f"Numérotation discontinue : « {match.group(1)} » après "
                                         f"« {'.'.join(map(str, previous))} » (ISO 2145).",
                                         "Numéroter sans saut : 1, 1.1, 1.2, 2…", segment, segment.text))
        previous = parts
    deepest = max(len(m.group(1).split(".")) for _, m in numbered)
    if deepest > 4:
        issues.append(_issue("norm_heading_depth", "info", f"Titres numérotés sur {deepest} niveaux : ISO 2145 "
                             "recommande de limiter la profondeur (3 niveaux en pratique).", None))
    dots = {bool(m.group(2)) for _, m in numbered}
    if len(dots) > 1:
        problems += 1
        issues.append(_issue("norm_heading_style", "warning", "Présentation des numéros de titres hétérogène "
                             "(« 1. Titre » et « 1 Titre » mélangés).", "Choisir une seule présentation."))
    checks.append(NormCheck(norm="ISO 2145", rule="numérotation des divisions continue et homogène",
                            status="conforme" if not problems else "non_conforme",
                            detail=f"{len(numbered)} titres numérotés ; {problems} anomalie(s)"))


# --- figures et tableaux -------------------------------------------------------------------------------

_FIGURE = r"(?:figure|fig\.|рисунок|рис\.)"
_TABLE = r"(?:tableau|table|таблица|табл\.)"
_CAPTION = re.compile(rf"^\s*({_FIGURE}|{_TABLE})\s*(\d{{1,2}}(?:[.\-]\d{{1,2}})?)", _I)
_CALL = re.compile(rf"\b({_FIGURE}|{_TABLE}|figures|tableaux|рисунк\w*|таблиц\w*|tables)\s*(?:n[°o]\s*)?"
                   r"(\d{1,2}(?:[.\-]\d{1,2})?)", _I)


def _kind(word: str) -> str:
    return "figure" if re.match(r"fig|рис", word, _I) else "tableau"


def _captions(target: Target, checks: list[NormCheck], issues: list[QualityIssue]) -> None:
    captions: dict[str, list[tuple[str, Segment]]] = {"figure": [], "tableau": []}
    calls: set[tuple[str, str]] = set()
    for segment in target.segments:
        match = _CAPTION.match(segment.text)
        if match and (segment.kind == "caption" or len(segment.text) < 200):
            captions[_kind(match.group(1))].append((match.group(2).replace("-", "."), segment))
            rest = segment.text[match.end():]
        else:
            rest = segment.text
        if segment.kind != "heading":
            for call in _CALL.finditer(rest):
                calls.add((_kind(call.group(1)), call.group(2).replace("-", ".")))
    total = sum(len(v) for v in captions.values())
    if not total:
        return
    problems = 0
    for kind, items in captions.items():
        numbers = [n for n, _ in items]
        for number, count in Counter(numbers).items():
            if count > 1:
                problems += 1
                issues.append(_issue("norm_caption_duplicate", "warning", f"{kind.capitalize()} {number} numéroté(e) "
                                     f"{count} fois.", "Numéroter les figures et tableaux sans doublon."))
        simple = [int(n) for n in numbers if n.isdigit()]
        if simple and simple == sorted(simple) and simple != list(range(1, len(simple) + 1)):
            problems += 1
            issues.append(_issue("norm_caption_gap", "warning", f"Numérotation des {kind}s discontinue : "
                                 f"{', '.join(map(str, simple))}.", "Numéroter 1, 2, 3… dans l'ordre d'apparition."))
        for number, segment in items:
            if (kind, number) not in calls:
                problems += 1
                issues.append(_issue("norm_caption_not_called", "info", f"{kind.capitalize()} {number} jamais appelé(e) "
                                     "dans le texte.", f"Ajouter un renvoi (« voir {kind} {number} »).", segment,
                                     segment.text))
    checks.append(NormCheck(norm="ISO 7144 / usage", rule="figures et tableaux numérotés et appelés dans le texte",
                            status="conforme" if not problems else "a_verifier",
                            detail=f"{len(captions['figure'])} figure(s), {len(captions['tableau'])} tableau(x) ; "
                                   f"{problems} point(s) à revoir"))


# --- unités SI, décimales, dates, sigles ---------------------------------------------------------------

_UNITS = (r"(?:mm|cm|km|m|µm|nm|kg|mg|g|t|s|ms|min|h|Hz|kHz|MHz|GHz|N|kN|MN|Pa|kPa|MPa|GPa|J|kJ|MJ|W|kW|MW|V|kV|A|mA|"
          r"Ω|kΩ|K|mol|L|ml|mL|rad|rpm|"
          r"мм|см|км|м|кг|мг|г|т|с|мин|ч|Гц|кГц|Н|кН|Па|кПа|МПа|ГПа|Дж|кДж|Вт|кВт|МВт|В|кВ|А|мА|Ом|К|об/мин)")
_NO_SPACE = re.compile(rf"(?<![\w.,])(\d+(?:[.,]\d+)?)({_UNITS})(?![\w/²³])")
_WRONG = (
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(Kg|KG|kgs)\b"), "kg"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(Km|KM|kms)\b"), "km"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(secs?|sec\.)(?!\w)"), "s"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(hrs?|hrs\.)(?!\w)"), "h"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(mn)\b"), "min"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(KW|Kw|kw)\b"), "kW"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(Mpa|MPA|mpa)\b"), "MPa"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(Gpa|GPA|gpa)\b"), "GPa"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(Hz\.|hz|HZ)\b"), "Hz"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(кгс?\.|сек\.?|мм\.|см\.|км\.)(?=\s+[а-яa-z])"), "symbole sans point"),
)
_DECIMAL_DOT = re.compile(r"(?<![\d.,])\d+\.\d+(?![\d.])")
_DECIMAL_COMMA = re.compile(r"(?<![\d.,])\d+,\d+(?![\d,])")
_DATE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b")
_ACRONYM = re.compile(r"(?<![\w-])([A-ZА-ЯЁ]{2,6})(?![\w-])")
_KNOWN = {"ISO", "IEC", "IEEE", "SI", "DOI", "PDF", "ГОСТ", "ОСТ", "СНиП", "СП", "РФ", "США", "ЕС", "ТП", "ТД", "TP", "TD",
          "UE", "USA", "EU", "UK", "NB", "OK", "CNC", "CAO", "CAD", "DIN", "EN", "NF", "ASTM", "ASME", "ANSI", "API",
          "URL", "HTML", "PC", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XX", "XXI", "XIX", "XVIII",
          "MPa", "GPa", "SA", "ЛР", "ЧПУ", "ЭВМ", "ПК", "ТММ", "САПР", "ВУЗ", "УДК", "ББК", "ISBN", "ISSN"}
_ABBREVIATIONS_HEADING = re.compile(r"abr[ée]viations|sigles|acronymes|сокращени\w*|обозначени\w*|abbreviations|"
                                    r"nomenclature|glossaire|glossary", _I)


def _units(target: Target, checks: list[NormCheck], issues: list[QualityIssue]) -> None:
    body = [s for s in target.body if s.kind in ("paragraph", "list_item", "caption", "note")]
    no_space = wrong = 0
    for segment in body:
        for match in _NO_SPACE.finditer(segment.text):
            if re.search(r"(?:fig\w*|figure|рис\w*|табл\w*|table\w*|section|annexe|приложени\w*|variante?|вариант)"
                         r"\.?\s*$", segment.text[max(0, match.start() - 14):match.start()], _I):
                continue  # « figure 1A », « вариант 3В » : repère, pas une unité
            no_space += 1
            if no_space <= 5:
                issues.append(_issue("norm_unit_space", "warning",
                                     f"« {match.group(0)} » : une espace sépare la valeur de l'unité "
                                     f"(« {match.group(1)} {match.group(2)} », ISO 80000-1).", None, segment,
                                     segment.text))
        for pattern, right in _WRONG:
            for match in pattern.finditer(segment.text):
                wrong += 1
                if wrong <= 5:
                    issues.append(_issue("norm_unit_symbol", "warning",
                                         f"Symbole d'unité « {match.group(1)} » non conforme au SI ({right}).",
                                         "Utiliser le symbole SI exact (casse, sans point, invariable).", segment,
                                         segment.text))
    text = " ".join(s.text for s in body)
    dots, commas = len(_DECIMAL_DOT.findall(text)), len(_DECIMAL_COMMA.findall(text))
    mixed = dots >= 3 and commas >= 3
    if mixed:
        issues.append(_issue("norm_decimal_mixed", "info", f"Séparateurs décimaux mélangés ({commas} virgules, {dots} "
                             "points).", "Utiliser un seul séparateur (virgule en français et en russe, point en "
                             "anglais) ; vérifier les listes de valeurs avant de corriger."))
    checks.append(NormCheck(norm="ISO 80000-1 / SI", rule="écriture des valeurs et des unités",
                            status="conforme" if not (no_space or wrong or mixed) else "non_conforme",
                            detail=f"{no_space} valeur(s) collée(s) à l'unité, {wrong} symbole(s) incorrect(s)"
                                   + ("; séparateurs décimaux mélangés" if mixed else "")))


def _dates(target: Target, checks: list[NormCheck], issues: list[QualityIssue]) -> None:
    ambiguous = []
    for segment in target.body:
        for match in _DATE.finditer(segment.text):
            day, month = int(match.group(1)), int(match.group(2))
            if day <= 12 and month <= 12 and day != month:
                ambiguous.append((match.group(0), segment))
    if ambiguous:
        date, segment = ambiguous[0]
        issues.append(_issue("norm_date_ambiguous", "info", f"{len(ambiguous)} date(s) numérique(s) ambiguë(s) "
                             f"(ex. « {date} » : jour/mois ou mois/jour ?).",
                             "Écrire le mois en lettres ou la forme ISO 8601 (AAAA-MM-JJ).", segment))
        checks.append(NormCheck(norm="ISO 8601", rule="dates sans ambiguïté", status="a_verifier",
                                detail=f"{len(ambiguous)} date(s) ambiguë(s)"))


def _acronyms(target: Target, checks: list[NormCheck], issues: list[QualityIssue]) -> None:
    if any(_ABBREVIATIONS_HEADING.search(s.text) for s in target.segments if s.kind == "heading"):
        checks.append(NormCheck(norm="usage", rule="sigles définis", status="conforme",
                                detail="liste des abréviations présente"))
        return
    seen: dict[str, tuple[Segment, bool]] = {}
    counts: Counter[str] = Counter()
    for segment in target.body:
        if segment.kind == "table":
            continue
        for match in _ACRONYM.finditer(segment.text):
            word = match.group(1)
            if word in _KNOWN:
                continue
            counts[word] += 1
            if word not in seen:
                around = segment.text[max(0, match.start() - 3):match.end() + 3]
                defined = "(" in around or ")" in around or "«" in around
                seen[word] = (segment, defined)
    undefined = [w for w, (_, defined) in seen.items() if not defined and counts[w] >= 2]
    for word in undefined[:8]:
        segment = seen[word][0]
        issues.append(_issue("norm_acronym_undefined", "info", f"Sigle « {word} » employé sans définition à sa "
                             "première occurrence.", f"Écrire le terme complet suivi de ({word}) ou ajouter une liste "
                             "des abréviations.", segment, segment.text))
    if seen:
        checks.append(NormCheck(norm="usage", rule="sigles définis à la première occurrence",
                                status="conforme" if not undefined else "a_verifier",
                                detail=f"{len(undefined)} sigle(s) sans définition"))


def check_norms(target: Target, document_type: str | None) -> NormsReport:
    checks: list[NormCheck] = []
    issues: list[QualityIssue] = []
    _elements(target, document_type, checks, issues)
    _abstract_length(target, document_type, checks, issues)
    _numbering(target, checks, issues)
    _captions(target, checks, issues)
    _units(target, checks, issues)
    _dates(target, checks, issues)
    _acronyms(target, checks, issues)
    status = Counter(c.status for c in checks)
    summary = (f"{len(checks)} règles contrôlées : {status.get('conforme', 0)} conformes, "
               f"{status.get('non_conforme', 0)} non conformes, {status.get('a_verifier', 0)} à vérifier.")
    return NormsReport(label=target.label, document_type=document_type, checks=checks, issues=issues, summary=summary)
