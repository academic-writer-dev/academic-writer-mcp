"""Détection d'indices d'injection de prompt dans le contenu des documents.

Le contenu d'un document est toujours traité comme des données. Cette détection
sert à avertir l'utilisateur et l'assistant ; elle n'est pas exhaustive.
"""

from __future__ import annotations

import re

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern, re.IGNORECASE))
    for label, pattern in (
        ("en: ignore instructions",
         r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|earlier|all|system)\b.{0,20}\b(instructions?|prompts?|rules?)\b"),
        ("en: role change", r"\byou are now\b|\bfrom now on,? you\b|\bact as (an? )?(ai|assistant|system)\b"),
        ("en: system prompt", r"\bsystem prompt\b|\bdeveloper message\b"),
        ("fr: ignorer les consignes",
         r"\b(ignore[rz]?|oublie[rz]?|néglige[rz]?)\b.{0,30}\b(instructions?|consignes?|règles?)\b.{0,20}\b(précédentes?|ci-dessus|antérieures?|système)\b"),
        ("fr: changement de rôle", r"\btu es (désormais|maintenant)\b|\bà partir de maintenant,? (tu|vous)\b"),
        ("fr: prompt système", r"\bprompt (du )?système\b|\binstructions? système\b"),
        ("ru: игнорировать инструкции",
         r"(игнорируй|игнорируйте|забудь|забудьте|не учитывай)\w*.{0,30}(предыдущ|прошл|все|системн)\w*.{0,20}(инструкц|указани|правил)\w*"),
        ("ru: смена роли", r"\bты теперь\b|\bс этого момента ты\b"),
        ("ru: системный промпт", r"системн\w* (промпт|подсказк|инструкц)\w*"),
    )
)

_INVISIBLE = re.compile("[​‌‍⁠⁢⁣⁤﻿­]")


def scan_text(text: str, location: str | None = None) -> list[str]:
    findings: list[str] = []
    for label, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 30)
            excerpt = " ".join(text[start: match.end() + 30].split())
            where = f" ({location})" if location else ""
            findings.append(f"Indice d'injection de prompt [{label}]{where} : « …{excerpt}… »")
    invisible = len(_INVISIBLE.findall(text))
    if invisible >= 20:
        where = f" ({location})" if location else ""
        findings.append(f"{invisible} caractères invisibles détectés{where} (texte caché possible).")
    return findings
