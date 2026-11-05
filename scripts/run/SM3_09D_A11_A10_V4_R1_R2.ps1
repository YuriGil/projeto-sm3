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

$repairFile = Join-Path $root "scripts\repair\09D\SM3_09D_A11_A10_V4_R1_R2_REPAIR.py"
$verifyFile = Join-Path $root "scripts\verify\09D\SM3_09D_A11_A10_V4_R1_R2_VERIFY.py"

$expectedEngineSha = "8121e44a017805018d6016b56378968144d8d1d1cda26869595632b9cfc497ee"
$expectedManifestSha = "0e604dd3e57275b908a32cd1f9c415b4bfdc5f60bd4c88823a054e776fbe3c1e"
$expectedRunnerSha = "683a8a20693dd08bea121487ef7da8a82260152e68b108be70c408d2e5275fa1"
$manifestFile = Join-Path $root "SM3_09D_A11_A10_MINIMAL_FEEDBACK_MANIFEST.json"

Write-Host ""
Write-Host "=== SM3 09D-A11-A10 V4-R1-R2 - HARNESS REPAIR + DUPLICATE AWARE RETRY ==="

$required = @(
    $engineFile,
    $manifestFile,
    $runnerFile,
    $repairFile,
    $verifyFile
)

foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "V4_R1_R2_REQUIRED_FILE_MISSING:$path"
    }
}

$engineSha = (Get-FileHash -LiteralPath $engineFile -Algorithm SHA256).Hash.ToLower()
$manifestSha = (Get-FileHash -LiteralPath $manifestFile -Algorithm SHA256).Hash.ToLower()
$runnerSha = (Get-FileHash -LiteralPath $runnerFile -Algorithm SHA256).Hash.ToLower()

$baselineChecks = @(
    ($engineSha -eq $expectedEngineSha),
    ($manifestSha -eq $expectedManifestSha),
    ($runnerSha -eq $expectedRunnerSha)
)

$baselinePass = ($baselineChecks -notcontains $false)

Write-Host "ENGINE_SHA256_BEFORE=$engineSha"
Write-Host "MANIFEST_SHA256_BEFORE=$manifestSha"
Write-Host "RUNNER_SHA256=$runnerSha"
Write-Host "BASELINE_AUTHORIZATION_PASS=$baselinePass"

if (-not $baselinePass) {
    throw "V4_R1_R2_BASELINE_AUTHORIZATION_FAILED"
}

Write-Host ""
Write-Host "=== 1. CONTROLLED REPAIR R2 ==="

& python -B $repairFile $root
$repairPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_R2_REPAIR_PASS=$repairPass"

if (-not $repairPass) {
    throw "V4_R1_R2_REPAIR_FAILED"
}

Write-Host ""
Write-Host "=== 2. ENGINE COMPILE ==="

& python -m py_compile $engineFile
$compilePass = ($LASTEXITCODE -eq 0)
Write-Host "ENGINE_COMPILE_PASS=$compilePass"

if (-not $compilePass) {
    throw "V4_R1_R2_ENGINE_COMPILE_FAILED"
}

Write-Host ""
Write-Host "=== 3. PREFLIGHT ==="

& $runnerFile -Action Preflight
$preflightPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_R2_PREFLIGHT_PASS=$preflightPass"

if (-not $preflightPass) {
    throw "V4_R1_R2_PREFLIGHT_FAILED"
}

if (Test-Path -LiteralPath $resultFile -PathType Leaf) {
    $backupDir = Join-Path $root "reports\09D\A11_A10_V4_R1_R2_DUPLICATE_RETRY"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = Join-Path $backupDir "SM3_09D_A11_A10_MINIMAL_FEEDBACK_RESULT.before_v4_r1_r2_$timestamp.json"
    Copy-Item -LiteralPath $resultFile -Destination $backup -Force
    Remove-Item -LiteralPath $resultFile -Force
    Write-Host "STALE_RESULT_BACKED_UP=$backup"
}

Write-Host ""
Write-Host "=== 4. FULL CHALLENGE ==="

& $runnerFile -Action Run
$runPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_R2_RUN_PASS=$runPass"

if (-not $runPass) {
    throw "V4_R1_R2_FULL_CHALLENGE_FAILED"
}

Write-Host ""
Write-Host "=== 5. EXISTING RESULT VALIDATION ==="

& $runnerFile -Action ValidateResult
$validatePass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_R2_VALIDATE_RESULT_PASS=$validatePass"

if (-not $validatePass) {
    throw "V4_R1_R2_RESULT_VALIDATION_FAILED"
}

Write-Host ""
Write-Host "=== 6. DIRECT UNIQUENESS VERIFY ==="

& python -B $verifyFile $root
$directVerifyPass = ($LASTEXITCODE -eq 0)
Write-Host "V4_R1_R2_DIRECT_VERIFY_PASS=$directVerifyPass"

if (-not $directVerifyPass) {
    throw "V4_R1_R2_DIRECT_VERIFY_FAILED"
}

$resultSha = (Get-FileHash -LiteralPath $resultFile -Algorithm SHA256).Hash.ToLower()

$checks = @(
    $baselinePass,
    $repairPass,
    $compilePass,
    $preflightPass,
    $runPass,
    $validatePass,
    $directVerifyPass
)

$pass = ($checks -notcontains $false)

Write-Host ""
Write-Host "=== 09D-A11-A10 V4-R1-R2 FINAL GATE ==="
Write-Host "BASELINE_AUTHORIZATION_PASS=$baselinePass"
Write-Host "V4_R1_R2_REPAIR_PASS=$repairPass"
Write-Host "ENGINE_COMPILE_PASS=$compilePass"
Write-Host "V4_R1_R2_PREFLIGHT_PASS=$preflightPass"
Write-Host "V4_R1_R2_RUN_PASS=$runPass"
Write-Host "V4_R1_R2_VALIDATE_RESULT_PASS=$validatePass"
Write-Host "V4_R1_R2_DIRECT_VERIFY_PASS=$directVerifyPass"
Write-Host "RESULT_SHA256=$resultSha"
Write-Host "PRODUCTION_STATE_WRITES=0"
Write-Host "A11_A10_V4_R1_R2_PASS=$pass"

if (-not $pass) {
    throw "SM3_09D_A11_A10_V4_R1_R2_FINAL_GATE_FAILED"
}

Write-Host ""
Write-Host "SM3_09D_A11_A10_V4_R1_R2_DUPLICATE_AWARE_RETRY_CHALLENGE_PASS"
