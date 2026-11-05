param(
    [ValidateSet("Run")]
    [string]$Action = "Run"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = "D:\MOLOTOV_SOCIAL_OS_RC7"

$engineFile = Join-Path $root "SM3_09D_A11_A10_MINIMAL_FEEDBACK_ENGINE.py"
$manifestFile = Join-Path $root "SM3_09D_A11_A10_MINIMAL_FEEDBACK_MANIFEST.json"
$runnerFile = Join-Path $root "SM3_09D_A11_A10_RUN_MINIMAL_FEEDBACK_CHALLENGE.ps1"
$resultFile = Join-Path $root "SM3_09D_A11_A10_MINIMAL_FEEDBACK_RESULT.json"

$repairFile = Join-Path $root "scripts\repair\09D\SM3_09D_A11_A10_V4_R1_R3_REPAIR.py"
$verifyFile = Join-Path $root "scripts\verify\09D\SM3_09D_A11_A10_V4_R1_R3_VERIFY.py"

$expectedEngineSha = "e7caceffcc0d9e66be16e7d605e3671cb646fcb5ce211bbd11747ac0122dbde6"
$expectedManifestSha = "bffbc73363c654c7ef6003bce0273029b25ab02b03a1ee5ea5686aacb4bcf1cd"
$expectedRunnerSha = "683a8a20693dd08bea121487ef7da8a82260152e68b108be70c408d2e5275fa1"

Write-Host ""
Write-Host "=== SM3 09D-A11-A10 V4-R1-R3 - MODEL SELECTOR RETRY + FULL CHALLENGE ==="

$required = @(
    $engineFile,
    $manifestFile,
    $runnerFile,
    $repairFile,
    $verifyFile
)

foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "V4_R1_R3_REQUIRED_FILE_MISSING:$path"
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
    throw "V4_R1_R3_BASELINE_AUTHORIZATION_FAILED"
}

Write-Host ""
Write-Host "=== 1. CONTROLLED R3 REPAIR ==="

& python -B $repairFile $root
$repairPass = ($LASTEXITCODE -eq 0)

Write-Host "V4_R1_R3_REPAIR_PASS=$repairPass"

if (-not $repairPass) {
    throw "V4_R1_R3_REPAIR_FAILED"
}

Write-Host ""
Write-Host "=== 2. ENGINE COMPILE ==="

& python -m py_compile $engineFile
$compilePass = ($LASTEXITCODE -eq 0)

Write-Host "ENGINE_COMPILE_PASS=$compilePass"

if (-not $compilePass) {
    throw "V4_R1_R3_ENGINE_COMPILE_FAILED"
}

Write-Host ""
Write-Host "=== 3. PREFLIGHT ==="

& $runnerFile -Action Preflight
$preflightPass = ($LASTEXITCODE -eq 0)

Write-Host "V4_R1_R3_PREFLIGHT_PASS=$preflightPass"

if (-not $preflightPass) {
    throw "V4_R1_R3_PREFLIGHT_FAILED"
}

if (Test-Path -LiteralPath $resultFile -PathType Leaf) {
    $backupDir = Join-Path $root "reports\09D\A11_A10_V4_R1_R3_SELECTOR_RETRY"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = Join-Path $backupDir "SM3_09D_A11_A10_MINIMAL_FEEDBACK_RESULT.before_v4_r1_r3_$timestamp.json"
    Copy-Item -LiteralPath $resultFile -Destination $backup -Force
    Remove-Item -LiteralPath $resultFile -Force
    Write-Host "STALE_RESULT_BACKED_UP=$backup"
}

Write-Host ""
Write-Host "=== 4. FULL CHALLENGE ==="

& $runnerFile -Action Run
$runPass = ($LASTEXITCODE -eq 0)

Write-Host "V4_R1_R3_RUN_PASS=$runPass"

if (-not $runPass) {
    throw "V4_R1_R3_FULL_CHALLENGE_FAILED"
}

Write-Host ""
Write-Host "=== 5. EXISTING RESULT VALIDATION ==="

& $runnerFile -Action ValidateResult
$validatePass = ($LASTEXITCODE -eq 0)

Write-Host "V4_R1_R3_VALIDATE_RESULT_PASS=$validatePass"

if (-not $validatePass) {
    throw "V4_R1_R3_RESULT_VALIDATION_FAILED"
}

Write-Host ""
Write-Host "=== 6. DIRECT RESULT VERIFY ==="

& python -B $verifyFile $root
$directVerifyPass = ($LASTEXITCODE -eq 0)

Write-Host "V4_R1_R3_DIRECT_VERIFY_PASS=$directVerifyPass"

if (-not $directVerifyPass) {
    throw "V4_R1_R3_DIRECT_VERIFY_FAILED"
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
Write-Host "=== 09D-A11-A10 V4-R1-R3 FINAL GATE ==="

Write-Host "BASELINE_AUTHORIZATION_PASS=$baselinePass"
Write-Host "V4_R1_R3_REPAIR_PASS=$repairPass"
Write-Host "ENGINE_COMPILE_PASS=$compilePass"
Write-Host "V4_R1_R3_PREFLIGHT_PASS=$preflightPass"
Write-Host "V4_R1_R3_RUN_PASS=$runPass"
Write-Host "V4_R1_R3_VALIDATE_RESULT_PASS=$validatePass"
Write-Host "V4_R1_R3_DIRECT_VERIFY_PASS=$directVerifyPass"
Write-Host "RESULT_SHA256=$resultSha"
Write-Host "PRODUCTION_STATE_WRITES=0"
Write-Host "A11_A10_V4_R1_R3_PASS=$pass"

if (-not $pass) {
    throw "SM3_09D_A11_A10_V4_R1_R3_FINAL_GATE_FAILED"
}

Write-Host ""
Write-Host "SM3_09D_A11_A10_V4_R1_R3_MODEL_SELECTOR_RETRY_CHALLENGE_PASS"
