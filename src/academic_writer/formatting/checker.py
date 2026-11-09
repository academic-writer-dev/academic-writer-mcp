"""Contrôle et application d'un gabarit de mise en forme sur un fichier Word existant (.docx).

Le contrôle lit les valeurs EFFECTIVES (mise en forme directe, puis styles hérités, puis valeurs par défaut du
document). L'application produit une COPIE mise en forme ; l'original n'est jamais modifié.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm
from pydantic import BaseModel, Field

from academic_writer.formatting.docx_writer import _add_page_numbers, _set_run_font, apply_margins, has_page_numbers
from academic_writer.formatting.presets import FormatPreset
from academic_writer.quality.models import QualityIssue, excerpt

_ALIGN_NAMES = {WD_ALIGN_PARAGRAPH.JUSTIFY: "justify", WD_ALIGN_PARAGRAPH.LEFT: "left",
                WD_ALIGN_PARAGRAPH.CENTER: "center", WD_ALIGN_PARAGRAPH.RIGHT: "right", None: "left"}


class PropertyCheck(BaseModel):
    property: str
    expected: str
    dominant: str = Field(description="Valeur la plus fréquente dans le corps du texte.")
    conforming_ratio: float = Field(description="Part des paragraphes du corps conformes (0 à 1).")
    examples: list[str] = Field(default_factory=list, description="Paragraphes non conformes (extraits).")


class FormattingCheck(BaseModel):
    document_id: str
    filename: str
    preset: str
    body_paragraphs: int
    margins_mm: dict[str, float]
    properties: list[PropertyCheck]
    issues: list[QualityIssue]
    notice: str = "Gabarit indicatif : vérifier les exigences de la кафедра / de l'établissement."


class FormattingApplied(BaseModel):
    document_id: str
    output_path: str
    pdf_path: str | None = None
    preset: str
    paragraphs_formatted: int
    headings_kept: int
    page_numbers_added: bool
    messages: list[str]
    notice: str = "Copie mise en forme : l'original est inchangé. Relire la copie (tableaux, figures, listes)."


def _is_heading(paragraph) -> bool:
    name = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
    return name.startswith(("heading", "title", "заголовок", "titre", "toc", "оглавление")) or "caption" in name


def _style_chain(paragraph):
    style = paragraph.style
    while style is not None:
        yield style
        style = style.base_style


def _doc_defaults(document) -> tuple[str | None, float | None]:
    defaults = document.styles.element.find(qn("w:docDefaults"))
    name, size = None, None
    if defaults is not None:
        rpr = defaults.find(f"{qn('w:rPrDefault')}/{qn('w:rPr')}")
        if rpr is not None:
            fonts = rpr.find(qn("w:rFonts"))
            if fonts is not None:
                name = fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi"))
            sz = rpr.find(qn("w:sz"))
            if sz is not None:
                size = int(sz.get(qn("w:val"))) / 2
    return name, size


def _effective(paragraph, defaults) -> dict[str, str]:
    runs = [r for r in paragraph.runs if r.text.strip()]
    font_name = next((r.font.name for r in runs if r.font.name), None)
    font_size = next((r.font.size.pt for r in runs if r.font.size), None)
    line_spacing = paragraph.paragraph_format.line_spacing
    indent = paragraph.paragraph_format.first_line_indent
    align = paragraph.paragraph_format.alignment
    for style in _style_chain(paragraph):
        font_name = font_name or style.font.name
        font_size = font_size or (style.font.size.pt if style.font.size else None)
        pf = style.paragraph_format
        line_spacing = line_spacing if line_spacing is not None else pf.line_spacing
        indent = indent if indent is not None else pf.first_line_indent
        align = align if align is not None else pf.alignment
    font_name = font_name or defaults[0] or "?"
    font_size = font_size or defaults[1] or 11.0
    if line_spacing is not None and not isinstance(line_spacing, float | int):
        line_spacing = round(line_spacing.pt / font_size, 2)  # interligne exact en points
    return {"font": font_name, "size": f"{font_size:g}",
            "line_spacing": f"{float(line_spacing):g}" if line_spacing is not None else "1",
            "indent": f"{indent.cm:.2f}" if indent is not None else "0.00", "align": _ALIGN_NAMES.get(align, "left")}


def body_paragraphs(document) -> list:
    return [p for p in document.paragraphs if len(p.text.strip()) >= 60 and not _is_heading(p)]


def check_docx(path: Path, document_id: str, filename: str, preset: FormatPreset) -> FormattingCheck:
    document = Document(str(path))
    defaults = _doc_defaults(document)
    paragraphs = body_paragraphs(document)
    expected = {"font": preset.font, "size": f"{preset.size_pt:g}", "line_spacing": f"{preset.line_spacing:g}",
                "indent": f"{preset.first_line_indent_cm:.2f}", "align": preset.align}
    labels = {"font": "Police", "size": "Taille (pt)", "line_spacing": "Interligne", "indent": "Retrait 1re ligne (cm)",
              "align": "Alignement"}
    values = [(_effective(p, defaults), p.text) for p in paragraphs]
    properties: list[PropertyCheck] = []
    issues: list[QualityIssue] = []

    def conforms(name: str, value: str) -> bool:
        if name in ("size", "line_spacing", "indent"):
            try:
                return abs(float(value) - float(expected[name])) <= (0.06 if name != "size" else 0.25)
            except ValueError:
                return False
        return value.casefold() == expected[name].casefold()

    for name in expected:
        found = [v[name] for v, _ in values]
        if not found:
            break
        ok = [conforms(name, x) for x in found]
        ratio = sum(ok) / len(ok)
        dominant = Counter(found).most_common(1)[0][0]
        examples = [excerpt(text, 90) + f" ({v[name]})" for (v, text), good in zip(values, ok, strict=True) if not good][:3]
        properties.append(PropertyCheck(property=labels[name], expected=expected[name], dominant=dominant,
                                        conforming_ratio=round(ratio, 3), examples=examples))
        if ratio < 0.9:
            issues.append(QualityIssue(category="mise_en_forme", code=f"{name}_mismatch",
                                       severity="warning" if ratio < 0.5 else "info",
                                       message=f"{labels[name]} : {expected[name]} attendu, {dominant} le plus fréquent "
                                               f"({ratio:.0%} des paragraphes conformes).",
                                       suggestion="Corriger le style « Normal » plutôt que paragraphe par paragraphe."))
    section = document.sections[0]
    margins = {"top": round(section.top_margin.mm, 1), "bottom": round(section.bottom_margin.mm, 1),
               "left": round(section.left_margin.mm, 1), "right": round(section.right_margin.mm, 1)}
    wrong = [f"{side} {margins[side]:g} mm (attendu {preset.margins_mm[side]:g})" for side in margins
             if abs(margins[side] - preset.margins_mm[side]) > 1.0]
    if wrong:
        issues.append(QualityIssue(category="mise_en_forme", code="margins", severity="warning",
                                   message="Marges non conformes : " + ", ".join(wrong) + ".",
                                   suggestion="Mise en page > Marges > Marges personnalisées."))
    if not has_page_numbers(document):
        issues.append(QualityIssue(category="mise_en_forme", code="page_numbers", severity="warning",
                                   message="Aucune numérotation des pages détectée.",
                                   suggestion="Insertion > Numéro de page (bas de page, "
                                              + ("centré)." if preset.page_numbers == "bottom_center" else "à droite).")))
    if preset.headings_no_final_period:
        dotted = [p.text.strip() for p in document.paragraphs if _is_heading(p) and p.text.strip().endswith(".")
                  and not p.text.strip().endswith("..")]
        if dotted:
            issues.append(QualityIssue(category="mise_en_forme", code="heading_period", severity="info",
                                       message=f"Titres terminés par un point ({len(dotted)}) : "
                                               + "; ".join(excerpt(t, 60) for t in dotted[:3]),
                                       suggestion="Supprimer le point final des titres (ГОСТ 7.32 / 2.105)."))
    if not paragraphs:
        issues.append(QualityIssue(category="mise_en_forme", code="no_body", severity="info",
                                   message="Aucun paragraphe de corps de texte assez long pour être analysé."))
    return FormattingCheck(document_id=document_id, filename=filename, preset=preset.id,
                           body_paragraphs=len(paragraphs), margins_mm=margins, properties=properties, issues=issues)


def apply_to_copy(source: Path, output: Path, preset: FormatPreset) -> tuple[int, int, bool]:
    """Applique le gabarit à une copie : marges, style Normal, corps du texte, numéros de page.
    Renvoie (paragraphes mis en forme, titres conservés, numérotation ajoutée)."""
    document = Document(str(source))
    for section in document.sections:
        apply_margins(section, preset)
    normal = document.styles["Normal"]
    _set_run_font(normal, preset.font, preset.size_pt)
    normal.paragraph_format.line_spacing = preset.line_spacing
    normal.paragraph_format.first_line_indent = Cm(preset.first_line_indent_cm)
    formatted = headings = 0
    in_tables = {id(p._p) for table in document.tables for row in table.rows for cell in row.cells
                 for p in cell.paragraphs}
    for paragraph in document.paragraphs:
        if id(paragraph._p) in in_tables or not paragraph.text.strip():
            continue
        if _is_heading(paragraph):
            headings += 1
            for run in paragraph.runs:
                _set_run_font(run, preset.font)
            continue
        pf = paragraph.paragraph_format
        centered = pf.alignment == WD_ALIGN_PARAGRAPH.CENTER  # légendes, formules, page de titre : conservées
        pf.line_spacing = preset.line_spacing
        if not centered:
            pf.first_line_indent = Cm(preset.first_line_indent_cm)
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if preset.align == "justify" else WD_ALIGN_PARAGRAPH.LEFT
        for run in paragraph.runs:
            _set_run_font(run, preset.font, preset.size_pt)
        formatted += 1
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        _set_run_font(run, preset.font, preset.table_font_size_pt or preset.size_pt)
    added = False
    if not has_page_numbers(document):
        _add_page_numbers(document.sections[0], preset)
        added = True
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output))
    return formatted, headings, added


__all__ = ["FormattingApplied", "FormattingCheck", "apply_to_copy", "check_docx"]
