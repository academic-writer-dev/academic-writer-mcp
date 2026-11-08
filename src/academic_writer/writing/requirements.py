"""Extraction des exigences dans des consignes (fr / ru / en), sur une base STRUCTURELLE.

- Les intertitres donnent le contexte : « Цель работы » → objectif ; « Последовательность /
  Порядок выполнения » → étapes ; « Вопросы для защиты / контрольные вопросы » → questions ;
  « Задания » → tâches.
- Un élément numéroté est traité comme un tout (jamais coupé en phrases) ; un paragraphe non
  numéroté qui suit une étape et la prolonge lui est rattaché.
- Dans une procédure, on distingue les LIVRABLES (« Рассчитать… », « Построить… ») des simples
  MANIPULATIONS (« Повернуть рычаг 16… »).
- Les grandeurs citées sans valeur (m, x, z…) sont relevées : données à demander à l'utilisateur.
Chaque exigence garde sa source (document, page), son numéro d'origine et son intertitre.
Ce sont des PROPOSITIONS que l'utilisateur confirme ou rejette.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from academic_writer.document.model import ExtractedDocument

_I = re.IGNORECASE

NUMBERED = re.compile(r"^\s*(?:(?:задач[аи]|задани[ея]|вопрос|пункт|exercice|question|t[aâ]che|task|problem|step|étape|этап)"
                      r"\s*(?:№\s*)?)?(\d{1,2}(?:\.\d{1,2})?)\s*[.)]\s+", _I)
TASK_START = re.compile(
    r"^\s*(?:\d{1,2}\s*[.)]\s+|[a-zа-я]\)\s+|"
    r"(?:задач[аи]|задани[ея]|exercice|t[aâ]che|task|problem)\s*(?:№\s*)?\d+)", _I)
DELIVERABLE = re.compile(
    r"^\s*(?:\d{1,2}(?:\.\d{1,2})?\s*[.)]\s*)?(?:calculer|déterminer|tracer|construire|rédiger|analyser|expliquer|"
    r"démontrer|comparer|proposer|justifier|dimensionner|concevoir|établir|vérifier|interpréter|"
    r"определить|рассчитать|построить|найти|разработать|составить|обосновать|проанализировать|исследовать|"
    r"вычислить|подобрать|спроектировать|сравнить|доказать|вывести|начертить|изобразить|описать|объяснить|"
    r"calculate|determine|draw|plot|derive|analy[sz]e|explain|prove|compare|justify|design|evaluate|compute)\b", _I)
MANIPULATION = re.compile(
    r"^\s*(?:\d{1,2}(?:\.\d{1,2})?\s*[.)]\s*)?(?:изучить|установить|повернуть|включить|выключить|отключить|"
    r"разомкнуть|замкнуть|снять|положить|переместить|закрепить|ослабить|отвернуть|завернуть|нажать|подключить|"
    r"собрать|разобрать|запустить|остановить|спрофилировать|отметить|проверить|подготовить|зафиксировать|"
    r"installer|placer|tourner|régler|brancher|mettre|retirer|monter|démonter|lancer|arrêter|étudier|relever|"
    r"install|set|turn|connect|switch|place|remove|mount|start|stop|study|record|prepare)\b", _I)
META_TASK = re.compile(r"(?:подготовить|оформить|сдать|защитить)\s+отч[её]т|rédiger le compte[- ]rendu|"
                       r"(?:prepare|write) (?:the|a) report|remettre le rapport", _I)
HEADERS = (
    ("question", re.compile(r"^(?:контрольн\w*\s+)?вопрос\w*|^вопросы\s+для|для\s+защиты|самопроверк|"
                            r"^questions?\b|^review questions|^self[- ]check|^questions de (?:contrôle|révision)", _I)),
    ("step", re.compile(r"^(?:последовательност\w*|порядок|ход)\s+(?:выполнения|работы|проведения)|^выполнение работы|"
                        r"^(?:procédure|mode opératoire|déroulement|manipulation)|^(?:procedure|experimental procedure|steps)\b", _I)),
    ("objective", re.compile(r"^(?:цель|цели)\s+работы|^objectifs?\b|^but du (?:tp|travail)|^(?:aim|objectives?|purpose)\b", _I)),
    ("task", re.compile(r"^(?:задани\w*|задачи|exercices?|travail demandé|tasks?|assignment)\b", _I)),
)
OBJECTIVE_INLINE = re.compile(r"(?:Цель работы|Цели работы|Objectifs? du (?:TP|travail)|Objectifs?|Aim|Objectives?)"
                              r"\s*[:.—-]?\s*(.+?)(?=\s+(?:Последовательность|Порядок выполнения|Ход работы|Оборудование|"
                              r"Procédure|Matériel|Procedure|Equipment)\b|$)", _I)
LENGTH = re.compile(
    r"(\d{1,6})\s*(?:(?:-|–|à|до|to)\s*(\d{1,6})\s*)?(pages?|mots|caractères|страниц\w*|листов|слов\w*|знаков|words|characters)",
    _I)
DATE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")
DEADLINE_WORD = re.compile(r"\b(?:avant le|date limite|à rendre|до|не позднее|срок\w*|сдать|deadline|due|submit by)\b", _I)
VARIANT = re.compile(r"(?:вариант|variante?|variant|var\.)\s*(?:№\s*)?(\d{1,3})", _I)
NORM = re.compile(
    r"(ГОСТ(?:\s*Р)?(?:\s*ИСО)?\s*\d[\d.]*(?:-\d{2,4})?|СТО\s*[\d.\-]+|СП\s*\d[\d.]+|"
    r"NF\s*(?:EN\s*|ISO\s*)?[A-Z]?\s*\d[\d\-]*|ISO\s*\d+(?:-\d+)?|IEC\s*\d+(?:-\d+)?|"
    r"\bAPA\b|\bIEEE\b|\bVancouver\b|\bChicago\b)", _I)
FORMAT = re.compile(
    r"\b(?:шрифт\w*|кегл\w*|интервал\w*|пол[яей]\b|отступ\w*|выравнивани\w*|Times New Roman|Arial|Calibri|"
    r"police|interligne|marges?|justifi\w*|taille de (?:police|caractère)|font|spacing|margins?|\d{1,2}\s*(?:pt|пт)\b)", _I)
STRUCTURE = re.compile(
    r"\b(?:введени\w*|заключени\w*|содержани\w*|реферат\w*|аннотаци\w*|список\s+(?:использованн\w*|литератур\w*)|"
    r"приложени\w*|титульн\w*|introduction|conclusion|bibliograph\w*|sommaire|table des matières|annexes?|"
    r"résumé|abstract|references|appendi\w*|page de (?:garde|titre)|title page|keywords|mots-clés|ключев\w* слов\w*)\b", _I)
DATA = re.compile(r"(?<![\w])([A-Za-zА-Яа-яωαβγδεμφλρστ][\w₀-₉']{0,6})\s*=\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-zА-Яа-я°/·²³%\-*]{0,12})")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-ZА-ЯЁÀ-Ý])")
MATH_CONTEXT = re.compile(r"[·×=±^]|\b\w\s*[·×]\s*\w")
SYMBOL = re.compile(r"(?<![\w])([A-Za-zα-ωΑ-Ω](?:_?[a-z0-9]{1,2})?|х)(?![\w])")
SYMBOL_LIST = re.compile(r"(?<![\w])((?:[A-Za-z](?:_?[a-z0-9]{1,2})?\s*,\s*){2,}[A-Za-z](?:_?[a-z0-9]{1,2})?)(?![\w])")
NOT_SYMBOLS = {"a", "i", "I", "A", "e", "B", "C", "D", "O", "y", "o"}


@dataclass
class Candidate:
    kind: str
    text: str
    value: str | None
    page: int | None
    number: str | None = None
    group_label: str | None = None


def _sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()] if len(text) > 220 else [text]


def header_kind(text: str) -> str | None:
    """Type de section annoncé par un intertitre court (« Вопросы для защиты… »), sinon None."""
    clean = " ".join(text.split()).rstrip(":").strip()
    if not clean or len(clean) > 110 or (clean.endswith(".") and len(clean.split()) > 8) or NUMBERED.match(clean):
        return None
    for kind, pattern in HEADERS:
        if pattern.search(clean):
            return kind
    return None


def classify_secondary(sentence: str) -> list[tuple[str, str | None]]:
    """Exigences autres que tâches/étapes/questions : longueur, échéance, variante, normes, format, structure, données."""
    found: list[tuple[str, str | None]] = []
    match = LENGTH.search(sentence)
    if match:
        low, high, unit = match.groups()
        found.append(("length", f"{low}-{high} {unit}" if high else f"{low} {unit}"))
    if DATE.search(sentence) and DEADLINE_WORD.search(sentence):
        found.append(("deadline", DATE.search(sentence).group(0)))
    match = VARIANT.search(sentence)
    if match:
        found.append(("variant", match.group(1)))
    norms = {" ".join(m.group(1).split()) for m in NORM.finditer(sentence)}
    if norms:
        found.append(("norm", ", ".join(sorted(norms))))
    if FORMAT.search(sentence):
        found.append(("format", None))
    data = DATA.findall(sentence)
    if data:
        found.append(("data", "; ".join(f"{n} = {v} {u}".strip() for n, v, u in data[:8])))
    return found


def classify(sentence: str, is_list_item: bool = False, context: str | None = None) -> list[tuple[str, str | None]]:
    """Classe une phrase ou un élément de liste (compatibilité : utilisée aussi pour du texte libre)."""
    found: list[tuple[str, str | None]] = []
    main = action_kind(sentence, is_list_item, context)
    if main:
        found.append((main, None))
    found += classify_secondary(sentence)
    if STRUCTURE.search(sentence) and main not in ("task", "step", "question"):
        found.append(("structure", None))
    return found


def action_kind(text: str, is_list_item: bool, context: str | None) -> str | None:
    """task / step / question / other (consigne méta) / None pour un élément."""
    stripped = text.strip()
    if context == "question" and (is_list_item or NUMBERED.match(stripped)):
        return "question"
    if stripped.endswith("?") and (is_list_item or NUMBERED.match(stripped)):
        return "question"
    if META_TASK.search(stripped):
        return "other"
    numbered = bool(TASK_START.match(stripped))
    if DELIVERABLE.match(stripped):
        return "task"
    if context == "step" and (is_list_item or numbered):
        return "step"
    if MANIPULATION.match(stripped):
        return "step" if (is_list_item or numbered or context == "step") else None
    if numbered or (is_list_item and context == "task"):
        return "task"
    return None


def _number(text: str) -> str | None:
    match = NUMBERED.match(text)
    return match.group(1) if match else None


def missing_symbols(texts: list[str], data_values: str) -> list[str]:
    """Grandeurs (m, x, z, rb…) citées dans un contexte mathématique sans valeur numérique fournie."""
    found: dict[str, None] = {}
    for text in texts:
        for listing in SYMBOL_LIST.findall(text):
            for symbol in re.split(r"\s*,\s*", listing):
                found.setdefault(symbol, None)
        if MATH_CONTEXT.search(text):
            for symbol in SYMBOL.findall(text):
                found.setdefault("x" if symbol == "х" else symbol, None)
    given = {m.group(1).casefold() for m in DATA.finditer(data_values)}
    return [s for s in found if s not in NOT_SYMBOLS and s.casefold() not in given]


def extract_candidates(document: ExtractedDocument) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    context: str | None = None
    group_label: str | None = None
    last_action: Candidate | None = None

    def add(candidate: Candidate) -> Candidate | None:
        key = (candidate.kind, candidate.text)
        if key in seen:
            return None
        seen.add(key)
        candidates.append(candidate)
        return candidate

    for block in document.blocks:
        if block.type == "image":
            continue
        if block.type == "table" and block.table_index:
            table = document.tables[block.table_index - 1]
            if any(any(ch.isdigit() for ch in cell) for row in table.rows for cell in row):
                preview = " / ".join(" | ".join(c for c in row if c) for row in table.rows[:4])
                add(Candidate("data", f"Tableau {table.index} : {preview}"[:600], f"tableau {table.index}", block.page))
            continue
        text = " ".join(block.text.split())
        if len(text) < 3:
            continue

        heading = header_kind(text) if block.type in ("heading", "paragraph") else None
        if heading:
            context, group_label, last_action = heading, text.rstrip(":"), None
            continue

        objective = OBJECTIVE_INLINE.search(text) if block.type == "paragraph" else None
        if objective and objective.group(1).strip():
            add(Candidate("objective", objective.group(1).strip()[:600], None, block.page, group_label="Цель работы"
                          if re.search(r"[а-я]", text, _I) else "Objectif"))
            for tail_kind in HEADERS:
                if tail_kind[1].search(text[objective.end():].strip()):
                    context = tail_kind[0]

        is_item = block.type == "list_item" or bool(NUMBERED.match(text))
        if is_item:
            kind = action_kind(text, True, context)
            if kind is None and context in ("step", "task", "question"):
                kind = {"step": "step", "task": "task", "question": "question"}[context]
            if kind:
                last_action = add(Candidate(kind, text[:1500], None, block.page, _number(text), group_label))
            for sec_kind, value in classify_secondary(text):
                add(Candidate(sec_kind, text[:600], value, block.page, _number(text), group_label))
            continue

        # Paragraphe non numéroté : prolongement de l'étape précédente ?
        if (last_action is not None and last_action.kind in ("step", "task") and block.type == "paragraph"
                and context in ("step", "task") and not header_kind(text)):
            last_action.text = (last_action.text + " " + text)[:2000]
            for sec_kind, value in classify_secondary(text):
                add(Candidate(sec_kind, text[:600], value, block.page, last_action.number, group_label))
            continue

        last_action = None
        for sentence in _sentences(text):
            if len(sentence) < 3:
                continue
            for kind, value in classify(sentence, False, context):
                if kind in ("step", "question") and context is None:
                    continue
                add(Candidate(kind, sentence[:600], value, block.page, _number(sentence), group_label))
    return candidates
