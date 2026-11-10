"""Tests des lecteurs de documents (sans base de données)."""

from pathlib import Path

import pytest

from academic_writer.core.config import Settings
from academic_writer.document.base import ExtractionContext, get_extractor
from academic_writer.document.layout import blocks_from_lines, heading_levels_from_sizes
from academic_writer.document.ocr import OcrEngine
from academic_writer.document.render import build_chunks
from academic_writer.document.text_reader import decode_text
from tests.samples import ARIAL, make_pptx, make_real_docx, make_scanned_pdf, make_text_pdf, make_xlsx

needs_arial = pytest.mark.skipif(not ARIAL.exists(), reason="police Arial absente")


def _extract(path: Path, settings: Settings, tmp_path: Path, **ctx_kwargs):
    ctx = ExtractionContext(settings=settings, images_dir=tmp_path / "images", **ctx_kwargs)
    return get_extractor(path.suffix, settings).extract(path, ctx)


# --- DOCX ----------------------------------------------------------------

def test_docx_structure(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_real_docx(tmp_path / "rapport.docx"), settings, tmp_path)
    headings = [(h.level, h.text) for h in result.headings]
    assert headings == [(0, "Rapport de travaux pratiques"), (1, "1. Introduction"), (2, "1.1 Objectifs"),
                        (1, "2. Кинематический анализ")]
    assert [b.text for b in result.blocks if b.type == "list_item"] == ["Déterminer les vitesses",
                                                                       "Déterminer les accélérations"]
    assert any(b.type == "caption" and "Figure 1" in b.text for b in result.blocks)
    assert result.metadata["author"] == "Иван Петров"


def test_docx_table_and_merged_cells(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_real_docx(tmp_path / "rapport.docx"), settings, tmp_path)
    assert len(result.tables) == 1
    rows = result.tables[0].rows
    assert rows[0] == ["Grandeur", "Valeur", "Unité"]
    assert rows[1] == ["ω1", "10", "rad/s"]
    assert rows[2] == ["Fusionnée", "", "m"]  # cellule fusionnée non dupliquée


def test_docx_images_saved_outside_originals(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_real_docx(tmp_path / "rapport.docx"), settings, tmp_path)
    assert len(result.images) == 1
    image = result.images[0]
    assert image.mime_type == "image/png" and len(image.sha256) == 64
    assert (tmp_path / "images" / "image-0001.png").exists()


# --- PDF -----------------------------------------------------------------

@needs_arial
def test_pdf_text_tables_and_heuristic_headings(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_text_pdf(tmp_path / "memoire.pdf"), settings, tmp_path, ocr_mode="never")
    assert result.page_count == 2
    titles = {h.text: h for h in result.headings}
    assert "Introduction générale" in titles and titles["Introduction générale"].origin == "font_heuristic"
    assert "Глава 2. Методология" in titles
    text = " ".join(b.text for b in result.blocks)
    assert "maintenance prédictive" in text and "спектральным методом" in text
    assert any(t.rows[0] == ["Paramètre", "Valeur"] for t in result.tables)
    assert result.metadata.get("author") == "Test Auteur"
    assert any("heuristique" in w for w in result.warnings)


@needs_arial
def test_pdf_bookmarks_give_reliable_headings(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_text_pdf(tmp_path / "signets.pdf", with_bookmarks=True), settings, tmp_path)
    origins = {h.text: h.origin for h in result.headings}
    assert origins == {"Introduction générale": "outline", "Глава 2. Методология": "outline"}
    assert not any("heuristique" in w for w in result.warnings)


@needs_arial
def test_pdf_pymupdf_backend(tmp_path: Path, inbox: Path) -> None:
    pytest.importorskip("pymupdf")
    settings = Settings(data_dir=tmp_path / "d", allowed_import_dirs=[inbox], pdf_backend="pymupdf")
    result = _extract(make_text_pdf(tmp_path / "m.pdf"), settings, tmp_path, ocr_mode="never")
    assert result.extractor == "pymupdf"
    assert "Introduction générale" in {h.text for h in result.headings}
    assert "спектральным методом" in " ".join(b.text for b in result.blocks)


@needs_arial
def test_scanned_pdf_without_ocr_is_reported(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_scanned_pdf(tmp_path / "scan.pdf", "Bonjour"), settings, tmp_path, ocr=None)
    assert result.ocr_pages == []
    assert any("sans texte extractible" in w for w in result.warnings)


@needs_arial
def test_scanned_pdf_with_ocr(settings: Settings, tmp_path: Path) -> None:
    engine = OcrEngine.detect(settings)
    if engine is None:
        pytest.skip("Tesseract non installé")
    if "fra" not in engine.available_languages():
        tessdata = Path(r"D:\AcademicWriter-Data\tessdata")
        if not (tessdata / "fra.traineddata").exists():
            pytest.skip("langue fra absente")
        engine = OcrEngine(engine.executable, tessdata, 120)
    result = _extract(make_scanned_pdf(tmp_path / "scan.pdf", "Analyse cinématique"), settings, tmp_path,
                      ocr=engine, ocr_languages="fra+eng")
    assert result.ocr_pages == [1]
    text = " ".join(b.text for b in result.blocks).lower()
    assert "analyse" in text and "cinématique" in text
    assert all(b.origin == "ocr" for b in result.blocks if b.type == "paragraph")


# --- TXT / MD --------------------------------------------------------------

