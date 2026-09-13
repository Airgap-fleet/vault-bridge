# SBOM / lockfile note

Vault Bridge is a Python package. The release-faithful dependency set is recorded in:

- **`uv.lock`** at the product repository root (authoritative pin for installs via `uv sync --frozen` / the Windows installer).

## How to inspect

```powershell
Get-FileHash -Algorithm SHA256 .\uv.lock
# Optional: uv export --frozen -o proof-pack\requirements.frozen.txt
```

## SBOM

A formal CycloneDX/SPDX SBOM is **not yet generated** in this Stage 2 pack. The lockfile is the practical SBOM stand-in for pilot installs. Generating CycloneDX from `uv.lock` is a follow-up once release automation is in place.

## Honesty

Do not claim “certified SBOM process” or supply-chain certifications we do not hold. Provide the lockfile digest + this note as evidence for the buyer’s own auditor.
