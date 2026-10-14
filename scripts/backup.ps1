# Back up an Odoo database and its filestore into backups\<db>_<timestamp>\.
# Usage: .\scripts\backup.ps1 <database>
param(
    [Parameter(Mandatory = $true)][string]$Database
)
$ErrorActionPreference = 'Stop'

if ($Database -cnotmatch '^[A-Za-z0-9_][A-Za-z0-9_.-]*$') {
    throw "Invalid database name: $Database"
}
$RepoRoot = Split-Path -Parent $PSScriptRoot

function ConvertTo-ProcessArgument([string]$Value) {
    if ($Value -ne '' -and $Value -notmatch '[\s"]') { return $Value }
    $escaped = $Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

# Runs `docker compose ...` with raw byte streams: Windows PowerShell re-encodes
# native stdout on `>`, which would corrupt the dump and the tar archive.
function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$OutFile,
        [switch]$Capture,
        [switch]$AllowFailure
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'docker'
    $psi.Arguments = ((@('compose') + $Arguments) | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join ' '
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = [bool]$OutFile -or $Capture
    $process = [System.Diagnostics.Process]::Start($psi)
    $text = $null
    if ($OutFile) {
        $out = [System.IO.File]::Create($OutFile)
        try { $process.StandardOutput.BaseStream.CopyTo($out) } finally { $out.Dispose() }
    } elseif ($Capture) {
        $text = $process.StandardOutput.ReadToEnd()
    }
    $process.WaitForExit()
    if ($AllowFailure) { return $process.ExitCode -eq 0 }
    if ($process.ExitCode -ne 0) { throw "docker compose exited with code $($process.ExitCode)" }
    return $text
}

$names = Invoke-Compose -Capture -Arguments @('exec', '-T', 'db', 'sh', '-c',
    'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT datname FROM pg_database"')
if (($names -split "`r?`n") -cnotcontains $Database) {
    throw "Database not found: $Database"
}
if (-not (Invoke-Compose -AllowFailure -Arguments @('exec', '-T', 'odoo', 'test', '-d', "/var/lib/odoo/filestore/$Database"))) {
    throw "Filestore not found: /var/lib/odoo/filestore/$Database"
}

$dest = Join-Path $RepoRoot (Join-Path 'backups' ("{0}_{1}" -f $Database, (Get-Date -Format 'yyyyMMdd_HHmmss')))
New-Item -ItemType Directory -Path $dest -Force | Out-Null
try {
    Invoke-Compose -OutFile (Join-Path $dest 'db.dump') -Arguments @('exec', '-T', 'db', 'sh', '-c',
        'pg_dump -U "$POSTGRES_USER" -Fc "$1"', '_', $Database) | Out-Null
    Invoke-Compose -OutFile (Join-Path $dest 'filestore.tar') -Arguments @('exec', '-T', 'odoo',
        'tar', '-C', '/var/lib/odoo/filestore', '-cf', '-', $Database) | Out-Null
} catch {
    Write-Warning "Backup failed, removing $dest"
    Remove-Item -Recurse -Force $dest
    throw
}
Write-Host "Backup written to $dest"
