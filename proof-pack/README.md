# Vault Bridge — zero-egress proof pack

**Audience:** COLP / practice manager / firm IT evaluating Airgap Fleet.  

**For COLP / practice manager / firm IT:** use this pack to run a live, repeatable demo that the **bridge process** does not open vendor outbound connections while handling local work. It is evidence for your controls — **not** a certification mark.
**Product:** Vault Bridge (local vault connector for your AI desk)  
**Build status:** **UNSIGNED INTERNAL** — Authenticode certificate not yet applied. Do not treat this as a prospect-ready signed release.

## What never leaves your PC

When Vault Bridge is running in its default **stdio** mode:

- Vault notes are read and written **only on the local disk path you configure**.
- The bridge talks to your AI desk over a **local process pipe** (no listening network port).
- There is **no telemetry channel**, no vendor cloud sync of vault content, and no model API call made by the bridge itself.
- Logs go to **stderr on the local machine** only.

Honest boundary: the **AI desk application** you attach (e.g. Claude Desktop, Cursor) is a separate product with its own network behaviour. This proof pack demonstrates the **bridge process** does not open outbound connections while handling vault queries. It does not certify third-party AI clients.

## Contents of this folder

| File | Purpose |
|------|---------|
| `VERSION.txt` | Product version + git commit |
| `DEMO-CHECKLIST.md` | **Live-repeatable** zero-egress demo (run twice) |
| `EGRESS-OBSERVATION.md` | How to observe / record network behaviour |
| `Observe-Egress.ps1` | Helper to snapshot process TCP connections during a self-test |
| `Compute-Hashes.ps1` / `SHA256SUMS.template` | SHA-256 verification |
| `SBOM-NOTE.md` | Dependency lockfile / SBOM note (`uv.lock`) |
| `SIGNING.md` | Authenticode thumbprint **placeholder** (unsigned today) |
| `KNOWN-LIMITATIONS.md` | Honest limits |

## Verify download (when you receive a release bundle)

```powershell
Get-FileHash -Algorithm SHA256 .\path\to\artefact
# Compare to the published SHA256SUMS for that release.
```

Digital Signatures tab will be **empty** on UNSIGNED INTERNAL builds — that is expected until Authenticode is available.

## Install + smoke

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\Install-VaultBridge.ps1 -VaultPath "C:\Path\To\Your\Vault"
powershell -ExecutionPolicy Bypass -File .\scripts\self_test.ps1 -VaultPath "C:\Path\To\Your\Vault"
```

## Support

Escalate via your Airgap Fleet contact (Brooke / firm channel). No public forum posts required for evaluation.
