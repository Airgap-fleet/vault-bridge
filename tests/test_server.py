"""Tests for ObsidianMCP server factory and CLI."""

from unittest.mock import Mock, patch

import pytest

from obsidian_mcp.models import ObsidianConfig
from obsidian_mcp.server import APIKeyVerifier, create_mcp_server


class TestAPIKeyVerifier:
    """Test API key authentication verifier."""

    @pytest.mark.asyncio
    async def test_verify_valid_token(self):
        """Test verifying a valid API key returns AccessToken."""
        verifier = APIKeyVerifier("test-key-123")
        result = await verifier.verify_token("test-key-123")
        assert result is not None
        assert hasattr(result, "token")
        assert result.token == "test-key-123"
        assert hasattr(result, "scopes")
        assert "mcp" in result.scopes

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self):
        """Test verifying an invalid API key returns None."""
        verifier = APIKeyVerifier("test-key-123")
        result = await verifier.verify_token("wrong-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_empty_token(self):
        """Test verifying empty token returns None."""
        verifier = APIKeyVerifier("test-key-123")
        result = await verifier.verify_token("")
        assert result is None


class TestCreateMCPServer:
    """Test FastMCP server factory function."""

    def test_create_server_default_config(self):
        """Test server creation with default config."""
        mcp, _run = create_mcp_server()
        assert mcp is not None
        assert callable(_run)
        assert mcp.name == "Vault Bridge"

    def test_create_server_custom_config(self):
        """Test server creation with custom config."""
        config = ObsidianConfig(vault_path="/custom/vault", log_level="DEBUG")
        mcp, _run = create_mcp_server(config)
        assert mcp is not None
        assert callable(_run)

    def test_create_server_auth_enabled_for_http(self):
        """Test auth is enabled for SSE/HTTP transports with API key."""
        config = ObsidianConfig(api_key="secret-key", transport="sse")
        mcp, _run = create_mcp_server(config)
        assert mcp.auth is not None

    def test_create_server_auth_disabled_for_stdio(self):
        """Test auth is disabled for stdio transport even with API key."""
        config = ObsidianConfig(api_key="secret-key", transport="stdio")
        mcp, _run = create_mcp_server(config)
        assert mcp.auth is None

    def test_create_server_auth_disabled_no_key(self):
        """Test auth is disabled when no API key configured."""
        config = ObsidianConfig(transport="sse")
        mcp, _run = create_mcp_server(config)
        assert mcp.auth is None


class TestMCPTools:
    """Test MCP tool registration and error handling."""

    def test_tools_registered(self):
        """Test all tools are registered."""
        mcp, _ = create_mcp_server()
        # FastMCP 3.x stores tools differently - check via list_tools (async)
        import asyncio
        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools] if tools else []
        
        expected = ["read_note", "write_note", "list_notes", "search_notes", "search_frontmatter", "get_daily_note"]
        for name in expected:
            assert name in tool_names, f"Tool {name} not registered"


