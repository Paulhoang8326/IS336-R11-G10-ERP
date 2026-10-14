# Restore a backup made by backup.ps1 into a target database.
# Usage: .\scripts\restore.ps1 <backup_dir> <target_database>
param(
    [Parameter(Mandatory = $true)][string]$BackupDir,
    [Parameter(Mandatory = $true)][string]$Database
)
$ErrorActionPreference = 'Stop'

if ($Database -cnotmatch '^[A-Za-z0-9_][A-Za-z0-9_.-]*$') {
    throw "Invalid database name: $Database"
}
$src = (Resolve-Path $BackupDir).Path
foreach ($f in 'db.dump', 'filestore.tar') {
    if (-not (Test-Path -PathType Leaf (Join-Path $src $f))) { throw "Missing $f in $src" }
}
$RepoRoot = Split-Path -Parent $PSScriptRoot

function ConvertTo-ProcessArgument([string]$Value) {
    if ($Value -ne '' -and $Value -notmatch '[\s"]') { return $Value }
    $escaped = $Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

# Runs `docker compose ...` with raw byte streams: Windows PowerShell re-encodes
# native stdin on pipes, which would corrupt the dump and the tar archive.
function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$InFile,
        [switch]$Capture
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'docker'
    $psi.Arguments = ((@('compose') + $Arguments) | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join ' '
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    # Always redirect stdin so docker never reads the console that Read-Host uses.
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = [bool]$Capture
    $process = [System.Diagnostics.Process]::Start($psi)
    $text = $null
    if ($InFile) {
        $in = [System.IO.File]::OpenRead($InFile)
        try { $in.CopyTo($process.StandardInput.BaseStream) } finally { $in.Dispose() }
    }
    $process.StandardInput.Close()
    if ($Capture) { $text = $process.StandardOutput.ReadToEnd() }
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "docker compose exited with code $($process.ExitCode)" }
    return $text
}

$names = Invoke-Compose -Capture -Arguments @('exec', '-T', 'db', 'sh', '-c',
    'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT datname FROM pg_database"')
if (($names -split "`r?`n") -ccontains $Database) {
    $answer = Read-Host "Database '$Database' already exists. Overwrite it and its filestore? [y/N]"
    if ($answer -notin 'y', 'yes') {
        Write-Host 'Aborted.'
        exit 1
    }
    Invoke-Compose -Arguments @('exec', '-T', 'db', 'sh', '-c', 'dropdb -U "$POSTGRES_USER" --force "$1"', '_', $Database) | Out-Null
}

Invoke-Compose -Arguments @('exec', '-T', 'db', 'sh', '-c', 'createdb -U "$POSTGRES_USER" "$1"', '_', $Database) | Out-Null
Invoke-Compose -InFile (Join-Path $src 'db.dump') -Arguments @('exec', '-T', 'db', 'sh', '-c',
    'pg_restore -U "$POSTGRES_USER" --no-owner --exit-on-error -d "$1"', '_', $Database) | Out-Null

# The archive holds one top-level folder named after the source database; rename it to the target.
$restoreFilestore = 'set -e; fs=/var/lib/odoo/filestore; mkdir -p "$fs"; rm -rf "$fs/$1"; ' +
    'tmp=$(mktemp -d "$fs/.restore.XXXXXX"); tar -C "$tmp" -xf -; mv "$tmp"/* "$fs/$1"; rmdir "$tmp"'
Invoke-Compose -InFile (Join-Path $src 'filestore.tar') -Arguments @('exec', '-T', 'odoo', 'sh', '-c',
    $restoreFilestore, '_', $Database) | Out-Null

Write-Host "Restored $src into database $Database"
