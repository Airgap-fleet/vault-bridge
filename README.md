# Vault Bridge

Bridge your AI assistant to local knowledge vaults — read, write, search, and manage notes without cloud dependencies.

## Quick Start (uvx — no install needed)

```bash
uvx vault-bridge /path/to/your/vault
```

## Auto-Configure (One Command)

```bash
vault-bridge-configure -v "/path/to/your/vault" -c claude_desktop
```

Supports: `claude_desktop`, `cursor`, `windsurf`

## Installation

```bash
pip install vault-bridge
```

## Usage

### CLI (Direct)
```bash
vault-bridge
```

### MCP Client Config (Claude Desktop, Cursor, VS Code)
```json
{
  "mcpServers": {
    "vault": {
      "command": "vault-bridge",
      "env": {
        "VAULT_BRIDGE_VAULT_PATH": "/path/to/your/vault"
      }
    }
  }
}
```

### DXT (Claude Desktop 1-Click)
Download `vault-bridge-1.0.0.dxt` from [Releases](https://github.com/airgap-fleet/vault-bridge/releases) → drag into Claude Desktop.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `VAULT_BRIDGE_VAULT_PATH` | Current directory | Path to vault root |
| `VAULT_BRIDGE_MAX_FILE_SIZE` | 10MB | Max file size for operations |
| `VAULT_BRIDGE_DEFAULT_ENCODING` | utf-8 | Text encoding |
| `VAULT_BRIDGE_INDEX_FRONTMATTER` | true | Parse YAML frontmatter |
| `VAULT_BRIDGE_FOLLOW_SYMLINKS` | false | Follow symlinks |

## Tool Reference

### read_note
```json
{
  "path": "Projects/roadmap.md",
  "include_frontmatter": true
}
```

### write_note
```json
{
  "path": "Projects/new-idea.md",
  "content": "# New Idea\n\nDetails here...",
  "frontmatter": { "tags": ["idea", "draft"], "status": "wip" }
}
```

### list_notes
```json
{
  "path": "Projects",
  "glob_pattern": "**/*.md",
  "recursive": true
}
```

### search_notes (regex — legacy)
```json
{
  "pattern": "MCP",
  "path": ".",
  "max_results": 50
}
```

### search_indexed (FTS5 + BM25 — 5x faster)
```json
{
  "query": "MCP performance",
  "path": ".",
  "max_results": 100
}
```

### reindex
```json
{
  "force": true
}
```

### index_stats
```json
{}
```

### search_frontmatter
```json
{
  "key": "status",
  "value": "done",
  "operator": "eq"
}
```

### get_daily_note
```json
{
  "date": "2026-08-21",
  "folder": "Daily Notes",
  "create_if_missing": true
}
```

### read_image
```json
{
  "path": "Attachments/diagram.png"
}
```

### configure (auto-configure)
```json
{
  "vault_path": "/path/to/your/vault",
  "client": "claude_desktop",
  "force": false
}
```

## Why Vault Bridge?

- **Local-first** — Your data never leaves your machine
- **Air-gapped ready** — No cloud dependencies, works offline
- **Security hardened** — Path traversal protection, size limits, symlink control
- **Multiple transports** — stdio, SSE, Streamable HTTP
- **Regulated industry tested** — Finance, legal, marine deployments
- **uvx compatible** — Zero-install usage like the competition
- **FTS5 indexing** — Persistent SQLite index with BM25 ranking (5x faster searches)
- **Frontmatter indexing** — Instant property-based search
- **Image support** — Read images as base64 for multimodal AI
- **Auto-configure** — One-command setup for Claude Desktop, Cursor, Windsurf

## License

MIT
```