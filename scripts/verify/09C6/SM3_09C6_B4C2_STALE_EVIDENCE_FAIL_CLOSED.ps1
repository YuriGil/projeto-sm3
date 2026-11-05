param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4C2_STALE_EVIDENCE_FAIL_CLOSED.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$currentRpdId = "RPD_e79a9e07fd53fd856b95fc25f6564626"

$existingMetricId = "RMS_3d62d8716eba2f0b6b47dbd52a4bb5f9"


$sourceSha = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

$prefix = $sourceSha.Substring(
    0,
    2
)


$localMediaRef = "reference_artifacts/$prefix/$sourceSha/source"

$absoluteMediaPath = "/data/media/$localMediaRef"


$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$videoRoot = "/data/media/production_state/reference_video_analyses"


$currentRpdPath = "$priorityRoot/$profileId/$itemId/$currentRpdId.json"


# Must be newer than B4C1's controlled snapshot:
# 2026-09-23T18:40:00+00:00
$staleMetricCapturedAt = "2026-09-23T18:50:00+00:00"


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


function Get-Count {

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

        throw "SM3_09C6_B4C2_COUNT_COMMAND_FAILED"
    }


    return [int]$raw
}


function Get-PhysicalMetadata {

    param(
        [string]$Path
    )


    $code = "import os,sys,hashlib,json;p=sys.argv[1];b=open(p,'rb').read();s=os.stat(p);print(json.dumps({'sha256':hashlib.sha256(b).hexdigest(),'mtime_ns':s.st_mtime_ns,'size':s.st_size,'inode':s.st_ino},separators=(',',':')))"


    $raw = (
        docker exec `
            $container `
            python `
            -c `
            $code `
            $Path |
        Out-String
    ).Trim()


    if ($LASTEXITCODE -ne 0) {

        throw "SM3_09C6_B4C2_METADATA_FAILED:$Path"
    }


    return (
        $raw |
        ConvertFrom-Json
    )
}


function Invoke-JsonPostCapture {

    param(
        [string]$Uri,
        [hashtable]$Body
    )


    Add-Type `
        -AssemblyName System.Net.Http `
        -ErrorAction SilentlyContinue


    $json = $Body |
        ConvertTo-Json `
            -Depth 20 `
            -Compress


    $client = New-Object `
        System.Net.Http.HttpClient


    try {

        $client.Timeout = [TimeSpan]::FromSeconds(
            60
        )


        $content = New-Object `
            System.Net.Http.StringContent(
                $json,
                [System.Text.Encoding]::UTF8,
                "application/json"
            )


        try {

            $response = $client.PostAsync(
                $Uri,
                $content
            ).GetAwaiter().GetResult()


            $responseBody = $response.Content.ReadAsStringAsync(
            ).GetAwaiter().GetResult()


            return [PSCustomObject]@{

                StatusCode = [int]$response.StatusCode

                Body = [string]$responseBody
            }

        }
        finally {

            $content.Dispose()
        }

    }
    finally {

        $client.Dispose()
    }
}


# ============================================================
# 1. RUNTIME IDENTITY
# ============================================================

Write-Host "`n== RUNTIME PREFLIGHT ==" -ForegroundColor Yellow


$health = Invoke-RestMethod `
    -Uri "$base/health" `
    -Method GET `
    -TimeoutSec 30


$runtimeShaLine = (
    docker exec `
        $container `
        sha256sum `
        /app/worker_service.py |
    Out-String
).Trim()


$runtimeSha = (
    ($runtimeShaLine -split "\s+")[0]
).Trim().ToLower()


Add-Check `
    "WORKER_VERSION_2_23_1" `
    ($health.version -eq "2.23.1") `
    $health.version


Add-Check `
    "RUNTIME_SHA_EXPECTED" `
    ($runtimeSha -eq $expectedWorkerSha) `
    $runtimeSha


Add-Check `
    "PRIORITY_FAIL_CLOSED_EXPORTED" `
    (
        $health.reference_priority_semantic_fail_closed `
        -eq $true
    )


Add-Check `
    "PRIORITY_ENGINE_NO_MODEL_CALL" `
    (
        $health.reference_priority_engine_model_call `
        -eq $false
    )


# ============================================================
# 2. ACTIVE ITEM
# ============================================================

$item = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


Add-Check `
    "ITEM_ACTIVE" `
    ($item.effective_state -eq "ACTIVE") `
    ([string]$item.effective_state)


Add-Check `
    "ITEM_PROFILE_MATCH" `
    ($item.reference_profile_id -eq $profileId)


# ============================================================
# 3. CAS SOURCE — VIDEO ENDPOINT WILL READ THIS
# ============================================================

docker exec `
    $container `
    test -f `
    $absoluteMediaPath


$mediaExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "CAS_MEDIA_EXISTS" `
    $mediaExists `
    $absoluteMediaPath


if (-not $mediaExists) {

    throw "SM3_09C6_B4C2_CAS_MEDIA_MISSING"
}


$mediaShaLine = (
    docker exec `
        $container `
        sha256sum `
        $absoluteMediaPath |
    Out-String
).Trim()


$mediaSha = (
    ($mediaShaLine -split "\s+")[0]
).Trim().ToLower()


Add-Check `
    "CAS_MEDIA_SHA_MATCH" `
    ($mediaSha -eq $sourceSha) `
    $mediaSha


# ============================================================
# 4. PRIORITY BASELINE — EXACTLY TWO RPDs
# ============================================================

$priorityBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityBefore = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


Add-Check `
    "ITEM_RPD_COUNT_TWO_BEFORE" `
    ($priorityBefore.count -eq 2) `
    ([string]$priorityBefore.count)


Add-Check `
    "GLOBAL_RPD_COUNT_TWO_BEFORE" `
    ($globalPriorityBefore -eq 2) `
    ([string]$globalPriorityBefore)


Add-Check `
    "LATEST_RPD_EXPECTED_BEFORE" `
    (
        $latestBefore.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


$currentFingerprint = [string]$latestBefore.priority_decision.evidence_fingerprint

$currentRecordHash = [string]$latestBefore.priority_decision.priority_decision_sha256

$currentCreatedAt = [string]$latestBefore.priority_decision.created_at


Add-Check `
    "CURRENT_RPD_DEFER" `
    (
        $latestBefore.priority_decision.decision `
        -eq "DEFER"
    )


Add-Check `
    "CURRENT_RPD_SEMANTIC_FALSE" `
    (
        $latestBefore.priority_decision.semantic_analysis_allowed `
        -eq $false
    )


# ============================================================
# 5. CURRENT RPD PHYSICAL BASELINE
# ============================================================

docker exec `
    $container `
    test -f `
    $currentRpdPath


$currentRpdExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "CURRENT_RPD_FILE_EXISTS" `
    $currentRpdExists `
    $currentRpdPath


if (-not $currentRpdExists) {

    throw "SM3_09C6_B4C2_CURRENT_RPD_FILE_MISSING"
}


$rpdPhysicalBefore = Get-PhysicalMetadata `
    -Path $currentRpdPath


# ============================================================
# 6. METRIC BASELINE — EXACTLY B4C1 SNAPSHOT
# ============================================================

$metricsBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$metricIdsBefore = @(
    $metricsBefore.snapshots |
    ForEach-Object {
        $_.snapshot_id
    }
)


Add-Check `
    "METRIC_COUNT_ONE_BEFORE" `
    ($metricsBefore.count -eq 1) `
    ([string]$metricsBefore.count)


Add-Check `
    "B4C1_METRIC_PRESENT_BEFORE" `
    ($metricIdsBefore -contains $existingMetricId)


# ============================================================
# 7. VIDEO + FEATURE BASELINE
# ============================================================

$videoCountBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$featuresBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


Add-Check `
    "VIDEO_COUNT_ZERO_BEFORE" `
    ($videoCountBefore -eq 0) `
    ([string]$videoCountBefore)


$featureCountBefore = [int]$featuresBefore.count


# ============================================================
# 8. STOP IF BASELINE IS NOT EXACT
# ============================================================

$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4C2_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 9. CREATE NEW EVIDENCE ONLY
#
# IMPORTANT:
# We intentionally DO NOT call /priority-decision after this.
# ============================================================

Write-Host "`n== CREATE STALE-EVIDENCE SNAPSHOT ==" -ForegroundColor Yellow


$metricBody = @{

    reference_item_id = $itemId

    provider = "MANUAL"

    likes = 124

    comments = 8

    interactions = 132

    engagement = 0.132

    raw_metrics = @{

        views = 1001

        sm3_test_canary = "09C6_B4C2_STALE"
    }

    captured_at = $staleMetricCapturedAt

    source = "CHATGPT"

    notes = "SM3_09C6_B4C2_STALE_EVIDENCE_DO_NOT_USE_FOR_LEARNING"

} | ConvertTo-Json -Depth 10


$newMetric = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/metric-snapshot" `
    -Method POST `
    -ContentType "application/json" `
    -Body $metricBody `
    -TimeoutSec 30


$newMetricId = [string]$newMetric.snapshot_id


Write-Host "NEW_METRIC_ID=$newMetricId"

Write-Host "NEW_METRIC_REUSED=$($newMetric.reused_existing)"


Add-Check `
    "NEW_METRIC_NOT_REUSED" `
    ($newMetric.reused_existing -eq $false)


Add-Check `
    "NEW_METRIC_ID_FORMAT" `
    ($newMetricId -match '^RMS_[0-9a-f]{32}$') `
    $newMetricId


Add-Check `
    "NEW_METRIC_DIFFERS_FROM_B4C1" `
    ($newMetricId -ne $existingMetricId)


# ============================================================
# 10. PROVE EVIDENCE CHANGED BUT PRIORITY WAS NOT RECALCULATED
# ============================================================

$metricsAfterEvidence = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$metricIdsAfter = @(
    $metricsAfterEvidence.snapshots |
    ForEach-Object {
        $_.snapshot_id
    }
)


$priorityBeforeGuard = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestBeforeGuard = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityBeforeGuard = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


Add-Check `
    "METRIC_COUNT_TWO_AFTER_EVIDENCE" `
    ($metricsAfterEvidence.count -eq 2) `
    "1->$($metricsAfterEvidence.count)"


Add-Check `
    "NEW_METRIC_PERSISTED" `
    ($metricIdsAfter -contains $newMetricId)


Add-Check `
    "OLD_METRIC_PRESERVED" `
    ($metricIdsAfter -contains $existingMetricId)


Add-Check `
    "NO_NEW_RPD_BEFORE_GUARD" `
    (
        $priorityBeforeGuard.count -eq 2 `
        -and
        $globalPriorityBeforeGuard -eq 2
    ) `
    "$($priorityBeforeGuard.count)/$globalPriorityBeforeGuard"


Add-Check `
    "LATEST_RPD_STILL_PREVIOUS" `
    (
        $latestBeforeGuard.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "LATEST_FINGERPRINT_STILL_PREVIOUS" `
    (
        $latestBeforeGuard.priority_decision.evidence_fingerprint `
        -eq $currentFingerprint
    )


# ============================================================
# 11. PROVE CURRENT RPD WAS NOT REWRITTEN BY METRIC CHANGE
# ============================================================

$rpdPhysicalAfterMetric = Get-PhysicalMetadata `
    -Path $currentRpdPath


Add-Check `
    "RPD_SHA_UNCHANGED_AFTER_NEW_EVIDENCE" `
    (
        $rpdPhysicalAfterMetric.sha256 `
        -eq $rpdPhysicalBefore.sha256
    )


Add-Check `
    "RPD_MTIME_UNCHANGED_AFTER_NEW_EVIDENCE" `
    (
        [string]$rpdPhysicalAfterMetric.mtime_ns `
        -eq [string]$rpdPhysicalBefore.mtime_ns
    )


# ============================================================
# 12. CALL PROTECTED VIDEO PATH
#
# Expected:
# HTTP 409
# REFERENCE_PRIORITY_DECISION_STALE
#
# The guard runs before contact sheet / Vision.
# ============================================================

Write-Host "`n== CALL VIDEO ANALYSIS WITH STALE PRIORITY ==" -ForegroundColor Yellow


$videoRequest = @{

    reference_item_id = $itemId

    local_media_ref = $localMediaRef

    preference_signal = "UNKNOWN"

    notes = "SM3_09C6_B4C2_STALE_GUARD_DO_NOT_USE_FOR_LEARNING"
}


$blocked = Invoke-JsonPostCapture `
    -Uri "$base/production/reference-corpus/video-analysis" `
    -Body $videoRequest


Write-Host "VIDEO_HTTP_STATUS=$($blocked.StatusCode)"

Write-Host "VIDEO_HTTP_BODY=$($blocked.Body)"


Add-Check `
    "VIDEO_BLOCKED_HTTP_409" `
    ($blocked.StatusCode -eq 409) `
    ([string]$blocked.StatusCode)


Add-Check `
    "VIDEO_BLOCK_REASON_STALE" `
    (
        $blocked.Body `
        -match 'REFERENCE_PRIORITY_DECISION_STALE'
    ) `
    $blocked.Body


Add-Check `
    "VIDEO_BLOCK_NOT_SEMANTIC_NOT_ALLOWED" `
    (
        $blocked.Body `
        -notmatch 'REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED'
    )


Add-Check `
    "VIDEO_BLOCK_NOT_DECISION_REQUIRED" `
    (
        $blocked.Body `
        -notmatch 'REFERENCE_PRIORITY_DECISION_REQUIRED'
    )


# ============================================================
# 13. POST-GUARD STATE
# ============================================================

$priorityAfterGuard = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestAfterGuard = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityAfter = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountAfter = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$featuresAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$metricsFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$rpdPhysicalFinal = Get-PhysicalMetadata `
    -Path $currentRpdPath


Add-Check `
    "PRIORITY_COUNT_STILL_TWO" `
    (
        $priorityAfterGuard.count -eq 2 `
        -and
        $globalPriorityAfter -eq 2
    ) `
    "2->$globalPriorityAfter"


Add-Check `
    "LATEST_RPD_STILL_PREVIOUS_AFTER_BLOCK" `
    (
        $latestAfterGuard.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "LATEST_RECORD_HASH_UNCHANGED" `
    (
        $latestAfterGuard.priority_decision.priority_decision_sha256 `
        -eq $currentRecordHash
    )


Add-Check `
    "LATEST_CREATED_AT_UNCHANGED" `
    (
        $latestAfterGuard.priority_decision.created_at `
        -eq $currentCreatedAt
    )


Add-Check `
    "VIDEO_ANALYSIS_COUNT_STILL_ZERO" `
    ($videoCountAfter -eq $videoCountBefore) `
    "$videoCountBefore->$videoCountAfter"


Add-Check `
    "FEATURE_COUNT_UNCHANGED" `
    (
        [int]$featuresAfter.count `
        -eq $featureCountBefore
    ) `
    "$featureCountBefore->$($featuresAfter.count)"


Add-Check `
    "METRIC_COUNT_STAYS_TWO" `
    ($metricsFinal.count -eq 2) `
    ([string]$metricsFinal.count)


Add-Check `
    "CURRENT_RPD_FILE_SHA_UNCHANGED_FINAL" `
    (
        $rpdPhysicalFinal.sha256 `
        -eq $rpdPhysicalBefore.sha256
    )


Add-Check `
    "CURRENT_RPD_FILE_MTIME_UNCHANGED_FINAL" `
    (
        [string]$rpdPhysicalFinal.mtime_ns `
        -eq [string]$rpdPhysicalBefore.mtime_ns
    )


Add-Check `
    "CURRENT_RPD_FILE_INODE_UNCHANGED_FINAL" `
    (
        [string]$rpdPhysicalFinal.inode `
        -eq [string]$rpdPhysicalBefore.inode
    )


# ============================================================
# 14. SUMMARY
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


Write-Host "`n== B4C2 CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4C2"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceItemId = $itemId

    LocalMediaRef = $localMediaRef

    PreviousMetricSnapshotId = $existingMetricId

    NewMetricSnapshotId = $newMetricId

    CurrentPriorityDecisionId = $currentRpdId

    CurrentEvidenceFingerprint = $currentFingerprint

    PriorityCountBefore = $globalPriorityBefore

    PriorityCountAfter = $globalPriorityAfter

    MetricCountBefore = $metricsBefore.count

    MetricCountAfter = $metricsFinal.count

    VideoCountBefore = $videoCountBefore

    VideoCountAfter = $videoCountAfter

    FeatureCountBefore = $featureCountBefore

    FeatureCountAfter = [int]$featuresAfter.count

    GuardHttpStatus = $blocked.StatusCode

    GuardResponseBody = $blocked.Body

    ExpectedGuard = "REFERENCE_PRIORITY_DECISION_STALE"

    StaleDetectedBeforeSemanticAllowCheck = (
        ($blocked.StatusCode -eq 409) `
        -and
        ($blocked.Body -match "REFERENCE_PRIORITY_DECISION_STALE") `
        -and
        ($blocked.Body -notmatch "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED")
    )

    RPDFileSHA256Before = $rpdPhysicalBefore.sha256

    RPDFileSHA256After = $rpdPhysicalFinal.sha256

    RPDFileMtimeNsBefore = [string]$rpdPhysicalBefore.mtime_ns

    RPDFileMtimeNsAfter = [string]$rpdPhysicalFinal.mtime_ns

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B4C2 SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 15. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    stale_metric_snapshot = $newMetric

    protected_video_response = $blocked

    latest_priority_decision = (
        $latestAfterGuard.priority_decision
    )

    checks = $checks
}


$report |
    ConvertTo-Json `
        -Depth 30 |
    Set-Content `
        -LiteralPath $ReportFile `
        -Encoding UTF8


$readback = Get-Content `
    -LiteralPath $ReportFile `
    -Raw |
    ConvertFrom-Json


$reportChecks = @(
    ($readback.summary.WorkerVersion -eq "2.23.1"),
    ($readback.summary.NewMetricSnapshotId -eq $newMetricId),
    ($readback.summary.CurrentPriorityDecisionId -eq $currentRpdId),
    ($readback.summary.PriorityCountBefore -eq 2),
    ($readback.summary.PriorityCountAfter -eq 2),
    ($readback.summary.MetricCountBefore -eq 1),
    ($readback.summary.MetricCountAfter -eq 2),
    ($readback.summary.VideoCountBefore -eq 0),
    ($readback.summary.VideoCountAfter -eq 0),
    ($readback.summary.GuardHttpStatus -eq 409),
    ($readback.summary.GuardResponseBody -match "REFERENCE_PRIORITY_DECISION_STALE"),
    ($readback.summary.StaleDetectedBeforeSemanticAllowCheck -eq $true),
    ($readback.summary.RPDFileSHA256Before -eq $readback.summary.RPDFileSHA256After),
    ($readback.summary.RPDFileMtimeNsBefore -eq $readback.summary.RPDFileMtimeNsAfter),
    ($readback.summary.AllPassed -eq $true)
)


$reportValid = (
    $reportChecks -notcontains $false
)


Write-Host "`nREPORT=$ReportFile"

Write-Host "REPORT_READBACK_VALID=$reportValid"


if (
    $allPassed `
    -and
    $reportValid
) {

    Write-Host `
        "`nSM3_09C6_B4C2_STALE_EVIDENCE_FAIL_CLOSED_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4C2_STALE_EVIDENCE_FAIL_CLOSED_FAIL" `
    -ForegroundColor Red

exit 1
