"""Fabrication de documents de test réalistes (DOCX, PDF, XLSX, PPTX, images)."""

from __future__ import annotations

import io
from pathlib import Path

ARIAL = Path(r"C:\Windows\Fonts\arial.ttf")


def png_bytes(text: str = "", size: tuple[int, int] = (200, 120)) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", size, "white")
    if text:
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(ARIAL), 48) if ARIAL.exists() else ImageFont.load_default()
        draw.text((20, 20), text, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_real_docx(path: Path) -> Path:
    from docx import Document
    from docx.shared import Inches

    document = Document()
    document.core_properties.author = "Иван Петров"
    document.core_properties.title = "Rapport de TP"
    document.add_heading("Rapport de travaux pratiques", level=0)
    document.add_heading("1. Introduction", level=1)
    document.add_paragraph("Ce rapport présente l'étude cinématique d'un mécanisme à coulisse.")
    document.add_heading("1.1 Objectifs", level=2)
    document.add_paragraph("Déterminer les vitesses", style="List Bullet")
    document.add_paragraph("Déterminer les accélérations", style="List Bullet")
    table = document.add_table(rows=3, cols=3)
    table.cell(0, 0).text = "Grandeur"
    table.cell(0, 1).text = "Valeur"
    table.cell(0, 2).text = "Unité"
    table.cell(1, 0).text = "ω1"
    table.cell(1, 1).text = "10"
    table.cell(1, 2).text = "rad/s"
    merged = table.cell(2, 0).merge(table.cell(2, 1))
    merged.text = "Fusionnée"
    table.cell(2, 2).text = "m"
    image_path = path.with_suffix(".png")
    image_path.write_bytes(png_bytes(size=(120, 80)))
    document.add_picture(str(image_path), width=Inches(1))
    document.add_paragraph("Figure 1 – Schéma du mécanisme", style="Caption")
    document.add_heading("2. Кинематический анализ", level=1)
    document.add_paragraph("Скорость точки B определяется методом планов.")
    document.save(str(path))
    image_path.unlink()
    return path


def make_text_pdf(path: Path, with_bookmarks: bool = False) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle

    if "ArialTest" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("ArialTest", str(ARIAL)))
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("Test Auteur")
    c.setTitle("Mémoire de test")
    _, height = A4

    c.setFont("ArialTest", 20)
    c.drawString(72, height - 80, "Introduction générale")
    if with_bookmarks:
        c.bookmarkPage("p1")
        c.addOutlineEntry("Introduction générale", "p1", level=0)
    c.setFont("ArialTest", 11)
    y = height - 120
    for line in ("La maintenance prédictive réduit les arrêts non planifiés.",
                 "Elle repose sur la surveillance de l'état des équipements.",
                 "",
                 "Les vibrations sont un indicateur essentiel."):
        c.drawString(72, y, line)
        y -= 16
    table = Table([["Paramètre", "Valeur"], ["Vitesse", "1500 tr/min"], ["Puissance", "15 kW"]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"), ("FONTNAME", (0, 0), (-1, -1), "ArialTest")]))
    table.wrapOn(c, 300, 100)
    table.drawOn(c, 72, y - 80)
    c.showPage()

    c.setFont("ArialTest", 20)
    c.drawString(72, height - 80, "Глава 2. Методология")
    if with_bookmarks:
        c.bookmarkPage("p2")
        c.addOutlineEntry("Глава 2. Методология", "p2", level=0)
    c.setFont("ArialTest", 11)
    c.drawString(72, height - 120, "Анализ вибрации проводится спектральным методом.")
    c.drawString(72, height - 136, "Результаты представлены в таблице.")
    c.showPage()
    c.save()
    return path


def make_scanned_pdf(path: Path, text: str) -> Path:
    """PDF ne contenant qu'une image de texte (simule un document scanné)."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = Image.new("RGB", (2000, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 120), text, fill="black", font=ImageFont.truetype(str(ARIAL), 90))
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(ImageReader(image), 40, 500, width=520, height=104)
    c.showPage()
    c.save()
    return path


def make_xlsx(path: Path) -> Path:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Mesures"
    sheet.append(["Essai", "Force (N)", "Allongement (mm)"])
    sheet.append([1, 100, 0.12])
    sheet.append([2, 200, 0.25])
    workbook.create_sheet("Vide")
    workbook.properties.creator = "Labo"
    workbook.save(str(path))
    return path


def make_pptx(path: Path) -> Path:
    from pptx import Presentation
    from pptx.util import Inches

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Soutenance de mémoire"
    body = slide.placeholders[1].text_frame
    body.text = "Contexte industriel"
    sub = body.add_paragraph()
    sub.text = "Maintenance des convoyeurs"
    sub.level = 1
    slide.notes_slide.notes_text_frame.text = "Parler lentement."
    slide2 = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide2.shapes.title.text = "Résultats"
    shape = slide2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1))
    shape.table.cell(0, 0).text = "Indicateur"
    shape.table.cell(0, 1).text = "Valeur"
    shape.table.cell(1, 0).text = "MTBF"
    shape.table.cell(1, 1).text = "320 h"
    image_path = path.with_suffix(".png")
    image_path.write_bytes(png_bytes(size=(120, 80)))
    slide2.shapes.add_picture(str(image_path), Inches(5), Inches(2))
    image_path.unlink()
    presentation.save(str(path))
    return path
