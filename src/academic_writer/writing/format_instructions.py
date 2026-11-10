"""Consignes de MISE EN FORME de l'enseignant (fr / ru / en) → réglages appliqués au document.

Exemples reconnus : « Times New Roman 14, interligne 1,5 », « marges : gauche 3 cm, droite 1,5 cm »,
« поля: левое — 30 мм, правое — 15 мм », « абзацный отступ 1,25 см », « выравнивание по ширине »,
« numéros de page en bas au centre », « références selon APA 7 / ГОСТ Р 7.0.5 », « remettre en PDF ».

Chaque réglage devient une exigence « format » (valeur « propriété=valeur ») que l'utilisateur peut confirmer ou
rejeter ; tant qu'elle n'est pas rejetée, elle PRIME sur le gabarit par défaut (ordre : consignes de l'enseignant
> gabarit de l'établissement > norme).
"""

from __future__ import annotations

import re

_I = re.IGNORECASE
_NUM = r"(\d{1,2}(?:[.,]\d{1,2})?)"

FONTS = re.compile(r"\b(Times New Roman|Arial|Calibri|Cambria|Garamond|Georgia|Helvetica|Verdana|Tahoma|"
                   r"PT Astra Serif|PT Serif|Liberation Serif|Book Antiqua|Palatino(?: Linotype)?|Century Gothic)\b", _I)
_SIZE_CONTEXT = re.compile(r"(?:taille|police|corps|caractères?|кегл\w*|шрифт\w*|размер\w*|font(?:\s+size)?|"
                           r"point size|" + FONTS.pattern[2:-2] + r")[^.;\d]{0,25}?" + _NUM
                           + r"\s*(?:pt|points?|пт|п\.|пунктов)?(?![\d.,]*\s*(?:cm|см|mm|мм|%))", _I)
_SIZE_UNIT = re.compile(_NUM + r"\s*(?:pt|points?|пт|пунктов)\b", _I)
_NOT_BODY = re.compile(r"\b(?:tableau|table|таблиц|note|сноск|footnote|titre|заголов|heading|légende|caption|подпис)\w*",
                       _I)

_SPACING_VALUE = re.compile(r"(?:interligne|interlignage|межстрочн\w*\s+интервал\w*|интервал\w*|line spacing|spacing)"
                            r"[^.;\d]{0,15}?" + _NUM, _I)
_SPACING_WORDS = (
    (re.compile(r"interligne\s+(?:et\s+demi|1\s*1/2)|полуторн\w*|one[- ]and[- ]a[- ]half", _I), 1.5),
    (re.compile(r"(?:interligne|interlignage)\s+double|double[- ]interligne|двойн\w*\s+(?:межстрочн\w*\s+)?интервал|"
                r"double[- ]spac\w*", _I), 2.0),
    (re.compile(r"(?:interligne|interlignage)\s+simple|одинарн\w*\s+(?:межстрочн\w*\s+)?интервал|single[- ]spac\w*", _I),
     1.0),
)
_INDENT = re.compile(r"(?:retrait|alinéa|абзацн\w*\s+отступ|отступ\w*\s+(?:первой\s+строки|абзаца)|красн\w*\s+строк\w*|"
                     r"(?:first[- ]line\s+)?indent\w*)[^.;\d]{0,25}?" + _NUM + r"\s*(cm|см|mm|мм|in(?:ch(?:es)?)?|\")", _I)
