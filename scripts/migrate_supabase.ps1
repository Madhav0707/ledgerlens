param(
    [string]$DbHost = "",
    [string]$Database = "postgres",
    [string]$User = "",
    [int]$Port = 0
)

$DbHost = if ($DbHost) { $DbHost } else { Read-Host "Supabase pooler host (from Connect > Session pooler)" }
$User = if ($User) { $User } else { Read-Host "Database user (pooler users usually look like postgres.PROJECT_REF)" }
$PortText = if ($Port -gt 0) { [string]$Port } else { Read-Host "Database port (usually 6543 for Session pooler)" }
if (-not [int]::TryParse($PortText, [ref]$Port)) {
    throw "Database port must be a number."
}

$dns = Resolve-DnsName $DbHost -ErrorAction SilentlyContinue
if (-not $dns) {
    throw "Supabase host '$DbHost' does not resolve. Copy the Session pooler host exactly from Supabase Connect settings."
}

$securePassword = Read-Host "Enter the Supabase database password" -AsSecureString
$password = [System.Net.NetworkCredential]::new("", $securePassword).Password
$encodedPassword = [System.Uri]::EscapeDataString($password)
$databaseUrl = "postgresql+psycopg://${User}:${encodedPassword}@${DbHost}:${Port}/${Database}?connect_timeout=10"

$env:DATABASE_URL = $databaseUrl
$env:APP_ENV = "production"
$env:AUTO_CREATE_SCHEMA = "false"
try {
    Write-Output "Connecting to Supabase at ${DbHost}:${Port}..."
    Write-Output "If this does not continue within 10 seconds, check VPN/firewall/network access or use Supabase IPv4 add-on."
    & .\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic migration failed. Verify the pooler host, port, username, password, and network access."
    }
    Write-Output "Supabase schema migration completed."
}
finally {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:APP_ENV -ErrorAction SilentlyContinue
    Remove-Item Env:AUTO_CREATE_SCHEMA -ErrorAction SilentlyContinue
    $password = $null
    $encodedPassword = $null
    $databaseUrl = $null
}