param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4C1_EVIDENCE_CHANGE_NEW_RPD.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$acquisitionId = "RM_60dcb91d058b58498e4af25b5d566f41"

$rmaId = "RMA_0072a9689863b956298a9ec34f01bd0e"

$oldRpdId = "RPD_c8182a42801dea53ae04497ce6e94cf8"


$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$videoRoot = "/data/media/production_state/reference_video_analyses"


$oldRpdPath = "$priorityRoot/$profileId/$itemId/$oldRpdId.json"


# Fixed test timestamp makes this canary idempotent if we ever
# need to diagnose a partially completed run.
$metricCapturedAt = "2026-09-23T18:40:00+00:00"


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

    $value = (
        docker exec `
            $container `
            sh -lc `
            $Command |
        Out-String
    ).Trim()

    if ($LASTEXITCODE -ne 0) {

        throw "SM3_09C6_B4C1_COUNT_COMMAND_FAILED"
    }

    return [int]$value
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

        throw "SM3_09C6_B4C1_METADATA_FAILED:$Path"
    }

    return (
        $raw |
        ConvertFrom-Json
    )
}


# ============================================================
# 1. RUNTIME BASELINE
# ============================================================

Write-Host "`n== RUNTIME BASELINE ==" -ForegroundColor Yellow


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
    "PRIORITY_ENGINE_DETERMINISTIC" `
    ($health.reference_priority_engine_deterministic -eq $true)


Add-Check `
    "PRIORITY_ENGINE_NO_MODEL_CALL" `
    ($health.reference_priority_engine_model_call -eq $false)


# ============================================================
# 2. OLD RPD BASELINE
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


$videoBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


docker exec `
    $container `
    test -f `
    $oldRpdPath


$oldExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "OLD_RPD_EXISTS" `
    $oldExists


Add-Check `
    "ITEM_HAS_ONE_RPD_BEFORE" `
    ($priorityBefore.count -eq 1) `
    ([string]$priorityBefore.count)


Add-Check `
    "GLOBAL_HAS_ONE_RPD_BEFORE" `
    ($globalPriorityBefore -eq 1) `
    ([string]$globalPriorityBefore)


Add-Check `
    "LATEST_IS_OLD_RPD_BEFORE" `
    (
        $latestBefore.priority_decision.priority_decision_id `
        -eq $oldRpdId
    )


Add-Check `
    "VIDEO_COUNT_ZERO_BEFORE" `
    ($videoBefore -eq 0) `
    ([string]$videoBefore)


if (-not $oldExists) {

    throw "SM3_09C6_B4C1_OLD_RPD_MISSING"
}


$oldJsonBefore = (
    docker exec `
        $container `
        cat `
        $oldRpdPath |
    Out-String
)


$oldRecordBefore = $oldJsonBefore |
    ConvertFrom-Json


$oldPhysicalBefore = Get-PhysicalMetadata `
    -Path $oldRpdPath


Add-Check `
    "OLD_RPD_ID_EXACT" `
    ($oldRecordBefore.priority_decision_id -eq $oldRpdId)


Add-Check `
    "OLD_RPD_DECISION_DEFER" `
    ($oldRecordBefore.decision -eq "DEFER")


Add-Check `
    "OLD_RPD_SCORE_66" `
    (
        [Math]::Abs(
            [double]$oldRecordBefore.priority_score - 66.0
        ) -lt 0.0001
    )


$oldEvidenceFingerprint = [string]$oldRecordBefore.evidence_fingerprint

$oldRecordHash = [string]$oldRecordBefore.priority_decision_sha256

$oldCreatedAt = [string]$oldRecordBefore.created_at


# ============================================================
# 3. METRIC BASELINE
# ============================================================

$metricsBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


Add-Check `
    "CANARY_METRIC_COUNT_ZERO_BEFORE" `
    ($metricsBefore.count -eq 0) `
    ([string]$metricsBefore.count)


$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4C1_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 4. CREATE ONE CONTROLLED METRIC SNAPSHOT
# ============================================================

Write-Host "`n== CREATE CONTROLLED METRIC EVIDENCE ==" -ForegroundColor Yellow


$metricBody = @{

    reference_item_id = $itemId

    provider = "MANUAL"

    likes = 123

    comments = 7

    interactions = 130

    engagement = 0.13

    raw_metrics = @{
        views = 1000
        sm3_test_canary = "09C6_B4C1"
    }

    captured_at = $metricCapturedAt

    source = "CHATGPT"

    notes = "SM3_09C6_B4C1_STALE_EVIDENCE_CANARY_DO_NOT_USE_FOR_LEARNING"

} | ConvertTo-Json -Depth 10


