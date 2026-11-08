"""Contrôles automatiques des brouillons de section (déterministes, multilingues).

- longueur par rapport à la cible ;
- chiffres absents des sources fournies (risque d'invention) ;
- termes à éviter du profil disciplinaire ;
- références bibliographiques non vérifiables ;
- marqueurs [À COMPLÉTER] ;
- langue attendue ;
- fidélité lors d'une réécriture (chiffres ou termes supprimés, ajoutés ou modifiés).
"""

from __future__ import annotations

import re
import unicodedata

from academic_writer.domains.model import DomainProfile
from academic_writer.security.injection import scan_text
from academic_writer.writing.models import Check

_NUMBER = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)?(?![\w])")
_CITATION = re.compile(r"\[\d+(?:[,–-]\s*\d+)*\]|\([A-ZА-Я][\w\-]+(?: et al\.| и др\.)?,? \d{4}[a-z]?\)")
_PLACEHOLDER = re.compile(r"\[(?:À COMPLÉTER|A COMPLETER|ЗАПОЛНИТЬ|TO COMPLETE|TODO)[^\]]*\]", re.IGNORECASE)
_WORD = re.compile(r"\w+", re.UNICODE)
PLACEHOLDER_HINT = {"fr": "[À COMPLÉTER : …]", "ru": "[ЗАПОЛНИТЬ: …]", "en": "[TO COMPLETE: …]"}


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ё", "е")


def numbers_in(text: str) -> set[str]:
    """Nombres « significatifs » normalisés (au moins 2 chiffres ou décimaux), virgule = point."""
    result = set()
    for raw in _NUMBER.findall(text):
        value = raw.replace(",", ".").lstrip("-")
        digits = sum(ch.isdigit() for ch in value)
        if "." in value or digits >= 2:
            result.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return result


