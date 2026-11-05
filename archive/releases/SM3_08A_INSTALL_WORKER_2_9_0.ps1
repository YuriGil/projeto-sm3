# Projeto SM3 - 08A Visual Feedback Contract installer
# Installs Worker 2.9.0 while preserving the edit-preview renderer identity at 2.8.0.
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$WorkerSource = (Join-Path $PSScriptRoot 'SM3_worker_service_2_9_0.py')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-DockerLive {
    param(
        [Parameter(Mandatory=$true)][string]$Code,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    Write-Host ""
    Write-Host ("==> " + $Code)
    Write-Host ("docker compose " + ($Arguments -join ' '))
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker compose @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
    if ($exitCode -ne 0) {
        throw ("${Code}: docker compose exit_code=$exitCode")
    }
    Write-Host ("<== " + $Code + " OK")
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$WorkerSource = (Resolve-Path -LiteralPath $WorkerSource).Path
$ProjectWorker = Join-Path $ProjectRoot 'worker\worker_service.py'
$ComposeBase = Join-Path $ProjectRoot 'deployment\docker-compose.yml'
$ComposeWorker = Join-Path $ProjectRoot 'deployment\docker-compose.worker.yml'

foreach ($required in @($WorkerSource,$ProjectWorker,$ComposeBase,$ComposeWorker)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "SM3_08A_REQUIRED_FILE_NOT_FOUND: $required"
    }
}

$sourceText = Get-Content -LiteralPath $WorkerSource -Raw
foreach ($requiredPattern in @(
    'WORKER_VERSION\s*=\s*"2\.9\.0"',
    'EDIT_PREVIEW_RENDERER_VERSION\s*=\s*"2\.8\.0"',
    'EDIT_PREVIEW_CONTRACT_VERSION\s*=\s*"SM3_EDIT_PREVIEW_V3"',
    'VISUAL_FEEDBACK_CONTRACT_VERSION\s*=\s*"SM3_VISUAL_FEEDBACK_V1"',
    'VISUAL_FEEDBACK_TAXONOMY_VERSION\s*=\s*"SM3_VISUAL_ISSUES_V1"'
)) {
    if ($sourceText -notmatch $requiredPattern) {
        throw "SM3_08A_PACKAGE_WORKER_CONTRACT_INVALID: $requiredPattern"
    }
}

$sourceHash = (Get-FileHash -LiteralPath $WorkerSource -Algorithm SHA256).Hash
$currentHash = (Get-FileHash -LiteralPath $ProjectWorker -Algorithm SHA256).Hash
$backupDir = $null

if ($sourceHash -cne $currentHash) {
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backupDir = Join-Path $ProjectRoot ("sm3_backups\worker_2_9_0_" + $timestamp)
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Copy-Item -LiteralPath $ProjectWorker -Destination (Join-Path $backupDir 'worker_service.py') -Force
    Write-Host "Backup: $backupDir"
    Copy-Item -LiteralPath $WorkerSource -Destination $ProjectWorker -Force
}
else {
    Write-Host "Worker 2.9.0 source already copied; reusing current worker_service.py."
}

$installedHash = (Get-FileHash -LiteralPath $ProjectWorker -Algorithm SHA256).Hash
if ($sourceHash -cne $installedHash) {
    throw 'SM3_08A_WORKER_COPY_HASH_MISMATCH'
}

$ComposeArgs = @('-f',$ComposeBase,'-f',$ComposeWorker)

Push-Location $ProjectRoot
try {
    Invoke-DockerLive -Code 'SM3_08A_DOCKER_CONFIG_VALIDATE' -Arguments ($ComposeArgs + @('config','--quiet'))
    Invoke-DockerLive -Code 'SM3_08A_WORKER_BUILD' -Arguments ($ComposeArgs + @('build','--no-cache','media-worker'))
    Invoke-DockerLive -Code 'SM3_08A_WORKER_UP' -Arguments ($ComposeArgs + @('up','-d','--force-recreate','media-worker'))
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Waiting for Worker 2.9.0 health..."
$health = $null
for ($i=1; $i -le 30; $i++) {
    try {
        $candidate = Invoke-RestMethod -Uri 'http://localhost:8090/health' -TimeoutSec 5
        if ($candidate.version -eq '2.9.0') {
            $health = $candidate
            break
        }
        Write-Host ("Health attempt {0}/30: worker answered version {1}" -f $i,$candidate.version)
    }
    catch {
        Write-Host ("Health attempt {0}/30: not ready yet" -f $i)
    }
    Start-Sleep -Seconds 2
}

if ($null -eq $health) {
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker compose @ComposeArgs ps media-worker
        & docker compose @ComposeArgs logs --tail 100 media-worker
    }
    finally {
        $ErrorActionPreference = $previous
    }
    throw 'SM3_08A_WORKER_HEALTH_UNREACHABLE'
}

if ($health.ok -ne $true -or
    $health.version -ne '2.9.0' -or
    $health.edit_preview_contract -ne 'SM3_EDIT_PREVIEW_V3' -or
    $health.edit_preview_renderer_version -ne '2.8.0' -or
    $health.identity_asset_binding_contract -ne 'SM3_IDENTITY_ASSET_BINDING_V1' -or
    $health.visual_feedback -ne $true -or
    $health.visual_feedback_contract -ne 'SM3_VISUAL_FEEDBACK_V1' -or
    $health.visual_feedback_taxonomy -ne 'SM3_VISUAL_ISSUES_V1') {
    throw ('SM3_08A_WORKER_HEALTH_CONTRACT_INVALID: ' + ($health | ConvertTo-Json -Depth 20 -Compress))
}

$taxonomy = Invoke-RestMethod -Uri 'http://localhost:8090/production/visual-feedback/taxonomy' -TimeoutSec 10
if ($taxonomy.ok -ne $true -or
    $taxonomy.contract_version -ne 'SM3_VISUAL_FEEDBACK_V1' -or
    $taxonomy.taxonomy_version -ne 'SM3_VISUAL_ISSUES_V1' -or
    @($taxonomy.issues).Count -lt 20) {
    throw 'SM3_08A_TAXONOMY_SELFTEST_FAILED'
}

Write-Host ""
Write-Output 'SM3_08A_VISUAL_FEEDBACK_INSTALL_PASS'
[pscustomobject]@{
    worker_version = $health.version
    renderer_version = $health.edit_preview_renderer_version
    preview_contract = $health.edit_preview_contract
    visual_feedback_contract = $health.visual_feedback_contract
    taxonomy = $health.visual_feedback_taxonomy
    taxonomy_issues = @($taxonomy.issues).Count
    backup = if ($backupDir) { $backupDir } else { 'REUSED_EXISTING_2_9_0_SOURCE' }
    worker_sha256 = $installedHash.ToLowerInvariant()
}
