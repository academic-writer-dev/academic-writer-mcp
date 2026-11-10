"""Rendu PPTX (python-pptx, licence MIT) : thèmes, mises en page par type de diapositive, notes du présentateur.

Principes de design : format 16:9, marges constantes, une idée par diapositive, hiérarchie (titre, puces,
sous-puces), couleur d'accent unique par thème, contraste élevé, numéro de diapositive et pied de page,
taille de police calculée pour que le texte tienne dans son cadre (jamais en dessous de 14 pt : au-delà, la
diapositive est signalée « surchargée » au lieu d'être rendue illisible).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

from academic_writer.presentations.models import Deck, Slide, SlideCheck

W, H = 13.333, 7.5  # pouces (16:9)
MARGIN = 0.6
MIN_FONT = 14


def _in(value: float) -> Emu:
    return Emu(int(value * 914400))


@dataclass(frozen=True)
class Theme:
    primary: str
    accent: str
    text: str
    muted: str
    background: str
    light: str
    title_font: str = "Segoe UI Semibold"
    body_font: str = "Segoe UI"
    heading: str = ""  # couleur des titres (par défaut : primary) — indispensable sur fond sombre


THEMES = {
    "academique": Theme(primary="1F3A5F", accent="2A9D8F", text="1F2933", muted="5C6B7A", background="FFFFFF",
                        light="EEF3F7"),
    "technique": Theme(primary="2B2D42", accent="E07A2F", text="1E1E24", muted="5F6470", background="FFFFFF",
                       light="F1F1F4"),
    "sobre": Theme(primary="0B3D91", accent="0B3D91", text="111111", muted="4A4A4A", background="FFFFFF",
                   light="EDF1F8", title_font="Arial", body_font="Arial"),
    "clair": Theme(primary="22577A", accent="57CC99", text="1B262C", muted="51606C", background="FBFCFD",
                   light="E8F6EF"),
    "minimal_premium": Theme(primary="111111", accent="B08D57", text="1A1A1A", muted="6B6B6B", background="FFFFFF",
                             light="F4F1EC", title_font="Segoe UI Light", body_font="Segoe UI"),
    "corporate": Theme(primary="003A70", accent="E4002B", text="1C1C1C", muted="5A6570", background="FFFFFF",
                       light="EEF2F6", title_font="Calibri", body_font="Calibri"),
    "scientifique": Theme(primary="12355B", accent="D17A22", text="1B1B1B", muted="586069", background="FFFFFF",
                          light="F2F5F8", title_font="Cambria", body_font="Calibri"),
    "industriel": Theme(primary="2F3E46", accent="F2A900", text="1E2427", muted="5B6870", background="FFFFFF",
                        light="EEF0F1", title_font="Segoe UI Semibold", body_font="Segoe UI"),
    "futuriste": Theme(primary="0B132B", accent="3DDCFF", text="E6EDF5", muted="9AA8BA", background="0D1B2A",
                       light="1B2A41", heading="FFFFFF"),
    "editorial": Theme(primary="2D2A26", accent="C0392B", text="2D2A26", muted="6E6A65", background="FBF8F3",
                       light="F0EBE3", title_font="Georgia", body_font="Segoe UI"),
}
LABELS = {
    "fr": {"references": "Références", "questions": "Merci de votre attention", "questions_sub": "Questions",
           "source": "Source", "supervisor": "Directeur", "author": "Présenté par"},
    "ru": {"references": "Список источников", "questions": "Спасибо за внимание", "questions_sub": "Вопросы",
           "source": "Источник", "supervisor": "Руководитель", "author": "Выполнил(а)"},
    "en": {"references": "References", "questions": "Thank you for your attention", "questions_sub": "Questions",
           "source": "Source", "supervisor": "Supervisor", "author": "Presented by"},
}


def luminance(hex_color: str) -> float:
    """Luminance relative (WCAG) d'une couleur hexadécimale."""
    channels = []
    for i in (0, 2, 4):
        c = int(hex_color[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def on(color: str) -> str:
    """Couleur de texte lisible sur un fond donné (blanc ou quasi-noir, le plus contrasté)."""
    return "FFFFFF" if contrast("FFFFFF", color) >= contrast("111111", color) else "111111"


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def fit_size(lines: list[str], width_in: float, height_in: float, start: int = 24, minimum: int = MIN_FONT,
             word_factor: float = 0.62) -> int | None:
    """Plus grande taille (pt) pour que les lignes tiennent dans le cadre ; None si impossible au minimum."""
    longest = max((len(word) for line in lines for word in line.split()), default=0)
    for size in range(start, minimum - 1, -1):
        if longest * size * word_factor / 72 > width_in:
            continue  # le mot le plus long doit tenir sur une ligne (pas de coupure en plein mot)
        chars_per_line = max(8, int(width_in * 72 / (size * 0.52)))
        used = 0.0
        for line in lines:
            used += max(1, math.ceil(len(line) / chars_per_line)) * size * 1.25 + size * 0.45
        if used / 72 <= height_in:
            return size
    return None


class Builder:
    def __init__(self, deck: Deck, images: dict[str, Path]) -> None:
        self.deck = deck
        self.theme = THEMES[deck.theme]
        self.labels = LABELS[deck.language]
        self.colon = " :" if deck.language == "fr" else ":"
        self.hc = self.theme.heading or self.theme.primary  # couleur des titres et des valeurs mises en avant
        self.images = images
        self.checks: list[SlideCheck] = []
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = _in(W), _in(H)
        self.blank = self.prs.slide_layouts[6]

    # --- primitives -------------------------------------------------------------------------------
    def check(self, index: int, severity: str, code: str, message: str) -> None:
        self.checks.append(SlideCheck(slide=index, severity=severity, code=code, message=message))  # type: ignore[arg-type]

    def rect(self, slide, x, y, w, h, color: str, shape=MSO_SHAPE.RECTANGLE):
        box = slide.shapes.add_shape(shape, _in(x), _in(y), _in(w), _in(h))
        box.fill.solid()
        box.fill.fore_color.rgb = _rgb(color)
        box.line.fill.background()
        box.shadow.inherit = False
        return box

    def text(self, slide, x, y, w, h, text: str, size: int, *, color: str | None = None, bold: bool = False,
             font: str | None = None, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic: bool = False):
        box = slide.shapes.add_textbox(_in(x), _in(y), _in(w), _in(h))
        frame = box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = anchor
        frame.margin_left = frame.margin_right = _in(0.05)
        paragraph = frame.paragraphs[0]
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.name = font or self.theme.body_font
        run.font.color.rgb = _rgb(color or self.theme.text)
        return box

    def bullets(self, slide, index: int, x, y, w, h, items: list[str], start: int = 24) -> None:
        if not items:
            return
        lines = [i.lstrip("- ").strip() for i in items]
        size = fit_size(lines, w - 0.4, h, start=start)
        if size is None:
            size = MIN_FONT
            self.check(index, "error", "overfull", "Texte trop long pour la diapositive même à 14 pt : scinder la "
                                                   "diapositive ou raccourcir les puces.")
        box = slide.shapes.add_textbox(_in(x), _in(y), _in(w), _in(h))
        frame = box.text_frame
        frame.word_wrap = True
        for n, item in enumerate(items):
            sub = item.startswith("- ")
            paragraph = frame.paragraphs[0] if n == 0 else frame.add_paragraph()
            paragraph.space_after = Pt(size * 0.45)
            paragraph.level = 1 if sub else 0
            marker = paragraph.add_run()
            marker.text = ("–  " if sub else "■  ")
            marker.font.size = Pt(size * (0.75 if sub else 0.55))
            marker.font.color.rgb = _rgb(self.theme.muted if sub else self.theme.accent)
            run = paragraph.add_run()
            run.text = item[2:].strip() if sub else item.strip()
            run.font.size = Pt(size - 2 if sub else size)
            run.font.name = self.theme.body_font
            run.font.color.rgb = _rgb(self.theme.muted if sub else self.theme.text)

    def header(self, slide, title: str, index: int) -> None:
        self.rect(slide, 0, 0, W, 0.12, self.theme.primary)
        self.rect(slide, MARGIN, 0.42, 0.09, 0.62, self.theme.accent)
        size = 30 if len(title) <= 48 else 26 if len(title) <= 70 else 22
        if len(title) > 95:
            self.check(index, "warning", "long_title", "Titre trop long (plus de 95 caractères).")
        self.text(slide, MARGIN + 0.25, 0.3, W - 2 * MARGIN - 0.25, 0.9, title, size, color=self.hc,
                  font=self.theme.title_font, anchor=MSO_ANCHOR.MIDDLE)

    def footer(self, slide, number: int) -> None:
        self.rect(slide, MARGIN, H - 0.55, W - 2 * MARGIN, 0.015, self.theme.light)
        if self.deck.footer:
            self.text(slide, MARGIN, H - 0.5, W - 3, 0.35, self.deck.footer, 11, color=self.theme.muted)
        self.text(slide, W - MARGIN - 1.0, H - 0.5, 1.0, 0.35, str(number), 11, color=self.theme.muted,
                  align=PP_ALIGN.RIGHT)

    def source_line(self, slide, text: str | None) -> None:
        if text:
            self.text(slide, MARGIN, H - 0.92, W - 2 * MARGIN, 0.35, f"{self.labels['source']}{self.colon} {text}", 11,
                      color=self.theme.muted, italic=True)

    # --- types de diapositives ------------------------------------------------------------------------------
    def slide_title(self, slide, s: Slide, index: int) -> None:
        info = self.deck.title_info
        self.rect(slide, 0, 0, W, H, self.theme.primary)
        self.rect(slide, 0, 4.65, W, 0.06, self.theme.accent)
        top = " · ".join(x for x in (info.institution, info.department) if x)
        if top:
            self.text(slide, MARGIN, 0.45, W - 2 * MARGIN, 0.8, top, 16, color="FFFFFF", align=PP_ALIGN.CENTER)
        if info.event:
            self.text(slide, MARGIN, 1.25, W - 2 * MARGIN, 0.5, info.event.upper(), 14, color="BFD7EA",
                      align=PP_ALIGN.CENTER, bold=True)
        title = s.title or self.deck.title
        size = fit_size([title], W - 2.4, 1.9, start=40, minimum=24) or 24
        self.text(slide, 1.2, 1.85, W - 2.4, 1.9, title, size, color="FFFFFF", font=self.theme.title_font,
                  align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        subtitle = s.subtitle or self.deck.subtitle
        if subtitle:
            self.text(slide, 1.2, 3.85, W - 2.4, 0.7, subtitle, 18, color="DCE6EF", align=PP_ALIGN.CENTER)
        people = []
        if info.author:
            people.append(f"{self.labels['author']}{self.colon} {info.author}")
        if info.supervisor:
            people.append(f"{self.labels['supervisor']}{self.colon} {info.supervisor}")
        if people:
            self.text(slide, MARGIN, 5.0, W - 2 * MARGIN, 1.0, "\n".join(people), 16, color="FFFFFF",
                      align=PP_ALIGN.CENTER)
        if info.city_year:
            self.text(slide, MARGIN, H - 0.9, W - 2 * MARGIN, 0.45, info.city_year, 14, color="BFD7EA",
                      align=PP_ALIGN.CENTER)

    def slide_section(self, slide, s: Slide, index: int, number: int) -> None:
        self.rect(slide, 0, 0, W, H, self.theme.light)
        self.rect(slide, 0, 0, 4.4, H, self.theme.primary)
        self.text(slide, 0.4, 2.3, 3.6, 2.2, f"{number:02d}", 96, color="FFFFFF", font=self.theme.title_font,
                  align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        self.text(slide, 5.0, 2.4, W - 5.6, 1.6, s.title, 36, color=self.hc, font=self.theme.title_font,
                  anchor=MSO_ANCHOR.MIDDLE)
        if s.subtitle:
            self.text(slide, 5.0, 4.0, W - 5.6, 1.0, s.subtitle, 18, color=self.theme.muted)

    def slide_bullets(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        self.bullets(slide, index, MARGIN + 0.25, 1.5, W - 2 * MARGIN - 0.3, H - 2.6, s.bullets, start=28)
        self.source_line(slide, s.source)

    def slide_two_columns(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        column = (W - 2 * MARGIN - 0.5) / 2
        for k, (title, items) in enumerate(((s.left_title, s.left_bullets), (s.right_title, s.right_bullets))):
            x = MARGIN + k * (column + 0.5)
            self.rect(slide, x, 1.45, column, H - 2.55, self.theme.light)
            y = 1.6
            if title:
                self.text(slide, x + 0.25, y, column - 0.5, 0.55, title, 20, color=self.hc, bold=True)
                y += 0.65
            self.bullets(slide, index, x + 0.2, y, column - 0.4, H - 1.25 - y - 0.1, items, start=20)
        self.source_line(slide, s.source)

    def picture(self, slide, path: Path, x, y, w, h) -> None:
        from PIL import Image

        with Image.open(path) as image:
            ratio = image.width / image.height
        width, height = (w, w / ratio) if w / ratio <= h else (h * ratio, h)
        slide.shapes.add_picture(str(path), _in(x + (w - width) / 2), _in(y + (h - height) / 2), _in(width), _in(height))

    def slide_chart(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        key = s.image_path if s.type == "image" else f"chart:{s.chart_id}"
        path = self.images.get(key or "")
        if path is None or not path.exists():
            self.check(index, "error", "missing_figure", f"Figure introuvable ({key}) : créer le graphique "
                                                         "(create_chart) ou indiquer une image du projet.")
            self.text(slide, MARGIN, 2.5, W - 2 * MARGIN, 1, "[Figure manquante]", 28, color="C0392B",
                      align=PP_ALIGN.CENTER)
            return
        has_text = bool(s.bullets)
        area_w = (W - 2 * MARGIN) * (0.62 if has_text else 1.0)
        self.picture(slide, path, MARGIN, 1.4, area_w, H - 2.65 - (0.35 if s.caption else 0))
        if s.caption:
            self.text(slide, MARGIN, H - 1.3, area_w, 0.4, s.caption, 13, color=self.theme.muted,
                      align=PP_ALIGN.CENTER, italic=True)
        if has_text:
            x = MARGIN + area_w + 0.3
            self.rect(slide, x, 1.45, W - MARGIN - x, H - 2.55, self.theme.light)
            self.bullets(slide, index, x + 0.2, 1.65, W - MARGIN - x - 0.4, H - 2.9, s.bullets, start=20)
        if s.type == "image" and not s.source:
            self.check(index, "error", "image_source", "Image sans source ni droits indiqués (champ source).")
        self.source_line(slide, s.source)

    def slide_table(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        if not s.header or not s.rows:
            self.check(index, "error", "empty_table", "Tableau sans en-tête ou sans lignes.")
            return
        rows, cols = len(s.rows) + 1, len(s.header)
        if rows > 9 or cols > 6:
            self.check(index, "warning", "table_size", "Tableau de plus de 8 lignes ou 6 colonnes : peu lisible "
                                                       "en projection, garder l'essentiel.")
        height = min(H - 2.8, 0.5 * rows)
        shape = slide.shapes.add_table(rows, cols, _in(MARGIN), _in(1.5), _in(W - 2 * MARGIN), _in(height))
        table = shape.table
        size = 16 if rows <= 6 else 13 if rows <= 10 else 11
        for c, value in enumerate(s.header):
            cell = table.cell(0, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(self.theme.primary)
            cell.text = value
            run = cell.text_frame.paragraphs[0].runs[0]
            run.font.size, run.font.bold, run.font.color.rgb = Pt(size), True, _rgb(on(self.theme.primary))
        for r, row in enumerate(s.rows, start=1):
            if len(row) != cols:
                self.check(index, "error", "table_shape", f"Ligne {r} : {len(row)} cellules pour {cols} colonnes.")
            for c in range(cols):
                cell = table.cell(r, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = _rgb(self.theme.light if r % 2 else "FFFFFF")
                cell.text = row[c] if c < len(row) else ""
                for paragraph in cell.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.size, run.font.color.rgb = Pt(size), _rgb(self.theme.text)
        if s.caption:
            self.text(slide, MARGIN, 1.55 + height, W - 2 * MARGIN, 0.4, s.caption, 13, color=self.theme.muted,
                      italic=True)
        self.source_line(slide, s.source)

    def slide_key_figures(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        figures = s.figures[:4]
        if not figures:
            self.check(index, "error", "no_figures", "Aucun chiffre clé.")
            return
        gap = 0.35
        card = (W - 2 * MARGIN - gap * (len(figures) - 1)) / len(figures)
        for k, figure in enumerate(figures):
            x = MARGIN + k * (card + gap)
            self.rect(slide, x, 1.8, card, 3.6, self.theme.light)
            self.rect(slide, x, 1.8, card, 0.09, self.theme.accent)
            value_size = fit_size([figure.value], card - 0.3, 1.3, start=48, minimum=24) or 24
            self.text(slide, x + 0.15, 2.15, card - 0.3, 1.4, figure.value, value_size, color=self.hc,
                      font=self.theme.title_font, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            self.text(slide, x + 0.2, 3.65, card - 0.4, 1.1, figure.label, 16, color=self.theme.text,
                      align=PP_ALIGN.CENTER)
            if figure.source:
                self.text(slide, x + 0.2, 4.8, card - 0.4, 0.5, figure.source, 11, color=self.theme.muted,
                          align=PP_ALIGN.CENTER, italic=True)
            else:
                self.check(index, "warning", "figure_source", f"Chiffre « {figure.value} » sans source indiquée.")

    def slide_quote(self, slide, s: Slide, index: int) -> None:
        self.rect(slide, 0, 0, W, H, self.theme.light)
        self.text(slide, 1.0, 0.8, 1.5, 1.5, "“", 120, color=self.theme.accent, font="Georgia")
        size = fit_size([s.quote or ""], W - 3.2, 3.2, start=30, minimum=18) or 18
        self.text(slide, 1.8, 1.9, W - 3.2, 3.2, s.quote or "", size, color=self.hc, italic=True,
                  font="Georgia", anchor=MSO_ANCHOR.MIDDLE)
        if s.quote_author:
            self.text(slide, 1.8, 5.2, W - 3.2, 0.5, f"— {s.quote_author}", 18, color=self.theme.muted,
                      align=PP_ALIGN.RIGHT)
        if not s.source:
            self.check(index, "error", "quote_source", "Citation sans référence (ouvrage, page) : à compléter.")
        self.source_line(slide, s.source)

    def slide_process(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        steps = s.steps[:6]
        if len(steps) < 2:
            self.check(index, "error", "process_steps", "Schéma de démarche : au moins 2 étapes.")
            return
        # cartes numérotées reliées par des flèches : zone de texte prévisible, une seule taille pour toutes
        gap = 0.5
        width = (W - 2 * MARGIN - gap * (len(steps) - 1)) / len(steps)
        top, height = 1.9, 2.4
        size = min(fit_size([step], width - 0.4, height - 1.15, start=20, minimum=11, word_factor=0.68) or 11
                   for step in steps)
        for k, step in enumerate(steps):
            x = MARGIN + k * (width + gap)
            self.rect(slide, x, top, width, height, self.theme.light, MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.08
            self.rect(slide, x, top, width, 0.08, self.theme.primary if k % 2 == 0 else self.theme.accent)
            badge = self.rect(slide, x + width / 2 - 0.32, top + 0.3, 0.64, 0.64,
                              self.theme.primary if k % 2 == 0 else self.theme.accent, MSO_SHAPE.OVAL)
            frame = badge.text_frame
            frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
            paragraph = frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.CENTER
            run = paragraph.add_run()
            run.text = str(k + 1)
            fill = self.theme.primary if k % 2 == 0 else self.theme.accent
            run.font.size, run.font.bold, run.font.color.rgb = Pt(18), True, _rgb(on(fill))
            self.text(slide, x + 0.2, top + 1.05, width - 0.4, height - 1.15, step, size, bold=True,
                      color=self.hc, align=PP_ALIGN.CENTER)
            if k < len(steps) - 1:
                self.rect(slide, x + width + 0.1, top + height / 2 - 0.18, gap - 0.2, 0.36, self.theme.muted,
                          MSO_SHAPE.RIGHT_ARROW)
        if s.bullets:
            self.bullets(slide, index, MARGIN + 0.25, top + height + 0.45, W - 2 * MARGIN - 0.3,
                         H - (top + height + 0.45) - 0.7, s.bullets, start=20)

    def slide_references(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title or self.labels["references"], index)
        items = s.references or s.bullets
        if not items:
            self.check(index, "warning", "no_references", "Diapositive des références vide.")
            return
        size = fit_size(items, W - 2 * MARGIN - 0.3, H - 2.5, start=16, minimum=11)
        if size is None:
            size = 11
            self.check(index, "warning", "references_overflow", "Trop de références pour une diapositive : répartir "
                                                                "sur deux diapositives.")
        box = slide.shapes.add_textbox(_in(MARGIN + 0.2), _in(1.45), _in(W - 2 * MARGIN - 0.3), _in(H - 2.4))
        frame = box.text_frame
        frame.word_wrap = True
        for n, item in enumerate(items):
            paragraph = frame.paragraphs[0] if n == 0 else frame.add_paragraph()
            paragraph.space_after = Pt(size * 0.5)
            run = paragraph.add_run()
            run.text = f"{n + 1}. {item}"
            run.font.size, run.font.color.rgb, run.font.name = Pt(size), _rgb(self.theme.text), self.theme.body_font

    def slide_questions(self, slide, s: Slide, index: int) -> None:
        self.rect(slide, 0, 0, W, H, self.theme.primary)
        self.rect(slide, W / 2 - 1.2, 4.35, 2.4, 0.06, self.theme.accent)
        self.text(slide, MARGIN, 2.3, W - 2 * MARGIN, 1.6, s.title or self.labels["questions"], 40, color="FFFFFF",
                  font=self.theme.title_font, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        self.text(slide, MARGIN, 4.6, W - 2 * MARGIN, 0.8, s.subtitle or self.labels["questions_sub"], 22,
                  color="DCE6EF", align=PP_ALIGN.CENTER)

    # --- sommaire, comparaison, définitions, chronologie ---------------------------------------------------
    def slide_agenda(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title or "Plan", index)
        items = s.bullets[:8]
        if not items:
            self.check(index, "error", "empty_agenda", "Sommaire vide.")
            return
        per_column = 4 if len(items) > 4 else len(items)
        width = (W - 2 * MARGIN - 0.5) / (2 if len(items) > 4 else 1)
        size = min(fit_size([i], width - 1.3, 0.9, start=22, minimum=14) or 14 for i in items)
        for k, item in enumerate(items):
            column, row = divmod(k, per_column)
            x, y = MARGIN + column * (width + 0.5), 1.6 + row * 1.15
            badge = self.rect(slide, x, y + 0.1, 0.7, 0.7, self.theme.accent, MSO_SHAPE.OVAL)
            frame = badge.text_frame
            frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
            run = frame.paragraphs[0].add_run()
            frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            run.text = f"{k + 1:02d}"
            run.font.size, run.font.bold, run.font.color.rgb = Pt(15), True, _rgb(on(self.theme.accent))
            self.text(slide, x + 0.95, y, width - 1.1, 0.9, item, size, color=self.theme.text,
                      anchor=MSO_ANCHOR.MIDDLE)

    def slide_comparison(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        rows = s.criteria[:6]
        if not rows:
            self.check(index, "error", "empty_comparison", "Comparaison sans critère.")
            return
        label_w = 2.8
        col_w = (W - 2 * MARGIN - label_w - 0.3) / 2
        top = 1.5
        left_color = self.theme.primary if contrast(self.theme.primary, self.theme.background) >= 1.6 \
            else self.theme.muted  # couleur principale trop proche du fond (thème sombre)
        for k, (title, color) in enumerate(((s.left_title or "A", left_color),
                                            (s.right_title or "B", self.theme.accent))):
            x = MARGIN + label_w + 0.15 + k * (col_w + 0.15)
            self.rect(slide, x, top, col_w, 0.7, color)
            self.text(slide, x, top, col_w, 0.7, title, 20, color=on(color), bold=True, align=PP_ALIGN.CENTER,
                      anchor=MSO_ANCHOR.MIDDLE)
        row_h = min(0.85, (H - 2.9) / len(rows))
        cells = [r.left for r in rows] + [r.right for r in rows]
        size = min(fit_size([c], col_w - 0.3, row_h - 0.1, start=18, minimum=12) or 12 for c in cells)
        for k, row in enumerate(rows):
            y = top + 0.8 + k * row_h
            if k % 2 == 0:
                self.rect(slide, MARGIN, y, W - 2 * MARGIN, row_h, self.theme.light)
            self.text(slide, MARGIN + 0.1, y, label_w - 0.1, row_h, row.criterion, size, bold=True, color=self.hc,
                      anchor=MSO_ANCHOR.MIDDLE)
            for c, value in enumerate((row.left, row.right)):
                x = MARGIN + label_w + 0.15 + c * (col_w + 0.15)
                self.text(slide, x + 0.1, y, col_w - 0.2, row_h, value, size, color=self.theme.text,
                          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        self.source_line(slide, s.source)

    def slide_definitions(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        cards = s.terms[:4]
        if not cards:
            self.check(index, "error", "no_terms", "Diapositive de définitions sans terme.")
            return
        columns = 2 if len(cards) > 1 else 1
        rows = (len(cards) + 1) // 2 if columns == 2 else 1
        gap = 0.35
        width = (W - 2 * MARGIN - gap * (columns - 1)) / columns
        height = (H - 2.55 - gap * (rows - 1)) / rows
        size = min(fit_size([c.definition], width - 0.6, height - 1.2, start=18, minimum=12) or 12 for c in cards)
        for k, card in enumerate(cards):
            row, column = divmod(k, columns)
            x, y = MARGIN + column * (width + gap), 1.45 + row * (height + gap)
            self.rect(slide, x, y, width, height, self.theme.light)
            self.rect(slide, x, y, 0.08, height, self.theme.accent)
            self.text(slide, x + 0.3, y + 0.15, width - 0.5, 0.6, card.term, 20, bold=True, color=self.hc)
            self.text(slide, x + 0.3, y + 0.8, width - 0.5, height - 1.2, card.definition, size, color=self.theme.text)
            if card.source:
                self.text(slide, x + 0.3, y + height - 0.42, width - 0.5, 0.35, card.source, 11,
                          color=self.theme.muted, italic=True)

    def slide_timeline(self, slide, s: Slide, index: int) -> None:
        self.header(slide, s.title, index)
        events = s.events[:7]
        if len(events) < 2:
            self.check(index, "error", "timeline_events", "Chronologie : au moins 2 jalons.")
            return
        axis_y = 3.9
        self.rect(slide, MARGIN, axis_y - 0.03, W - 2 * MARGIN, 0.06, self.theme.muted)
        step = (W - 2 * MARGIN) / len(events)
        size = min(fit_size([e.label], step - 0.2, 1.6, start=16, minimum=11) or 11 for e in events)
        for k, event in enumerate(events):
            cx = MARGIN + step * (k + 0.5)
            self.rect(slide, cx - 0.17, axis_y - 0.17, 0.34, 0.34, self.theme.accent, MSO_SHAPE.OVAL)
            self.text(slide, cx - step / 2 + 0.1, axis_y - 0.95, step - 0.2, 0.6, event.date, 18,
                      bold=True, color=self.hc, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.BOTTOM)
            self.text(slide, cx - step / 2 + 0.1, axis_y + 0.35, step - 0.2, 1.7, event.label,
                      size, color=self.theme.text, align=PP_ALIGN.CENTER)
        self.source_line(slide, s.source)

    # --- notes du présentateur -------------------------------------------------------------------------------------
    def notes_text(self, s: Slide) -> str:
        parts = [s.notes.strip()] if s.notes.strip() else []
        if s.transition:
            parts.append(("Transition : " if self.deck.language != "ru" else "Переход: ") + s.transition)
        if s.jury_questions:
            head = {"fr": "Questions possibles du jury :", "ru": "Возможные вопросы комиссии:",
                    "en": "Possible questions from the jury:"}[self.deck.language]
            lines = [head]
            for q in s.jury_questions:
                lines.append(f"— {q.question}")
                if q.answer:
                    lines.append(f"   → {q.answer}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    # --- assemblage --------------------------------------------------------------------------------------
    def build(self, path: Path) -> list[SlideCheck]:
        section_number = 0
        for index, s in enumerate(self.deck.slides, start=1):
            slide = self.prs.slides.add_slide(self.blank)
            background = slide.background.fill
            background.solid()
            background.fore_color.rgb = _rgb(self.theme.background)
            if s.type == "title":
                self.slide_title(slide, s, index)
            elif s.type == "section":
                section_number += 1
                self.slide_section(slide, s, index, section_number)
            elif s.type in ("bullets", "conclusion"):
                self.slide_bullets(slide, s, index)
            elif s.type == "two_columns":
                self.slide_two_columns(slide, s, index)
            elif s.type in ("chart", "image"):
                self.slide_chart(slide, s, index)
            elif s.type == "table":
                self.slide_table(slide, s, index)
            elif s.type == "key_figures":
                self.slide_key_figures(slide, s, index)
            elif s.type == "quote":
                self.slide_quote(slide, s, index)
            elif s.type == "process":
                self.slide_process(slide, s, index)
            elif s.type == "references":
                self.slide_references(slide, s, index)
            elif s.type == "questions":
                self.slide_questions(slide, s, index)
            elif s.type == "agenda":
                self.slide_agenda(slide, s, index)
            elif s.type == "comparison":
                self.slide_comparison(slide, s, index)
            elif s.type == "definitions":
                self.slide_definitions(slide, s, index)
            elif s.type == "timeline":
                self.slide_timeline(slide, s, index)
            if s.type not in ("title", "section", "quote", "questions"):
                self.footer(slide, index)
            notes = self.notes_text(s)
            if notes:
                slide.notes_slide.notes_text_frame.text = notes
        self.layout_checks()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(path))
        return self.checks

    def layout_checks(self) -> None:
        """Éléments hors de la diapositive et chevauchements entre éléments porteurs de contenu (texte, image,
        tableau) ; les formes décoratives sans texte (cartes, bandeaux) sont ignorées."""
        width, height = int(self.prs.slide_width), int(self.prs.slide_height)
        tolerance = int(0.02 * 914400)
        for index, slide in enumerate(self.prs.slides, start=1):
            boxes = []
            for shape in slide.shapes:
                left, top = int(shape.left or 0), int(shape.top or 0)
                right, bottom = left + int(shape.width or 0), top + int(shape.height or 0)
                if left < -tolerance or top < -tolerance or right > width + tolerance or bottom > height + tolerance:
                    self.check(index, "error", "out_of_slide", "Élément en dehors de la diapositive.")
                has_text = shape.has_text_frame and shape.text_frame.text.strip()
                is_content = has_text or shape.shape_type in (13, 19)  # image, tableau
                if is_content and not (shape.has_text_frame and shape.shape_type == 1 and len(shape.text_frame.text) <= 3):
                    boxes.append((left, top, right, bottom, (shape.text_frame.text[:30] if has_text else shape.name)))
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    a, b = boxes[i], boxes[j]
                    w = min(a[2], b[2]) - max(a[0], b[0])
                    h = min(a[3], b[3]) - max(a[1], b[1])
                    if w > tolerance and h > tolerance:
                        smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1
                        if w * h / smaller > 0.05:
                            self.check(index, "warning", "overlap",
                                       f"Chevauchement : « {a[4]} » et « {b[4]} ».")
