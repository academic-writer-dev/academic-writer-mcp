"""Tests de la mise en forme et de l'export (phase 9)."""

from pathlib import Path

import pytest
from docx import Document
from docx.shared import Pt
from mcp import Client

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.formatting import word
from academic_writer.formatting.docx_writer import ExportSection, build_docx, heading_text, is_structural
from academic_writer.formatting.presets import PRESETS
from academic_writer.research.models import Person, SourceData
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

BOOK = SourceData(authors=[Person(family="Артоболевский", given="Иван Иванович")], title="Теория механизмов и машин",
                  publisher="Наука", place="Москва", year=1988, pages="640")


@pytest.fixture(autouse=True)
def no_word(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les tests n'automatisent jamais Microsoft Word (lent, dépend de la machine)."""
    monkeypatch.setattr(word, "word_available", lambda: False)


@pytest.fixture
def project(services: Services, inbox: Path):
    project = services.projects.create("ЛР4 ТММ", DocumentType.RAPPORT_LABORATOIRE, Language.RU)
    path = inbox / "zadanie.txt"
    path.write_text("1. Изучить метод обкатки.\n2. Построить профиль зуба.", encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.INSTRUCTIONS)
    services.domains.assign(project.id, "genie_mecanique", "ru")
    services.writing.analyze_assignment(project.id)
    outline = services.writing.create_outline(project.id)
    services.writing.validate_outline(outline.id, approve=True, force=True)
    services.sources.register(project.id, "book", BOOK, key="artobolevsky1988")
    return project


def _accept(services: Services, project, key: str, text: str) -> None:
    section = next(s for s in services.writing.current_outline(project.id).sections if s.section_key == key)
    draft = services.writing.save_section_draft(project.id, section.id, text)
    services.writing.review_revision(draft.id, "accept")


def _texts(path: str) -> list[str]:
    return [p.text for p in Document(path).paragraphs]


def test_heading_numbering_and_structural() -> None:
    preset = PRESETS["gost_7_32"]
    counters = [0, 0, 0]
    assert heading_text(ExportSection(None, "Теоретические сведения.", 1, ""), preset, counters, 1, False) == \
        "1 Теоретические сведения"
    assert heading_text(ExportSection(None, "Метод обкатки", 2, ""), preset, counters, 2, False) == "1.1 Метод обкатки"
    assert heading_text(ExportSection(None, "Ход работы", 1, ""), preset, counters, 1, False) == "2 Ход работы"
    assert is_structural("conclusion", "Выводы") and is_structural(None, "Введение") and not is_structural(None, "Ход")
    assert heading_text(ExportSection(None, "Partie", 1, ""), PRESETS["fr_universitaire"], [0, 0, 0], 1, False) == \
        "1. Partie"


def test_build_docx_gost(tmp_path: Path) -> None:
    sections = [
        ExportSection("title_page", "Титульный лист", 1, None, "title_page"),
        ExportSection("contents", "Содержание", 1, None, "contents"),
        ExportSection("introduction", "Введение", 1, "Цель работы — **изучить** метод обкатки [1, с. 15]."),
        ExportSection("theory", "Теоретические сведения", 1,
                      "## Модуль\n\nМодуль m определяет размеры.\n\n- первый пункт\n- второй пункт\n\n"
                      "Таблица 1 – Параметры\n\n| Параметр | Значение |\n|---|---|\n| m | [ЗАПОЛНИТЬ: m] |\n\n"
                      "![Рисунок 1 – Станок](станок.png)"),
        ExportSection("conclusion", "Выводы", 1, None),
        ExportSection("references", "Список использованных источников", 1, "1. Артоболевский И. И. ТММ.",
                      "bibliography"),
    ]
    path = tmp_path / "out.docx"
    stats = build_docx(path, sections, PRESETS["gost_7_32"], "ru", {"organization": "МГТУ «СТАНКИН»", "title": "ЛР4"})
    document = Document(str(path))
    texts = [p.text for p in document.paragraphs]
    assert "МГТУ «СТАНКИН»" in texts and any("____" in t for t in texts)  # champs requis manquants en blanc
    assert any("Page de titre" in w and "author" in w for w in stats.warnings)
    assert "1 Теоретические сведения" in texts and "1.1 Модуль" in texts
    assert "– первый пункт" in texts and "Таблица 1 – Параметры" in texts
    assert stats.tables == 1 and stats.placeholders == 1 and stats.images_missing == 1
    assert stats.unwritten == ["Выводы"] and "[Раздел не написан]" in texts
    section = document.sections[0]
    assert round(section.left_margin.mm) == 30 and round(section.right_margin.mm) == 15
    normal = document.styles["Normal"]
    assert normal.font.name == "Times New Roman" and normal.font.size == Pt(14)
    assert normal.paragraph_format.line_spacing == 1.5
    xml = document.element.xml
    assert "TOC \\o" in xml
    assert "PAGE" in section.footer._element.xml and section.different_first_page_header_footer


def test_export_project(services: Services, project) -> None:
    _accept(services, project, "objective", "Изучить нарезание зубьев методом обкатки [@artobolevsky1988, с. 15].")
    result = services.formatting.export(project.id, title_page={"organization": "МГТУ «СТАНКИН»",
                                                                "document_kind": "Отчёт по лабораторной работе № 4",
                                                                "title": "Нарезание зубьев", "author": "Студент",
                                                                "city": "Москва"})
    assert result.preset == "gost_7_32" and result.citation_style == "gost"
    texts = _texts(result.docx_path)
    assert any("методом обкатки [1, с. 15]" in t for t in texts)
    assert any(t.startswith("1. Артоболевский") for t in texts)
    assert result.bibliography_entries == 1 and result.unknown_citation_keys == []
    assert result.unwritten_sections and not result.ready  # les autres sections ne sont pas rédigées
    assert not result.word_finalized and result.pdf_path is None
    assert "w:updateFields" in Document(result.docx_path).settings.element.xml
    # page de titre mémorisée et réutilisée
    again = services.formatting.export(project.id, citation_style="apa", preset_id="apa7")
    texts = _texts(again.docx_path)
    assert "Нарезание зубьев" in texts and any("(Артоболевский, 1988, с. 15)" in t for t in texts)


def test_export_rejects_unknown_title_field(services: Services, project) -> None:
    with pytest.raises(ValidationFailed, match="inconnus"):
        services.formatting.export(project.id, title_page={"university": "X"})


def _student_docx(path: Path) -> Path:
    from docx.shared import Mm
    document = Document()
    section = document.sections[0]
    section.left_margin = Mm(20)
    document.styles["Normal"].font.name = "Arial"
    document.styles["Normal"].font.size = Pt(12)
    document.add_heading("Введение.", level=1)
    for _ in range(4):
        document.add_paragraph("Метод обкатки позволяет нарезать зубья колеса инструментом реечного типа, "
                               "имитируя зацепление рейки и колеса.")
    document.save(str(path))
    return path


def test_check_and_apply_formatting(services: Services, project, inbox: Path) -> None:
    document_id = services.documents.import_document(project.id, str(_student_docx(inbox / "otchet.docx")),
                                                     DocumentRole.DRAFT).document.id
    check = services.formatting.check(document_id)
    codes = {i.code for i in check.issues}
    assert {"font_mismatch", "size_mismatch", "margins", "page_numbers", "heading_period"} <= codes
    font = next(p for p in check.properties if p.property == "Police")
    assert font.dominant == "Arial" and font.conforming_ratio == 0
    original = services.documents.stored_file(services.documents.get(document_id)).read_bytes()
    applied = services.formatting.apply(document_id)
    assert applied.paragraphs_formatted == 4 and applied.page_numbers_added
    assert services.documents.stored_file(services.documents.get(document_id)).read_bytes() == original
    # la copie mise en forme est conforme
    from academic_writer.formatting.checker import check_docx
    recheck = check_docx(Path(applied.output_path), "copie", "copie.docx", PRESETS["gost_7_32"])
    assert not {"font_mismatch", "size_mismatch", "line_spacing_mismatch", "indent_mismatch", "margins",
                "page_numbers"} & {i.code for i in recheck.issues}
    assert "Введение." in [p.text for p in Document(applied.output_path).paragraphs]  # texte inchangé


def test_check_requires_docx(services: Services, project) -> None:
    document_id = services.documents.list(project.id)[0].id  # zadanie.txt
    with pytest.raises(ValidationFailed, match="docx"):
        services.formatting.check(document_id)


@pytest.mark.anyio
async def test_formatting_tools_exposed(project) -> None:
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"list_format_presets", "export_document", "check_formatting", "apply_formatting"} <= names
        result = await client.call_tool("list_format_presets", {"project_id": project.id})
        assert result.structured_content["default_for_project"] == "gost_7_32"
        result = await client.call_tool("export_document", {"project_id": project.id, "preset": "inexistant"})
        assert result.is_error and "Gabarit inconnu" in result.content[0].text


