"""Similarité avec les sources du projet, citations manquantes, répétitions, ruptures de style (local).

Méthode : séquences de n mots consécutifs identiques (n = 8 par défaut, après normalisation de la casse et de
la ponctuation) entre le texte analysé et chaque document du projet ; les séquences contiguës sont fusionnées
en passages. Un passage repris est « cité » s'il est entre guillemets ou suivi d'un appel de citation
([@clé], [1], (Auteur, année)).

Limites : seules les sources présentes dans le projet sont comparées (pas Internet) ; une reformulation n'est
pas détectée ; un pourcentage de similarité n'est PAS un pourcentage de plagiat : il signale des passages à
examiner (citations correctes, formules, définitions normalisées, consignes recopiées…).
"""

from __future__ import annotations

import re
from collections import defaultdict

from pydantic import BaseModel, Field

_WORD = re.compile(r"[\w’']+", re.UNICODE)
_CITATION_AFTER = re.compile(r"^\s*[\"»”]?\s*(?:\[@[^\]]+\]|\[\d+(?:[,–-]\s*\d+)*\]|\([^()]{2,60},?\s*\d{4}[a-z]?\)|\[\s*\d+\s*,\s*[сcp]\.)")
_QUOTES = (("«", "»"), ("“", "”"), ('"', '"'), ("„", "“"))

NOTICE = ("Similarité ≠ plagiat : les passages listés sont à examiner (citation correcte, formule, définition "
          "normalisée, consigne recopiée…). Comparaison limitée aux documents du projet ; les reformulations ne "
          "sont pas détectées. Aucun outil ne prouve l'auteur d'un texte.")


class SimilarPassage(BaseModel):
    location: str | None
    text: str = Field(description="Passage du texte analysé.")
    source: str
    words: int
    cited: bool
    status: str = Field(description="cité, ou citation_manquante.")


class SourceOverlap(BaseModel):
    source: str
    matched_words: int
    share: float = Field(description="Part des mots du texte analysé retrouvés dans cette source (0 à 1).")


class Repetition(BaseModel):
    text: str
    occurrences: int
    locations: list[str]


class SimilarityReport(BaseModel):
    label: str
    words: int
    min_words: int
    overall_share: float = Field(description="Part des mots appartenant à un passage repris (0 à 1).")
    sources: list[SourceOverlap]
    passages: list[SimilarPassage]
    missing_citations: int
    repetitions: list[Repetition]
    style_breaks: list[str]
    notice: str = NOTICE


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0).casefold().replace("’", "'"), m.start(), m.end()) for m in _WORD.finditer(text)]


def _is_quoted(text: str, start: int, end: int) -> bool:
    before, after = text[:start], text[end:]
    for opening, closing in _QUOTES:
        if opening == closing:
            inside = before.count(opening) % 2 == 1
        else:
            inside = before.rfind(opening) > before.rfind(closing)
        if inside and closing in after[:200]:
            return True
    return False


def _cited(text: str, start: int, end: int) -> bool:
    if _is_quoted(text, start, end):
        return True
    tail = text[end:end + 120]
    sentence_end = re.search(r"[.!?](?:\s|$)", tail)
    window = tail[: sentence_end.end() if sentence_end else 120]
    return bool(_CITATION_AFTER.search(window) or re.search(r"\[@[^\]]+\]", window))


def analyze(label: str, segments: list[tuple[str | None, str]], sources: list[tuple[str, str]],
            min_words: int = 8, language: str = "fr") -> SimilarityReport:
    """segments : (emplacement, texte) du texte analysé ; sources : (nom, texte) des documents de comparaison."""
    n = max(5, min(min_words, 30))
    index: dict[tuple[str, ...], set[int]] = defaultdict(set)
    for number, (_, source_text) in enumerate(sources):
        words = [t[0] for t in _tokens(source_text)]
        for i in range(len(words) - n + 1):
            index[tuple(words[i:i + n])].add(number)
    passages: list[SimilarPassage] = []
    matched_total = 0
    per_source: dict[int, int] = defaultdict(int)
    total_words = 0
    for location, text in segments:
        tokens = _tokens(text)
        total_words += len(tokens)
        words = [t[0] for t in tokens]
        covered = [set() for _ in tokens]
        for i in range(len(words) - n + 1):
            found = index.get(tuple(words[i:i + n]))
            if found:
                for k in range(i, i + n):
                    covered[k] |= found
        i = 0
        while i < len(tokens):
            if not covered[i]:
                i += 1
                continue
            j = i
            common = set(covered[i])
            while j + 1 < len(tokens) and covered[j + 1] & common:
                j += 1
                common &= covered[j]
            length = j - i + 1
            source = min(common) if common else min(covered[i])
            start, end = tokens[i][1], tokens[j][2]
            cited = _cited(text, start, end)
            passages.append(SimilarPassage(location=location, text=text[start:end][:500], source=sources[source][0],
                                           words=length, cited=cited,
                                           status="cité" if cited else "citation_manquante"))
            matched_total += length
            per_source[source] += length
            i = j + 1
    # répétitions internes : phrases identiques (≥ 6 mots) répétées
    seen: dict[str, list[str]] = defaultdict(list)
    for location, text in segments:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            key = " ".join(w for w, _, _ in _tokens(sentence))
            if len(key.split()) >= 6:
                seen[key].append(location or "texte")
    repetitions = [Repetition(text=k[:300], occurrences=len(v), locations=v[:6]) for k, v in seen.items() if len(v) > 1]
    style_breaks: list[str] = []
    if len(segments) >= 3:
        from academic_writer.ai_detection.stylometry import analyze_style

        style = analyze_style([(loc or f"partie {i + 1}", t) for i, (loc, t) in enumerate(segments) if t.strip()],
                              language)
        style_breaks = [ind.observation for ind in style.indicators if ind.type == "rupture_de_style"]
    total = max(total_words, 1)
    overlaps = sorted((SourceOverlap(source=sources[s][0], matched_words=w, share=round(w / total, 3))
                       for s, w in per_source.items()), key=lambda o: -o.matched_words)
    passages.sort(key=lambda p: (p.cited, -p.words))
    return SimilarityReport(label=label, words=total_words, min_words=n, overall_share=round(matched_total / total, 3),
                            sources=overlaps, passages=passages[:80],
                            missing_citations=sum(1 for p in passages if not p.cited),
                            repetitions=repetitions[:30], style_breaks=style_breaks)
