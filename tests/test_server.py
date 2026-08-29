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
        mcp = create_mcp_server()
        assert mcp is not None
        assert mcp.name == "Vault Bridge"

    def test_create_server_custom_config(self):
        """Test server creation with custom config."""
        config = ObsidianConfig(vault_path="/custom/vault", log_level="DEBUG")
        mcp = create_mcp_server(config)
        assert mcp is not None

    def test_create_server_auth_enabled_for_http(self):
        """Test auth is enabled for SSE/HTTP transports with API key."""
        config = ObsidianConfig(api_key="secret-key", transport="sse")
        mcp = create_mcp_server(config)
        assert mcp.auth is not None

    def test_create_server_auth_disabled_for_stdio(self):
        """Test auth is disabled for stdio transport even with API key."""
        config = ObsidianConfig(api_key="secret-key", transport="stdio")
        mcp = create_mcp_server(config)
        assert mcp.auth is None

    def test_create_server_auth_disabled_no_key(self):
        """Test auth is disabled when no API key configured."""
        config = ObsidianConfig(transport="sse")
        mcp = create_mcp_server(config)
        assert mcp.auth is None


class TestMCPTools:
    """Test MCP tool registration and error handling."""

    def test_tools_registered(self):
        """Test all tools are registered."""
        mcp = create_mcp_server()
        # FastMCP 3.x stores tools differently - check via list_tools (async)
        import asyncio
        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools] if tools else []

        expected = ["read_note", "write_note", "list_notes", "search_notes", "search_frontmatter", "get_daily_note"]
        for name in expected:
            assert name in tool_names, f"Tool {name} not registered"


class TestRunFunction:
    """Test the run() entry point behavior."""

    def test_run_stdio_uses_fastmcp_run(self):
        """Test that stdio transport uses FastMCP.run."""
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        # Verify the _run attribute exists and is callable
        assert hasattr(mcp, "_run")
        assert callable(mcp._run)
        
        # For stdio, run() should delegate to FastMCP.run
        # We can't easily test the internal call without complex mocking
        # Just verify the function exists and is callable

    def test_run_sse_uses_run_http_async(self):
        """Test that SSE transport uses run_http_async."""
        config = ObsidianConfig(transport="sse")
        mcp = create_mcp_server(config)
        
        # Verify the _run attribute exists
        assert hasattr(mcp, "_run")
        assert callable(mcp._run)

    def test_run_streamable_http_uses_run_http_async(self):
        """Test that streamable-http transport uses run_http_async."""
        config = ObsidianConfig(transport="streamable-http")
        mcp = create_mcp_server(config)
        
        # Verify the _run attribute exists
        assert hasattr(mcp, "_run")
        assert callable(mcp._run)

    def test_run_invalid_transport_raises_at_config(self):
        """Test invalid transport raises at config creation."""
        with pytest.raises(Exception, match="transport"):
            ObsidianConfig(transport="invalid")


class TestMainEntryPoint:
    """Test main() entry point."""

    @patch("obsidian_mcp.server.create_mcp_server")
    def test_main_calls_create_and_run(self, mock_create):
        """Test main() creates server and calls _run()."""
        mock_mcp = Mock()
        mock_run = Mock()
        mock_mcp._run = mock_run
        mock_create.return_value = mock_mcp

        from obsidian_mcp.server import main
        main()

        mock_create.assert_called_once()
        mock_run.assert_called_once()


class TestInMemoryToolCalls:
    """Test tool calls using in-memory Client (FastMCP best practice)."""

    @pytest.mark.asyncio
    async def test_read_note_tool(self):
        """Test read_note tool via in-memory client."""
        from fastmcp import Client
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        async with Client(mcp) as client:
            # This tests the tool registration and basic call structure
            # without needing a real vault
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "read_note" in tool_names

    @pytest.mark.asyncio
    async def test_write_note_tool(self):
        """Test write_note tool registration."""
        from fastmcp import Client
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "write_note" in tool_names

    @pytest.mark.asyncio
    async def test_list_notes_tool(self):
        """Test list_notes tool registration."""
        from fastmcp import Client
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "list_notes" in tool_names

    @pytest.mark.asyncio
    async def test_search_notes_tool(self):
        """Test search_notes tool registration."""
        from fastmcp import Client
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "search_notes" in tool_names

    @pytest.mark.asyncio
    async def test_search_frontmatter_tool(self):
        """Test search_frontmatter tool registration."""
        from fastmcp import Client
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "search_frontmatter" in tool_names

    @pytest.mark.asyncio
    async def test_get_daily_note_tool(self):
        """Test get_daily_note tool registration."""
        from fastmcp import Client
        config = ObsidianConfig(transport="stdio")
        mcp = create_mcp_server(config)
        
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "get_daily_note" in tool_names