class TestMCPToolIntegration:
    """Integration tests for MCP tools via the server."""

    def _extract_result(self, tool_result):
        """Extract the actual result from FastMCP ToolResult."""
        if hasattr(tool_result, 'structured_content') and tool_result.structured_content:
            return tool_result.structured_content.get('result')
        return tool_result

    def test_read_note_not_found(self):
        """Test read_note returns ErrorResponse for missing file."""
        import asyncio

        
        mcp, _ = create_mcp_server()
        tools = asyncio.run(mcp.list_tools())
        read_tool = next(t for t in tools if t.name == "read_note")
        
        # FastMCP tools expect args wrapped in the parameter name
        request = {"request": {"path": "nonexistent.md"}}
        result = asyncio.run(read_tool.run(request))
        result = self._extract_result(result)
        
        assert result["error"] == "FileNotFoundError"

    def test_write_note_and_read_back(self, tmp_path):
        """Test write_note then read_note roundtrip."""
        import asyncio

        
        config = ObsidianConfig(vault_path=str(tmp_path))
        mcp, _ = create_mcp_server(config)
        tools = asyncio.run(mcp.list_tools())
        write_tool = next(t for t in tools if t.name == "write_note")
        read_tool = next(t for t in tools if t.name == "read_note")
        
        # Write a note
        write_req = {"request": {"path": "test.md", "content": "Hello World", "create_dirs": True}}
        write_result = asyncio.run(write_tool.run(write_req))
        write_result = self._extract_result(write_result)
        assert write_result["path"] == "test.md"
        
        # Read it back
        read_req = {"request": {"path": "test.md"}}
        read_result = asyncio.run(read_tool.run(read_req))
        read_result = self._extract_result(read_result)
        assert read_result["content"] == "Hello World"

    def test_list_notes(self, tmp_path):
        """Test list_notes returns entries."""
        import asyncio
        
        config = ObsidianConfig(vault_path=str(tmp_path))
        mcp, _ = create_mcp_server(config)
        tools = asyncio.run(mcp.list_tools())
        write_tool = next(t for t in tools if t.name == "write_note")
        list_tool = next(t for t in tools if t.name == "list_notes")
        
        # Write a couple notes
        asyncio.run(write_tool.run({"request": {"path": "note1.md", "content": "Content 1", "create_dirs": True}}))
        asyncio.run(write_tool.run({"request": {"path": "sub/note2.md", "content": "Content 2", "create_dirs": True}}))
        
        # List them
        list_req = {"request": {"path": "", "recursive": True}}
        list_result = asyncio.run(list_tool.run(list_req))
        list_result = self._extract_result(list_result)
        assert list_result["total"] >= 2
        paths = [e["path"].replace("\\", "/") for e in list_result["entries"]]
        assert "note1.md" in paths
        assert "sub/note2.md" in paths

    def test_search_notes(self, tmp_path):
        """Test search_notes finds matches."""
        import asyncio
        
        config = ObsidianConfig(vault_path=str(tmp_path))
        mcp, _ = create_mcp_server(config)
        tools = asyncio.run(mcp.list_tools())
        write_tool = next(t for t in tools if t.name == "write_note")
        search_tool = next(t for t in tools if t.name == "search_notes")
        
        asyncio.run(write_tool.run({"request": {"path": "searchable.md", "content": "Find this needle in haystack", "create_dirs": True}}))
        
        search_req = {"request": {"pattern": "needle", "path": ""}}
        result = asyncio.run(search_tool.run(search_req))
        result = self._extract_result(result)
        assert result["total"] == 1
        assert result["matches"][0]["match"] == "needle"

    def test_search_frontmatter(self, tmp_path):
        """Test search_frontmatter finds frontmatter matches."""
        import asyncio
        
        config = ObsidianConfig(vault_path=str(tmp_path))
        mcp, _ = create_mcp_server(config)
        tools = asyncio.run(mcp.list_tools())
        write_tool = next(t for t in tools if t.name == "write_note")
        search_tool = next(t for t in tools if t.name == "search_frontmatter")
        
        # Write note with frontmatter
        content = "---\ntags: [important, review]\n---\nBody content"
        asyncio.run(write_tool.run({"request": {"path": "fm.md", "content": content, "create_dirs": True}}))
        
        search_req = {"request": {"key": "tags", "operator": "contains", "value": "important", "path": ""}}
        result = asyncio.run(search_tool.run(search_req))
        result = self._extract_result(result)
        assert result["total"] == 1

    def test_get_daily_note_create(self, tmp_path):
        """Test get_daily_note creates new daily note."""
        import asyncio
        
        config = ObsidianConfig(vault_path=str(tmp_path))
        mcp, _ = create_mcp_server(config)
        tools = asyncio.run(mcp.list_tools())
        daily_tool = next(t for t in tools if t.name == "get_daily_note")
        
        req = {"request": {"date": "2024-01-15", "folder": "daily", "create_if_missing": True}}
        result = asyncio.run(daily_tool.run(req))
        result = self._extract_result(result)
        assert result["created"] is True
        assert result["date"] == "2024-01-15"
        assert "daily/2024-01-15.md" in result["path"].replace("\\", "/")


class TestRunFunction:
    """Test the run() function for different transports."""

    @patch("obsidian_mcp.server.FastMCP.run")
    def test_run_stdio(self, mock_run):
        """Test stdio transport calls mcp.run()."""
        config = ObsidianConfig(transport="stdio")
        _, run = create_mcp_server(config)
        run()
        mock_run.assert_called_once()

    @patch("obsidian_mcp.server.FastMCP.run_http_async")
    def test_run_sse(self, mock_run_http):
        """Test SSE transport calls mcp.run_http_async()."""
        config = ObsidianConfig(transport="sse")
        _, run = create_mcp_server(config)
        run()
        mock_run_http.assert_called_once()

    @patch("obsidian_mcp.server.FastMCP.run_http_async")
    def test_run_streamable_http(self, mock_run_http):
        """Test streamable-http transport calls mcp.run_http_async()."""
        config = ObsidianConfig(transport="streamable-http")
        _, run = create_mcp_server(config)
        run()
        mock_run_http.assert_called_once()

    def test_run_invalid_transport_raises_at_config(self):
        """Test invalid transport raises at config creation."""
        with pytest.raises(Exception, match="transport"):
            ObsidianConfig(transport="invalid")


class TestMainEntryPoint:
    """Test main() entry point."""

    @patch("obsidian_mcp.server.create_mcp_server")
    def test_main_calls_create_and_run(self, mock_create):
        """Test main() creates server and calls run()."""
        mock_mcp = Mock()
        mock_run = Mock()
        mock_create.return_value = (mock_mcp, mock_run)

        from obsidian_mcp.server import main
        main()

        mock_create.assert_called_once()
        mock_run.assert_called_once()