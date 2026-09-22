param(
    [string]$Database = "ledgerlens.db",
    [string]$Destination = "backups"
)

if (-not (Test-Path $Database)) {
    throw "Database file not found: $Database"
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item $Database (Join-Path $Destination "ledgerlens-$stamp.db")
Write-Output "Backup created in $Destination"