param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4A_F3_DEPLOY_RUNTIME_PERSISTENCE.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$worker = Join-Path `
    $Root `
    "worker\worker_service.py"


$staticReportFile = Join-Path `
    $Root `
    "reports\09C6\SM3_09C6_B2_PRIORITY_STATIC_GATE.json"


$expectedHostSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"

$expectedOldRuntimeSha = "227ecf9eefcdb020f1da6917a30d32717d8f10d7addc2d615d044b4ef7ce39d7"

$expectedVersion = "2.23.1"


$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$acquisitionId = "RM_60dcb91d058b58498e4af25b5d566f41"

$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$sourceSha = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

$artifactId = "MA_$sourceSha"

$rmaId = "RMA_0072a9689863b956298a9ec34f01bd0e"


$prefix = $sourceSha.Substring(
    0,
    2
)


$casPath = "/data/media/reference_artifacts/$prefix/$sourceSha/source"

$rmaPath = "/data/media/production_state/reference_mechanical_analyses/$prefix/$sourceSha/$rmaId.json"


$dc = @(
    "-f",
    "deployment\docker-compose.yml",
    "-f",
    "deployment\docker-compose.worker.yml"
)


$checks = @()


function Add-Check {

    param(
        [string]$Name,
        [bool]$Pass,
        [string]$Detail = ""
    )


    $script:checks += [PSCustomObject]@{
        Check  = $Name
        Pass   = $Pass
        Detail = $Detail
    }
}


function Get-ContainerCount {

    param(
        [string]$Command
    )


    $raw = (
        docker exec `
            $container `
            sh -lc `
            $Command |
        Out-String
    ).Trim()


    if ($LASTEXITCODE -ne 0) {

        throw "SM3_09C6_B4A_F3_COUNT_COMMAND_FAILED:$Command"
    }


    return [int]$raw
}


function Get-RuntimeSha {

    $line = (
        docker exec `
            $container `
            sha256sum `
            /app/worker_service.py |
        Out-String
    ).Trim()


    if ($LASTEXITCODE -ne 0) {

        throw "SM3_09C6_B4A_F3_RUNTIME_SHA_FAILED"
    }


    return (
        ($line -split "\s+")[0]
    ).Trim().ToLower()
}


# ============================================================
# 1. HOST + STATIC GATE PREFLIGHT
# ============================================================

Write-Host "`n== HOST + STATIC PREFLIGHT ==" -ForegroundColor Yellow


$hostSha = (
    Get-FileHash `
        -LiteralPath $worker `
        -Algorithm SHA256
).Hash.ToLower()


$hostVersion = (
    Select-String `
        -LiteralPath $worker `
        -Pattern 'WORKER_VERSION = "2.23.1"' `
        -SimpleMatch `
        -Quiet
)


if (-not (Test-Path -LiteralPath $staticReportFile)) {

    throw "SM3_09C6_B4A_F3_STATIC_REPORT_MISSING"
}


$staticReport = Get-Content `
    -LiteralPath $staticReportFile `
    -Raw |
    ConvertFrom-Json


Add-Check `
    "HOST_SHA_2_23_1_EXPECTED" `
    ($hostSha -eq $expectedHostSha) `
    $hostSha


Add-Check `
    "HOST_VERSION_2_23_1" `
    ($hostVersion -eq $true)


Add-Check `
    "STATIC_GATE_SOURCE_SHA_MATCH" `
    ($staticReport.source_sha256 -eq $expectedHostSha) `
    ([string]$staticReport.source_sha256)


Add-Check `
    "STATIC_GATE_CHECK_COUNT_139" `
    ([int]$staticReport.check_count -eq 139) `
    ([string]$staticReport.check_count)


Add-Check `
    "STATIC_GATE_PASS_COUNT_139" `
    ([int]$staticReport.pass_count -eq 139) `
    ([string]$staticReport.pass_count)


Add-Check `
    "STATIC_GATE_FAIL_COUNT_ZERO" `
    ([int]$staticReport.fail_count -eq 0) `
    ([string]$staticReport.fail_count)


Add-Check `
    "STATIC_GATE_ALL_PASSED" `
    ($staticReport.all_passed -eq $true)


$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $preflightMessage = "SM3_09C6_B4A_F3_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $preflightMessage
}


# ============================================================
# 2. CURRENT 2.23.0 RUNTIME BASELINE
# ============================================================

Write-Host "`n== PRE-DEPLOY RUNTIME BASELINE ==" -ForegroundColor Yellow


