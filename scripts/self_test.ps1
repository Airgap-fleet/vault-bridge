<#
.SYNOPSIS
  Post-install / developer JSON-RPC smoke test for vault-bridge.
  Fails loudly (non-zero exit) if stdout is polluted or tools do not respond.
#>
[CmdletBinding()]
param(
    [string]$VaultBridgeExe = "",
    [string]$PythonExe = "",
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,
    [int]$TimeoutSec = 25
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$SelfTestPy = Join-Path $PSScriptRoot "self_test.py"

if (-not (Test-Path -LiteralPath $SelfTestPy)) {
    Write-Host "[FAIL] Missing $SelfTestPy" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $VaultPath -PathType Container)) {
    Write-Host "[FAIL] VaultPath not a directory: $VaultPath" -ForegroundColor Red
    exit 2
}

if (-not $PythonExe) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "AirgapFleet\vault-bridge\venv\Scripts\python.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\python.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $PythonExe = $c; break }
    }
}
if (-not $PythonExe) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { $PythonExe = $py.Source }
}
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Host "[FAIL] No Python interpreter found for self-test." -ForegroundColor Red
    exit 2
}

if (-not $VaultBridgeExe) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "AirgapFleet\vault-bridge\venv\Scripts\vault-bridge.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\vault-bridge.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $VaultBridgeExe = $c; break }
    }
}

Write-Host "=== vault-bridge self-test ==="
Write-Host "Python:  $PythonExe"
Write-Host "Exe:     $(if ($VaultBridgeExe) { $VaultBridgeExe } else { '(module fallback)' })"
Write-Host "Vault:   $VaultPath"
Write-Host ""

$argList = @(
    $SelfTestPy,
    "--python", $PythonExe,
    "--vault", $VaultPath,
    "--timeout", "$TimeoutSec"
)
if ($VaultBridgeExe -and (Test-Path $VaultBridgeExe)) {
    $argList += @("--exe", $VaultBridgeExe)
}

& $PythonExe @argList
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host ""
    Write-Host "[FAIL] self-test exited $code" -ForegroundColor Red
    exit $code
}
Write-Host ""
Write-Host "[OK] self-test passed" -ForegroundColor Green
exit 0