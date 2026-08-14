"""Testes de contrato do MCP server."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.interfaces.mcp_server import (
    build_mcp_tools,
    handle_mcp_call,
)

pytestmark = pytest.mark.contract


class TestMcpTools:
    def test_has_four_tools(self) -> None:
        tools = build_mcp_tools()
        assert len(tools) == 4

    def test_tool_shape(self) -> None:
        tools = build_mcp_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_manifest_call(self) -> None:
        result = handle_mcp_call("living_video_manifest", {})
        assert "agents" in result
        assert "prompts" in result

    def test_doctor_call(self) -> None:
        result = handle_mcp_call("living_video_doctor", {})
        assert "checks" in result
        assert "python" in result["checks"]

    def test_unknown_tool(self) -> None:
        result = handle_mcp_call("nonexistent", {})
        assert "error" in result