_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$|`[^`]*`|\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
_CAPITALIZED = re.compile(r"(?<![\w.])([A-ZА-ЯЁ][a-zа-яё]{3,})\b")
_LATIN_WORD = re.compile(r"\b[A-Za-z]{4,}\b")
_CYRILLIC_WORD = re.compile(r"\b[А-Яа-яЁё]{4,}\b")


def _strip_math(text: str) -> str:
    return _MATH.sub(" ", text)


def _profile_text(profile: DomainProfile) -> str:
    parts: list[str] = []
    for term in profile.terminology:
        parts += [term.fr or "", term.ru or "", term.en or ""]
        if term.definition:
            parts += [term.definition.fr or "", term.definition.ru or "", term.definition.en or ""]
    parts += [s.code + " " + (s.title.fr or "") + " " + (s.title.ru or "") for s in profile.standards]
    return " ".join(parts)


def _proper_names(text: str) -> set[str]:
    """Mots capitalisés qui ne sont pas en début de phrase, de ligne ou d'élément de liste (Markdown ignoré)."""
    names = set()
    for match in _CAPITALIZED.finditer(text):
        prefix = text[: match.start()].rstrip(" \t*_#>-–—«\"'(0123456789.)")
        if prefix and prefix[-1] not in ".!?:;\n":
            names.add(match.group(1))
    return names


_BIBLIO_HEADING = re.compile(
    r"^\s*#{0,6}\s*\**\s*(?:список\s+(?:использованн\w+\s+)?(?:источников|литературы)|литература|bibliograph\w*|"
    r"r[ée]f[ée]rences(?:\s+bibliographiques)?|sources)\b", re.IGNORECASE | re.MULTILINE)
_BIBLIO_ENTRY = re.compile(r"^\s*(?:\d{1,3}[.)]|[-*])\s+.*(?:ГОСТ|ISO|NF |IEEE|[A-ZА-ЯЁ][a-zа-яё]+,?\s+[A-ZА-ЯЁ]\.\s*[A-ZА-ЯЁ]?\.?|"
                           r"\b(?:19|20)\d{2}\b.*(?:изд|Press|éd\.|Verlag|журнал|Journal))", re.MULTILINE)


def _foreign_words(text: str, language: str) -> list[str]:
    if language == "ru":
        words = [w for w in _LATIN_WORD.findall(text) if not w.isupper()]
    else:
        words = _CYRILLIC_WORD.findall(text)
    return sorted(set(words))


def check_draft(text: str, *, language: str, target_words: int | None, sources_text: str,
                profile: DomainProfile, has_bibliography: bool = False, truncated: bool = False,
                is_references_section: bool = False) -> list[Check]:
    checks: list[Check] = []
    if not is_references_section:
        entries = _BIBLIO_ENTRY.findall(text)
        if _BIBLIO_HEADING.search(text) or len(entries) >= 2:
            checks.append(Check(code="generated_bibliography", severity="error",
                                message="Liste de références produite par le rédacteur dans le corps de la section : "
                                        "à supprimer. Aucune référence ne doit être générée sans vérification "
                                        "(gestion des sources : Phase 6).",
                                details=[e.strip()[:120] for e in entries[:5]]))
    words = word_count(text)
    if target_words:
        ratio = words / target_words
        if ratio < 0.75 or ratio > 1.25:
            checks.append(Check(code="length", severity="warning",
                                message=f"Longueur : {words} mots pour une cible de {target_words} ({ratio:.0%})."))
        else:
            checks.append(Check(code="length", severity="info", message=f"Longueur : {words} mots (cible {target_words})."))
    if truncated:
        checks.append(Check(code="truncated", severity="error",
                            message="Texte coupé par la limite de génération : la fin manque."))

    unsourced = sorted(numbers_in(text) - numbers_in(sources_text), key=lambda n: (len(n), n))
    if unsourced:
        checks.append(Check(code="unsourced_numbers", severity="warning",
                            message=f"{len(unsourced)} valeur(s) chiffrée(s) absente(s) des sources et données fournies : "
                                    "à vérifier (risque d'invention).", details=unsourced[:30]))

    folded = _fold(text)
    avoided: list[str] = []
    for term in profile.terminology:
        for expression in term.avoid.get(language, []):
            core = re.sub(r"\s*\(.*?\)", "", expression).strip()
            if core and _fold(core) in folded:
                preferred = getattr(term, language) or term.fr or term.en
                avoided.append(f"« {core} » → préférer « {preferred} »")
    if avoided:
        checks.append(Check(code="avoided_terms", severity="warning",
                            message="Terminologie déconseillée par le profil disciplinaire.", details=avoided))

    citations = sorted(set(_CITATION.findall(text)))
    if citations and not has_bibliography:
        checks.append(Check(code="unverified_citations", severity="warning",
                            message="Références citées sans bibliographie vérifiée dans le projet : "
                                    "ne pas les conserver sans vérification.", details=citations[:20]))

    placeholders = _PLACEHOLDER.findall(text)
    if placeholders:
        checks.append(Check(code="placeholders", severity="info",
                            message=f"{len(placeholders)} information(s) manquante(s) signalée(s) par le rédacteur.",
                            details=placeholders[:20]))

    letters = [ch for ch in text if ch.isalpha()]
    if letters:
        cyrillic = sum("Ѐ" <= ch <= "ӿ" for ch in letters) / len(letters)
        if language == "ru" and cyrillic < 0.5:
            checks.append(Check(code="language", severity="warning", message="Le texte ne semble pas rédigé en russe."))
        elif language in ("fr", "en") and cyrillic > 0.3:
            checks.append(Check(code="language", severity="warning",
                                message=f"Le texte contient beaucoup de cyrillique alors que la langue attendue est « {language} »."))

    prose = _strip_math(text)
    known = _fold(sources_text + " " + _profile_text(profile))
    names = sorted({w for w in _proper_names(prose) if _fold(w)[:5] not in known})
    if names:
        checks.append(Check(code="unsourced_names", severity="warning",
                            message="Noms propres absents des sources et du profil (attribution inventée possible : "
                                    "auteur, méthode, formule, norme).", details=names[:20]))

    foreign = _foreign_words(prose, language)
    if foreign:
        checks.append(Check(code="mixed_language", severity="warning",
                            message="Mots dans une autre langue (ou alphabet) au milieu du texte.", details=foreign[:20]))

    injections = scan_text(text)
    if injections:
        checks.append(Check(code="injection_echo", severity="warning",
                            message="Le texte produit contient des formulations d'instructions (copiées d'une source ?).",
                            details=injections[:5]))
    return checks


def _term_variants(value: str | None) -> list[str]:
    return [v.strip() for v in re.split(r"[/(),;]", value or "") if len(v.strip()) >= 3]


def term_present(term: str, folded_text: str) -> bool:
    """Chaque mot du terme doit apparaître en DÉBUT de mot, avec un radical tolérant les flexions
    (« кривошип » ↔ « кривошипа » ; mais « предел » n'est pas trouvé dans « определяется »)."""
    words = [w for w in _WORD.findall(_fold(term)) if len(w) >= 3]
    if not words:
        return False
    for word in words:
        stem = word if len(word) <= 4 else word[: max(4, len(word) - 3)]
        if not re.search(rf"(?<!\w){re.escape(stem)}", folded_text):
            return False
    return True


def glossary_for(text: str, profile: DomainProfile, source: str, target: str) -> list[tuple[str, str]]:
    """Termes du profil présents dans le texte source, avec leur équivalent dans la langue cible."""
    folded = _fold(text)
    pairs: list[tuple[str, str]] = []
    for term in profile.terminology:
        src, tgt = getattr(term, source), getattr(term, target)
        if not src or not tgt:
            continue
        if any(term_present(v, folded) for v in _term_variants(src)):
            pairs.append((src, tgt))
    return pairs


def translation_checks(original: str, translated: str, profile: DomainProfile, source: str, target: str) -> list[Check]:
    """Traduction : valeurs chiffrées identiques et termes du glossaire rendus par leur équivalent."""
    checks: list[Check] = []
    before, after = numbers_in(original), numbers_in(translated)
    if before != after:
        details = [f"absent de la traduction : {n}" for n in sorted(before - after)[:15]]
        details += [f"ajouté par la traduction : {n}" for n in sorted(after - before)[:15]]
        checks.append(Check(code="translation_numbers", severity="error",
                            message="Les valeurs chiffrées diffèrent entre l'original et la traduction.", details=details))
    folded = _fold(translated)
    missing = [f"{src} → {tgt}" for src, tgt in glossary_for(original, profile, source, target)
               if not any(term_present(v, folded) for v in _term_variants(tgt))]
    if missing:
        checks.append(Check(code="translation_terms", severity="warning",
                            message="Termes du glossaire disciplinaire non retrouvés dans la traduction.",
                            details=missing[:20]))
    return checks


def check_fidelity(original: str, revised: str, profile: DomainProfile, language: str) -> list[Check]:
    """Compare deux versions : chiffres et termes techniques supprimés, ajoutés ou modifiés."""
    checks: list[Check] = []
    before, after = numbers_in(original), numbers_in(revised)
    removed, added = sorted(before - after), sorted(after - before)
    if removed or added:
        details = [f"supprimé : {n}" for n in removed[:15]] + [f"ajouté : {n}" for n in added[:15]]
        checks.append(Check(code="fidelity_numbers", severity="error" if added else "warning",
                            message="Valeurs chiffrées modifiées par rapport à la version précédente : "
                                    "changement de sens possible, à vérifier.", details=details))
    folded_before, folded_after = _fold(original), _fold(revised)
    lost: list[str] = []
    for term in profile.terminology:
        name = getattr(term, language) or ""
        for variant in [v.strip() for v in re.split(r"[/(),]", name) if len(v.strip()) >= 4]:
            if _fold(variant) in folded_before and _fold(variant) not in folded_after:
                lost.append(variant)
    if lost:
        checks.append(Check(code="fidelity_terms", severity="warning",
                            message="Termes techniques présents avant et absents après réécriture.",
                            details=sorted(set(lost))[:20]))
    before_words = set(w for w in _WORD.findall(folded_before) if len(w) >= 6 and w[0].isalpha())
    after_words = set(w for w in _WORD.findall(folded_after) if len(w) >= 6 and w[0].isalpha())
    capitalized_new = sorted({w for w in re.findall(r"(?<![.!?]\s)(?<!^)\b[A-ZА-ЯЁ][a-zа-яё]{4,}\b", revised)
                              if _fold(w) not in folded_before})
    if capitalized_new:
        checks.append(Check(code="fidelity_new_names", severity="warning",
                            message="Nouveaux noms propres ou termes en majuscule absents de la version précédente "
                                    "(invention possible).", details=capitalized_new[:15]))
    if before_words:
        kept = len(before_words & after_words) / len(before_words)
        if kept < 0.4:
            checks.append(Check(code="fidelity_rewrite_extent", severity="info",
                                message=f"Réécriture profonde : {kept:.0%} du vocabulaire d'origine conservé."))
    return checks