_ALIGN = (
    (re.compile(r"justifi\w*|по\s+ширине|justified|full justification", _I), "justify"),
    (re.compile(r"align\w*\s+à\s+gauche|fer\s+à\s+gauche|по\s+левому\s+краю|left[- ]align\w*|align\w* left", _I), "left"),
)
_PAGES = (
    (re.compile(r"(?:en\s+)?bas\s+(?:de\s+(?:la\s+)?page\s+)?(?:au\s+)?(?:centre|centr\w*)|внизу\s+(?:страницы\s+)?"
                r"(?:по\s+)?(?:центру|центре|середин\w*)|(?:в\s+)?центре\s+нижн\w*|нижн\w*\s+част\w*\s+.{0,20}"
                r"(?:по\s+)?центр\w*|bottom[- ]cent(?:er|re)|cent(?:er|re)d?\s+at\s+the\s+bottom", _I), "bottom_center"),
    (re.compile(r"(?:en\s+)?bas\s+(?:de\s+(?:la\s+)?page\s+)?à\s+droite|внизу\s+(?:страницы\s+)?справа|"
                r"правом\s+нижн\w*|bottom[- ]right", _I), "bottom_right"),
    (re.compile(r"(?:en\s+)?haut\s+(?:de\s+(?:la\s+)?page\s+)?à\s+droite|вверху\s+(?:страницы\s+)?справа|"
                r"правом\s+верхн\w*|top[- ]right", _I), "top_right"),
)
_PAGE_CONTEXT = re.compile(r"num[ée]ro\w*\s+(?:de\s+)?pages?|pagination|нумерац\w*|номер\w*\s+страниц|page\s+numbers?|"
                           r"paginat\w*", _I)
_STYLES = (
    (re.compile(r"ГОСТ\s*Р?\s*7\.0\.(?:5|100)|ГОСТ\s*7\.1\b", _I), "gost"),
    (re.compile(r"\bAPA\b", _I), "apa"), (re.compile(r"\bIEEE\b", _I), "ieee"),
    (re.compile(r"\bISO\s*690\b", _I), "iso690"), (re.compile(r"\bVancouver\b", _I), "vancouver"),
    (re.compile(r"\bChicago\b", _I), "chicago"), (re.compile(r"\bHarvard\b", _I), "harvard"),
)
_STYLE_CONTEXT = re.compile(r"référen\w*|bibliograph\w*|citation\w*|norme|style|список|литератур\w*|ссылк\w*|"
                            r"оформ\w*|reference\w*|citing|cite", _I)
