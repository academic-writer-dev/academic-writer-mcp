"""Identification de la discipline par score de mots-clés (transparent et explicable).

Le résultat est une SUGGESTION accompagnée des termes trouvés et d'un niveau de
confiance ; la décision appartient toujours à l'utilisateur.

Syntaxe des mots-clés dans les profils : « механизм* » (préfixe, pour les
flexions russes et françaises), « analyse fonctionnelle » (expression),
« plan* de vitesse* » (expression avec préfixes). Casse et accents ignorés.
"""

from __future__ import annotations

import bisect
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from academic_writer.domains.model import DomainProfile

_WORD = re.compile(r"\w+", re.UNICODE)


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ё", "е")


def parse_keyword(keyword: str) -> list[tuple[str, bool]]:
    """« plan* de vitesse* » → [("plan", True), ("de", False), ("vitesse", True)].

    Les mots composés (« génie-civil ») deviennent des expressions de plusieurs mots.
    """
    pieces: list[tuple[str, bool]] = []
    for token in fold(keyword).split():
        is_prefix = token.endswith("*")
        words = _WORD.findall(token.rstrip("*"))
        for position, word in enumerate(words):
            pieces.append((word, is_prefix and position == len(words) - 1))
    return pieces


@dataclass
class KeywordMatch:
    keyword: str
    count: int


@dataclass
class ProfileScore:
    profile: DomainProfile
    score: float
    matches: list[KeywordMatch] = field(default_factory=list)


class TextIndex:
    """Index des mots d'un texte pour compter rapidement mots, préfixes et expressions."""

    def __init__(self, text: str) -> None:
        words = _WORD.findall(fold(text))
        self.word_count = len(words)
        self.counts = Counter(words)
        self.sorted_words = sorted(self.counts)
        self.joined = " " + " ".join(words) + " "

    def count(self, keyword: str) -> int:
        pieces = parse_keyword(keyword)
        if not pieces:
            return 0
        if len(pieces) == 1:
            word, is_prefix = pieces[0]
            return self._prefix_count(word) if is_prefix else self.counts.get(word, 0)
        pattern = " ".join(re.escape(word) + (r"\w*" if is_prefix else "") for word, is_prefix in pieces)
        return len(re.findall(r"(?<= )" + pattern + r"(?= )", self.joined))

    def _prefix_count(self, prefix: str) -> int:
        if len(prefix) < 3:
            return self.counts.get(prefix, 0)
        start = bisect.bisect_left(self.sorted_words, prefix)
        total = 0
        for word in self.sorted_words[start:]:
            if not word.startswith(prefix):
                break
            total += self.counts[word]
        return total


def score_profiles(text: str, profiles: list[DomainProfile]) -> tuple[list[ProfileScore], int]:
    index = TextIndex(text)
    results: list[ProfileScore] = []
    for profile in profiles:
        keywords = {kw for words in profile.keywords.values() for kw in words}
        if not keywords:
            continue
        matches = []
        raw = 0.0
        for keyword in keywords:
            count = index.count(keyword)
            if count:
                matches.append(KeywordMatch(keyword, count))
                raw += 1.0 + math.log(count)
        score = raw / math.sqrt(max(len(keywords), 1) / 20)  # atténue l'avantage des listes longues
        matches.sort(key=lambda m: m.count, reverse=True)
        results.append(ProfileScore(profile=profile, score=round(score, 2), matches=matches))
    results.sort(key=lambda r: r.score, reverse=True)
    return results, index.word_count


def lineage(profile_id: str, profiles: dict[str, DomainProfile]) -> set[str]:
    """Le profil, ses ancêtres (sauf le généraliste) et ses descendants."""
    related = {profile_id}
    current = profiles.get(profile_id)
    while current is not None and current.parent and current.parent != "generaliste":
        related.add(current.parent)
        current = profiles.get(current.parent)
    changed = True
    while changed:
        changed = False
        for candidate in profiles.values():
            if candidate.parent in related and candidate.id not in related:
                related.add(candidate.id)
                changed = True
    return related


def confidence_level(scores: list[ProfileScore], word_count: int,
                     profiles: dict[str, DomainProfile]) -> tuple[str, float]:
    """Renvoie (niveau, écart avec le meilleur candidat d'une autre famille)."""
    if not scores or scores[0].score < 2.0 or word_count < 30:
        return "indéterminée", 0.0
    top = scores[0]
    related = lineage(top.profile.id, profiles)
    rival = next((s for s in scores[1:] if s.profile.id not in related), None)
    gap = top.score / rival.score if rival and rival.score > 0 else 10.0
    if top.score >= 6 and gap >= 1.6:
        return "élevée", gap
    if top.score >= 3.5 and gap >= 1.25:
        return "moyenne", gap
    return "faible", gap