def test_decode_cp1251_and_utf8_bom() -> None:
    text, encoding = decode_text("Кинематический анализ механизма".encode("cp1251"))
    assert text == "Кинематический анализ механизма" and encoding.lower().replace("_", "-") in ("cp1251", "windows-1251")
    text, encoding = decode_text("\ufeffÉté".encode("utf-8"))
    assert text == "Été" and encoding == "utf-8-sig"


def test_markdown_structure(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Titre\n\nIntro sur\ndeux lignes.\n\n## Partie\n\n- point A\n- point B\n\n"
                    "| A | B |\n|---|---|\n| 1 | 2 |\n\n> remarque\n", encoding="utf-8")
    result = _extract(path, settings, tmp_path)
    assert [(h.level, h.text) for h in result.headings] == [(1, "Titre"), (2, "Partie")]
    assert any(b.type == "paragraph" and b.text == "Intro sur deux lignes." for b in result.blocks)
    assert [b.text for b in result.blocks if b.type == "list_item"] == ["point A", "point B"]
    assert result.tables[0].rows == [["A", "B"], ["1", "2"]]
    assert any(b.type == "note" for b in result.blocks)


def test_plain_text_paragraphs(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes("Premier paragraphe\nsur deux lignes.\n\nSecond.".encode("cp1252"))
    result = _extract(path, settings, tmp_path)
    assert [b.text for b in result.blocks] == ["Premier paragraphe sur deux lignes.", "Second."]


# --- XLSX / PPTX -------------------------------------------------------------

def test_xlsx_sheets_as_tables(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_xlsx(tmp_path / "mesures.xlsx"), settings, tmp_path)
    assert result.page_count == 2
    assert result.tables[0].title == "Mesures"
    assert result.tables[0].rows[0] == ["Essai", "Force (N)", "Allongement (mm)"]
    assert result.tables[0].rows[2] == ["2", "200", "0.25"]
    assert any(b.text == "(feuille vide)" for b in result.blocks)


def test_pptx_slides(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_pptx(tmp_path / "soutenance.pptx"), settings, tmp_path)
    assert result.page_count == 2
    assert [h.text for h in result.headings] == ["Soutenance de mémoire", "Résultats"]
    assert any(b.type == "list_item" and b.text == "Maintenance des convoyeurs" for b in result.blocks)
    assert any(b.type == "note" and "lentement" in b.text for b in result.blocks)
    assert result.tables[0].rows == [["Indicateur", "Valeur"], ["MTBF", "320 h"]]
    assert len(result.images) == 1


# --- mise en page / découpage ------------------------------------------------

def test_layout_paragraphs_hyphenation_and_bullets() -> None:
    lines = ["La maintenance pré-", "dictive est utile.", "Elle réduit les coûts.", "• premier point", "",
             "Nouveau paragraphe"]
    blocks = blocks_from_lines(lines, page=1)
    assert [b.type for b in blocks] == ["paragraph", "paragraph", "list_item", "paragraph"]
    assert blocks[0].text == "La maintenance prédictive est utile."


def test_heading_heuristic_ignores_drawing_labels() -> None:
    lines = [("ω1", 20.0), ("a'", 20.0), ("Conclusion générale", 20.0)] + [("texte courant du corps", 11.0)] * 10
    levels = heading_levels_from_sizes(lines)
    assert "conclusion générale" in levels
    assert "ω1" not in levels and "a'" not in levels


def test_chunks_keep_heading_and_page(settings: Settings, tmp_path: Path) -> None:
    result = _extract(make_real_docx(tmp_path / "r.docx"), settings, tmp_path)
    chunks = build_chunks(result)
    assert any(c.heading == "2. Кинематический анализ" and "методом планов" in c.text for c in chunks)
    assert any("ω1 | 10 | rad/s" in c.text for c in chunks)  # tableaux indexés


def test_pdf_hex_metadata_decoded() -> None:
    """Titre réel du PDF de la ЛР4 : chaîne hexadécimale en Windows-1251."""
    from academic_writer.document.pdf_pdfium import decode_pdf_string
    raw = "<4D6963726F736F667420576F7264202D20CBE0E1EEF0E0F2EEF0EDE0FF20F0E0E1EEF2E020B9342E646F63>"
    assert decode_pdf_string(raw) == "Microsoft Word - Лабораторная работа №4.doc"
    assert decode_pdf_string("<FEFF0410>") == "А" and decode_pdf_string("Titre normal") == "Titre normal"


def test_ocr_tsv_confidence_and_uncertain_words() -> None:
    """G4 : la confiance OCR est mesurée et les passages douteux sont signalés, jamais présentés comme exacts."""
    from academic_writer.document.model import ocr_quality, ocr_warning
    from academic_writer.document.ocr import parse_tsv

    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    rows = ["5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t96\tVitesse", "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t41\tmoblde",
            "5\t1\t1\t1\t2\t1\t0\t0\t1\t1\t90\t15", "5\t1\t2\t1\t1\t1\t0\t0\t1\t1\t88\tFin"]
    text = parse_tsv("\n".join([header, *rows]))
    assert str(text) == "Vitesse moblde\n15\n\nFin" and text.uncertain == ["moblde"]
    assert text.confidence == pytest.approx(78.8, abs=0.1)
    quality = ocr_quality(3, text)
    assert quality.level == "à vérifier" and "moblde" in ocr_warning(quality, "Page 3")
    assert ocr_warning(ocr_quality(1, parse_tsv("\n".join([header, rows[0]]))), "Page 1") is None
