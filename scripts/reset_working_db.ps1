$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root "data\campus_customs.db"
$target = Join-Path $root "data\campus_customs_new.db"

if (-not (Test-Path $source)) {
    throw "Reset failed: original database is missing at $source"
}

$sourceItem = Get-Item -Path $source -ErrorAction Stop
if ($sourceItem.Length -eq 0) {
    throw "Reset failed: original database is empty at $source"
}

Copy-Item -Path $source -Destination $target -Force
Write-Host "Reset working database from original."
