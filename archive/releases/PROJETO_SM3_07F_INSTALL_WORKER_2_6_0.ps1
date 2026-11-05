[CmdletBinding()]
param([string]$ProjectRoot = "")

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param([string]$Code, $Actual, $Expected)
    if ([string]$Actual -ne [string]$Expected) {
        throw "${Code}: actual='$Actual' expected='$Expected'"
    }
}

function Invoke-DockerChecked {
    param([string]$Step, [string[]]$DockerArgs)
    Write-Host "${Step}: iniciando (o build pode demorar alguns minutos; a saída aparece ao vivo)"
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker @DockerArgs 2>&1 | ForEach-Object { Write-Host ([string]$_) }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $oldPreference }
    if ($code -ne 0) { throw "${Step}_FAILED: exit_code=$code" }
}

$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = Split-Path -Parent $PackageRoot }
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$PackageWorker = Join-Path $PackageRoot 'PROJETO_SM3_MEDIA_WORKER_v2_6_0_EDIT_PREVIEWS\worker\worker_service.py'
$ProjectWorker = Join-Path $ProjectRoot 'worker\worker_service.py'
$BaseCompose = Join-Path $ProjectRoot 'deployment\docker-compose.yml'
$WorkerCompose = Join-Path $ProjectRoot 'deployment\docker-compose.worker.yml'
foreach ($item in @($PackageWorker, $ProjectWorker, $BaseCompose, $WorkerCompose)) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) { throw "REQUIRED_FILE_MISSING: $item" }
}
$source = Get-Content -LiteralPath $PackageWorker -Raw
if ($source -notmatch 'WORKER_VERSION\s*=\s*"2\.6\.0"') { throw 'PACKAGE_VERSION_INVALID' }
$hash = (Get-FileHash -LiteralPath $PackageWorker -Algorithm SHA256).Hash.ToLowerInvariant()
$Preflight = Join-Path $PackageRoot 'PROJETO_SM3_07F_PREFLIGHT.ps1'
if (-not (Test-Path -LiteralPath $Preflight -PathType Leaf)) { throw 'PREFLIGHT_SCRIPT_MISSING' }
& $Preflight
$Backup = Join-Path $ProjectRoot ('sm3_backups\worker_07f_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $Backup -Force | Out-Null
Copy-Item -LiteralPath $ProjectWorker -Destination (Join-Path $Backup 'worker_service.py')
$composeArgs = @('-f', $BaseCompose, '-f', $WorkerCompose)
$installed = $false
Push-Location $ProjectRoot
try {
    Copy-Item -LiteralPath $PackageWorker -Destination $ProjectWorker -Force
    Assert-Equal -Code 'WORKER_COPY_HASH_MISMATCH' -Actual ((Get-FileHash -LiteralPath $ProjectWorker -Algorithm SHA256).Hash.ToLowerInvariant()) -Expected $hash
    Invoke-DockerChecked -Step 'MEDIA_WORKER_2_6_BUILD' -DockerArgs (@('compose') + $composeArgs + @('build', 'media-worker'))
    Invoke-DockerChecked -Step 'MEDIA_WORKER_2_6_UP' -DockerArgs (@('compose') + $composeArgs + @('up', '-d', 'media-worker'))
    $health = $null
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $health = Invoke-RestMethod -Uri 'http://localhost:8090/health' -TimeoutSec 5
            if ($health.ok -eq $true -and $health.version -eq '2.6.0') { break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if ($null -eq $health) { throw 'WORKER_HEALTH_UNAVAILABLE' }
    Assert-Equal -Code 'WORKER_VERSION' -Actual $health.version -Expected '2.6.0'
    Assert-Equal -Code 'EDIT_PREVIEW_CONTRACT' -Actual $health.edit_preview_contract -Expected 'SM3_EDIT_PREVIEW_V1'
    Assert-Equal -Code 'EDIT_PREVIEW_RENDERER' -Actual $health.edit_preview_renderer -Expected $true
    Assert-Equal -Code 'EDIT_SAVE_CONTRACT' -Actual $health.edit_session_save_contract -Expected 'SM3_EDIT_SAVE_V1'
    $installed = $true
    Write-Host 'SM3_MEDIA_WORKER_2_6_0_INSTALL_PASS'
    Write-Host "backup=$Backup"
    Write-Host "worker_sha256=$hash"
}
finally {
    if (-not $installed) {
        Write-Host 'Instalação não confirmada; restaurando fonte anterior.'
        Copy-Item -LiteralPath (Join-Path $Backup 'worker_service.py') -Destination $ProjectWorker -Force
        try {
            Invoke-DockerChecked -Step 'ROLLBACK_BUILD' -DockerArgs (@('compose') + $composeArgs + @('build', 'media-worker'))
            Invoke-DockerChecked -Step 'ROLLBACK_UP' -DockerArgs (@('compose') + $composeArgs + @('up', '-d', 'media-worker'))
        } catch { Write-Host "ROLLBACK_FAILED: $($_.Exception.Message)" }
    }
    Pop-Location
}
