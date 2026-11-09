"""Gabarits de mise en forme (indicatifs : les exigences de l'établissement priment toujours)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HeadingStyle(BaseModel):
    size_pt: float
    bold: bool = True
    uppercase: bool = False
    align: Literal["left", "center", "justify"] = "left"
    indent: bool = True  # retrait de première ligne (titres de sections ГОСТ)
    space_before_pt: float = 12
    space_after_pt: float = 12


class FormatPreset(BaseModel):
    id: str
    label: str
    standard: str
    font: str = "Times New Roman"
    size_pt: float
    line_spacing: float = Field(description="Multiple de l'interligne simple (1.5, 2.0...).")
    first_line_indent_cm: float
    margins_mm: dict[str, float] = Field(description="top, bottom, left, right")
    align: Literal["left", "justify"] = "justify"
    space_after_pt: float = 0
    page_numbers: Literal["bottom_center", "bottom_right", "top_right"] = "bottom_center"
    number_title_page: bool = False
    number_headings: bool = Field(default=True, description="Numéroter 1, 1.1 les sections du corps.")
    heading_number_dot: bool = Field(default=False, description="« 1. Titre » (fr) ou « 1 Titre » (ГОСТ).")
    structural: HeadingStyle = Field(description="Éléments structurels non numérotés (Введение, Заключение...).")
    headings: list[HeadingStyle] = Field(description="Titres des niveaux 1, 2, 3.")
    figure_caption: str = Field(description="Gabarit de légende de figure (sous la figure, centrée).")
    table_caption: str = Field(description="Gabarit de titre de tableau (au-dessus, à gauche).")
    list_marker: str = "–"
    table_font_size_pt: float | None = None
    headings_no_final_period: bool = True
    notes: list[str] = Field(default_factory=list)


_GOST_STRUCTURAL = HeadingStyle(size_pt=14, bold=True, uppercase=True, align="center", indent=False)
_GOST_HEADINGS = [HeadingStyle(size_pt=14, bold=True), HeadingStyle(size_pt=14, bold=True),
                  HeadingStyle(size_pt=14, bold=False, space_before_pt=6, space_after_pt=6)]

PRESETS: dict[str, FormatPreset] = {
    "gost_7_32": FormatPreset(
        id="gost_7_32", label="ГОСТ 7.32-2017 — отчёт, курсовая, лабораторная (14 пт)",
        standard="ГОСТ 7.32-2017 (структура и оформление отчётов), ГОСТ 2.105-2019 (текстовые документы)",
        size_pt=14, line_spacing=1.5, first_line_indent_cm=1.25,
        margins_mm={"top": 20, "bottom": 20, "left": 30, "right": 15},
        structural=_GOST_STRUCTURAL, headings=_GOST_HEADINGS,
        figure_caption="Рисунок {n} – {title}", table_caption="Таблица {n} – {title}", table_font_size_pt=12,
        notes=["Титульный лист входит в нумерацию, номер на нём не ставится.",
               "Заголовки структурных элементов — прописными, по центру ; разделы — с абзацного отступа, без точки.",
               "Шрифт не менее 12 пт допускается ГОСТ 7.32 ; проверьте требования кафедры."]),
    "gost_7_32_12": FormatPreset(
        id="gost_7_32_12", label="ГОСТ 7.32-2017 — вариант 12 пт",
        standard="ГОСТ 7.32-2017", size_pt=12, line_spacing=1.5, first_line_indent_cm=1.25,
        margins_mm={"top": 20, "bottom": 20, "left": 30, "right": 15},
        structural=_GOST_STRUCTURAL.model_copy(update={"size_pt": 12}),
        headings=[h.model_copy(update={"size_pt": 12}) for h in _GOST_HEADINGS],
        figure_caption="Рисунок {n} – {title}", table_caption="Таблица {n} – {title}", table_font_size_pt=10),
    "fr_universitaire": FormatPreset(
        id="fr_universitaire", label="Usage universitaire francophone (Times 12, interligne 1,5)",
        standard="Usages courants (NF Z 41-006 pour la présentation des thèses) — consignes de l'établissement",
        size_pt=12, line_spacing=1.5, first_line_indent_cm=1.0,
        margins_mm={"top": 25, "bottom": 25, "left": 25, "right": 25},
        heading_number_dot=True,
        structural=HeadingStyle(size_pt=16, bold=True, align="center", indent=False),
        headings=[HeadingStyle(size_pt=16, bold=True, indent=False), HeadingStyle(size_pt=14, bold=True, indent=False),
                  HeadingStyle(size_pt=12, bold=True, indent=False)],
        figure_caption="Figure {n} – {title}", table_caption="Tableau {n} – {title}"),
    "apa7": FormatPreset(
        id="apa7", label="APA 7 (Times 12, double interligne)",
        standard="Publication Manual of the APA, 7th ed.", size_pt=12, line_spacing=2.0, first_line_indent_cm=1.27,
        margins_mm={"top": 25.4, "bottom": 25.4, "left": 25.4, "right": 25.4}, align="left",
        page_numbers="top_right", number_title_page=True, number_headings=False,
        structural=HeadingStyle(size_pt=12, bold=True, align="center", indent=False, space_before_pt=0,
                                space_after_pt=0),
        headings=[HeadingStyle(size_pt=12, bold=True, align="center", indent=False, space_before_pt=0, space_after_pt=0),
                  HeadingStyle(size_pt=12, bold=True, indent=False, space_before_pt=0, space_after_pt=0),
                  HeadingStyle(size_pt=12, bold=True, indent=False, space_before_pt=0, space_after_pt=0)],
        figure_caption="Figure {n}. {title}", table_caption="Table {n}. {title}", list_marker="•"),
    "ieee": FormatPreset(
        id="ieee", label="IEEE (Times 10, interligne simple — une colonne)",
        standard="IEEE Editorial Style Manual (mise en page simplifiée, sans colonnes)", size_pt=10,
        line_spacing=1.0, first_line_indent_cm=0.36, margins_mm={"top": 19, "bottom": 25.4, "left": 17, "right": 17},
        heading_number_dot=True,
        structural=HeadingStyle(size_pt=10, bold=False, uppercase=True, align="center", indent=False,
                                space_before_pt=6, space_after_pt=3),
        headings=[HeadingStyle(size_pt=10, bold=False, uppercase=True, align="center", indent=False,
                               space_before_pt=6, space_after_pt=3),
                  HeadingStyle(size_pt=10, bold=False, indent=False, space_before_pt=6, space_after_pt=3),
                  HeadingStyle(size_pt=10, bold=False, indent=False, space_before_pt=3, space_after_pt=3)],
        figure_caption="Fig. {n}. {title}", table_caption="TABLE {n}. {title}", list_marker="•"),
}
DEFAULT_PRESET = {"ru": "gost_7_32", "fr": "fr_universitaire", "intl": "apa7"}

# Sections non numérotées (éléments structurels) : identifiants du gabarit et intitulés usuels.
STRUCTURAL_IDS = {"title_page", "abstract", "contents", "introduction", "conclusion", "conclusions", "references",
                  "annexes", "appendices", "abbreviations", "terms", "acknowledgements", "assignment",
                  "control_questions"}
STRUCTURAL_TITLES = ("введение", "заключение", "выводы", "вывод", "реферат", "содержание", "список",
                     "приложение", "определения", "обозначения и сокращения", "introduction", "conclusion",
                     "résumé", "bibliographie", "références", "annexe", "references", "abstract", "appendix",
                     "remerciements", "sommaire", "table des matières")
