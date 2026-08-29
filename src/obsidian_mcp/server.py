"""Vault Bridge — Bridge your AI assistant to local knowledge vaults.
Stateless protocol (2026-07-28): no global session state, explicit config per request.
"""

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from .core import ObsidianCore
from .logging import configure_logging, get_logger
from .models import (
    DailyNoteRequest,
    DailyNoteResponse,
    ErrorResponse,
    ListNotesRequest,
    ListNotesResponse,
    ObsidianConfig,
    ReadNoteRequest,
    ReadNoteResponse,
    SearchFrontmatterRequest,
    SearchFrontmatterResponse,
    SearchNotesRequest,
    SearchNotesResponse,
    WriteNoteRequest,
    WriteNoteResponse,
)


class APIKeyVerifier(TokenVerifier):
    """Simple API key verifier for MCP transport authentication."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        super().__init__()

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self.api_key:
            return AccessToken(token=token, client_id="mcp-client", scopes=["mcp"])
        return None


def create_core(config: ObsidianConfig) -> ObsidianCore:
    """Create a fresh ObsidianCore instance (stateless - no global state)."""
    return ObsidianCore(config)


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

    try:
        mcp = FastMCP(
            "Vault Bridge",
            auth=auth,
        )
    except Exception as e:
        logger.error("fastmcp.init_failed", error=type(e).__name__, message=str(e))
        raise

    @mcp.tool()
    def read_note(request: ReadNoteRequest) -> ReadNoteResponse | ErrorResponse:
        """Read a note from the Obsidian vault."""
        try:
            core = create_core(config)
            return core.read_note(request)
        except Exception as e:  # noqa: BLE001
            logger.error("read_note.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def write_note(request: WriteNoteRequest) -> WriteNoteResponse | ErrorResponse:
        """Write a note to the Obsidian vault."""
        try:
            core = create_core(config)
            return core.write_note(request)
        except Exception as e:  # noqa: BLE001
            logger.error("write_note.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def list_notes(request: ListNotesRequest) -> ListNotesResponse | ErrorResponse:
        """List notes in the Obsidian vault."""
        try:
            core = create_core(config)
            return core.list_notes(request)
        except Exception as e:  # noqa: BLE001
            logger.error("list_notes.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def search_notes(request: SearchNotesRequest) -> SearchNotesResponse | ErrorResponse:
        """Search notes in the Obsidian vault using regex."""
        try:
            core = create_core(config)
            return core.search_notes(request)
        except Exception as e:  # noqa: BLE001
            logger.error("search_notes.error", pattern=request.pattern, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def search_frontmatter(request: SearchFrontmatterRequest) -> SearchFrontmatterResponse | ErrorResponse:
        """Search notes by frontmatter key/value."""
        try:
            core = create_core(config)
            return core.search_frontmatter(request)
        except Exception as e:  # noqa: BLE001
            logger.error("search_frontmatter.error", key=request.key, operator=request.operator, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    @mcp.tool()
    def get_daily_note(request: DailyNoteRequest) -> DailyNoteResponse | ErrorResponse:
        """Get or create a daily note."""
        try:
            core = create_core(config)
            return core.get_daily_note(request)
        except Exception as e:  # noqa: BLE001
            logger.error("get_daily_note.error", date=request.date, folder=request.folder, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))

    def run():
        """Entry point for the vault-bridge CLI."""
        logger.info("server.starting", name="Vault Bridge", transport=config.transport, host=config.host, port=config.port, path=config.path)

        if config.transport == "stdio":
            mcp.run()
        elif config.transport == "sse" or config.transport == "streamable-http":
            mcp.run_http_async()
        else:
            logger.error("server.invalid_transport", transport=config.transport)
            raise ValueError(f"Unknown transport: {config.transport}")

    # Attach run function to mcp for CLI access
        mcp.run = run
        return mcp


def main():
    """Entry point for the vault-bridge CLI."""
    mcp = create_mcp_server()
    mcp._run()


if __name__ == "__main__":
    main()