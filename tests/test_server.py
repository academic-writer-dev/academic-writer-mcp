"""Tests du serveur MCP minimal via le client MCP en mémoire."""

import pytest
from mcp import Client

from academic_writer import __version__
from academic_writer.server.app import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_tools_listed() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()
        names = {tool.name for tool in result.tools}
        assert "ping" in names


async def test_ping_returns_structured_result() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("ping", {"message": "bonjour"})
        assert not result.is_error
        data = result.structured_content
        assert data is not None
        assert data["status"] == "ok"
        assert data["version"] == __version__
        assert data["echo"] == "bonjour"


async def test_info_resource() -> None:
    async with Client(mcp) as client:
        result = await client.read_resource("academic-writer://info")
        text = result.contents[0].text
        assert "Academic Writer MCP" in text


async def test_academic_analysis_prompt() -> None:
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "academic_analysis", {"document_type": "mémoire de Master", "language": "fr"}
        )
        text = result.messages[0].content.text
        assert "mémoire de Master" in text
        assert "N'invente aucune" in text
