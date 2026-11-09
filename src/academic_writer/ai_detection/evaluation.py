"""Évaluation des indices sur un corpus annoté (mesure réelle, jamais théorique).

Organisation attendue :
    <dossier>/humain/*.txt   textes dont l'origine humaine est connue
    <dossier>/ia/*.txt       textes dont la génération par IA est connue
Pour chaque indice : taux de déclenchement sur les textes humains (= faux positifs si l'on s'en
servait comme détecteur) et sur les textes IA (= vrais positifs). Les résultats ne valent que pour
la langue, la discipline et les outils représentés dans le corpus.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from academic_writer.ai_detection.stylometry import analyze_style
from academic_writer.document.text_reader import decode_text


class IndicatorRate(BaseModel):
    indicator: str
    human_rate: float
    ai_rate: float


class EvaluationResult(BaseModel):
    language: str
    human_texts: int
    ai_texts: int
    skipped_short: int
    rates: list[IndicatorRate]
    any_indicator_human_rate: float
    any_indicator_ai_rate: float
    warning: str


def evaluate(folder: Path, language: str) -> EvaluationResult:
    counts = {"humain": Counter(), "ia": Counter()}
    totals = {"humain": 0, "ia": 0}
    any_hit = {"humain": 0, "ia": 0}
    skipped = 0
    for group in ("humain", "ia"):
        for path in sorted((folder / group).glob("*.txt")):
            text, _ = decode_text(path.read_bytes())
            analysis = analyze_style([(path.stem, text)], language)
            if not analysis.indicators and analysis.words < 150:
                skipped += 1
                continue
            totals[group] += 1
            types = {i.type for i in analysis.indicators}
            counts[group].update(types)
            any_hit[group] += bool(types)
    names = sorted(set(counts["humain"]) | set(counts["ia"]))
    rate = lambda group, n: round(n / totals[group], 3) if totals[group] else 0.0  # noqa: E731
    return EvaluationResult(
        language=language, human_texts=totals["humain"], ai_texts=totals["ia"], skipped_short=skipped,
        rates=[IndicatorRate(indicator=n, human_rate=rate("humain", counts["humain"][n]),
                             ai_rate=rate("ia", counts["ia"][n])) for n in names],
        any_indicator_human_rate=rate("humain", any_hit["humain"]), any_indicator_ai_rate=rate("ia", any_hit["ia"]),
        warning="Mesure valable uniquement pour ce corpus (langue, discipline, outils, taille). Un faible écart entre "
                "les deux taux signifie que l'indice ne distingue pas les groupes.",
    )