$healthBefore = Invoke-RestMethod `
    -Uri "$base/health" `
    -Method GET `
    -TimeoutSec 30


$runtimeShaBefore = Get-RuntimeSha


$containerIdBefore = (
    docker inspect `
        -f "{{.Id}}" `
        $container |
    Out-String
).Trim()


$priorityCountBefore = Get-ContainerCount `
    "find /data/media/production_state/reference_priority_decisions -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountBefore = Get-ContainerCount `
    "find /data/media/production_state/reference_video_analyses -type f -name '*.json' 2>/dev/null | wc -l"


$itemBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


$mediaBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/reference-media" `
    -Method GET `
    -TimeoutSec 30


$acquisitionBefore = @(
    $mediaBefore.acquisitions |
    Where-Object {
        $_.acquisition_id -eq $acquisitionId
    }
)


docker exec `
    $container `
    test -f `
    $casPath


$casExistsBefore = (
    $LASTEXITCODE -eq 0
)


docker exec `
    $container `
    test -f `
    $rmaPath


$rmaExistsBefore = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "PREDEPLOY_VERSION_2_23_0" `
    ($healthBefore.version -eq "2.23.0") `
    $healthBefore.version


Add-Check `
    "PREDEPLOY_RUNTIME_SHA_2_23_0" `
    ($runtimeShaBefore -eq $expectedOldRuntimeSha) `
    $runtimeShaBefore


Add-Check `
    "PREDEPLOY_PRIORITY_COUNT_ZERO" `
    ($priorityCountBefore -eq 0) `
    ([string]$priorityCountBefore)


Add-Check `
    "PREDEPLOY_VIDEO_COUNT_ZERO" `
    ($videoCountBefore -eq 0) `
    ([string]$videoCountBefore)


Add-Check `
    "CANARY_ITEM_ACTIVE_BEFORE" `
    ($itemBefore.effective_state -eq "ACTIVE") `
    ([string]$itemBefore.effective_state)


Add-Check `
    "CANARY_ACQUISITION_PRESENT_BEFORE" `
    ($acquisitionBefore.Count -eq 1) `
    ([string]$acquisitionBefore.Count)


Add-Check `
    "CAS_EXISTS_BEFORE" `
    $casExistsBefore


Add-Check `
    "RMA_EXISTS_BEFORE" `
    $rmaExistsBefore


$baselineFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($baselineFailed.Count -ne 0) {

    $baselineMessage = "SM3_09C6_B4A_F3_BASELINE_FAILED:" + ($baselineFailed.Check -join ",")

    throw $baselineMessage
}


# ============================================================
# 3. BUILD 2.23.1
# ============================================================

Write-Host "`n== BUILD WORKER 2.23.1 ==" -ForegroundColor Yellow


Push-Location $Root


try {

    docker compose @dc build `
        --no-cache `
        media-worker


    if ($LASTEXITCODE -ne 0) {

        throw "SM3_09C6_B4A_F3_BUILD_FAILED"
    }


    Write-Host `
        "SM3_09C6_B4A_F3_BUILD_OK" `
        -ForegroundColor Green


    # ========================================================
    # 4. RECREATE
    # ========================================================

    Write-Host "`n== RECREATE WORKER ==" -ForegroundColor Yellow


    docker compose @dc up `
        -d `
        --force-recreate `
        media-worker


    if ($LASTEXITCODE -ne 0) {

        throw "SM3_09C6_B4A_F3_RECREATE_FAILED"
    }

}
finally {

    Pop-Location
}


# ============================================================
# 5. WAIT FOR EXACT 2.23.1
# ============================================================

Write-Host "`n== WAIT FOR WORKER 2.23.1 ==" -ForegroundColor Yellow


$healthAfter = $null


for ($i = 1; $i -le 60; $i++) {

    try {

        $candidate = Invoke-RestMethod `
            -Uri "$base/health" `
            -Method GET `
            -TimeoutSec 5


        if (
            $candidate.ok -eq $true `
            -and
            $candidate.version -eq $expectedVersion
        ) {

            $healthAfter = $candidate

            break
        }
    }
    catch {

        # Expected while container is restarting.
    }


    Start-Sleep -Seconds 2
}


if ($null -eq $healthAfter) {

    throw "SM3_09C6_B4A_F3_HEALTH_2_23_1_NOT_RECOVERED"
}


# ============================================================
# 6. RUNTIME IDENTITY
# ============================================================

$runtimeShaAfter = Get-RuntimeSha


$containerIdAfter = (
    docker inspect `
        -f "{{.Id}}" `
        $container |
    Out-String
).Trim()


$containerStatus = (
    docker inspect `
        -f "{{.State.Status}}" `
        $container |
    Out-String
).Trim()


