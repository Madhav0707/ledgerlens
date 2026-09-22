param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [Parameter(Mandatory = $true)]
    [string]$TargetDatabaseUrl
)

$pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
if (-not $pgRestore) {
    throw "pg_restore was not found. Install PostgreSQL client tools first."
}
if (-not (Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

& $pgRestore.Source --dbname=$TargetDatabaseUrl --clean --if-exists --no-owner $BackupFile
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore failed."
}
Write-Output "Restore completed into the target database. Verify with the application and reports."
