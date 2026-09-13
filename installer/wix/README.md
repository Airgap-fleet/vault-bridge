# WiX MSI scaffold (next step)

**Not built on this machine.** WiX Toolset / Visual Studio Build Tools / `signtool` were absent when Stage 2 packaging was added.

## Intent

Prefer a signed MSI for Intune / SCCM / solicitor firm IT once an Authenticode certificate is available in governed storage.

## Scaffold

- `VaultBridge.wxs` — minimal product definition pointing at the per-user layout produced by `Install-VaultBridge.ps1` (or a future harvest of that tree).
- Build (when WiX is installed):

```bat
candle -nologo installer\wix\VaultBridge.wxs -out installer\wix\VaultBridge.wixobj
light -nologo installer\wix\VaultBridge.wixobj -out dist\VaultBridge-1.0.4-UNSIGNED.msi
```

Then Authenticode-sign + timestamp before any prospect distribution.

Until then, the **PowerShell one-command installer** is the supported Windows path.