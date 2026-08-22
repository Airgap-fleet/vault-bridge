# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-22

### Added
- **Core MCP Tools**: `read_note`, `write_note`, `list_notes`, `search_notes`, `search_frontmatter`, `get_daily_note`
- **Path Security**: Path traversal protection with vault-root enforcement
- **Frontmatter Support**: Full YAML frontmatter parsing, formatting, and round-trip preservation
- **Daily Notes**: Get/create daily notes with optional templates
- **Structured Logging**: JSON logging via `structlog` with configurable level
- **Configuration**: Pydantic Settings with environment variable support (`OBSIDIAN_MCP_*`)
- **Multi-Transport**: stdio (default), SSE, and Streamable HTTP transports
- **API Key Auth**: Bearer token authentication for HTTP/SSE transports
- **Test Suite**: 37 unit tests with 81% core coverage
- **CI/CD**: GitHub Actions workflow (test matrix 3.10/3.11/3.12, lint, build, publish)

### Changed
- Refactored server to factory pattern (`create_mcp_server`) for config-driven instantiation
- Entry point updated to `obsidian_mcp.server:main`
- Dependency: added `pydantic-settings>=2.3` for config management

### Security
- Path traversal attacks prevented (absolute paths and `../` sequences rejected)
- File size limits enforced (configurable, default 10MB)
- Symlink following disabled by default
- API key authentication required for non-stdio transports

## [0.1.0] - 2026-08-21

### Added
- Initial release with basic Obsidian vault operations
- FastMCP 3.4 integration
- Basic test infrastructure