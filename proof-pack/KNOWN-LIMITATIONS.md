# Known limitations (honest)

1. **UNSIGNED INTERNAL** — no Authenticode signature yet; SmartScreen / firm policy may block until a signed MSI/EXE exists.
2. **MSI not built on this machine** — WiX / Build Tools absent; PowerShell one-command installer is the supported Windows path. `installer\wix\` is a scaffold only.
3. **Env var prefix** — runtime settings use **`OBSIDIAN_MCP_*`** (see `src/obsidian_mcp/models.py`). Older docs mentioning `VAULT_BRIDGE_VAULT_PATH` are incorrect for this codebase; the installer sets `OBSIDIAN_MCP_VAULT_PATH`.
4. **Installer may use the internet during setup** (uv, CPython, locked wheels). Runtime bridge operation does not require network.
5. **AI desk clients are out of scope** — Claude Desktop / Cursor may open their own connections; this pack proves the bridge process path only.
6. **Default transport must stay stdio** for air-gap claims. HTTP/SSE modes exist in code for enterprise scenarios and are **not** part of the zero-egress demo.
7. **No fabricated certifications** — no ISO 27001 / SOC 2 / Cyber Essentials / Lexcel claim in this pack.
8. **configure.py historically suggested `uvx`** — the Windows installer writes MCP config pointing at the **local** launcher instead, so runtime does not pull from PyPI.
9. **Formal CycloneDX SBOM** not yet emitted; `uv.lock` is the lockfile evidence.
10. **Non-technical client README** is at repo-root `CLIENT-README.md` (Stage 2 item 3). Technical `README.md` keeps developer detail and points non-technical readers there.
