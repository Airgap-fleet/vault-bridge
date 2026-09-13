# Egress observation notes

## Claim (architecture)

Default Vault Bridge transport is **stdio**. The process does not open a server port and does not call vendor APIs with vault content.

## Observation methods

1. **Windows Resource Monitor (`resmon.exe`)** — Network tab; watch the bridge PID during `scripts\self_test.ps1`.
2. **`Observe-Egress.ps1`** — starts the self-test while sampling `Get-NetTCPConnection` for the child process; writes JSON snapshots under an output folder.
3. Optional firm tools (TCPView, Wireshark, firewall logs) — acceptable substitutes; record tool name + version in the pilot notes.

## Pass criteria

- No established TCP connections from the bridge process to non-loopback remote addresses during initialize / tools/list / list_notes.
- Self-test exits 0.

## Setup-time vs runtime

The **installer** may use the internet to fetch `uv`, CPython, and locked packages. That is **setup only**. Runtime demos must use an already-installed tree and must not invoke `uv sync` / `pip install` during the recording.
