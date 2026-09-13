# Signing status — Vault Bridge Windows artefacts

## Current status: UNSIGNED INTERNAL

No Authenticode certificate / `signtool` was available on the build machine when Stage 2 packaging was produced.  
**Do not present this build as signed.** SmartScreen may warn; firm IT should treat this as an internal/pilot artefact until signing is enabled.

## Placeholder (fill when cert is available)

| Field | Value |
|------|-------|
| Subject | _TBD — Airgap Fleet code-signing certificate_ |
| Thumbprint (SHA1) | `_PLACEHOLDER_THUMBPRINT_` |
| Timestamp server | _TBD_ |
| Signed artefacts | _none yet_ |

## Verification (once signed)

1. Right-click MSI/EXE → Properties → **Digital Signatures**.
2. Or: `Get-AuthenticodeSignature .\path\to\artefact`

## Policy

- Keys stay in governed storage — never on a laptop.
- No fake certificates, no self-signed “looks signed” theatre for prospects.
