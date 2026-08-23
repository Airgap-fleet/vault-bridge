"""Obsidian MCP Server configuration."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObsidianConfig(BaseSettings):
    """Configuration for the Obsidian MCP Server."""

    model_config = SettingsConfigDict(
        env_prefix="OBSIDIAN_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Vault settings
    vault_path: Path = Field(
        default=Path.cwd(),
        description="Path to the Obsidian vault root directory.",
    )
    max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        ge=1024,
        le=1024 * 1024 * 1024,  # 1 GB max
        description="Maximum file size for read/write operations in bytes.",
    )
    default_encoding: str = Field(
        default="utf-8",
        description="Default text encoding for read/write operations.",
    )
    index_frontmatter: bool = Field(
        default=True,
        description="Whether to parse and index YAML frontmatter.",
    )
    follow_symlinks: bool = Field(
        default=False,
        description="Whether to follow symlinks.",
    )

    # Transport settings
    transport: Literal["stdio", "sse", "streamable-http"] = Field(
        default="stdio",
        description="MCP transport protocol: stdio, sse, or streamable-http.",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Host to bind HTTP/SSE server to.",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port to bind HTTP/SSE server to.",
    )
    path: str = Field(
        default="/mcp",
        description="MCP endpoint path for HTTP/SSE transports.",
    )

    # Auth settings
    api_key: str | None = Field(
        default=None,
        description="API key for authentication (required for HTTP/SSE transports).",
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="HTTP header name for API key authentication.",
    )

    # Logging settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level.",
    )
    log_json: bool = Field(
        default=True,
        description="Output logs as JSON (structured) instead of console format.",
    )

    @property
    def resolved_vault_path(self) -> Path:
        """Return resolved absolute vault path."""
        return self.vault_path.expanduser().resolve()


class ReadNoteRequest(BaseModel):
    """Request model for read_note tool."""

    path: str = Field(description="Path to the note relative to vault root.")
    include_frontmatter: bool = Field(
        default=True,
        description="Whether to parse and return frontmatter separately.",
    )


class ReadNoteResponse(BaseModel):
    """Response model for read_note tool."""

    path: str = Field(description="The path that was read.")
    content: str = Field(description="Note content as text (without frontmatter).")
    frontmatter: dict[str, Any] | None = Field(
        default=None, description="Parsed YAML frontmatter if present and requested."
    )
    size: int = Field(description="File size in bytes.")
    modified: float = Field(description="Last modified timestamp (Unix epoch).")


class WriteNoteRequest(BaseModel):
    """Request model for write_note tool."""

    path: str = Field(description="Path to the note relative to vault root.")
    content: str = Field(description="Note content to write.")
    frontmatter: dict[str, Any] | None = Field(
        default=None, description="YAML frontmatter to prepend to the note."
    )
    create_dirs: bool = Field(
        default=True,
        description="Create parent directories if they don't exist.",
    )
    atomic: bool = Field(
        default=True,
        description="Write atomically using a temporary file and rename.",
    )


class WriteNoteResponse(BaseModel):
    """Response model for write_note tool."""

    path: str = Field(description="The path that was written.")
    size: int = Field(description="Number of bytes written.")


class ListNotesRequest(BaseModel):
    """Request model for list_notes tool."""

    path: str = Field(default=".", description="Directory path to list, relative to vault root.")
    glob_pattern: str | None = Field(
        default="**/*.md",
        description="Glob pattern to filter notes (default: all markdown files).",
    )
    recursive: bool = Field(
        default=True,
        description="Whether to list recursively.",
    )
    max_depth: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum recursion depth.",
    )
    include_frontmatter: bool = Field(
        default=False,
        description="Whether to include parsed frontmatter in results.",
    )


class NoteEntry(BaseModel):
    """A single note entry."""

    name: str = Field(description="Note name (basename).")
    path: str = Field(description="Full path relative to vault root.")
    size: int = Field(description="File size in bytes.")
    modified: float = Field(description="Last modified timestamp (Unix epoch).")
    frontmatter: dict[str, Any] | None = Field(
        default=None, description="Parsed frontmatter if requested."
    )


class ListNotesResponse(BaseModel):
    """Response model for list_notes tool."""

    path: str = Field(description="The directory path that was listed.")
    entries: list[NoteEntry] = Field(description="List of note entries.")
    total: int = Field(description="Total number of entries returned.")


class SearchNotesRequest(BaseModel):
    """Request model for search_notes tool."""

    pattern: str = Field(description="Search pattern (ripgrep-compatible regex).")
    path: str = Field(default=".", description="Directory to search in, relative to vault root.")
    glob_pattern: str | None = Field(
        default="**/*.md",
        description="Glob pattern to filter files.",
    )
    case_sensitive: bool = Field(
        default=True,
        description="Whether the search is case-sensitive.",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of results to return.",
    )
    context_lines: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of context lines around each match.",
    )


class SearchMatch(BaseModel):
    """A single search match."""

    file: str = Field(description="Path to the file containing the match, relative to vault root.")
    line: int = Field(description="Line number of the match (1-indexed).")
    column: int | None = Field(default=None, description="Column number of the match (1-indexed).")
    match: str = Field(description="The matched text.")
    context_before: list[str] = Field(default_factory=list, description="Lines before the match.")
    context_after: list[str] = Field(default_factory=list, description="Lines after the match.")


class SearchNotesResponse(BaseModel):
    """Response model for search_notes tool."""

    pattern: str = Field(description="The search pattern used.")
    path: str = Field(description="The directory that was searched.")
    matches: list[SearchMatch] = Field(description="List of matches found.")
    total: int = Field(description="Total number of matches found.")
    truncated: bool = Field(description="Whether results were truncated due to max_results.")


class SearchFrontmatterRequest(BaseModel):
    """Request model for search_frontmatter tool."""

    key: str = Field(description="Frontmatter key to search for.")
    value: str | None = Field(
        default=None, description="Optional value to match (exact or substring)."
    )
    path: str = Field(default=".", description="Directory to search in, relative to vault root.")
    glob_pattern: str | None = Field(
        default="**/*.md",
        description="Glob pattern to filter files.",
    )
    operator: str = Field(
        default="eq",
        description="Comparison operator: eq, ne, contains, startswith, endswith, gt, lt, gte, lte, exists.",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of results to return.",
    )


class FrontmatterMatch(BaseModel):
    """A single frontmatter match."""

    file: str = Field(description="Path to the file, relative to vault root.")
    frontmatter: dict[str, Any] = Field(description="Full frontmatter of the matched note.")


class SearchFrontmatterResponse(BaseModel):
    """Response model for search_frontmatter tool."""

    key: str = Field(description="The frontmatter key searched.")
    value: str | None = Field(description="The value searched for (if any).")
    operator: str = Field(description="The operator used.")
    matches: list[FrontmatterMatch] = Field(description="List of matching notes.")
    total: int = Field(description="Total number of matches found.")
    truncated: bool = Field(description="Whether results were truncated due to max_results.")


class DailyNoteRequest(BaseModel):
    """Request model for get_daily_note tool."""

    date: str | None = Field(
        default=None, description="Date in YYYY-MM-DD format (default: today)."
    )
    folder: str = Field(
        default="Daily Notes", description="Folder containing daily notes."
    )
    create_if_missing: bool = Field(
        default=False, description="Create the daily note if it doesn't exist."
    )
    template: str | None = Field(
        default=None, description="Optional template path for new daily notes."
    )


class DailyNoteResponse(BaseModel):
    """Response model for get_daily_note tool."""

    path: str = Field(description="Path to the daily note.")
    content: str = Field(description="Note content.")
    frontmatter: dict[str, Any] | None = Field(default=None, description="Parsed frontmatter.")
    date: str = Field(description="Date of the daily note (YYYY-MM-DD).")
    created: bool = Field(description="Whether the note was created.")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error type/code.")
    message: str = Field(description="Human-readable error message.")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details.")


class IndexStatsRequest(BaseModel):
    """Request model for index_stats tool."""

    pass


class IndexStatsResponse(BaseModel):
    """Response model for index_stats tool."""

    total_notes: int = Field(description="Total notes in index.")
    indexed_count: int = Field(description="Notes indexed in last full run.")
    last_full_index: float = Field(description="Timestamp of last full index.")
    db_size_bytes: int = Field(description="Index database size in bytes.")
    index_path: str = Field(description="Path to index database.")


class ReindexRequest(BaseModel):
    """Request model for reindex tool."""

    force: bool = Field(default=False, description="Force full re-index (ignore mtime).")


class ReindexResponse(BaseModel):
    """Response model for reindex tool."""

    indexed: int = Field(description="Files indexed.")
    removed: int = Field(description="Files removed from index.")
    errors: int = Field(description="Files with errors.")
    skipped: int = Field(description="Files skipped (unchanged).")
    elapsed_ms: int = Field(description="Time taken in milliseconds.")


class SearchIndexedRequest(BaseModel):
    """Request model for search_indexed tool (FTS5 + BM25)."""

    query: str = Field(description="Full-text search query (FTS5 syntax).")
    path: str = Field(default=".", description="Directory to search in, relative to vault root.")
    max_results: int = Field(default=100, ge=1, le=10000, description="Maximum results.")


class SearchIndexedMatch(BaseModel):
    """A single indexed search match with ranking."""

    file: str = Field(description="Path to the file, relative to vault root.")
    name: str = Field(description="File name.")
    size: int = Field(description="File size in bytes.")
    modified: float = Field(description="Last modified timestamp.")
    frontmatter: dict[str, Any] | None = Field(default=None, description="Parsed frontmatter.")
    rank: float = Field(description="BM25 rank (lower is better).")
    snippet: str = Field(description="Highlighted snippet from match.")


class SearchIndexedResponse(BaseModel):
    """Response model for search_indexed tool."""

    query: str = Field(description="The search query used.")
    path: str = Field(description="The directory that was searched.")
    matches: list[SearchIndexedMatch] = Field(description="Ranked matches.")
    total: int = Field(description="Total matches found.")
    truncated: bool = Field(description="Whether results were truncated.")


class ReadImageRequest(BaseModel):
    """Request model for read_image tool."""

    path: str = Field(description="Path to the image relative to vault root.")


class ReadImageResponse(BaseModel):
    """Response model for read_image tool."""

    path: str = Field(description="Path to the image.")
    mime_type: str = Field(description="MIME type of the image.")
    size: int = Field(description="File size in bytes.")
    width: int = Field(description="Image width in pixels.")
    height: int = Field(description="Image height in pixels.")
    base64: str = Field(description="Base64-encoded image data.")


class ConfigureRequest(BaseModel):
    """Request model for configure tool (auto-config CLI)."""

    vault_path: str = Field(description="Path to the Obsidian vault root directory.")
    client: str = Field(default="claude_desktop", description="Target client: claude_desktop, cursor, windsurf.")
    force: bool = Field(default=False, description="Overwrite existing configuration.")


class ConfigureResponse(BaseModel):
    """Response model for configure tool."""

    success: bool = Field(description="Whether configuration succeeded.")
    config_path: str = Field(description="Path to the configuration file that was updated.")
    message: str = Field(description="Human-readable result message.")


# ===== NEW: MCP Resources API (vault://, file://, postgres:// URIs) =====

class ResourceRequest(BaseModel):
    """Request model for read_resource tool."""

    uri: str = Field(description="Resource URI (vault://, file://, postgres://).")
    offset: int = Field(default=0, ge=0, description="Byte offset for pagination.")
    limit: int = Field(default=8192, ge=1, le=1048576, description="Max bytes to read.")


class ResourceContent(BaseModel):
    """A single resource content block."""

    uri: str = Field(description="Resource URI.")
    mime_type: str = Field(description="MIME type.")
    text: str | None = Field(default=None, description="Text content (if text-based).")
    blob: str | None = Field(default=None, description="Base64-encoded binary (if binary).")
    name: str | None = Field(default=None, description="Human-readable name (for directory listings).")


class ResourceResponse(BaseModel):
    """Response model for read_resource tool."""

    contents: list[ResourceContent] = Field(description="List of resource contents.")


class ListResourcesRequest(BaseModel):
    """Request model for list_resources tool."""

    uri_prefix: str = Field(default="vault://", description="URI prefix to list (vault://, file://).")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum resources to return.")
    cursor: str | None = Field(default=None, description="Pagination cursor.")


class ResourceEntry(BaseModel):
    """A single resource entry."""

    uri: str = Field(description="Resource URI.")
    name: str = Field(description="Human-readable name.")
    mime_type: str = Field(description="MIME type.")
    size: int | None = Field(default=None, description="Size in bytes if known.")


class ListResourcesResponse(BaseModel):
    """Response model for list_resources tool."""

    resources: list[ResourceEntry] = Field(description="List of resources.")
    next_cursor: str | None = Field(default=None, description="Next pagination cursor.")


# ===== NEW: Wikilink / Backlink Graph =====

class WikilinkRequest(BaseModel):
    """Request model for wikilink tools."""

    path: str = Field(description="Path to note relative to vault root.")
    include_backlinks: bool = Field(default=True, description="Include backlinks in response.")


class WikilinkEntry(BaseModel):
    """A single wikilink."""

    target: str = Field(description="Target of the wikilink (e.g., [[Target Note]]).")
    alias: str | None = Field(default=None, description="Display alias if different from target.")
    line: int = Field(description="Line number where link appears.")
    context: str = Field(description="Surrounding text context.")


class BacklinkEntry(BaseModel):
    """A single backlink (reverse link)."""

    source: str = Field(description="Path to the note containing the link.")
    line: int = Field(description="Line number in source note.")
    context: str = Field(description="Surrounding text context.")


class WikilinkResponse(BaseModel):
    """Response model for get_wikilinks tool."""

    path: str = Field(description="Note that was analyzed.")
    wikilinks: list[WikilinkEntry] = Field(description="Outgoing wikilinks.")
    backlinks: list[BacklinkEntry] = Field(description="Incoming backlinks.")
    total_outgoing: int = Field(description="Total outgoing links.")
    total_incoming: int = Field(description="Total incoming backlinks.")


class GraphRequest(BaseModel):
    """Request model for graph tools."""

    center: str | None = Field(default=None, description="Center note for graph (optional).")
    depth: int = Field(default=2, ge=1, le=5, description="Graph traversal depth.")
    limit: int = Field(default=200, ge=1, le=1000, description="Max nodes to return.")
    include_orphans: bool = Field(default=False, description="Include notes with no links.")


class GraphNode(BaseModel):
    """Graph node (note)."""

    id: str = Field(description="Node ID (note path).")
    label: str = Field(description="Display label.")
    note_count: int = Field(default=0, description="Number of notes at this path (for vaults).")


class GraphEdge(BaseModel):
    """Graph edge (link)."""

    source: str = Field(description="Source node ID.")
    target: str = Field(description="Target node ID.")
    type: str = Field(default="wikilink", description="Edge type: wikilink, tag, folder.")


class GraphResponse(BaseModel):
    """Response model for graph tool."""

    nodes: list[GraphNode] = Field(description="Graph nodes.")
    edges: list[GraphEdge] = Field(description="Graph edges.")
    center: str | None = Field(default=None, description="Center node if specified.")


# ===== NEW: Canvas Support =====

class CanvasRequest(BaseModel):
    """Request model for read_canvas tool."""

    path: str = Field(description="Path to .canvas file relative to vault root.")


class CanvasNode(BaseModel):
    """Canvas node (text, link, file, group)."""

    id: str = Field(description="Node ID.")
    type: str = Field(description="Node type: text, link, file, group.")
    x: float = Field(description="X position.")
    y: float = Field(description="Y position.")
    width: float | None = Field(default=None, description="Width.")
    height: float | None = Field(default=None, description="Height.")
    text: str | None = Field(default=None, description="Text content (for text nodes).")
    url: str | None = Field(default=None, description="URL (for link nodes).")
    file: str | None = Field(default=None, description="File path (for file nodes).")
    color: str | None = Field(default=None, description="Node color.")
    label: str | None = Field(default=None, description="Group label.")


class CanvasEdge(BaseModel):
    """Canvas edge (connection)."""

    id: str = Field(description="Edge ID.")
    from_node: str = Field(description="Source node ID.")
    from_side: str | None = Field(default=None, description="Source side: top, right, bottom, left.")
    to_node: str = Field(description="Target node ID.")
    to_side: str | None = Field(default=None, description="Target side.")
    label: str | None = Field(default=None, description="Edge label.")
    color: str | None = Field(default=None, description="Edge color.")


class CanvasResponse(BaseModel):
    """Response model for read_canvas tool."""

    path: str = Field(description="Canvas file path.")
    nodes: list[CanvasNode] = Field(description="Canvas nodes.")
    edges: list[CanvasEdge] = Field(description="Canvas edges.")


# ===== NEW: Properties v2 (Obsidian native) =====

class PropertiesRequest(BaseModel):
    """Request model for get_properties tool."""

    path: str = Field(description="Path to note relative to vault root.")


class PropertyValue(BaseModel):
    """A single property value (supports Obsidian property types)."""

    type: str = Field(description="Property type: string, number, boolean, date, datetime, list, multiselect.")
    value: Any = Field(description="Property value (type-dependent).")


class PropertiesResponse(BaseModel):
    """Response model for get_properties tool."""

    path: str = Field(description="Note path.")
    properties: dict[str, PropertyValue] = Field(description="Parsed properties.")


# ===== NEW: Multi-Vault =====

class VaultEntry(BaseModel):
    """A single vault in multi-vault setup."""

    name: str = Field(description="Vault display name.")
    path: str = Field(description="Absolute path to vault root.")
    is_active: bool = Field(default=True, description="Whether vault is currently indexed.")


class MultiVaultConfigRequest(BaseModel):
    """Request model for multi_vault_config tool."""

    vaults: list[VaultEntry] = Field(description="List of vaults to configure.")


class MultiVaultConfigResponse(BaseModel):
    """Response model for multi_vault_config tool."""

    configured: list[str] = Field(description="Successfully configured vault names.")
    failed: list[str] = Field(description="Vault names that failed.")
    total: int = Field(description="Total vaults processed.")


class MultiVaultStatusRequest(BaseModel):
    """Request model for multi_vault_status tool."""

    pass


class MultiVaultStatusResponse(BaseModel):
    """Response model for multi_vault_status tool."""

    vaults: list[VaultEntry] = Field(description="Configured vaults.")
    active_count: int = Field(description="Number of active vaults.")
    total_notes: int = Field(description="Total notes across all vaults.")


# ===== NEW: Prometheus Metrics =====

class MetricsRequest(BaseModel):
    """Request model for metrics tool."""

    pass


class MetricsResponse(BaseModel):
    """Response model for metrics tool."""

    metrics: str = Field(description="Prometheus-formatted metrics text.")