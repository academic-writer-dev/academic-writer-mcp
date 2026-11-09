"""Plans de présentation : structure par occasion (exposé, soutenances, présentation scientifique ou
professionnelle), minutage, et matière sourcée tirée de la rédaction du projet ou d'un document importé."""

from __future__ import annotations

import re

from academic_writer.presentations.models import PlannedSlide

# (clé, type de diapositive, titres fr/ru/en, rôle, poids de temps)
_BLOCKS = {
    "title": ("title", {"fr": "Page de titre", "ru": "Титульный слайд", "en": "Title"}, "Identifier le travail et l'auteur.", 0.5),
    "outline": ("bullets", {"fr": "Plan", "ru": "Содержание доклада", "en": "Outline"}, "Annoncer le déroulé.", 0.5),
    "context": ("bullets", {"fr": "Contexte et problématique", "ru": "Актуальность и постановка проблемы",
                            "en": "Context and problem"}, "Pourquoi ce travail : enjeu et question posée.", 1.2),
    "objectives": ("bullets", {"fr": "Objectif et tâches", "ru": "Цель и задачи", "en": "Aim and tasks"},
                   "Objectif unique et tâches qui y mènent.", 1.0),
    "state_of_art": ("two_columns", {"fr": "État de l'art", "ru": "Обзор существующих решений", "en": "State of the art"},
                     "Ce qui existe, ses limites, la place du travail.", 1.0),
    "method": ("process", {"fr": "Méthodologie", "ru": "Методика исследования", "en": "Methodology"},
               "Démarche en étapes, données, outils.", 1.3),
    "results": ("chart", {"fr": "Résultats", "ru": "Результаты", "en": "Results"},
                "Résultats principaux, chacun appuyé sur une figure ou un tableau.", 2.6),
    "key_figures": ("key_figures", {"fr": "Chiffres clés", "ru": "Ключевые показатели", "en": "Key figures"},
                    "Deux à quatre valeurs marquantes, sourcées.", 0.7),
    "discussion": ("bullets", {"fr": "Discussion", "ru": "Обсуждение результатов", "en": "Discussion"},
                   "Interprétation, comparaison, limites.", 1.0),
    "conclusion": ("conclusion", {"fr": "Conclusion et apports", "ru": "Заключение", "en": "Conclusion"},
                   "Réponse à la question, apports.", 1.0),
    "perspectives": ("bullets", {"fr": "Perspectives", "ru": "Перспективы", "en": "Outlook"}, "Suites possibles.", 0.5),
    "intro": ("bullets", {"fr": "Introduction", "ru": "Введение", "en": "Introduction"}, "Sujet, intérêt, plan.", 1.0),
    "part": ("bullets", {"fr": "Partie", "ru": "Раздел", "en": "Part"}, "Développement argumenté et sourcé.", 2.0),
    "diagnosis": ("bullets", {"fr": "Diagnostic", "ru": "Анализ текущего состояния", "en": "Diagnosis"},
                  "Situation actuelle, chiffres.", 1.2),
    "solution": ("process", {"fr": "Solution proposée", "ru": "Предлагаемое решение", "en": "Proposed solution"},
                 "Démarche et choix.", 1.5),
    "action_plan": ("table", {"fr": "Plan d'action", "ru": "План мероприятий", "en": "Action plan"},
                    "Qui, quoi, quand.", 1.0),
    "references": ("references", {"fr": "Références", "ru": "Список источников", "en": "References"},
                   "Sources citées dans la présentation.", 0.4),
    "questions": ("questions", {"fr": "Merci de votre attention", "ru": "Спасибо за внимание", "en": "Thank you"},
                  "Ouvrir les questions.", 0.0),
}
STRUCTURES = {
    "expose": ["title", "outline", "intro", "part", "part", "key_figures", "conclusion", "references", "questions"],
    "soutenance_licence": ["title", "context", "objectives", "method", "results", "conclusion", "perspectives",
                           "questions"],
    "soutenance_master": ["title", "context", "objectives", "state_of_art", "method", "results", "key_figures",
                          "discussion", "conclusion", "perspectives", "questions"],
    "soutenance_doctorat": ["title", "outline", "context", "objectives", "state_of_art", "method", "results",
                            "key_figures", "discussion", "conclusion", "perspectives", "references", "questions"],
    "presentation_scientifique": ["title", "context", "objectives", "method", "results", "discussion", "conclusion",
                                  "references", "questions"],
    "presentation_professionnelle": ["title", "context", "diagnosis", "key_figures", "solution", "results",
                                     "action_plan", "conclusion", "questions"],
}
_SECTION_HINTS = {
    "context": r"introduc|актуальн|введени|context|problém|постановк|problem",
    "objectives": r"objecti|цел|задач|aim|tâche",
    "state_of_art": r"état de l'art|обзор|state of the art|analyse|аналитическ|literature",
    "method": r"méthod|методик|method|protocole|conception|проектн|расчёт|calcul|matériel|оборудован",
    "results": r"résultat|результат|result|mesure|измерен|validation|обработк",
    "discussion": r"discussion|обсужден|interprétation",
    "conclusion": r"conclusion|заключен|вывод",
    "perspectives": r"perspective|перспектив|outlook",
    "intro": r"introduc|введени",
    "diagnosis": r"diagnostic|анализ|état actuel",
    "solution": r"solution|решени|conception|проект",
}
_NUMBER_WITH_UNIT = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|[A-Za-zА-Яа-я°/·²³]{1,8})?(?=[\s.,;)]|$)")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _material(text: str, limit: int = 5) -> list[str]:
    """Phrases porteuses (avec chiffres d'abord), telles qu'écrites : matière à condenser, jamais à compléter."""
    clean = re.sub(r"\[@[^\]]+\]", "", re.sub(r"[#*_`>|]", " ", text))
    sentences = [s.strip() for s in _SENTENCE.split(" ".join(clean.split())) if 25 <= len(s.strip()) <= 300]
    with_numbers = [s for s in sentences if re.search(r"\d", s)]
    ordered = with_numbers[:3] + [s for s in sentences if s not in with_numbers[:3]]
    return ordered[:limit]