_FILE = (
    (re.compile(r"(?:en|au)\s+(?:format\s+)?PDF|format\s+PDF|в\s+формате\s+PDF|PDF\s+(?:format|file)|\.pdf\b", _I), "pdf"),
    (re.compile(r"(?:en|au)\s+(?:format\s+)?(?:Word|docx)|format\s+(?:Word|docx)|в\s+формате\s+(?:Word|docx?)|"
                r"\.docx?\b|Word\s+(?:format|file|document)", _I), "docx"),
)
_SIDES = {
    "left": r"gauche|лев\w*|left", "right": r"droite|прав\w*|right",
    "top": r"haut\w*|supérieur\w*|верхн\w*|top", "bottom": r"bas\b|inférieur\w*|нижн\w*|bottom",
}
_MARGIN_CONTEXT = re.compile(r"marges?|пол[яей]\b|поля|margins?", _I)
_LENGTH = _NUM + r"\s*-?\s*(cm|см|mm|мм|in(?:ch(?:es)?)?\b|\"|дюйм\w*)"


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def _to_mm(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit in ("cm", "см"):
        return round(value * 10, 1)
    if unit.startswith(("in", '"', "дюйм")):
        return round(value * 25.4, 1)
    return round(value, 1)


def _margins(sentence: str) -> dict[str, float]:
    if not _MARGIN_CONTEXT.search(sentence):
        return {}
    found: dict[str, float] = {}
    for side, words in _SIDES.items():
        match = re.search(rf"(?:{words})[^.;\d]{{0,20}}?{_LENGTH}", sentence, _I)
        if match:
            found[side] = _to_mm(_number(match.group(1)), match.group(2))
    if not found:
        match = re.search(rf"(?:marges?|пол[яей]|поля|margins?)[^.;\d]{{0,25}}?{_LENGTH}", sentence, _I) or \
            re.search(rf"{_LENGTH}\s*(?:de\s+)?(?:marges?|margins?)", sentence, _I)
        if match:
            value = _to_mm(_number(match.group(1)), match.group(2))
            found = {side: value for side in ("top", "bottom", "left", "right")}
    return {k: v for k, v in found.items() if 5 <= v <= 60}


def _size(sentence: str) -> float | None:
    for pattern in (_SIZE_CONTEXT, _SIZE_UNIT):
        for match in pattern.finditer(sentence):
            start = max(sentence.rfind(",", 0, match.start()), sentence.rfind(";", 0, match.start())) + 1
            ends = [i for i in (sentence.find(",", match.end()), sentence.find(";", match.end())) if i >= 0]
            if _NOT_BODY.search(sentence[start:min(ends) if ends else len(sentence)]):
                continue  # taille des tableaux, notes ou titres, pas du texte courant
            value = _number(match.group(match.lastindex))
            if 8 <= value <= 20:
                return value
    return None


def parse_format(sentence: str) -> list[str]:
    """Réglages de mise en forme d'une phrase de consignes, sous la forme « propriété=valeur »."""
    found: list[str] = []
    font = FONTS.search(sentence)
    if font:
        found.append(f"font={font.group(1)}")
    size = _size(sentence)
    if size:
        found.append(f"size_pt={size:g}")
    spacing = next((value for pattern, value in _SPACING_WORDS if pattern.search(sentence)), None)
    if spacing is None:
        match = _SPACING_VALUE.search(sentence)
        if match and 1.0 <= _number(match.group(1)) <= 3.0:
            spacing = _number(match.group(1))
    if spacing:
        found.append(f"line_spacing={spacing:g}")
    margins = _margins(sentence)
    if margins:
        found.append("margins_mm=" + ",".join(f"{k}:{v:g}" for k, v in margins.items()))
    indent = _INDENT.search(sentence)
    if indent:
        value_mm = _to_mm(_number(indent.group(1)), indent.group(2))
        if 0 <= value_mm <= 30:
            found.append(f"first_line_indent_cm={value_mm / 10:g}")
    align = next((value for pattern, value in _ALIGN if pattern.search(sentence)), None)
    if align:
        found.append(f"align={align}")
    if _PAGE_CONTEXT.search(sentence):
        position = next((value for pattern, value in _PAGES if pattern.search(sentence)), None)
        if position:
            found.append(f"page_numbers={position}")
    if _STYLE_CONTEXT.search(sentence):
        style = next((value for pattern, value in _STYLES if pattern.search(sentence)), None)
        if style:
            found.append(f"citation_style={style}")
    file_format = next((value for pattern, value in _FILE if pattern.search(sentence)), None)
    if file_format:
        found.append(f"file_format={file_format}")
    return found


_LABELS = {"font": "police", "size_pt": "taille (pt)", "line_spacing": "interligne",
           "margins_mm": "marges (mm)", "first_line_indent_cm": "retrait de 1re ligne (cm)", "align": "alignement",
           "page_numbers": "numéros de page", "citation_style": "style des références", "file_format": "format de remise"}


def overrides(values: list[str]) -> tuple[dict, list[str]]:
    """Réglages (« propriété=valeur ») → modifications du gabarit + description lisible ; la dernière consigne
    d'une même propriété l'emporte, les marges partielles complètent celles du gabarit."""
    update: dict = {}
    margins: dict[str, float] = {}
    applied: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        try:
            if key == "font":
                update["font"] = value
            elif key in ("size_pt", "line_spacing", "first_line_indent_cm"):
                update[key] = float(value)
            elif key == "margins_mm":
                margins.update({side: float(v) for side, v in (part.split(":") for part in value.split(","))})
            elif key in ("align", "page_numbers"):
                update[key] = value
            elif key in ("citation_style", "file_format"):
                pass  # utilisés à l'export, pas dans le gabarit de page
            else:
                continue
        except ValueError:
            continue
        applied[key] = value
    if margins:
        update["margins_mm"] = margins
    return update, [f"{_LABELS[k]} : {v}" for k, v in applied.items()]


def setting(values: list[str], key: str) -> str | None:
    found = [item.split("=", 1)[1] for item in values if item.startswith(key + "=")]
    return found[-1] if found else None
