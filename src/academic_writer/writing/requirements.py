"""Extraction heuristique des exigences dans des consignes (fr / ru / en).

Méthode déterministe et explicable : chaque exigence garde la phrase source, le document
et la page. Les résultats sont des PROPOSITIONS que l'utilisateur confirme ou rejette.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from academic_writer.document.model import ExtractedDocument

_I = re.IGNORECASE

TASK_START = re.compile(
    r"^\s*(?:\d{1,2}\s*[.)]\s+|[a-zа-я]\)\s+|"
    r"(?:задач[аи]|задани[ея]|вопрос|пункт|exercice|question|t[aâ]che|partie|task|problem|part|step|étape|этап)"
    r"\s*(?:№\s*)?\d+)", _I)
IMPERATIVE = re.compile(
    r"^\s*(?:\d{1,2}\s*[.)]\s*)?(?:calculer|déterminer|tracer|rédiger|analyser|expliquer|montrer|démontrer|comparer|"
    r"proposer|décrire|justifier|dimensionner|concevoir|réaliser|présenter|identifier|vérifier|établir|"
    r"определить|рассчитать|построить|выполнить|провести|найти|описать|разработать|составить|обосновать|"
    r"проанализировать|исследовать|вычислить|подобрать|спроектировать|оформить|проверить|сравнить|"
    r"calculate|determine|draw|write|analy[sz]e|explain|show|prove|compare|propose|describe|justify|design|"
    r"identify|verify|present|develop|evaluate)\b", _I)
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
SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-ZА-ЯЁÀ-Ý0-9])")


@dataclass
class Candidate:
    kind: str
    text: str
    value: str | None
    page: int | None


def _sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()] if len(text) > 220 else [text]


def classify(sentence: str, is_list_item: bool = False) -> list[tuple[str, str | None]]:
    """Renvoie les (type, valeur) détectés dans une phrase ; une phrase peut porter plusieurs exigences."""
    found: list[tuple[str, str | None]] = []
    if TASK_START.match(sentence) or IMPERATIVE.match(sentence) or (is_list_item and IMPERATIVE.search(sentence)):
        found.append(("task", None))
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
    if STRUCTURE.search(sentence) and not any(k == "task" for k, _ in found):
        found.append(("structure", None))
    data = DATA.findall(sentence)
    if data:
        found.append(("data", "; ".join(f"{n} = {v} {u}".strip() for n, v, u in data[:8])))
    return found


def extract_candidates(document: ExtractedDocument) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for block in document.blocks:
        if block.type in ("image",):
            continue
        if block.type == "table" and block.table_index:
            table = document.tables[block.table_index - 1]
            if any(any(ch.isdigit() for ch in cell) for row in table.rows for cell in row):
                preview = " / ".join(" | ".join(c for c in row if c) for row in table.rows[:4])
                key = ("data", preview)
                if key not in seen:
                    seen.add(key)
                    candidates.append(Candidate("data", f"Tableau {table.index} : {preview}"[:600],
                                                f"tableau {table.index}", block.page))
            continue
        for sentence in _sentences(block.text):
            if len(sentence) < 3:
                continue
            for kind, value in classify(sentence, block.type == "list_item"):
                key = (kind, sentence)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(Candidate(kind, sentence[:600], value, block.page))
    return candidates
