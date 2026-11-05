[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Command 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    foreach ($line in $output) {
        Write-Host ([string]$line)
    }
    if ($exitCode -ne 0) {
        throw "${Name}_FAILED: exit_code=$exitCode"
    }
}

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)][string]$Code,
        [AllowNull()]$Actual,
        [AllowNull()]$Expected
    )
    if ([string]$Actual -ne [string]$Expected) {
        throw "${Code}: actual='$Actual' expected='$Expected'"
    }
}

$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PackageRoot
}
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$PackageWorker = Join-Path $PackageRoot "PROJETO_SM3_MEDIA_WORKER_v2_5_0_MANUAL_EDITOR\worker\worker_service.py"
$PackageCompose = Join-Path $PackageRoot "PROJETO_SM3_MEDIA_WORKER_v2_5_0_MANUAL_EDITOR\deployment\docker-compose.worker.yml"
$ProjectWorker = Join-Path $ProjectRoot "worker\worker_service.py"
$ComposeBase = Join-Path $ProjectRoot "deployment\docker-compose.yml"
$ComposeWorker = Join-Path $ProjectRoot "deployment\docker-compose.worker.yml"

foreach ($required in @($PackageWorker, $PackageCompose, $ProjectWorker, $ComposeBase, $ComposeWorker)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "REQUIRED_FILE_NOT_FOUND: $required"
    }
}

$sourceText = Get-Content -LiteralPath $PackageWorker -Raw
if ($sourceText -notmatch 'WORKER_VERSION\s*=\s*"2\.5\.0"') {
    throw "PACKAGE_WORKER_VERSION_INVALID"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDirectory = Join-Path $ProjectRoot "sm3_backups\worker_$timestamp"
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
Copy-Item -LiteralPath $ProjectWorker -Destination (Join-Path $BackupDirectory "worker_service.py")
Copy-Item -LiteralPath $ComposeWorker -Destination (Join-Path $BackupDirectory "docker-compose.worker.yml")

Copy-Item -LiteralPath $PackageWorker -Destination $ProjectWorker -Force
Copy-Item -LiteralPath $PackageCompose -Destination $ComposeWorker -Force
$installedHash = (Get-FileHash -LiteralPath $ProjectWorker -Algorithm SHA256).Hash
$packageHash = (Get-FileHash -LiteralPath $PackageWorker -Algorithm SHA256).Hash
Assert-Equal -Code "WORKER_COPY_HASH_MISMATCH" -Actual $installedHash -Expected $packageHash
Assert-Equal -Code "WORKER_COMPOSE_HASH_MISMATCH" -Actual (Get-FileHash -LiteralPath $ComposeWorker -Algorithm SHA256).Hash -Expected (Get-FileHash -LiteralPath $PackageCompose -Algorithm SHA256).Hash

$ComposeArgs = @(
    "-f", $ComposeBase,
    "-f", $ComposeWorker
)

Push-Location $ProjectRoot
try {
    Invoke-NativeChecked -Name "MEDIA_WORKER_BUILD" -Command {
        docker compose @ComposeArgs build media-worker
    }
    Invoke-NativeChecked -Name "MEDIA_WORKER_UP" -Command {
        docker compose @ComposeArgs up -d media-worker
    }
}
finally {
    Pop-Location
}

$health = $null
for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8090/health" -TimeoutSec 5
        if ($health.ok -eq $true -and $health.version -eq "2.5.0") { break }
    }
    catch {
        if ($attempt -eq 20) { throw }
    }
    Start-Sleep -Seconds 2
}

if ($null -eq $health -or $health.version -ne "2.5.0") {
    throw "MEDIA_WORKER_HEALTH_UNAVAILABLE"
}

Assert-Equal -Code "WORKER_VERSION_MISMATCH" -Actual $health.version -Expected "2.5.0"
Assert-Equal -Code "PRODUCTION_CONTRACT_MISMATCH" -Actual $health.production_edit_contract -Expected "SM3_PRODUCTION_EDIT_V1"
Assert-Equal -Code "EDIT_SESSION_START_MISSING" -Actual $health.edit_session_start -Expected $true
Assert-Equal -Code "EDIT_SESSION_IDEMPOTENCY_MISSING" -Actual $health.edit_session_start_idempotent -Expected $true
Assert-Equal -Code "EDIT_SESSION_CONTRACT_MISMATCH" -Actual $health.edit_session_contract -Expected "SM3_EDIT_SESSION_V1"
Assert-Equal -Code "EDITOR_WORKSPACE_MISSING" -Actual $health.editor_workspace -Expected $true
Assert-Equal -Code "EDITOR_WORKSPACE_EDITABLE_MISMATCH" -Actual $health.editor_workspace_read_only -Expected $false
Assert-Equal -Code "EDITOR_WORKSPACE_ASSET_VERIFICATION_MISSING" -Actual $health.editor_workspace_asset_verified -Expected $true
Assert-Equal -Code "EDITOR_WORKSPACE_CONTRACT_MISMATCH" -Actual $health.editor_workspace_contract -Expected "SM3_EDITOR_WORKSPACE_V1"
Assert-Equal -Code "EDIT_SESSION_SAVE_SAFE_MISSING" -Actual $health.edit_session_save_safe -Expected $true
Assert-Equal -Code "EDIT_SESSION_SAVE_CONTRACT_MISMATCH" -Actual $health.edit_session_save_contract -Expected "SM3_EDIT_SAVE_V1"

Write-Host "SM3_MEDIA_WORKER_2_5_0_INSTALL_PASS"
Write-Host "backup=$BackupDirectory"
Write-Host "sha256=$installedHash"
$health | ConvertTo-Json -Depth 10