def test_export_markdown_and_txt(services: Services, inbox: Path) -> None:
    """G14 : export de la rédaction en Markdown et en texte brut."""
    from academic_writer.core.models import DocumentType, Language

    project = services.projects.create("Rapport court", DocumentType.RAPPORT_TECHNIQUE, Language.FR)
    services.domains.assign(project.id, "generaliste", "fr")
    outline = services.writing.create_outline(project.id)
    outline = services.writing.validate_outline(outline.id, approve=True, force=True).outline
    section = next(s for s in outline.sections if s.section_key == "introduction")
    revision = services.writing.save_section_draft(project.id, section.id, "Le **rapport** présente l'étude.")
    services.writing.review_revision(revision.id, "accept")
    md = services.formatting.export(project.id, output_format="markdown")
    text = Path(md.output_path).read_text(encoding="utf-8")
    assert md.docx_path is None and text.startswith("# Rapport court") and "Le **rapport** présente" in text
    assert "[Section non rédigée]" in text and md.unwritten_sections and not md.ready
    txt = services.formatting.export(project.id, output_format="txt")
    plain = Path(txt.output_path).read_text(encoding="utf-8")
    assert "Le rapport présente" in plain and "#" not in plain.splitlines()[0]


def test_export_tables_xlsx_and_csv(services: Services, inbox: Path) -> None:
    from openpyxl import load_workbook

    from academic_writer.core.models import DocumentRole, DocumentType, Language
    from tests.samples import make_xlsx

    project = services.projects.create("Mesures", DocumentType.TP, Language.FR)
    imported = services.documents.import_document(project.id, str(make_xlsx(inbox / "mesures.xlsx")), DocumentRole.DATA)
    document_id = imported.document.id if hasattr(imported, "document") else imported.id
    result = services.extraction.export_tables(document_id, "xlsx")
    workbook = load_workbook(result.paths[0])
    assert result.tables == len(workbook.sheetnames) and workbook.worksheets[0]["A1"].value == "Essai"
    csv_result = services.extraction.export_tables(document_id, "csv", table_index=1)
    content = Path(csv_result.paths[0]).read_text(encoding="utf-8-sig")
    assert content.splitlines()[0] == "Essai;Force (N);Allongement (mm)"
