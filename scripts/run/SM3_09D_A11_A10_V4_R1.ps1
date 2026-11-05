param(
    [ValidateSet("Run")]
    [string]$Action = "Run"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = "D:\MOLOTOV_SOCIAL_OS_RC7"

$engineFile = Join-Path $root "SM3_09D_A11_A10_MINIMAL_FEEDBACK_ENGINE.py"
$runnerFile = Join-Path $root "SM3_09D_A11_A10_RUN_MINIMAL_FEEDBACK_CHALLENGE.ps1"
$resultFile = Join-Path $root "SM3_09D_A11_A10_MINIMAL_FEEDBACK_RESULT.json"

$repairFile = Join-Path $root "scripts\repair\09D\SM3_09D_A11_A10_V4_R1_REPAIR.py"
$verifyFile = Join-Path $root "scripts\verify\09D\SM3_09D_A11_A10_V4_R1_VERIFY.py"

$expectedRunnerSha = "683a8a20693dd08bea121487ef7da8a82260152e68b108be70c408d2e5275fa1"

Write-Host ""
Write-Host "=== SM3 09D-A11-A10 V4-R1 - DUPLICATE AWARE RETRY + FULL RERUN ==="

$required = @(
    $engineFile,
    $runnerFile,
    $repairFile,
    $verifyFile
)

foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "V4_R1_REQUIRED_FILE_MISSING:$path"
    }
}

$runnerSha = (Get-FileHash -LiteralPath $runnerFile -Algorithm SHA256).Hash.ToLower()
$runnerAuthorized = ($runnerSha -eq $expectedRunnerSha)

Write-Host "RUNNER_SHA256=$runnerSha"
Write-Host "RUNNER_AUTHORIZATION_PASS=$runnerAuthorized"

if (-not $runnerAuthorized) {
    throw "V4_R1_RUNNER_AUTHORIZATION_FAILED"
}

Write-Host ""
Write-Host "=== 1. CONTROLLED REPAIR ==="

& python -B $repairFile $root
if ($LASTEXITCODE -ne 0) {
    throw "V4_R1_REPAIR_FAILED"
}

Write-Host ""
Write-Host "=== 2. ENGINE COMPILE ==="

& python -m py_compile $engineFile
$compilePass = ($LASTEXITCODE -eq 0)
Write-Host "ENGINE_COMPILE_PASS=$compilePass"

if (-not $compilePass) {
    throw "V4_R1_ENGINE_COMPILE_FAILED"
}

Write-Host ""
Write-Host "=== 3. PREFLIGHT ==="

& $runnerFile -Action Preflight
$preflightPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_PREFLIGHT_PASS=$preflightPass"

if (-not $preflightPass) {
    throw "V4_R1_PREFLIGHT_FAILED"
}

if (Test-Path -LiteralPath $resultFile -PathType Leaf) {
    $backupDir = Join-Path $root "reports\09D\A11_A10_V4_R1_DUPLICATE_RETRY"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = Join-Path $backupDir "SM3_09D_A11_A10_MINIMAL_FEEDBACK_RESULT.before_v4_r1_$timestamp.json"
    Copy-Item -LiteralPath $resultFile -Destination $backup -Force
    Remove-Item -LiteralPath $resultFile -Force
    Write-Host "STALE_RESULT_BACKED_UP=$backup"
}

Write-Host ""
Write-Host "=== 4. FULL CHALLENGE ==="

& $runnerFile -Action Run
$runPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_RUN_PASS=$runPass"

if (-not $runPass) {
    throw "V4_R1_FULL_CHALLENGE_FAILED"
}

Write-Host ""
Write-Host "=== 5. INDEPENDENT EXISTING RESULT VALIDATION ==="

& $runnerFile -Action ValidateResult
$validatePass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_VALIDATE_RESULT_PASS=$validatePass"

if (-not $validatePass) {
    throw "V4_R1_RESULT_VALIDATION_FAILED"
}

Write-Host ""
Write-Host "=== 6. DIRECT UNIQUENESS VERIFY ==="

& python -B $verifyFile $root
$directVerifyPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_DIRECT_VERIFY_PASS=$directVerifyPass"

if (-not $directVerifyPass) {
    throw "V4_R1_DIRECT_VERIFY_FAILED"
}

$resultSha = (Get-FileHash -LiteralPath $resultFile -Algorithm SHA256).Hash.ToLower()

$checks = @(
    $runnerAuthorized,
    $compilePass,
    $preflightPass,
    $runPass,
    $validatePass,
    $directVerifyPass
)

$pass = ($checks -notcontains $false)

Write-Host ""
Write-Host "=== 09D-A11-A10 V4-R1 FINAL GATE ==="
Write-Host "RUNNER_AUTHORIZATION_PASS=$runnerAuthorized"
Write-Host "ENGINE_COMPILE_PASS=$compilePass"
Write-Host "V4_R1_PREFLIGHT_PASS=$preflightPass"
Write-Host "V4_R1_RUN_PASS=$runPass"
Write-Host "V4_R1_VALIDATE_RESULT_PASS=$validatePass"
Write-Host "V4_R1_DIRECT_VERIFY_PASS=$directVerifyPass"
Write-Host "RESULT_SHA256=$resultSha"
Write-Host "PRODUCTION_STATE_WRITES=0"
Write-Host "A11_A10_V4_R1_PASS=$pass"

if (-not $pass) {
    throw "SM3_09D_A11_A10_V4_R1_FINAL_GATE_FAILED"
}

Write-Host ""
Write-Host "SM3_09D_A11_A10_V4_R1_DUPLICATE_AWARE_RETRY_CHALLENGE_PASS"
