# Zero-egress live demo checklist (run twice)

**Audience:** COLP / practice manager / firm IT. Run this live demo twice. It shows the **Vault Bridge** process does not open vendor outbound connections during local work. This is evidence for your controls, not a certification.

**Goal:** On a visible network monitor, run a realistic vault query through Vault Bridge and show **zero outbound connections from the bridge process**. Recordable as a short screen capture; must be live-repeatable.

**Signing note:** This demo uses the UNSIGNED INTERNAL build until Authenticode is available.

## Before you start

1. Install via `installer\Install-VaultBridge.ps1` (or use the repo `.venv` for an internal dry-run).
2. Have a small markdown vault ready (repo `test-vault\` is fine for dry-runs; use a sample matter folder for client demos).
3. Close unrelated heavy network apps if you want a cleaner Resource Monitor view (optional).

## Pass 1

### A. Open a network monitor (visible on screen)

**Option A (no extra tools):** Windows Resource Monitor

```powershell
resmon.exe
```

- Open the **Network** tab.
- Leave it visible for the recording.

**Option B (scripted snapshot):**

```powershell
powershell -ExecutionPolicy Bypass -File .\proof-pack\Observe-Egress.ps1 -VaultPath "C:\Path\To\Vault" -OutDir "$env:TEMP\vault-bridge-egress-pass1"
```

### B. Run a realistic query through the bridge

Use the JSON-RPC self-test (exercises `initialize`, `tools/list`, and `list_notes` against the vault):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -VaultPath "C:\Path\To\Vault"
```

Expected: `[OK] self-test passed` and a JSON `status=pass` line.

Optional narrative for sales capture: “List notes in this matter folder” / “Search for the undertaking clause” — the self-test’s `list_notes` call is the technical equivalent without requiring a full AI desk in the recording.

### C. Show zero outbound

- In Resource Monitor → Network: confirm the `vault-bridge` / `python` bridge process shows **no remote TCP connections** during the query.
- If using `Observe-Egress.ps1`: open `connections-during.json` / summary — remote endpoints for the bridge PID should be empty (or only loopback, which is not egress).

### D. Tick

- [ ] Monitor visible
- [ ] Query completed successfully
- [ ] No outbound from bridge process
- [ ] Pass 1 timestamp: __________

## Pass 2 (must be consistent)

Repeat A–C immediately (or after a reboot — both are valid). Do not “warm up” with hidden network steps.

- [ ] Monitor visible
- [ ] Query completed successfully
- [ ] No outbound from bridge process
- [ ] Pass 2 timestamp: __________

## Result

If both passes succeed with matching “no outbound” evidence, the proof pack demo is **live-repeatable**. Attach screen capture + the `Observe-Egress` output folders to the pilot record.

## What this does *not* prove

- Behaviour of Claude Desktop / Cursor / other AI clients (separate products).
- Behaviour of optional HTTP/SSE transport modes (not the default; do not use for air-gap demos).
- Future update mechanisms (must remain customer-controlled; see KNOWN-LIMITATIONS.md).
