# Projeto SM3 - install Media Worker 2.8.0 (Identity Asset Bindings)
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$WorkerSource = (Join-Path $PSScriptRoot 'SM3_worker_service_2_8_0.py')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-NativeChecked {
    param([string]$Code, [scriptblock]$Command)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Command 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    foreach ($line in $output) { Write-Host ([string]$line) }
    if ($exitCode -ne 0) { throw ("${Code}: exit_code=$exitCode") }
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$WorkerSource = (Resolve-Path -LiteralPath $WorkerSource).Path
$ProjectWorker = Join-Path $ProjectRoot 'worker\worker_service.py'
$ComposeBase = Join-Path $ProjectRoot 'deployment\docker-compose.yml'
$ComposeWorker = Join-Path $ProjectRoot 'deployment\docker-compose.worker.yml'

foreach ($required in @($WorkerSource,$ProjectWorker,$ComposeBase,$ComposeWorker)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "SM3_08_REQUIRED_FILE_NOT_FOUND: $required"
    }
}

$sourceText = Get-Content -LiteralPath $WorkerSource -Raw
if ($sourceText -notmatch 'WORKER_VERSION\s*=\s*"2\.8\.0"' -or
    $sourceText -notmatch 'EDIT_PREVIEW_CONTRACT_VERSION\s*=\s*"SM3_EDIT_PREVIEW_V3"' -or
    $sourceText -notmatch 'SM3_IDENTITY_ASSET_BINDING_V1') {
    throw 'SM3_08_PACKAGE_WORKER_CONTRACT_INVALID'
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $ProjectRoot ("sm3_backups\worker_2_8_0_" + $timestamp)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -LiteralPath $ProjectWorker -Destination (Join-Path $backupDir 'worker_service.py') -Force
Write-Host "Backup: $backupDir"

Copy-Item -LiteralPath $WorkerSource -Destination $ProjectWorker -Force
$sourceHash = (Get-FileHash -LiteralPath $WorkerSource -Algorithm SHA256).Hash
$installedHash = (Get-FileHash -LiteralPath $ProjectWorker -Algorithm SHA256).Hash
if ($sourceHash -cne $installedHash) { throw 'SM3_08_WORKER_COPY_HASH_MISMATCH' }

$ComposeArgs = @('-f',$ComposeBase,'-f',$ComposeWorker)
Push-Location $ProjectRoot
try {
    Invoke-NativeChecked 'SM3_08_DOCKER_CONFIG_FAILED' { docker compose @ComposeArgs config }
    Invoke-NativeChecked 'SM3_08_WORKER_BUILD_FAILED' { docker compose @ComposeArgs build --no-cache media-worker }
    Invoke-NativeChecked 'SM3_08_WORKER_UP_FAILED' { docker compose @ComposeArgs up -d --force-recreate media-worker }
}
finally { Pop-Location }

$health = $null
for ($i=0; $i -lt 30; $i++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://localhost:8090/health' -TimeoutSec 5
        if ($health.version -eq '2.8.0') { break }
    }
    catch { }
    Start-Sleep -Seconds 2
}
if ($null -eq $health) { throw 'SM3_08_WORKER_HEALTH_UNREACHABLE' }
if ($health.ok -ne $true -or $health.version -ne '2.8.0' -or
    $health.edit_preview_contract -ne 'SM3_EDIT_PREVIEW_V3' -or
    $health.edit_preview_identity_assets -ne $true -or
    $health.identity_asset_binding_contract -ne 'SM3_IDENTITY_ASSET_BINDING_V1') {
    throw ('SM3_08_WORKER_HEALTH_CONTRACT_INVALID: ' + ($health | ConvertTo-Json -Depth 20 -Compress))
}

Write-Output 'SM3_WORKER_2_8_0_IDENTITY_BINDINGS_INSTALL_PASS'
[pscustomobject]@{
    version = $health.version
    preview_contract = $health.edit_preview_contract
    identity_binding_contract = $health.identity_asset_binding_contract
    backup = $backupDir
    worker_sha256 = $installedHash.ToLowerInvariant()
}
