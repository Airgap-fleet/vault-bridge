# Vault Bridge — Windows installer

**Status:** UNSIGNED INTERNAL build path (no Authenticode certificate on this machine yet).  
**Primary artefact:** PowerShell one-command installer (MSI is a documented next step; see `wix/`).

## One-command install (recommended)

From an elevated-or-normal PowerShell session, in the extracted product tree:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault"
```

Silent / unattended (firm IT):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault" -Quiet
```

Skip client config write:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault" -SkipClientConfig
```

Skip self-test (not recommended):

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault" -SkipSelfTest
```

## What it does

1. Checks Windows + PowerShell prerequisites (clear pass/fail).
2. Ensures `uv` is available (may download during **setup only** — not used at runtime by the bridge).
3. Creates a dedicated per-user install under `%LOCALAPPDATA%\AirgapFleet\vault-bridge`.
4. Creates a pinned Python 3.11 venv and installs from this tree using `uv.lock` (lockfile-faithful).
5. Writes a launcher + uninstall registration (HKCU Add/Remove Programs).
6. Optionally writes Claude Desktop / Cursor MCP config pointing at the **local** `vault-bridge.exe` (no `uvx` / no PyPI at runtime).
7. Runs `scripts\self_test.ps1` (JSON-RPC over stdio) and **fails loudly** if it does not pass.

## Runtime air-gap

Installer may use the internet for prerequisites **during setup only**.  
Once installed, vault-bridge speaks stdio JSON-RPC only — **no outbound network is required or performed for vault content**.

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Uninstall-VaultBridge.ps1
```

Or use Settings → Apps → Vault Bridge (Airgap Fleet).

## MSI (next step)

WiX Toolset / Visual Studio Build Tools were **not** present on the build machine when this path was added. See `wix/README.md` for the scaffold. Prefer a signed MSI for Intune/SCCM once Authenticode is available.