$metric = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/metric-snapshot" `
    -Method POST `
    -ContentType "application/json" `
    -Body $metricBody `
    -TimeoutSec 30


$metricId = [string]$metric.snapshot_id


if ([string]::IsNullOrWhiteSpace($metricId)) {

    throw "SM3_09C6_B4C1_METRIC_ID_MISSING"
}


Write-Host "METRIC_SNAPSHOT_ID=$metricId"

Write-Host "METRIC_REUSED=$($metric.reused_existing)"


Add-Check `
    "METRIC_FIRST_WRITE_NOT_REUSED" `
    ($metric.reused_existing -eq $false)


Add-Check `
    "METRIC_ID_FORMAT" `
    ($metricId -match '^RMS_[0-9a-f]{32}$') `
    $metricId


Add-Check `
    "METRIC_ITEM_MATCH" `
    ($metric.reference_item_id -eq $itemId)


Add-Check `
    "METRIC_PROFILE_MATCH" `
    ($metric.reference_profile_id -eq $profileId)


Add-Check `
    "METRIC_SOURCE_CHATGPT" `
    ($metric.source -eq "CHATGPT")


Add-Check `
    "METRIC_PROVIDER_MANUAL" `
    ($metric.provider -eq "MANUAL")


# ============================================================
# 5. PROVE METRIC PERSISTED
# ============================================================

$metricsAfterWrite = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$metricMatches = @(
    $metricsAfterWrite.snapshots |
    Where-Object {
        $_.snapshot_id -eq $metricId
    }
)


Add-Check `
    "METRIC_COUNT_ONE_AFTER" `
    ($metricsAfterWrite.count -eq 1) `
    ([string]$metricsAfterWrite.count)


Add-Check `
    "METRIC_FOUND_AFTER" `
    ($metricMatches.Count -eq 1) `
    ([string]$metricMatches.Count)


$metricPhysicalPath = (
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state -type f -name '$metricId.json' -print -quit" |
    Out-String
).Trim()


Add-Check `
    "METRIC_PHYSICAL_FILE_FOUND" `
    (-not [string]::IsNullOrWhiteSpace($metricPhysicalPath)) `
    $metricPhysicalPath


# ============================================================
# 6. OLD RPD MUST NOT CHANGE WHEN EVIDENCE CHANGES
# ============================================================

$oldPhysicalAfterMetric = Get-PhysicalMetadata `
    -Path $oldRpdPath


Add-Check `
    "OLD_RPD_SHA_UNCHANGED_AFTER_METRIC" `
    (
        $oldPhysicalAfterMetric.sha256 `
        -eq $oldPhysicalBefore.sha256
    )


Add-Check `
    "OLD_RPD_MTIME_UNCHANGED_AFTER_METRIC" `
    (
        [string]$oldPhysicalAfterMetric.mtime_ns `
        -eq [string]$oldPhysicalBefore.mtime_ns
    )


Add-Check `
    "OLD_RPD_INODE_UNCHANGED_AFTER_METRIC" `
    (
        [string]$oldPhysicalAfterMetric.inode `
        -eq [string]$oldPhysicalBefore.inode
    )


# ============================================================
# 7. RE-EVALUATE WITH NEW CURRENT EVIDENCE
# ============================================================

Write-Host "`n== RE-EVALUATE PRIORITY AFTER EVIDENCE CHANGE ==" -ForegroundColor Yellow


$priorityBody = @{

    reference_item_id = $itemId

    acquisition_id = $acquisitionId

    mechanical_analysis_id = $rmaId

    use_latest_acquisition = $false

} | ConvertTo-Json -Depth 10


$priorityResult = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/priority-decision" `
    -Method POST `
    -ContentType "application/json" `
    -Body $priorityBody `
    -TimeoutSec 60


$newDecision = $priorityResult.priority_decision


if ($null -eq $newDecision) {

    throw "SM3_09C6_B4C1_NEW_DECISION_MISSING"
}


$newRpdId = [string]$newDecision.priority_decision_id

$newEvidenceFingerprint = [string]$newDecision.evidence_fingerprint


Write-Host "OLD_RPD_ID=$oldRpdId"

Write-Host "NEW_RPD_ID=$newRpdId"

Write-Host "OLD_EVIDENCE_FINGERPRINT=$oldEvidenceFingerprint"

Write-Host "NEW_EVIDENCE_FINGERPRINT=$newEvidenceFingerprint"

Write-Host "NEW_SCORE=$($newDecision.priority_score)"

Write-Host "NEW_DECISION=$($newDecision.decision)"

Write-Host "METRIC_SIGNAL_AVAILABLE=$($newDecision.components.metric_signal.available)"


# ============================================================
# 8. EVIDENCE CHANGE MUST CREATE NEW IDENTITY
# ============================================================

Add-Check `
    "NEW_PRIORITY_NOT_REUSED" `
    ($priorityResult.reused_existing -eq $false)


Add-Check `
    "NEW_RPD_ID_FORMAT" `
    ($newRpdId -match '^RPD_[0-9a-f]{32}$') `
    $newRpdId


Add-Check `
    "NEW_RPD_DIFFERS_FROM_OLD" `
    ($newRpdId -ne $oldRpdId) `
    "$oldRpdId->$newRpdId"


Add-Check `
    "EVIDENCE_FINGERPRINT_CHANGED" `
    (
        $newEvidenceFingerprint `
        -ne $oldEvidenceFingerprint
    )


