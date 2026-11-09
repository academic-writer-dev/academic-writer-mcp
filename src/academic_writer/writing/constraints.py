"""Restriction des sources imposée par l'enseignant, détectée dans les consignes (fr / ru / en).

« Répondez uniquement à partir du cours », « только по материалам лекций », « use only the lecture notes »
→ ``course_only`` ; « les sources externes sont autorisées », « допускается использование дополнительной
литературы » → ``external_allowed``.
"""

from __future__ import annotations

import re

_I = re.IGNORECASE

_TEACHER_MATERIAL = (r"(?:la |le |les |l['’])?(?:cours|explications?|notes?|supports?|polycopiés?|diapositives|"
                     r"documents?\s+(?:fournis|distribués|du cours)|enseignant|professeur)")

COURSE_ONLY = re.compile(
    r"(?:uniquement|seulement|exclusivement)\s+(?:à partir|sur la base|en (?:vous )?(?:appuyant|basant)|au moyen)\s+"
    r"(?:de |du |des |d['’]|sur )?" + _TEACHER_MATERIAL
    + r"|(?:à partir|sur la base)\s+(?:du |des |de )?" + _TEACHER_MATERIAL + r"\s+(?:uniquement|seulement|exclusivement)"
    r"|sans\s+(?:utiliser\s+|recourir\s+à\s+|consulter\s+)?(?:de |d['’]|des |aucune?\s+)?(?:autres?\s+)?"
    r"(?:sources?|documents?|ressources?|références?)\s+(?:externes?|extérieur\w*|supplémentaires?)"
    r"|n['’]utilisez\s+(?:pas|aucune?)\s+(?:d['’]autres?\s+|de\s+)?(?:sources?|documents?|ressources?|internet)"
    r"|(?:только|исключительно)\s+(?:по|на основе|на основании|с использованием|используя|из)\s+"
    r"(?:материал\w*|лекци\w*|конспект\w*|учебн\w*\s+пособи\w*|методическ\w*|объяснени\w*|курс\w*|презентаци\w*)"
    r"|используя\s+только\s+(?:материал|лекци|конспект|методическ|курс)\w*"
    r"|без\s+(?:использования|привлечения)\s+(?:посторонн|сторонн|внешн|други|дополнительн)\w*\s+"
    r"(?:источник|материал|литератур)\w*"
    r"|\b(?:use|using|based on|from|refer to)\s+(?:only|solely|exclusively)\s+(?:the\s+)?(?:lecture|course|class|"
    r"provided|teacher|instructor|handout)"
    r"|\b(?:only|solely|exclusively)\s+(?:use|using|from|on|based on)\s+(?:the\s+)?(?:lecture|course|class|provided|"
    r"teacher|instructor|handout)"
    r"|\b(?:do not|don['’]t|must not|may not)\s+(?:use|consult)\s+(?:any\s+)?(?:external|outside|other|additional)\s+"
    r"(?:sources|materials|references|resources)|\bno\s+(?:external|outside)\s+(?:sources|materials|references)", _I)

EXTERNAL_ALLOWED = re.compile(
    r"sources?\s+(?:externes?|extérieures?|complémentaires?)\s+(?:sont\s+|est\s+)?(?:autorisée?s?|permises?|acceptée?s?)"
    r"|vous\s+pouvez\s+(?:utiliser|consulter|vous appuyer sur)\s+(?:d['’]autres|des|toute)\s+(?:sources?|références?|"
    r"documents?)|recherche\s+(?:documentaire|bibliographique)\s+(?:personnelle|complémentaire)"
    r"|(?:допускается|разрешается|можно|рекомендуется)\s+(?:использовать|привлекать|использование|привлечение)\s+"
    r"(?:дополнительн|други|внешн|сторонн)\w*\s+(?:источник|литератур|материал)\w*"
    r"|\b(?:external|outside|additional)\s+(?:sources|references|materials)\s+(?:are\s+)?(?:allowed|permitted|"
    r"welcome|accepted)|\byou\s+may\s+(?:use|consult)\s+(?:other|additional|external)\s+(?:sources|references)", _I)


def source_constraint(sentence: str) -> str | None:
    """« course_only », « external_allowed » ou None."""
    if COURSE_ONLY.search(sentence):
        return "course_only"
    if EXTERNAL_ALLOWED.search(sentence):
        return "external_allowed"
    return None
