# Vault Bridge

Bridge your AI assistant to local knowledge vaults â€” read, write, search, and manage notes without cloud dependencies.

**Default mode:** local stdio connector (no listening port). Vault content stays on the path you configure.

> **Non-technical readers (COLP / practice manager / firm IT):** start with [`CLIENT-README.md`](CLIENT-README.md) - install, privacy boundary, verify, uninstall, and support without developer jargon.

## Features

- **read_note** â€” Read a note with optional frontmatter parsing
- **write_note** â€” Write notes with YAML frontmatter support
- **list_notes** â€” List notes with glob filtering and recursion
- **search_notes** â€” Regex search across vault content
- **search_frontmatter** â€” Query notes by frontmatter key/value
- **get_daily_note** â€” Get or create daily notes with templates

## Installation (Windows â€” recommended)

**One command** from the product tree (UNSIGNED INTERNAL until Authenticode is available):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault"
```

Silent (firm IT):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault" -Quiet
```

Post-install smoke (JSON-RPC; fails loudly):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -VaultPath "C:\Path\To\Your\Vault"
```

Details: `installer\README.md`. Zero-egress proof pack: `proof-pack\README.md` (see also `proof-pack\DEMO-CHECKLIST.md`).

> **Signing:** builds produced without an Authenticode certificate are labelled **UNSIGNED INTERNAL**. See `proof-pack\SIGNING.md`.

### Advanced â€” pip / uv (developers)

```bash
pip install vault-bridge
# (some indexes may still show airgap-vault-bridge)
# or, from a checkout with uv.lock:
uv sync --frozen
```

## Usage

### CLI (Direct)
```bash
vault-bridge
```

### MCP Client Config (Claude Desktop, Cursor, VS Code)

Prefer the Private Desk / installer local path over `uvx` for air-gapped desks:

**Windows (requires full path to executable):**
```json
{
  "mcpServers": {
    "vault-bridge": {
      "command": "C:\\Users\\YOU\\AppData\\Local\\AirgapFleet\\vault-bridge\\bin\\vault-bridge.cmd",
      "env": {
        "OBSIDIAN_MCP_VAULT_PATH": "C:/path/to/vault",
        "OBSIDIAN_MCP_TRANSPORT": "stdio"
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
Download `airgap-vault-bridge-1.0.2.dxt` from [Releases](https://github.com/airgap-fleet/vault-bridge/releases) â†’ drag into Claude Desktop.

## Configuration

Runtime settings use the **`OBSIDIAN_MCP_`** environment prefix (see `src/obsidian_mcp/models.py`).

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OBSIDIAN_MCP_VAULT_PATH` | Current directory | Path to vault root |
| `OBSIDIAN_MCP_MAX_FILE_SIZE` | 10MB | Max file size for operations |
| `OBSIDIAN_MCP_DEFAULT_ENCODING` | utf-8 | Text encoding |
| `OBSIDIAN_MCP_INDEX_FRONTMATTER` | true | Parse YAML frontmatter |
| `OBSIDIAN_MCP_FOLLOW_SYMLINKS` | false | Follow symlinks |

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

- Preferred install path after Private Desk installer: `%LOCALAPPDATA%\AirgapFleet\vault-bridge\bin\vault-bridge.cmd` (avoid legacy Hermes venv paths for pilots)
- **Always use the full `.exe` path in MCP client configs on Windows** â€” bare commands like `vault-bridge` will fail with `ENOENT` because the venv Scripts folder is not on system PATH
- Use forward slashes in environment variable values (`C:/path/to/vault`) â€” they work fine in JSON
- Escape backslashes in JSON command paths (`C:\Users\...`)

## License

MIT