Add-Check `
    "CONTAINER_RUNNING" `
    ($containerStatus -eq "running") `
    $containerStatus


Add-Check `
    "CONTAINER_RECREATED" `
    ($containerIdAfter -ne $containerIdBefore)


Add-Check `
    "HEALTH_OK_AFTER" `
    ($healthAfter.ok -eq $true)


Add-Check `
    "RUNTIME_VERSION_2_23_1" `
    ($healthAfter.version -eq "2.23.1") `
    $healthAfter.version


Add-Check `
    "RUNTIME_SHA_EQUALS_HOST" `
    ($runtimeShaAfter -eq $hostSha) `
    $runtimeShaAfter


Add-Check `
    "RUNTIME_SHA_EXPECTED_2_23_1" `
    ($runtimeShaAfter -eq $expectedHostSha) `
    $runtimeShaAfter


Add-Check `
    "PRIORITY_GATE_EXPORTED" `
    ($healthAfter.reference_priority_gate -eq $true)


Add-Check `
    "PRIORITY_CONTRACT_V1_EXPORTED" `
    (
        $healthAfter.reference_priority_decision_contract `
        -eq "SM3_REFERENCE_PRIORITY_DECISION_V1"
    )


Add-Check `
    "PRIORITY_ENGINE_V1_EXPORTED" `
    (
        $healthAfter.reference_priority_engine_version `
        -eq "SM3_REFERENCE_PRIORITY_ENGINE_V1"
    )


Add-Check `
    "PRIORITY_ENGINE_DETERMINISTIC" `
    (
        $healthAfter.reference_priority_engine_deterministic `
        -eq $true
    )


Add-Check `
    "PRIORITY_ENGINE_NO_MODEL_CALL" `
    (
        $healthAfter.reference_priority_engine_model_call `
        -eq $false
    )


