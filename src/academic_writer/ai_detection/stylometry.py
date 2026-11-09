"""Indices stylistiques (fr / ru / en).

AVERTISSEMENT : ces mesures décrivent un style. Un rédacteur humain peut écrire de façon très
régulière, et un texte produit par IA puis retravaillé peut ne présenter aucun indice. Aucun seuil
n'a été calibré sur un corpus : les niveaux (faible, moyen, fort) sont descriptifs, pas des
probabilités. Les résultats ne doivent jamais servir seuls à conclure.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

Strength = Literal["faible", "moyen", "fort"]

GENERIC_PHRASES = {
    "fr": ["il est important de noter", "il convient de noter", "joue un rôle crucial", "joue un rôle essentiel",
           "dans le monde d'aujourd'hui", "à l'ère du numérique", "en constante évolution", "un large éventail",
           "il est essentiel de", "en fin de compte", "dans un monde en constante", "force est de constater",
           "revêt une importance particulière", "de manière significative", "un enjeu majeur", "plonger dans"],
    "ru": ["в современном мире", "играет важную роль", "играет ключевую роль", "важно отметить", "стоит отметить",
           "следует отметить", "необходимо подчеркнуть", "в целом можно сказать", "широкий спектр",
           "неотъемлемой частью", "в заключение можно сказать", "в условиях современности", "является актуальной",
           "имеет большое значение", "в настоящее время", "таким образом, можно сделать вывод"],
    "en": ["it is important to note", "it is worth noting", "plays a crucial role", "plays a vital role",
           "in today's world", "in the ever-evolving", "a wide range of", "delve into", "it is essential to",
           "in conclusion", "a testament to", "navigate the complexities", "the landscape of", "in the realm of",
           "unlock the potential", "shed light on"],
}
CONNECTORS = {
    "fr": ["de plus", "en outre", "par ailleurs", "ainsi", "cependant", "néanmoins", "en effet", "par conséquent",
           "en conclusion", "enfin", "d'une part", "d'autre part", "toutefois", "de ce fait"],
    "ru": ["кроме того", "более того", "также", "однако", "тем не менее", "таким образом", "следовательно",
           "в результате", "во-первых", "во-вторых", "в-третьих", "в заключение", "при этом", "вместе с тем"],
    "en": ["furthermore", "moreover", "additionally", "however", "therefore", "thus", "consequently", "in addition",
           "firstly", "secondly", "finally", "in conclusion", "nevertheless", "overall"],
}
_SENTENCE = re.compile(r"[^.!?…\n]+[.!?…]+")
_WORD = re.compile(r"\w+", re.UNICODE)
_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$|`[^`]*`", re.DOTALL)
_BOLD_LABEL = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\*\*[^*]{2,60}\*\*\s*[:—–-]", re.MULTILINE)


class Indicator(BaseModel):
    type: str
    strength: Strength
    observation: str
    passages: list[str] = Field(default_factory=list, description="Extraits concernés (courts).")
    value: float | None = Field(default=None, description="Valeur mesurée (descriptive, non calibrée).")


class SegmentProfile(BaseModel):
    index: int
    label: str
    words: int
    mean_sentence: float
    connector_rate: float
    lexical_diversity: float


class StyleAnalysis(BaseModel):
    language: str
    words: int
    sentences: int
    indicators: list[Indicator]
    segments: list[SegmentProfile]
    limits: list[str]


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).replace("ё", "е")


def _clip(text: str, n: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def mattr(words: list[str], window: int = 50) -> float:
    """Diversité lexicale (moyenne mobile du rapport types/occurrences), stable selon la longueur."""
    if len(words) < window:
        return len(set(words)) / len(words) if words else 0.0
    ratios = [len(set(words[i: i + window])) / window for i in range(0, len(words) - window + 1, 10)]
    return sum(ratios) / len(ratios)


def _segment_profile(index: int, label: str, text: str, language: str) -> SegmentProfile | None:
    words = _WORD.findall(_fold(text))
    sentences = [s for s in _SENTENCE.findall(text) if len(_WORD.findall(s)) >= 3]
    if len(words) < 80 or len(sentences) < 3:
        return None
    folded = f" {_fold(text)} "
    connectors = sum(folded.count(f" {_fold(c)} ") + folded.count(f" {_fold(c)},") for c in CONNECTORS.get(language, []))
    return SegmentProfile(index=index, label=label[:80], words=len(words),
                          mean_sentence=round(statistics.mean(len(_WORD.findall(s)) for s in sentences), 1),
                          connector_rate=round(connectors / len(sentences), 2),
                          lexical_diversity=round(mattr(words), 3))


def analyze_style(segments: list[tuple[str, str]], language: str) -> StyleAnalysis:
    """``segments`` : [(intitulé, texte)] — sections d'un document ou paragraphes regroupés."""
    full = "\n\n".join(text for _, text in segments)
    prose = _MATH.sub(" ", full)
    sentences = [s.strip() for s in _SENTENCE.findall(prose) if len(_WORD.findall(s)) >= 3]
    words = _WORD.findall(_fold(prose))
    indicators: list[Indicator] = []
    limits = [
        "Indices stylistiques uniquement : ils ne prouvent ni une rédaction humaine ni une rédaction par IA.",
        "Seuils non calibrés sur un corpus d'évaluation : niveaux descriptifs, pas des probabilités.",
        "Un texte technique (formules, procédures, listes) est naturellement régulier : risque de faux positifs.",
        "Un texte généré puis retravaillé, traduit ou corrigé peut ne présenter aucun indice (faux négatifs).",
    ]
    if len(words) < 150 or len(sentences) < 8:
        limits.insert(0, f"Texte trop court ({len(words)} mots) pour une analyse stylistique significative.")
        return StyleAnalysis(language=language, words=len(words), sentences=len(sentences), indicators=[],
                             segments=[], limits=limits)

    lengths = [len(_WORD.findall(s)) for s in sentences]
    cv = statistics.pstdev(lengths) / statistics.mean(lengths)
    if cv < 0.35:
        indicators.append(Indicator(
            type="regularite_phrases", strength="fort" if cv < 0.25 else "moyen", value=round(cv, 2),
            observation=f"Longueur des phrases très homogène (coefficient de variation {cv:.2f}) : la prose humaine "
                        "alterne en général phrases courtes et longues."))

    folded = f" {_fold(prose)} "
    generic = [(p, folded.count(_fold(p))) for p in GENERIC_PHRASES.get(language, []) if _fold(p) in folded]
    per_thousand = sum(n for _, n in generic) / len(words) * 1000
    if generic and per_thousand >= 1.0:
        indicators.append(Indicator(
            type="formules_generiques", strength="fort" if per_thousand >= 3 else "moyen" if per_thousand >= 1.5 else "faible",
            value=round(per_thousand, 2), passages=[f"« {p} » ×{n}" for p, n in generic[:10]],
            observation=f"Formules génériques fréquentes ({per_thousand:.1f} pour 1000 mots), typiques de textes "
                        "génériques (humains ou automatiques)."))

    starts = Counter(_fold(" ".join(_WORD.findall(s)[:1])) for s in sentences)
    connectors_used = [c for c in CONNECTORS.get(language, []) if f" {_fold(c)} " in folded or f" {_fold(c)}," in folded]
    connector_sentences = sum(1 for s in sentences if any(_fold(s).lstrip().startswith(_fold(c))
                                                          for c in CONNECTORS.get(language, [])))
    rate = connector_sentences / len(sentences)
    if rate >= 0.3:
        indicators.append(Indicator(
            type="transitions_systematiques", strength="fort" if rate >= 0.45 else "moyen", value=round(rate, 2),
            passages=connectors_used[:10],
            observation=f"{rate:.0%} des phrases commencent par un connecteur logique : enchaînement mécanique possible."))
    common_start, count = starts.most_common(1)[0]
    if count / len(sentences) >= 0.2 and len(common_start) > 2:
        indicators.append(Indicator(
            type="debuts_repetes", strength="moyen", value=round(count / len(sentences), 2),
            observation=f"Début de phrase répété : « {common_start} » ({count} phrases sur {len(sentences)})."))

    paragraphs = [p for p in re.split(r"\n\s*\n", prose) if len(_WORD.findall(p)) >= 20]
    if len(paragraphs) >= 5:
        p_lengths = [len(_WORD.findall(p)) for p in paragraphs]
        p_cv = statistics.pstdev(p_lengths) / statistics.mean(p_lengths)
        if p_cv < 0.2:
            indicators.append(Indicator(
                type="paragraphes_uniformes", strength="moyen", value=round(p_cv, 2),
                observation=f"Paragraphes de longueur presque identique (variation {p_cv:.2f})."))

    labels = _BOLD_LABEL.findall(full)
    if len(labels) >= 4:
        indicators.append(Indicator(
            type="listes_etiquetees", strength="faible", value=float(len(labels)),
            observation=f"{len(labels)} éléments de liste du type « **Terme** : explication » : mise en forme "
                        "fréquente dans les réponses d'assistants."))

    trigrams = Counter(tuple(words[i: i + 3]) for i in range(len(words) - 2))
    repeated = [(" ".join(t), n) for t, n in trigrams.most_common(15) if n >= 3 and all(len(w) > 3 for w in t)]
    if len(repeated) >= 3:
        indicators.append(Indicator(
            type="expressions_repetees", strength="faible", value=float(len(repeated)),
            passages=[f"« {t} » ×{n}" for t, n in repeated[:8]],
            observation="Groupes de mots répétés à l'identique."))

    concrete = len(re.findall(r"\d", prose)) / max(1, len(words))
    if concrete < 0.005 and len(words) > 400:
        indicators.append(Indicator(
            type="absence_de_concret", strength="faible", value=round(concrete, 4),
            observation="Très peu de données chiffrées ou de détails concrets : texte général (à interpréter selon "
                        "la nature du document)."))

    profiles = [p for p in (_segment_profile(i, label, text, language) for i, (label, text) in enumerate(segments)) if p]
    if len(profiles) >= 3:
        for metric, label in (("mean_sentence", "longueur moyenne des phrases"), ("lexical_diversity", "diversité lexicale"),
                              ("connector_rate", "densité de connecteurs")):
            values = [getattr(p, metric) for p in profiles]
            mean, stdev = statistics.mean(values), statistics.pstdev(values)
            if stdev == 0:
                continue
            outliers = [p for p in profiles if abs(getattr(p, metric) - mean) / stdev >= 2.0 and len(profiles) >= 4]
            for outlier in outliers[:3]:
                indicators.append(Indicator(
                    type="rupture_de_style", strength="moyen", value=getattr(outlier, metric),
                    passages=[outlier.label],
                    observation=f"La section « {outlier.label} » s'écarte nettement des autres ({label} : "
                                f"{getattr(outlier, metric)} contre {mean:.2f} en moyenne) : changement de rédacteur, "
                                "d'outil ou de source possible."))
    return StyleAnalysis(language=language, words=len(words), sentences=len(sentences), indicators=indicators,
                         segments=profiles, limits=limits)
