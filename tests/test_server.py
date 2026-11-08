"""Tests du serveur MCP via le client MCP en mémoire (comme un vrai assistant)."""

import json
from pathlib import Path

import pytest
from mcp import Client

from academic_writer import __version__
from academic_writer.server.app import mcp
from tests.conftest import make_docx

pytestmark = pytest.mark.anyio

EXPECTED_TOOLS = {
    "ping", "create_project", "get_project", "list_projects", "update_project", "archive_project",
    "import_document", "list_documents", "get_document_metadata",
    "extract_document_content", "extract_document_tables", "extract_document_images", "search_in_documents",
    "identify_domain", "set_project_domain", "list_domain_profiles", "get_domain_profile",
    "get_document_structure_template", "lookup_terminology", "reload_domain_profiles",
    "get_ai_status", "set_project_ai_consent", "test_ai_provider", "get_writing_engine",
    "analyze_assignment", "extract_requirements", "manage_requirement", "create_academic_outline",
    "get_academic_outline", "edit_academic_outline", "validate_outline", "write_academic_section",
    "rewrite_academic_section", "get_section_brief", "save_section_draft", "get_section_revision",
    "review_revision", "get_draft_status",
}


async def test_tools_listed_with_annotations() -> None:
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert EXPECTED_TOOLS <= set(tools)
        assert tools["list_projects"].annotations.read_only_hint is True
        assert tools["create_project"].output_schema is not None
        enum_values = tools["create_project"].input_schema["$defs"]["DocumentType"]["enum"]
        assert "memoire_master" in enum_values


async def test_ping_returns_structured_result() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("ping", {"message": "bonjour"})
        assert not result.is_error
        data = result.structured_content
        assert data["status"] == "ok"
        assert data["version"] == __version__
        assert data["mode"] == "local"
        assert data["echo"] == "bonjour"


async def test_full_workflow(inbox: Path) -> None:
    source = make_docx(inbox / "consignes.docx")
    async with Client(mcp) as client:
        created = await client.call_tool("create_project", {
            "name": "Rapport de maintenance", "document_type": "rapport_maintenance", "language": "fr",
        })
        assert not created.is_error
        project_id = created.structured_content["id"]

        imported = await client.call_tool("import_document", {
            "project_id": project_id, "file_path": str(source), "role": "instructions",
        })
        assert not imported.is_error, imported.content
        document_id = imported.structured_content["document"]["id"]

        listed = await client.call_tool("list_documents", {"project_id": project_id})
        assert listed.structured_content["count"] == 1

        meta = await client.call_tool("get_document_metadata", {"document_id": document_id})
        assert meta.structured_content["integrity_ok"] is True

        resource = await client.read_resource(f"academic-writer://projects/{project_id}")
        payload = json.loads(resource.contents[0].text)
        assert payload["project"]["name"] == "Rapport de maintenance"
        assert len(payload["documents"]) == 1


async def test_business_errors_are_readable() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_project", {"project_id": "0" * 32})
        assert result.is_error
        assert "Projet introuvable" in result.content[0].text


async def test_security_error_message_reaches_client(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    async with Client(mcp) as client:
        created = await client.call_tool("create_project", {
            "name": "P", "document_type": "td", "language": "en",
        })
        result = await client.call_tool("import_document", {
            "project_id": created.structured_content["id"], "file_path": str(secret),
        })
        assert result.is_error
        assert "Accès refusé" in result.content[0].text


async def test_invalid_enum_rejected_by_schema() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("create_project", {
            "name": "P", "document_type": "roman", "language": "fr",
        })
        assert result.is_error


async def test_static_resources() -> None:
    async with Client(mcp) as client:
        info = await client.read_resource("academic-writer://info")
        assert "Academic Writer MCP" in info.contents[0].text
        types = json.loads((await client.read_resource("academic-writer://document-types")).contents[0].text)
        assert types["these_doctorat"] == "Thèse de Doctorat"
        langs = json.loads((await client.read_resource("academic-writer://languages")).contents[0].text)
        assert set(langs) == {"fr", "ru", "en"}


async def test_academic_analysis_prompt() -> None:
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "academic_analysis", {"document_type": "mémoire de Master", "language": "fr"}
        )
        text = result.messages[0].content.text
        assert "mémoire de Master" in text
        assert "N'invente aucune" in text
