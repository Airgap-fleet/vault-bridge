<#
.SYNOPSIS
  Compute SHA-256 for release artefacts and write SHA256SUMS.
#>
[CmdletBinding()]
param(
    [string[]]$Path = @(),
    [string]$OutFile = ""
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Path -or $Path.Count -eq 0) {
    $Path = @(
        (Join-Path $RepoRoot "installer\Install-VaultBridge.ps1"),
        (Join-Path $RepoRoot "scripts\self_test.ps1"),
        (Join-Path $RepoRoot "scripts\self_test.py"),
        (Join-Path $RepoRoot "uv.lock"),
        (Join-Path $RepoRoot "pyproject.toml")
    )
}
if (-not $OutFile) { $OutFile = Join-Path $RepoRoot "proof-pack\SHA256SUMS" }

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# SHA-256 sums - Vault Bridge proof pack") | Out-Null
$lines.Add("# Generated (UTC): $((Get-Date).ToUniversalTime().ToString('o'))") | Out-Null
$lines.Add("# Signing: UNSIGNED INTERNAL (see SIGNING.md)") | Out-Null
foreach ($p in $Path) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Host "[WARN] Missing: $p" -ForegroundColor Yellow
        continue
    }
    $h = Get-FileHash -LiteralPath $p -Algorithm SHA256
    $rel = $p
    try { $rel = Resolve-Path -LiteralPath $p -Relative } catch { }
    $lines.Add("$($h.Hash)  $rel") | Out-Null
    Write-Host "$($h.Hash)  $rel"
}
$lines | Set-Content -Path $OutFile -Encoding utf8
Write-Host "Wrote $OutFile"