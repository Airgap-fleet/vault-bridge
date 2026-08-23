"""Vault Bridge — Bridge your AI assistant to local knowledge vaults.
Stateless protocol (2026-07-28): no global session state, explicit config per request.
"""

import re
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from .core import ObsidianCore
from .logging import configure_logging, get_logger
from .models import (
    CanvasRequest,
    CanvasResponse,
    ConfigureRequest,
    ConfigureResponse,
    DailyNoteRequest,
    DailyNoteResponse,
    ErrorResponse,
    GraphRequest,
    GraphResponse,
    IndexStatsRequest,
    IndexStatsResponse,
    ListNotesRequest,
    ListNotesResponse,
    ListResourcesRequest,
    ListResourcesResponse,
    MetricsRequest,
    MetricsResponse,
    MultiVaultConfigRequest,
    MultiVaultConfigResponse,
    MultiVaultStatusRequest,
    MultiVaultStatusResponse,
    ObsidianConfig,
    PropertiesRequest,
    PropertiesResponse,
    ReadImageRequest,
    ReadImageResponse,
    ReadNoteRequest,
    ReadNoteResponse,
    ReindexRequest,
    ReindexResponse,
    ResourceContent,
    ResourceEntry,
    ResourceRequest,
    ResourceResponse,
    SearchFrontmatterRequest,
    SearchFrontmatterResponse,
    SearchIndexedRequest,
    SearchIndexedResponse,
    SearchNotesRequest,
    SearchNotesResponse,
    VaultEntry,
    WikilinkRequest,
    WikilinkResponse,
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


def create_mcp_server(config: ObsidianConfig | None = None) -> tuple[FastMCP, Callable[[], None]]:
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
        "Vault Bridge",
        auth=auth,
    )
    
    @mcp.tool()
    def read_note(request: ReadNoteRequest) -> ReadNoteResponse | ErrorResponse:
        """Read a note from the Obsidian vault."""
        try:
            core = create_core(config)
            return core.read_note(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("read_note.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("read_note.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error reading note")

    @mcp.tool()
    def write_note(request: WriteNoteRequest) -> WriteNoteResponse | ErrorResponse:
        """Write a note to the Obsidian vault."""
        try:
            core = create_core(config)
            return core.write_note(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("write_note.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("write_note.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error writing note")

    @mcp.tool()
    def list_notes(request: ListNotesRequest) -> ListNotesResponse | ErrorResponse:
        """List notes in the Obsidian vault."""
        try:
            core = create_core(config)
            return core.list_notes(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("list_notes.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("list_notes.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error listing notes")

    @mcp.tool()
    def search_notes(request: SearchNotesRequest) -> SearchNotesResponse | ErrorResponse:
        """Search notes in the Obsidian vault using regex."""
        try:
            core = create_core(config)
            return core.search_notes(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError, re.error) as e:
            logger.error("search_notes.error", pattern=request.pattern, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("search_notes.unexpected", pattern=request.pattern)
            return ErrorResponse(error="InternalError", message="Unexpected error searching notes")

    @mcp.tool()
    def search_frontmatter(request: SearchFrontmatterRequest) -> SearchFrontmatterResponse | ErrorResponse:
        """Search notes by frontmatter key/value."""
        try:
            core = create_core(config)
            return core.search_frontmatter(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("search_frontmatter.error", key=request.key, operator=request.operator, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("search_frontmatter.unexpected", key=request.key)
            return ErrorResponse(error="InternalError", message="Unexpected error searching frontmatter")

    @mcp.tool()
    def get_daily_note(request: DailyNoteRequest) -> DailyNoteResponse | ErrorResponse:
        """Get or create a daily note."""
        try:
            core = create_core(config)
            return core.get_daily_note(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("get_daily_note.error", date=request.date, folder=request.folder, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("get_daily_note.unexpected", date=request.date)
            return ErrorResponse(error="InternalError", message="Unexpected error getting daily note")

    # ===== NEW: Indexed Search (FTS5 + BM25) =====

    @mcp.tool()
    def search_indexed(request: SearchIndexedRequest) -> SearchIndexedResponse | ErrorResponse:
        """Search notes using persistent FTS5 index with BM25 ranking (5x faster than regex)."""
        try:
            core = create_core(config)
            return core.search_indexed(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("search_indexed.error", query=request.query, path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("search_indexed.unexpected", query=request.query)
            return ErrorResponse(error="InternalError", message="Unexpected error searching indexed notes")

    @mcp.tool()
    def reindex(request: ReindexRequest) -> ReindexResponse | ErrorResponse:
        """Rebuild the search index."""
        try:
            core = create_core(config)
            return core.reindex(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("reindex.error", force=request.force, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("reindex.unexpected")
            return ErrorResponse(error="InternalError", message="Unexpected error reindexing")

    @mcp.tool()
    def index_stats(request: IndexStatsRequest) -> IndexStatsResponse | ErrorResponse:
        """Get index statistics."""
        try:
            core = create_core(config)
            return core.index_stats(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("index_stats.error", error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("index_stats.unexpected")
            return ErrorResponse(error="InternalError", message="Unexpected error getting index stats")

    # ===== NEW: Image Support =====

    @mcp.tool()
    def read_image(request: ReadImageRequest) -> ReadImageResponse | ErrorResponse:
        """Read an image from the vault and return base64-encoded data."""
        try:
            core = create_core(config)
            return core.read_image(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("read_image.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("read_image.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error reading image")

    # ===== NEW: Auto-configure =====

    @mcp.tool()
    def configure(request: ConfigureRequest) -> ConfigureResponse | ErrorResponse:
        """Auto-configure vault-bridge for an AI client (Claude Desktop, Cursor, Windsurf)."""
        try:
            # This is a management tool - run the configure logic directly
            from click.testing import CliRunner

            from .configure import main as configure_main

            runner = CliRunner()
            result = runner.invoke(configure_main, [
                "--vault-path", request.vault_path,
                "--client", request.client,
                "--force" if request.force else "",
            ])
            
            if result.exit_code == 0:
                return ConfigureResponse(
                    success=True,
                    config_path=f"~/.config/{request.client}/mcp.json",
                    message="Configuration applied successfully. Restart your client to apply.",
                )
            else:
                return ConfigureResponse(
                    success=False,
                    config_path="",
                    message=result.output,
                )
        except Exception:
            logger.exception("configure.unexpected")
            return ErrorResponse(error="InternalError", message="Unexpected error configuring")

    # ===== NEW: MCP Resources API (vault://, file:// URIs) =====

    @mcp.tool()
    def read_resource(request: ResourceRequest) -> ResourceResponse | ErrorResponse:
        """Read a resource by URI (vault://, file://)."""
        try:
            core = create_core(config)
            return core.read_resource(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("read_resource.error", uri=request.uri, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("read_resource.unexpected", uri=request.uri)
            return ErrorResponse(error="InternalError", message="Unexpected error reading resource")

    @mcp.tool()
    def list_resources(request: ListResourcesRequest) -> ListResourcesResponse | ErrorResponse:
        """List resources under a URI prefix."""
        try:
            core = create_core(config)
            return core.list_resources(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("list_resources.error", uri_prefix=request.uri_prefix, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("list_resources.unexpected", uri_prefix=request.uri_prefix)
            return ErrorResponse(error="InternalError", message="Unexpected error listing resources")

    # ===== NEW: Wikilink / Backlink Graph =====

    @mcp.tool()
    def get_wikilinks(request: WikilinkRequest) -> WikilinkResponse | ErrorResponse:
        """Get outgoing wikilinks and incoming backlinks for a note."""
        try:
            core = create_core(config)
            return core.get_wikilinks(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("get_wikilinks.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("get_wikilinks.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error getting wikilinks")

    @mcp.tool()
    def get_graph(request: GraphRequest) -> GraphResponse | ErrorResponse:
        """Get graph of notes and links."""
        try:
            core = create_core(config)
            return core.get_graph(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("get_graph.error", center=request.center, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("get_graph.unexpected", center=request.center)
            return ErrorResponse(error="InternalError", message="Unexpected error getting graph")

    # ===== NEW: Canvas (.canvas) Support =====

    @mcp.tool()
    def read_canvas(request: CanvasRequest) -> CanvasResponse | ErrorResponse:
        """Read a .canvas file."""
        try:
            core = create_core(config)
            return core.read_canvas(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("read_canvas.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("read_canvas.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error reading canvas")

    # ===== NEW: Properties v2 (Obsidian native) =====

    @mcp.tool()
    def get_properties(request: PropertiesRequest) -> PropertiesResponse | ErrorResponse:
        """Get Obsidian Properties (frontmatter v2) for a note."""
        try:
            core = create_core(config)
            return core.get_properties(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("get_properties.error", path=request.path, error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("get_properties.unexpected", path=request.path)
            return ErrorResponse(error="InternalError", message="Unexpected error getting properties")

    # ===== NEW: Multi-Vault Support =====

    @mcp.tool()
    def multi_vault_config(request: MultiVaultConfigRequest) -> MultiVaultConfigResponse | ErrorResponse:
        """Configure multiple vaults."""
        try:
            core = create_core(config)
            return core.multi_vault_config(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("multi_vault_config.error", error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("multi_vault_config.unexpected")
            return ErrorResponse(error="InternalError", message="Unexpected error configuring vaults")

    @mcp.tool()
    def multi_vault_status(request: MultiVaultStatusRequest) -> MultiVaultStatusResponse | ErrorResponse:
        """Get status of all configured vaults."""
        try:
            core = create_core(config)
            return core.multi_vault_status(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("multi_vault_status.error", error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("multi_vault_status.unexpected")
            return ErrorResponse(error="InternalError", message="Unexpected error getting vault status")

    # ===== NEW: Prometheus Metrics =====

    @mcp.tool()
    def get_metrics(request: MetricsRequest) -> MetricsResponse | ErrorResponse:
        """Get Prometheus-formatted metrics."""
        try:
            core = create_core(config)
            return core.get_metrics(request)
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error("get_metrics.error", error=type(e).__name__, message=str(e))
            return ErrorResponse(error=type(e).__name__, message=str(e))
        except Exception:
            logger.exception("get_metrics.unexpected")
            return ErrorResponse(error="InternalError", message="Unexpected error getting metrics")

    def run() -> None:
        """Entry point for the vault-bridge CLI."""
        logger.info("server.starting", name="Vault Bridge", transport=config.transport, host=config.host, port=config.port, path=config.path)
        
        if config.transport == "stdio":
            mcp.run()
        elif config.transport == "sse" or config.transport == "streamable-http":
            import asyncio
            asyncio.run(mcp.run_http_async())
        else:
            logger.error("server.invalid_transport", transport=config.transport)
            raise ValueError(f"Unknown transport: {config.transport}")

    return mcp, run


def main() -> None:
    """Entry point for the vault-bridge CLI."""
    _, run = create_mcp_server()
    run()


if __name__ == "__main__":
    main()