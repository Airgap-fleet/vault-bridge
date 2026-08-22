"""Obsidian MCP Server - FastMCP server for Obsidian vault operations."""

import sys
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier, AccessToken

from .core import ObsidianCore
from .models import (
    ObsidianConfig,
    ReadNoteRequest,
    ReadNoteResponse,
    WriteNoteRequest,
    WriteNoteResponse,
    ListNotesRequest,
    ListNotesResponse,
    SearchNotesRequest,
    SearchNotesResponse,
    SearchFrontmatterRequest,
    SearchFrontmatterResponse,
    DailyNoteRequest,
    DailyNoteResponse,
    ErrorResponse,
)

from .logging import configure_logging, get_logger


class APIKeyVerifier(TokenVerifier):
    """Simple API key verifier for MCP transport authentication."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        super().__init__()
    
    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self.api_key:
            return AccessToken(token=token, scopes=["mcp"])
        return None


def create_mcp_server(config: ObsidianConfig | None = None):
    """Create and configure the FastMCP server."""
    config = config or ObsidianConfig()
    
    # Configure structured logging
    configure_logging(level=config.log_level, json_output=config.log_json)
    logger = get_logger(__name__)
    
    # Initialize FastMCP server with auth if API key is configured
    auth = None
    if config.api_key and config.transport != "stdio":
        auth = APIKeyVerifier(config.api_key)
        logger.info("auth.enabled", transport=config.transport)
    
    mcp = FastMCP(
        "Obsidian Vault",
        auth=auth,
    )
    
    # Initialize core with config
    core = ObsidianCore(config)

    @mcp.tool()
    def read_note(request: ReadNoteRequest) -> ReadNoteResponse | ErrorResponse:
        """Read a note from the Obsidian vault."""
        try:
            return core.read_note(request)
        except Exception as e:
            logger.error("read_note.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def write_note(request: WriteNoteRequest) -> WriteNoteResponse | ErrorResponse:
        """Write a note to the Obsidian vault."""
        try:
            return core.write_note(request)
        except Exception as e:
            logger.error("write_note.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def list_notes(request: ListNotesRequest) -> ListNotesResponse | ErrorResponse:
        """List notes in the Obsidian vault."""
        try:
            return core.list_notes(request)
        except Exception as e:
            logger.error("list_notes.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def search_notes(request: SearchNotesRequest) -> SearchNotesResponse | ErrorResponse:
        """Search notes in the Obsidian vault using regex."""
        try:
            return core.search_notes(request)
        except Exception as e:
            logger.error("search_notes.error", pattern=request.pattern, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def search_frontmatter(request: SearchFrontmatterRequest) -> SearchFrontmatterResponse | ErrorResponse:
        """Search notes by frontmatter key/value."""
        try:
            return core.search_frontmatter(request)
        except Exception as e:
            logger.error("search_frontmatter.error", key=request.key, operator=request.operator, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def get_daily_note(request: DailyNoteRequest) -> DailyNoteResponse | ErrorResponse:
        """Get or create a daily note."""
        try:
            return core.get_daily_note(request)
        except Exception as e:
            logger.error("get_daily_note.error", date=request.date, folder=request.folder, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    def run():
        """Entry point for the obsidian-mcp CLI."""
        logger.info("server.starting", name="Obsidian Vault", transport=config.transport, host=config.host, port=config.port, path=config.path)
        
        if config.transport == "stdio":
            mcp.run()
        elif config.transport == "sse":
            mcp.run_sse()
        elif config.transport == "streamable-http":
            mcp.run_streamable_http()
        else:
            logger.error("server.invalid_transport", transport=config.transport)
            raise ValueError(f"Unknown transport: {config.transport}")

    return mcp, run


def main():
    """Entry point for the obsidian-mcp CLI."""
    mcp, run = create_mcp_server()
    run()


if __name__ == "__main__":
    main()