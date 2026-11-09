"""Génération d'un document Word mis en forme à partir des sections rédigées (Markdown léger).

Markdown pris en charge dans les sections : paragraphes, titres #, listes (- , 1.), tableaux |…|,
**gras**, *italique*, `code`, formules $…$ / $$…$$, légendes « Рисунок 1 – … » / « Таблица 1 – … ».
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

from academic_writer.formatting.presets import STRUCTURAL_IDS, STRUCTURAL_TITLES, FormatPreset, HeadingStyle
from academic_writer.writing.checks import _PLACEHOLDER

_ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
          "justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "right": WD_ALIGN_PARAGRAPH.RIGHT}
_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\$[^$\n]+\$|\[(?:À COMPLÉTER|A COMPLETER|ЗАПОЛНИТЬ|"
                     r"TO COMPLETE|TODO)[^\]]*\])", re.IGNORECASE)
_NUMBERED_TITLE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
_CAPTION = re.compile(r"^\s*(рисунок|рис\.|figure|fig\.|таблица|tableau|table)\s*\d", re.IGNORECASE)
_TABLE_CAPTION = re.compile(r"^\s*(таблица|tableau|table)\s*\d", re.IGNORECASE)
_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]*)\)$")
_LIST = re.compile(r"^\s*(?:([-*•–])|(\d+)[.)])\s+(.*)$")

TITLE_LABELS = {
    "ru": {"author": "Выполнил(а)", "group": "студент(ка) группы", "supervisor": "Проверил(а)",
           "variant": "Вариант", "unwritten": "[Раздел не написан]", "toc": "Обновите оглавление (F9)",
           "image": "[Вставить рисунок]"},
    "fr": {"author": "Réalisé par", "group": "groupe", "supervisor": "Sous la direction de", "variant": "Variante",
           "unwritten": "[Section non rédigée]", "toc": "Mettre à jour la table (F9)", "image": "[Insérer la figure]"},
    "en": {"author": "Prepared by", "group": "group", "supervisor": "Supervisor", "variant": "Variant",
           "unwritten": "[Section not written]", "toc": "Update the table of contents (F9)",
           "image": "[Insert figure]"},
}
TITLE_FIELDS = ("ministry", "organization", "faculty", "department", "document_kind", "discipline", "title",
                "variant", "author", "group", "supervisor", "supervisor_title", "city", "year")
REQUIRED_TITLE_FIELDS = ("organization", "document_kind", "title", "author", "city", "year")


@dataclass
class ExportSection:
    key: str | None
    title: str
    level: int
    text: str | None  # None = non rédigée
    kind: str = "body"  # body, title_page, contents, bibliography


@dataclass
class BuildStats:
    placeholders: int = 0
    unwritten: list[str] = field(default_factory=list)
    images_missing: int = 0
    tables: int = 0
    headings: int = 0
    warnings: list[str] = field(default_factory=list)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("ё", "е")


def is_structural(key: str | None, title: str) -> bool:
    folded = _fold(title).strip()
    return (key in STRUCTURAL_IDS) or any(folded.startswith(_fold(t)) for t in STRUCTURAL_TITLES)


# --- bas niveau (OXML) ------------------------------------------------------------------------

def _set_run_font(run_or_style, name: str, size: float | None = None) -> None:
    font = run_or_style.font
    font.name = name
    if size:
        font.size = Pt(size)
    element = run_or_style.element if hasattr(run_or_style, "element") else run_or_style._element
    rpr = element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attribute), name)
    # les polices du thème (Calibri Light des titres...) l'emportent sinon sur la police explicite
    for attribute in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if fonts.get(qn(attribute)) is not None:
            del fonts.attrib[qn(attribute)]


def _field(paragraph, instruction: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    run._r.append(begin)
    run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    run._r.append(instr)
    run = paragraph.add_run()
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    run._r.append(separate)
    if placeholder:
        paragraph.add_run(placeholder)
    run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(end)


def set_update_fields_on_open(document) -> None:
    settings = document.settings.element
    element = settings.find(qn("w:updateFields"))
    if element is None:
        element = OxmlElement("w:updateFields")
        settings.append(element)
    element.set(qn("w:val"), "true")


def _table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        item = OxmlElement(f"w:{edge}")
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:color"), "000000")
        borders.append(item)
    tbl_pr.append(borders)


# --- styles -----------------------------------------------------------------------------------

def configure_document(document, preset: FormatPreset) -> None:
    section = document.sections[0]
    apply_margins(section, preset)
    normal = document.styles["Normal"]
    _set_run_font(normal, preset.font, preset.size_pt)
    pf = normal.paragraph_format
    pf.line_spacing = preset.line_spacing
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE if preset.line_spacing not in (1.0, 1.5, 2.0) else (
        {1.0: WD_LINE_SPACING.SINGLE, 1.5: WD_LINE_SPACING.ONE_POINT_FIVE, 2.0: WD_LINE_SPACING.DOUBLE}[
            preset.line_spacing])
    pf.first_line_indent = Cm(preset.first_line_indent_cm)
    pf.space_before = Pt(0)
    pf.space_after = Pt(preset.space_after_pt)
    pf.alignment = _ALIGN[preset.align]
    pf.widow_control = True
    for level, style in enumerate(preset.headings, start=1):
        _style_heading(document.styles[f"Heading {level}"], style, preset)
    _add_page_numbers(section, preset)


def apply_margins(section, preset: FormatPreset) -> None:
    section.page_height, section.page_width = Mm(297), Mm(210)
    section.top_margin = Mm(preset.margins_mm["top"])
    section.bottom_margin = Mm(preset.margins_mm["bottom"])
    section.left_margin = Mm(preset.margins_mm["left"])
    section.right_margin = Mm(preset.margins_mm["right"])


def _style_heading(style, spec: HeadingStyle, preset: FormatPreset) -> None:
    _set_run_font(style, preset.font, spec.size_pt)
    style.font.bold = spec.bold
    style.font.italic = False
    style.font.all_caps = spec.uppercase
    style.font.color.rgb = RGBColor(0, 0, 0)
    pf = style.paragraph_format
    pf.alignment = _ALIGN[spec.align]
    pf.first_line_indent = Cm(preset.first_line_indent_cm) if spec.indent else Cm(0)
    pf.space_before = Pt(spec.space_before_pt)
    pf.space_after = Pt(spec.space_after_pt)
    pf.line_spacing = preset.line_spacing
    pf.keep_with_next = True


def _add_page_numbers(section, preset: FormatPreset) -> None:
    section.different_first_page_header_footer = not preset.number_title_page
    container = section.header if preset.page_numbers == "top_right" else section.footer
    paragraph = container.paragraphs[0] if container.paragraphs else container.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if preset.page_numbers == "bottom_center" else WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.first_line_indent = Cm(0)
    _field(paragraph, "PAGE", "1")


def has_page_numbers(document) -> bool:
    for section in document.sections:
        for part in (section.footer, section.header, section.first_page_footer, section.first_page_header):
            xml = part._element.xml if part is not None and part._element is not None else ""
            if "PAGE" in xml:
                return True
    return False


# --- contenu ----------------------------------------------------------------------------------

def add_inline(paragraph, text: str, stats: BuildStats, *, bold: bool | None = None) -> None:
    for piece in _INLINE.split(text):
        if not piece:
            continue
        if _PLACEHOLDER.fullmatch(piece):
            run = paragraph.add_run(piece)
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            stats.placeholders += 1
        elif piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            run = paragraph.add_run(piece[2:-2])
            run.bold = True
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            run = paragraph.add_run(piece[1:-1])
            run.italic = True
        elif piece.startswith("`") and piece.endswith("`"):
            run = paragraph.add_run(piece[1:-1])
            run.font.name = "Courier New"
        elif piece.startswith("$") and piece.endswith("$") and len(piece) > 2:
            run = paragraph.add_run(piece[1:-1])
            run.italic = True
        else:
            run = paragraph.add_run(piece)
        if bold is not None and not run.bold:
            run.bold = bold


def _plain(paragraph, *, align: str = "center", indent: bool = False) -> None:
    paragraph.alignment = _ALIGN[align]
    if not indent:
        paragraph.paragraph_format.first_line_indent = Cm(0)


def heading_text(section: ExportSection, preset: FormatPreset, counters: list[int], level: int,
                 structural: bool) -> str:
    title = section.title.strip()
    if preset.headings_no_final_period:
        title = title.rstrip(".").rstrip()
    if structural or not preset.number_headings or _NUMBERED_TITLE.match(title):
        return title
    index = min(level, 3) - 1
    counters[index] += 1
    for deeper in range(index + 1, 3):
        counters[deeper] = 0
    number = ".".join(str(counters[i]) for i in range(index + 1))
    return f"{number}{'.' if preset.heading_number_dot else ''} {title}"


def add_heading(document, text: str, level: int, preset: FormatPreset, structural: bool, page_break: bool,
                stats: BuildStats) -> None:
    level = max(1, min(level, 3))
    paragraph = document.add_paragraph(style=f"Heading {level}")
    if page_break:
        paragraph.paragraph_format.page_break_before = True
    if structural:
        spec = preset.structural
        paragraph.alignment = _ALIGN[spec.align]
        paragraph.paragraph_format.first_line_indent = Cm(0) if not spec.indent else None
    run = paragraph.add_run(text)
    if structural:
        run.font.all_caps = preset.structural.uppercase
        run.bold = preset.structural.bold
        run.font.size = Pt(preset.structural.size_pt)
    stats.headings += 1


def add_markdown(document, text: str, preset: FormatPreset, base_level: int, language: str, stats: BuildStats,
                 counters: list[int]) -> None:
    labels = TITLE_LABELS.get(language, TITLE_LABELS["fr"])
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.splitlines()
        first = lines[0].strip()
        heading = re.match(r"^(#{1,6})\s+(.+)$", first)
        if heading and len(lines) == 1:
            level = base_level + max(1, len(heading.group(1)) - 1)  # « ## » = sous-section de la section
            pseudo = ExportSection(None, heading.group(2), level, None)
            add_heading(document, heading_text(pseudo, preset, counters, level, False), level, preset, False,
                        False, stats)
            continue
        if first.startswith("|"):
            _add_table(document, lines, preset, stats)
            continue
        if first.startswith("$$"):
            formula = block.strip().strip("$").strip()
            paragraph = document.add_paragraph()
            _plain(paragraph)
            run = paragraph.add_run(formula)
            run.italic = True
            continue
        image = _IMAGE.match(first)
        if image:
            paragraph = document.add_paragraph()
            _plain(paragraph)
            run = paragraph.add_run(labels["image"])
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            stats.images_missing += 1
            if image.group(1):
                caption = document.add_paragraph()
                _plain(caption)
                add_inline(caption, image.group(1), stats)
            continue
        if all(_LIST.match(line) for line in lines if line.strip()):
            for line in lines:
                match = _LIST.match(line)
                if not match:
                    continue
                marker = f"{match.group(2)})" if match.group(2) else preset.list_marker
                paragraph = document.add_paragraph()
                add_inline(paragraph, f"{marker} {match.group(3)}", stats)
            continue
        joined = " ".join(line.strip() for line in lines)
        paragraph = document.add_paragraph()
        if _CAPTION.match(joined) and len(joined) < 250:
            _plain(paragraph, align="left" if _TABLE_CAPTION.match(joined) else "center")
            paragraph.paragraph_format.keep_with_next = bool(_TABLE_CAPTION.match(joined))
        add_inline(paragraph, joined, stats)


def _add_table(document, lines: list[str], preset: FormatPreset, stats: BuildStats) -> None:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines
            if line.strip() and not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", line)]
    if not rows:
        return
    width = max(len(r) for r in rows)
    table = document.add_table(rows=len(rows), cols=width)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _table_borders(table)
    for r, row in enumerate(rows):
        for c in range(width):
            cell = table.cell(r, c)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.paragraph_format.line_spacing = 1.0
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if r == 0 else WD_ALIGN_PARAGRAPH.LEFT
            add_inline(paragraph, row[c] if c < len(row) else "", stats, bold=True if r == 0 else None)
            if preset.table_font_size_pt:
                for run in paragraph.runs:
                    run.font.size = Pt(preset.table_font_size_pt)
    document.add_paragraph()
    stats.tables += 1


def add_title_page(document, fields: dict[str, str], language: str, preset: FormatPreset) -> list[str]:
    """Page de titre à partir des seules informations fournies ; les champs requis manquants restent en blanc."""
    labels = TITLE_LABELS.get(language, TITLE_LABELS["fr"])
    missing = [name for name in REQUIRED_TITLE_FIELDS if not fields.get(name)]

    def line(text: str, *, bold: bool = False, size: float | None = None, upper: bool = False,
             align: str = "center", space_after: float = 0) -> None:
        paragraph = document.add_paragraph()
        _plain(paragraph, align=align)
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_after = Pt(space_after)
        run = paragraph.add_run(text)
        run.bold = bold
        run.font.all_caps = upper
        if size:
            run.font.size = Pt(size)

    blank = "____________________"
    for name in ("ministry", "organization", "faculty", "department"):
        if fields.get(name) or name == "organization":
            line(fields.get(name) or blank, upper=name in ("ministry",), space_after=2)
    for _ in range(5):
        line("")
    line(fields.get("document_kind") or blank, bold=True, size=preset.size_pt + 2, upper=language == "ru",
         space_after=6)
    if fields.get("discipline"):
        line(fields["discipline"], space_after=6)
    line(fields.get("title") or blank, bold=True, size=preset.size_pt + 2, space_after=6)
    if fields.get("variant"):
        line(f"{labels['variant']} {fields['variant']}")
    for _ in range(5):
        line("")
    author = fields.get("author") or blank
    group = f"{labels['group']} {fields['group']}" if fields.get("group") else ""
    line(f"{labels['author']}: {group}".rstrip(": ").rstrip(), align="right")
    line(author, align="right", space_after=10)
    if fields.get("supervisor"):
        line(f"{labels['supervisor']}: {fields.get('supervisor_title', '')}".rstrip(": ").rstrip(), align="right")
        line(fields["supervisor"], align="right")
    for _ in range(4):
        line("")
    line(f"{fields.get('city') or blank} {fields.get('year') or ''}".strip())
    paragraph = document.add_paragraph()
    paragraph.add_run().add_break(WD_BREAK.PAGE)
    return missing


def add_contents(document, title: str, language: str, preset: FormatPreset, stats: BuildStats) -> None:
    # titre en paragraphe ordinaire (et non en style Titre 1) : le sommaire ne se cite pas lui-même
    spec = preset.structural
    heading = document.add_paragraph()
    _plain(heading, align=spec.align)
    heading.paragraph_format.space_after = Pt(spec.space_after_pt)
    run = heading.add_run(title)
    run.bold, run.font.all_caps, run.font.size = spec.bold, spec.uppercase, Pt(spec.size_pt)
    paragraph = document.add_paragraph()
    _plain(paragraph, align="left")
    _field(paragraph, 'TOC \\o "1-3" \\h \\z \\u', TITLE_LABELS.get(language, TITLE_LABELS["fr"])["toc"])


def build_docx(path: Path, sections: list[ExportSection], preset: FormatPreset, language: str,
               title_fields: dict[str, str]) -> BuildStats:
    document = Document()
    configure_document(document, preset)
    stats = BuildStats()
    labels = TITLE_LABELS.get(language, TITLE_LABELS["fr"])
    counters = [0, 0, 0]
    first_body = True
    for section in sections:
        if section.kind == "title_page":
            missing = add_title_page(document, title_fields, language, preset)
            if missing:
                stats.warnings.append("Page de titre : informations manquantes laissées en blanc : "
                                      + ", ".join(missing) + " (rien n'est inventé).")
            continue
        if section.kind == "contents":
            add_contents(document, section.title, language, preset, stats)
            first_body = False
            continue
        structural = is_structural(section.key, section.title)
        page_break = section.level == 1 and not first_body and preset.id != "ieee"
        add_heading(document, heading_text(section, preset, counters, section.level, structural), section.level,
                    preset, structural, page_break, stats)
        first_body = False
        if section.text is None:
            paragraph = document.add_paragraph()
            run = paragraph.add_run(labels["unwritten"])
            run.italic = True
            run.font.color.rgb = RGBColor(0xC0, 0, 0)
            stats.unwritten.append(section.title)
            continue
        if section.kind == "bibliography":
            for entry in [e for e in section.text.split("\n\n") if e.strip()]:
                paragraph = document.add_paragraph()
                add_inline(paragraph, entry.strip(), stats)
            continue
        add_markdown(document, section.text, preset, section.level, language, stats, counters)
    document.sections[0].start_type = WD_SECTION.NEW_PAGE
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))
    return stats
