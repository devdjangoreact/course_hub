# Sync local .env into Vercel project env (Production + Preview).
# Does not print secret values. Requires: npx vercel login + linked project.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/sync-vercel-env.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/sync-vercel-env.ps1 -EnvFile .env -Targets production,preview

param(
    [string]$EnvFile = ".env",
    [string[]]$Targets = @("production", "preview")
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path $EnvFile)) {
    Write-Error "Env file not found: $EnvFile"
}

$skipKeys = @(
    "HOST",
    "PORT"
)

function Get-EnvPairs([string]$path) {
    $pairs = [ordered]@{}
    foreach ($raw in Get-Content -LiteralPath $path) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { continue }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($skipKeys -contains $key) { continue }
        $pairs[$key] = $value
    }
    return $pairs
}

$pairs = Get-EnvPairs $EnvFile
Write-Host "Loaded $($pairs.Count) keys from $EnvFile (values hidden)."

if ($pairs.Contains("DATABASE_URL") -and $pairs["DATABASE_URL"] -like "sqlite*") {
    Write-Warning "DATABASE_URL is SQLite. Vercel needs Supabase Postgres — update .env before relying on prod."
}
if ($pairs.Contains("BACKEND_URL") -and ($pairs["BACKEND_URL"] -like "*localhost*" -or $pairs["BACKEND_URL"] -like "*127.0.0.1*")) {
    Write-Warning "BACKEND_URL points to localhost. After first deploy, set it to https://YOUR_PROJECT.vercel.app and re-run this script."
}

foreach ($target in $Targets) {
    Write-Host "`n=== Syncing target: $target ==="
    foreach ($key in $pairs.Keys) {
        $value = $pairs[$key]
        $tmp = New-TemporaryFile
        try {
            Set-Content -LiteralPath $tmp.FullName -Value $value -NoNewline -Encoding utf8
            # Remove existing then add (idempotent-ish for CLI)
            npx --yes vercel env rm $key $target --yes 2>$null | Out-Null
            Get-Content -LiteralPath $tmp.FullName -Raw | npx --yes vercel env add $key $target
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Failed to set $key for $target"
            } else {
                Write-Host "OK  $key"
            }
        }
        finally {
            Remove-Item -LiteralPath $tmp.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "`nDone. Trigger a redeploy so new env vars apply:"
Write-Host "  npx vercel --prod"