def plan(occasion: str, language: str, duration_minutes: int, sections: list[tuple[str, str]],
         charts: list[tuple[str, str]], has_sources: bool) -> tuple[list[PlannedSlide], list[str]]:
    """sections : (titre, texte) de la rédaction ou du document ; charts : (id, titre)."""
    keys = list(STRUCTURES[occasion])
    if not has_sources and "references" in keys:
        keys.remove("references")
    # nombre de diapositives de résultats et de parties selon la durée (≈ 1 diapositive par minute)
    target = max(5, min(40, round(duration_minutes)))
    extra = max(0, target - len(keys))
    expandable = [k for k in ("results", "part", "method") if k in keys]
    while extra > 0 and expandable:
        for key in expandable:
            if extra <= 0:
                break
            keys.insert(keys.index(key) + 1, key)
            extra -= 1
    weights = [_BLOCKS[k][3] for k in keys]
    total_weight = sum(weights) or 1
    seconds_total = duration_minutes * 60
    used_sections: set[int] = set()
    chart_queue = list(charts)
    planned: list[PlannedSlide] = []
    part_number = 0
    warnings: list[str] = []
    for position, key in enumerate(keys, start=1):
        slide_type, titles, purpose, weight = _BLOCKS[key]
        title = titles.get(language, titles["fr"])
        material: list[str] = []
        origin = None
        hint = _SECTION_HINTS.get(key)
        if key == "part":
            part_number += 1
            candidates = [i for i in range(len(sections)) if i not in used_sections]
            index = candidates[0] if candidates else None
            if index is not None:
                title = sections[index][0]
        elif hint:
            index = next((i for i, (t, _) in enumerate(sections) if i not in used_sections
                          and re.search(hint, t, re.IGNORECASE)), None)
        else:
            index = None
        if index is not None:
            used_sections.add(index)
            origin = sections[index][0]
            material = _material(sections[index][1])
        chart_ids: list[str] = []
        if slide_type == "chart":
            if chart_queue:
                chart_id, chart_title = chart_queue.pop(0)
                chart_ids = [chart_id]
                title = f"{title} — {chart_title}" if chart_title else title
            else:
                slide_type = "bullets"
                warnings.append(f"Diapositive {position} (résultats) : aucun graphique disponible — en créer avec "
                                "create_chart à partir des données, ou présenter un tableau.")
        planned.append(PlannedSlide(position=position, type=slide_type, title=title, purpose=purpose,
                                    seconds=round(seconds_total * weight / total_weight), material=material,
                                    chart_ids=chart_ids, origin=origin))
    if not sections:
        warnings.append("Aucun contenu rédigé ni document : la présentation ne peut contenir que des informations "
                        "vérifiables fournies par l'utilisateur ou trouvées dans des sources (find_works_by_topic) ; "
                        "aucun chiffre ni résultat ne doit être inventé.")
    missing = [p.title for p in planned if not p.material and p.type in ("bullets", "two_columns", "process", "conclusion")
               and sections]
    if missing:
        warnings.append("Sans matière dans la rédaction pour : " + ", ".join(missing[:6])
                        + " — demander le contenu à l'utilisateur ou laisser un marqueur [À COMPLÉTER].")
    return planned, warnings