Add-Check `
    "SEMANTIC_FAIL_CLOSED" `
    (
        $healthAfter.reference_priority_semantic_fail_closed `
        -eq $true
    )


# ============================================================
# 7. PERSISTENCE AFTER RECREATE
# ============================================================

Write-Host "`n== PERSISTENCE AFTER RECREATE ==" -ForegroundColor Yellow


$priorityCountAfter = Get-ContainerCount `
    "find /data/media/production_state/reference_priority_decisions -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountAfter = Get-ContainerCount `
    "find /data/media/production_state/reference_video_analyses -type f -name '*.json' 2>/dev/null | wc -l"


$itemAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


$mediaAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/reference-media" `
    -Method GET `
    -TimeoutSec 30


$acquisitionAfter = @(
    $mediaAfter.acquisitions |
    Where-Object {
        $_.acquisition_id -eq $acquisitionId
    }
)


docker exec `
    $container `
    test -f `
    $casPath


$casExistsAfter = (
    $LASTEXITCODE -eq 0
)


if ($casExistsAfter) {

    $casShaLine = (
        docker exec `
            $container `
            sha256sum `
            $casPath |
        Out-String
    ).Trim()


    $casShaAfter = (
        ($casShaLine -split "\s+")[0]
    ).Trim().ToLower()

}
else {

    $casShaAfter = ""
}


docker exec `
    $container `
    test -f `
    $rmaPath


$rmaExistsAfter = (
    $LASTEXITCODE -eq 0
)


$rmaSourceSha = ""


if ($rmaExistsAfter) {

    $rmaJson = (
        docker exec `
            $container `
            cat `
            $rmaPath |
        Out-String
    )


    $rma = $rmaJson |
        ConvertFrom-Json


    $rmaSourceSha = [string]$rma.source_sha256
}


Add-Check `
    "PRIORITY_COUNT_STILL_ZERO" `
    ($priorityCountAfter -eq 0) `
    "$priorityCountBefore->$priorityCountAfter"


Add-Check `
    "VIDEO_COUNT_STILL_ZERO" `
    ($videoCountAfter -eq 0) `
    "$videoCountBefore->$videoCountAfter"


Add-Check `
    "CANARY_ITEM_STILL_ACTIVE" `
    ($itemAfter.effective_state -eq "ACTIVE") `
    ([string]$itemAfter.effective_state)


Add-Check `
    "CANARY_ITEM_ID_PRESERVED" `
    ($itemAfter.reference_item_id -eq $itemId)


Add-Check `
    "CANARY_PROFILE_PRESERVED" `
    ($itemAfter.reference_profile_id -eq $profileId)


Add-Check `
    "ACQUISITION_PRESERVED" `
    ($acquisitionAfter.Count -eq 1) `
    ([string]$acquisitionAfter.Count)


if ($acquisitionAfter.Count -eq 1) {

    Add-Check `
        "ACQUISITION_V2_PRESERVED" `
        (
            $acquisitionAfter[0].contract_version `
            -eq "SM3_REFERENCE_MEDIA_ACQUISITION_V2"
        )


    Add-Check `
        "ACQUISITION_SOURCE_SHA_PRESERVED" `
        (
            $acquisitionAfter[0].source_sha256 `
            -eq $sourceSha
        )


    Add-Check `
        "ACQUISITION_ARTIFACT_PRESERVED" `
        (
            $acquisitionAfter[0].media_artifact_id `
            -eq $artifactId
        )

}
else {

    Add-Check "ACQUISITION_V2_PRESERVED" $false
    Add-Check "ACQUISITION_SOURCE_SHA_PRESERVED" $false
    Add-Check "ACQUISITION_ARTIFACT_PRESERVED" $false
}


Add-Check `
    "CAS_EXISTS_AFTER" `
    $casExistsAfter


Add-Check `
    "CAS_SHA_PRESERVED" `
    ($casShaAfter -eq $sourceSha) `
    $casShaAfter


Add-Check `
    "RMA_EXISTS_AFTER" `
    $rmaExistsAfter


Add-Check `
    "RMA_SOURCE_SHA_PRESERVED" `
    ($rmaSourceSha -eq $sourceSha) `
    $rmaSourceSha


# ============================================================
# 8. PROVE DEPLOY ITSELF DID NOT CALL PRIORITY OR VISION
# ============================================================

Add-Check `
    "DEPLOY_CREATED_NO_PRIORITY_DECISION" `
    ($priorityCountAfter -eq 0)


Add-Check `
    "DEPLOY_CREATED_NO_VIDEO_ANALYSIS" `
    ($videoCountAfter -eq 0)


# ============================================================
# 9. SUMMARY
# ============================================================

$failed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


$checkCount = [int]$checks.Count


$passCount = @(
    $checks |
    Where-Object {
        $_.Pass -eq $true
    }
).Count


$failCount = [int]$failed.Count


$allPassed = (
    $failCount -eq 0
)


Write-Host "`n== F3 CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4A-F3"

    HostVersion = "2.23.1"

    HostSHA256 = $hostSha

    RuntimeVersionBefore = $healthBefore.version

    RuntimeSHABefore = $runtimeShaBefore

    RuntimeVersionAfter = $healthAfter.version

    RuntimeSHAAfter = $runtimeShaAfter

    ContainerRecreated = (
        $containerIdBefore -ne $containerIdAfter
    )

    StaticGateChecks = [int]$staticReport.check_count

    StaticGatePasses = [int]$staticReport.pass_count

    ReferenceItemId = $itemId

    AcquisitionId = $acquisitionId

    MediaArtifactId = $artifactId

    MechanicalAnalysisId = $rmaId

    PriorityCountBefore = $priorityCountBefore

    PriorityCountAfter = $priorityCountAfter

    VideoAnalysisCountBefore = $videoCountBefore

    VideoAnalysisCountAfter = $videoCountAfter

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== F3 SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 10. PERSIST REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    checks = $checks
}


$report |
    ConvertTo-Json `
        -Depth 20 |
    Set-Content `
        -LiteralPath $ReportFile `
        -Encoding UTF8


# ============================================================
# 11. READ-BACK
# ============================================================

$persisted = Get-Content `
    -LiteralPath $ReportFile `
    -Raw |
    ConvertFrom-Json


$readbackChecks = @(
    ($persisted.summary.HostVersion -eq "2.23.1"),
    ($persisted.summary.HostSHA256 -eq $expectedHostSha),
    ($persisted.summary.RuntimeVersionAfter -eq "2.23.1"),
    ($persisted.summary.RuntimeSHAAfter -eq $expectedHostSha),
    ($persisted.summary.StaticGateChecks -eq 139),
    ($persisted.summary.StaticGatePasses -eq 139),
    ($persisted.summary.ReferenceItemId -eq $itemId),
    ($persisted.summary.AcquisitionId -eq $acquisitionId),
    ($persisted.summary.PriorityCountAfter -eq 0),
    ($persisted.summary.VideoAnalysisCountAfter -eq 0),
    ($persisted.summary.AllPassed -eq $true)
)


$reportValid = (
    $readbackChecks -notcontains $false
)


Write-Host "`nREPORT=$ReportFile" -ForegroundColor Cyan

Write-Host "REPORT_READBACK_VALID=$reportValid"


if (
    $allPassed `
    -and $reportValid
) {

    Write-Host `
        "`nSM3_09C6_B4A_F3_DEPLOY_2_23_1_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4A_F3_DEPLOY_2_23_1_FAIL" `
    -ForegroundColor Red

exit 1

