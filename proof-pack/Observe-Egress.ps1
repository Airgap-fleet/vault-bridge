<#
.SYNOPSIS
  Sample TCP connections for the vault-bridge self-test process (egress observation helper).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath,
    [string]$OutDir = $(Join-Path $env:TEMP ("vault-bridge-egress-" + (Get-Date -Format "yyyyMMdd-HHmmss"))),
    [string]$PythonExe = "",
    [string]$VaultBridgeExe = ""
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Output: $OutDir"
Write-Host "Capturing baseline connections..."
Get-NetTCPConnection -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess |
  ConvertTo-Json -Depth 4 |
  Set-Content (Join-Path $OutDir "connections-baseline.json") -Encoding utf8

$selfTest = Join-Path $RepoRoot "scripts\self_test.ps1"
$stdoutPath = Join-Path $OutDir "self-test-stdout.txt"
$stderrPath = Join-Path $OutDir "self-test-stderr.txt"

# Single ArgumentList string so paths with spaces (e.g. C:\The Force\...) stay intact
$argList = "-NoProfile -ExecutionPolicy Bypass -File `"$selfTest`" -VaultPath `"$VaultPath`""
if ($PythonExe) { $argList += " -PythonExe `"$PythonExe`"" }
if ($VaultBridgeExe) { $argList += " -VaultBridgeExe `"$VaultBridgeExe`"" }

Write-Host "Starting self-test (monitored)..."
$p = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

$samples = @()
while (-not $p.HasExited) {
    Start-Sleep -Milliseconds 200
    try { $p.Refresh() } catch { }
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match 'vault-bridge|python' -or $_.ProcessId -eq $p.Id -or $_.ParentProcessId -eq $p.Id }
    foreach ($proc in $procs) {
        $conns = Get-NetTCPConnection -OwningProcess $proc.ProcessId -ErrorAction SilentlyContinue |
          Where-Object { $_.RemoteAddress -and $_.RemoteAddress -notin @('0.0.0.0','::','127.0.0.1','::1') -and $_.State -eq 'Established' }
        foreach ($c in $conns) {
            $samples += [pscustomobject]@{
                t = (Get-Date).ToUniversalTime().ToString('o')
                pid = $proc.ProcessId
                name = $proc.Name
                remote = "$($c.RemoteAddress):$($c.RemotePort)"
                state = "$($c.State)"
            }
        }
    }
}

$p.WaitForExit()
Start-Sleep -Milliseconds 200
try { $p.Refresh() } catch { }
$exitCode = $p.ExitCode
if ($null -eq $exitCode) {
    $outText = ""
    if (Test-Path $stdoutPath) { $outText = Get-Content $stdoutPath -Raw -ErrorAction SilentlyContinue }
    if ($outText -match '"status"\s*:\s*"pass"' -or $outText -match '\[OK\] self-test passed') { $exitCode = 0 }
    else { $exitCode = 1 }
}

($samples | ConvertTo-Json -Depth 4) | Set-Content (Join-Path $OutDir "connections-during.json") -Encoding utf8

$nonLoopback = @($samples)
$summary = @"
self_test_exit=$exitCode
non_loopback_established_samples=$($nonLoopback.Count)
out_dir=$OutDir
note=Zero non-loopback established samples is the expected pass for an air-gapped stdio bridge during self-test.
"@
$summary | Set-Content (Join-Path $OutDir "SUMMARY.txt") -Encoding utf8
Write-Host $summary

if ($exitCode -ne 0) {
    Write-Host "[FAIL] self-test failed during observation (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}
if ($nonLoopback.Count -gt 0) {
    Write-Host "[FAIL] Observed non-loopback established TCP during test - review connections-during.json" -ForegroundColor Red
    exit 10
}
Write-Host "[OK] No non-loopback established TCP observed during self-test" -ForegroundColor Green
exit 0
