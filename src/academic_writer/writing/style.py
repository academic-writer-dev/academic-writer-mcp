"""Analyse de style académique (déterministe, fr / ru / en) et application prudente des
corrections LanguageTool."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from academic_writer.writing.languagetool import LTMatch
from academic_writer.writing.models import Check

_SENTENCE = re.compile(r"[^.!?…]+[.!?…]+|[^.!?…]+$")
_WORD = re.compile(r"\w+", re.UNICODE)
_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$|`[^`]*`", re.DOTALL)
LONG_SENTENCE = {"fr": 40, "en": 35, "ru": 30}
VAGUE = {
    "fr": ["chose", "choses", "truc", "beaucoup", "très", "il y a", "etc", "assez", "plutôt", "certains", "certaines",
           "différents", "différentes", "en quelque sorte", "un peu", "énormément", "vraiment"],
    "ru": ["очень", "много", "как бы", "типа", "и т.д", "вещь", "вещи", "достаточно", "довольно", "некоторые",
           "различные", "в принципе", "немного", "действительно", "огромный"],
    "en": ["very", "a lot", "thing", "things", "stuff", "etc", "kind of", "really", "basically", "quite", "somewhat",
           "various", "huge", "pretty much"],
}
FIRST_PERSON = {"fr": r"\b(?:je|j'|moi)\b", "ru": r"\b(?:я|мне|меня|мной)\b", "en": r"\b(?:I|me|my)\b"}
STOPWORDS_MIN_LEN = 6
AUTO_CATEGORIES = {"TYPOS", "GRAMMAR", "PUNCTUATION", "TYPOGRAPHY", "CASING", "CAT_HOMONYMES_PARONYMES",
                   "CONFUSED_WORDS"}


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ё", "е")


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def protected_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _MATH.finditer(text)]


def apply_safe_corrections(text: str, matches: list[LTMatch], known_terms: str) -> tuple[str, list[str], list[str]]:
    """Applique les seules corrections sûres ; renvoie (texte, appliquées, suggestions non appliquées).

    Sûre = catégorie orthographe/grammaire/typographie, première suggestion à ≤ 2 caractères d'écart,
    mot absent des sources et de la terminologie du projet, hors formule ou code.
    """
    known = _fold(known_terms)
    spans = protected_spans(text)
    applied: list[str] = []
    suggested: list[str] = []
    edits: list[tuple[int, int, str]] = []
    for match in sorted(matches, key=lambda m: m.offset):
        original = text[match.offset: match.offset + match.length]
        label = f"« {original} » : {match.message}"
        in_math = any(start <= match.offset < end for start, end in spans)
        word_known = len(original) >= 3 and re.search(rf"(?<!\w){re.escape(_fold(original))}(?!\w)", known) is not None
        replacement = match.replacements[0] if match.replacements else None
        safe = (replacement is not None and not in_math and not word_known and match.category in AUTO_CATEGORIES
                and levenshtein(_fold(original), _fold(replacement)) <= 2
                and not (edits and match.offset < edits[-1][1]))
        if safe:
            edits.append((match.offset, match.offset + match.length, replacement))
            applied.append(f"« {original} » → « {replacement} » ({match.message})")
        else:
            reason = (" [terme du projet conservé]" if word_known else " [formule]" if in_math else "")
            options = ", ".join(match.replacements[:3]) or "—"
            suggested.append(f"{label} — suggestions : {options}{reason}")
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text, applied, suggested


def style_report(text: str, language: str) -> list[Check]:
    checks: list[Check] = []
    prose = _MATH.sub(" ", text)
    limit = LONG_SENTENCE.get(language, 35)
    long_sentences = [s.strip() for s in _SENTENCE.findall(prose) if len(_WORD.findall(s)) > limit]
    if long_sentences:
        checks.append(Check(code="long_sentences", severity="warning",
                            message=f"{len(long_sentences)} phrase(s) de plus de {limit} mots : à scinder.",
                            details=[s[:160] + ("…" if len(s) > 160 else "") for s in long_sentences[:10]]))
    words = [w for w in _WORD.findall(_fold(prose)) if len(w) >= STOPWORDS_MIN_LEN and w.isalpha()]
    repeated: list[str] = []
    for index in range(0, max(1, len(words) - 60), 30):
        window = Counter(words[index: index + 60])
        repeated += [w for w, n in window.items() if n >= 3]
    if repeated:
        checks.append(Check(code="repetitions", severity="info",
                            message="Mots répétés à courte distance : varier ou reformuler.",
                            details=sorted(set(repeated))[:15]))
    folded = f" {_fold(prose)} "
    vague = [w for w in VAGUE.get(language, []) if re.search(rf"(?<!\w){re.escape(_fold(w))}(?!\w)", folded)]
    if vague:
        checks.append(Check(code="vague_words", severity="info",
                            message="Formulations vagues ou familières : préciser (valeur, référence, exemple).",
                            details=vague))
    pattern = FIRST_PERSON.get(language)
    if pattern and re.search(pattern, prose, flags=0 if language == "en" else re.IGNORECASE):
        checks.append(Check(code="first_person", severity="info",
                            message="Première personne du singulier : registre académique impersonnel recommandé "
                                    "(selon les usages de l'établissement)."))
    if not checks:
        checks.append(Check(code="style_ok", severity="info", message="Aucun problème de style détecté automatiquement."))
    return checks
