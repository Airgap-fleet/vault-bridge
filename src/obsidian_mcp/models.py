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