param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,
    [string]$Destination = "backups"
)

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    throw "pg_dump was not found. Install PostgreSQL client tools first."
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $Destination "ledgerlens-$stamp.dump"
& $pgDump.Source --dbname=$DatabaseUrl --format=custom --file=$file
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed."
}
Write-Output "Backup created: $file"
Write-Output "Restore with pg_restore into a separate empty test database before trusting the backup."
