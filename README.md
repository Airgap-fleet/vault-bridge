# Vault Bridge

Bridge your AI assistant to local knowledge vaults — read, write, search, and manage notes without cloud dependencies.

## Features

- **read_note** — Read a note with optional frontmatter parsing
- **write_note** — Write notes with YAML frontmatter support
- **list_notes** — List notes with glob filtering and recursion
- **search_notes** — Regex search across vault content
- **search_frontmatter** — Query notes by frontmatter key/value
- **get_daily_note** — Get or create daily notes with templates

## Installation

```bash
pip install airgap-vault-bridge
```

## Usage

### CLI (Direct)
```bash
vault-bridge
```

### MCP Client Config (Claude Desktop, Cursor, VS Code)

**Windows (requires full path to executable):**
```json
{
  "mcpServers": {
    "vault": {
      "command": "C:\Users\<user>\AppData\Local\hermes\hermes-agent\venv\Scripts\vault-bridge.exe",
      "env": {
        "OBSIDIAN_MCP_VAULT_PATH": "C:/path/to/vault"
      }
    }
  }
}
```

**macOS/Linux (if on PATH):**
```json
{
  "mcpServers": {
    "vault": {
      "command": "vault-bridge",
      "env": {
        "OBSIDIAN_MCP_VAULT_PATH": "/path/to/vault"
      }
    }
  }
}
```

### DXT (Claude Desktop 1-Click)
Download `airgap-vault-bridge-1.0.2.dxt` from [Releases](https://github.com/airgap-fleet/vault-bridge/releases) → drag into Claude Desktop.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OBSIDIAN_MCP_VAULT_PATH` | Current directory | Path to vault root |
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

### search_notes
```json
{
  "pattern": "MCP",
  "path": ".",
  "max_results": 50
}
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

## Windows-Specific Notes

- The executable is installed to `C:\Users\<user>\AppData\Local\hermes\hermes-agent\venv\Scripts\vault-bridge.exe` when using Hermes
- **Always use the full `.exe` path in MCP client configs on Windows** — bare commands like `vault-bridge` will fail with `ENOENT` because the venv Scripts folder is not on system PATH
- Use forward slashes in environment variable values (`C:/path/to/vault`) — they work fine in JSON
- Escape backslashes in JSON command paths (`C:\Users\...`)

## License

MIT