Add-Check `
    "SOURCE_SHA_STILL_SAME" `
    (
        $newDecision.source_sha256 `
        -eq $oldRecordBefore.source_sha256
    )


Add-Check `
    "RMA_ID_STILL_SAME" `
    (
        $newDecision.mechanical_analysis_id `
        -eq $rmaId
    )


Add-Check `
    "RMA_RECORD_HASH_STILL_SAME" `
    (
        $newDecision.mechanical_analysis_sha256 `
        -eq $oldRecordBefore.mechanical_analysis_sha256
    )


Add-Check `
    "PRIORITY_ENGINE_STILL_V1" `
    (
        $newDecision.engine_version `
        -eq "SM3_REFERENCE_PRIORITY_ENGINE_V1"
    )


Add-Check `
    "MODEL_CALL_USED_FALSE" `
    ($newDecision.model_call_used -eq $false)


Add-Check `
    "COPYING_FORBIDDEN" `
    ($newDecision.copying_forbidden -eq $true)


Add-Check `
    "FOUNDATION_OVERRIDE_FALSE" `
    ($newDecision.foundation_override_allowed -eq $false)


# ============================================================
# 9. OLD HISTORY MUST STILL BE IMMUTABLE
# ============================================================

$oldJsonAfter = (
    docker exec `
        $container `
        cat `
        $oldRpdPath |
    Out-String
)


$oldRecordAfter = $oldJsonAfter |
    ConvertFrom-Json


$oldPhysicalFinal = Get-PhysicalMetadata `
    -Path $oldRpdPath


Add-Check `
    "OLD_RPD_RECORD_HASH_UNCHANGED" `
    (
        $oldRecordAfter.priority_decision_sha256 `
        -eq $oldRecordHash
    )


Add-Check `
    "OLD_RPD_EVIDENCE_HASH_UNCHANGED" `
    (
        $oldRecordAfter.evidence_fingerprint `
        -eq $oldEvidenceFingerprint
    )


Add-Check `
    "OLD_RPD_CREATED_AT_UNCHANGED" `
    (
        $oldRecordAfter.created_at `
        -eq $oldCreatedAt
    )


Add-Check `
    "OLD_RPD_FILE_SHA_FINAL_UNCHANGED" `
    (
        $oldPhysicalFinal.sha256 `
        -eq $oldPhysicalBefore.sha256
    )


Add-Check `
    "OLD_RPD_FILE_MTIME_FINAL_UNCHANGED" `
    (
        [string]$oldPhysicalFinal.mtime_ns `
        -eq [string]$oldPhysicalBefore.mtime_ns
    )


# ============================================================
# 10. NEW RPD MUST PERSIST SEPARATELY
# ============================================================

$newRpdPath = "$priorityRoot/$profileId/$itemId/$newRpdId.json"


docker exec `
    $container `
    test -f `
    $newRpdPath


$newRpdExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "NEW_RPD_FILE_EXISTS" `
    $newRpdExists `
    $newRpdPath


if (-not $newRpdExists) {

    throw "SM3_09C6_B4C1_NEW_RPD_FILE_MISSING"
}


$newPersistedJson = (
    docker exec `
        $container `
        cat `
        $newRpdPath |
    Out-String
)


$newPersisted = $newPersistedJson |
    ConvertFrom-Json


Add-Check `
    "NEW_PERSISTED_ID_MATCH" `
    ($newPersisted.priority_decision_id -eq $newRpdId)


Add-Check `
    "NEW_PERSISTED_EVIDENCE_MATCH" `
    (
        $newPersisted.evidence_fingerprint `
        -eq $newEvidenceFingerprint
    )


Add-Check `
    "NEW_PERSISTED_RECORD_HASH_MATCH" `
    (
        $newPersisted.priority_decision_sha256 `
        -eq $newDecision.priority_decision_sha256
    )


# ============================================================
# 11. API HISTORY + LATEST
# ============================================================

$priorityAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityAfter = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoAfter = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$historyIds = @(
    $priorityAfter.priority_decisions |
    ForEach-Object {
        $_.priority_decision_id
    }
)


Add-Check `
    "ITEM_RPD_COUNT_TWO" `
    ($priorityAfter.count -eq 2) `
    "1->$($priorityAfter.count)"


Add-Check `
    "GLOBAL_RPD_COUNT_TWO" `
    ($globalPriorityAfter -eq 2) `
    "$globalPriorityBefore->$globalPriorityAfter"


Add-Check `
    "HISTORY_CONTAINS_OLD_RPD" `
    ($historyIds -contains $oldRpdId)


Add-Check `
    "HISTORY_CONTAINS_NEW_RPD" `
    ($historyIds -contains $newRpdId)


Add-Check `
    "LATEST_IS_NEW_RPD" `
    (
        $latestAfter.priority_decision.priority_decision_id `
        -eq $newRpdId
    )


Add-Check `
    "VIDEO_COUNT_STILL_ZERO" `
    ($videoAfter -eq $videoBefore) `
    "$videoBefore->$videoAfter"


# ============================================================
# 12. SUMMARY
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


Write-Host "`n== B4C1 CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4C1"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceItemId = $itemId

    AcquisitionId = $acquisitionId

    MechanicalAnalysisId = $rmaId

    MetricSnapshotId = $metricId

    OldPriorityDecisionId = $oldRpdId

    NewPriorityDecisionId = $newRpdId

    OldEvidenceFingerprint = $oldEvidenceFingerprint

    NewEvidenceFingerprint = $newEvidenceFingerprint

    EvidenceChanged = (
        $newEvidenceFingerprint `
        -ne $oldEvidenceFingerprint
    )

    MetricSignalAvailable = (
        $newDecision.components.metric_signal.available
    )

    OldScore = $oldRecordBefore.priority_score

    NewScore = $newDecision.priority_score

    OldDecision = $oldRecordBefore.decision

    NewDecision = $newDecision.decision

    PriorityCountBefore = $globalPriorityBefore

    PriorityCountAfter = $globalPriorityAfter

    VideoCountBefore = $videoBefore

    VideoCountAfter = $videoAfter

    OldFileSHA256Before = $oldPhysicalBefore.sha256

    OldFileSHA256After = $oldPhysicalFinal.sha256

    OldFileMtimeNsBefore = [string]$oldPhysicalBefore.mtime_ns

    OldFileMtimeNsAfter = [string]$oldPhysicalFinal.mtime_ns

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B4C1 SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 13. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    metric_snapshot = $metric

    old_priority_decision = $oldRecordAfter

    new_priority_decision = $newPersisted

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
    ($readback.summary.MetricSnapshotId -eq $metricId),
    ($readback.summary.OldPriorityDecisionId -eq $oldRpdId),
    ($readback.summary.NewPriorityDecisionId -eq $newRpdId),
    ($readback.summary.OldPriorityDecisionId -ne $readback.summary.NewPriorityDecisionId),
    ($readback.summary.OldEvidenceFingerprint -ne $readback.summary.NewEvidenceFingerprint),
    ($readback.summary.PriorityCountBefore -eq 1),
    ($readback.summary.PriorityCountAfter -eq 2),
    ($readback.summary.VideoCountBefore -eq 0),
    ($readback.summary.VideoCountAfter -eq 0),
    ($readback.summary.OldFileSHA256Before -eq $readback.summary.OldFileSHA256After),
    ($readback.summary.OldFileMtimeNsBefore -eq $readback.summary.OldFileMtimeNsAfter),
    ($readback.summary.AllPassed -eq $true)
)


$reportValid = (
    $reportChecks -notcontains $false
)


Write-Host "`nREPORT=$ReportFile"

Write-Host "REPORT_READBACK_VALID=$reportValid"


if (
    $allPassed `
    -and $reportValid
) {

    Write-Host `
        "`nSM3_09C6_B4C1_EVIDENCE_CHANGE_NEW_RPD_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4C1_EVIDENCE_CHANGE_NEW_RPD_FAIL" `
    -ForegroundColor Red

exit 1
