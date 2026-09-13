<#
.SYNOPSIS
  Uninstall Vault Bridge per-user install.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = $(Join-Path $env:LOCALAPPDATA "AirgapFleet\vault-bridge"),
    [switch]$Quiet
)
$ErrorActionPreference = "Stop"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AirgapFleet-VaultBridge"
$BinDir = Join-Path $InstallDir "bin"

function Say([string]$m) { if (-not $Quiet) { Write-Host $m } }

Say "Uninstalling Vault Bridge from $InstallDir ..."

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -and $BinDir -and $userPath -like "*$BinDir*") {
    $parts = $userPath.Split(';') | Where-Object { $_ -and ($_ -ne $BinDir) }
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ';'), "User")
    Say "Removed bin from user PATH"
}

if (Test-Path -LiteralPath $UninstallKey) {
    Remove-Item -LiteralPath $UninstallKey -Recurse -Force
    Say "Removed Add/Remove Programs entry"
}

if (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
    Say "Removed install directory"
}

Say "Uninstall complete. MCP client config entries (if any) were left in place - remove vault-bridge from Claude/Cursor config manually if desired."
exit 0
