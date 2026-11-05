param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4C3_CURRENT_DECISION_SEMANTIC_NOT_ALLOWED.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$acquisitionId = "RM_60dcb91d058b58498e4af25b5d566f41"

$rmaId = "RMA_0072a9689863b956298a9ec34f01bd0e"


$staleRpdId = "RPD_e79a9e07fd53fd856b95fc25f6564626"

$b4c1MetricId = "RMS_3d62d8716eba2f0b6b47dbd52a4bb5f9"

$b4c2MetricId = "RMS_605b8d285820af00a725bdda3b135b31"


$sourceSha = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

$prefix = $sourceSha.Substring(
    0,
    2
)


$localMediaRef = "reference_artifacts/$prefix/$sourceSha/source"


$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$videoRoot = "/data/media/production_state/reference_video_analyses"


$staleRpdPath = "$priorityRoot/$profileId/$itemId/$staleRpdId.json"


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

        throw "SM3_09C6_B4C3_COUNT_COMMAND_FAILED"
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

        throw "SM3_09C6_B4C3_METADATA_FAILED:$Path"
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


            $body = $response.Content.ReadAsStringAsync(
            ).GetAwaiter().GetResult()


            return [PSCustomObject]@{

                StatusCode = [int]$response.StatusCode

                Body = [string]$body
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
# 1. RUNTIME
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
    "SEMANTIC_FAIL_CLOSED_EXPORTED" `
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
# 2. ITEM
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
    "PROFILE_MATCH" `
    ($item.reference_profile_id -eq $profileId)


# ============================================================
# 3. METRIC STATE FROM B4C2
# ============================================================

$metricsBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$metricIds = @(
    $metricsBefore.snapshots |
    ForEach-Object {
        $_.snapshot_id
    }
)


Add-Check `
    "METRIC_COUNT_TWO" `
    ($metricsBefore.count -eq 2) `
    ([string]$metricsBefore.count)


Add-Check `
    "B4C1_METRIC_PRESENT" `
    ($metricIds -contains $b4c1MetricId)


Add-Check `
    "B4C2_METRIC_PRESENT" `
    ($metricIds -contains $b4c2MetricId)


# ============================================================
# 4. STALE PRIORITY BASELINE
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
    "LATEST_IS_STALE_RPD" `
    (
        $latestBefore.priority_decision.priority_decision_id `
        -eq $staleRpdId
    )


$staleFingerprint = [string]$latestBefore.priority_decision.evidence_fingerprint


# ============================================================
# 5. PHYSICAL IMMUTABILITY BASELINE
# ============================================================

docker exec `
    $container `
    test -f `
    $staleRpdPath


$staleFileExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "STALE_RPD_FILE_EXISTS" `
    $staleFileExists


if (-not $staleFileExists) {

    throw "SM3_09C6_B4C3_STALE_RPD_FILE_MISSING"
}


$stalePhysicalBefore = Get-PhysicalMetadata `
    -Path $staleRpdPath


# ============================================================
# 6. VIDEO / FEATURE BASELINE
# ============================================================

$videoBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$featuresBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$featureCountBefore = [int]$featuresBefore.count


Add-Check `
    "VIDEO_COUNT_ZERO_BEFORE" `
    ($videoBefore -eq 0) `
    ([string]$videoBefore)


# ============================================================
# 7. PREFLIGHT GATE
# ============================================================

$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4C3_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 8. REFRESH PRIORITY USING CURRENT EVIDENCE
# ============================================================

Write-Host "`n== REFRESH PRIORITY WITH CURRENT EVIDENCE ==" -ForegroundColor Yellow


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

    throw "SM3_09C6_B4C3_PRIORITY_DECISION_MISSING"
}


$newRpdId = [string]$newDecision.priority_decision_id

$newFingerprint = [string]$newDecision.evidence_fingerprint


Write-Host "STALE_RPD_ID=$staleRpdId"

Write-Host "CURRENT_RPD_ID=$newRpdId"

Write-Host "STALE_FINGERPRINT=$staleFingerprint"

Write-Host "CURRENT_FINGERPRINT=$newFingerprint"

Write-Host "CURRENT_SCORE=$($newDecision.priority_score)"

Write-Host "CURRENT_DECISION=$($newDecision.decision)"

Write-Host "CURRENT_SEMANTIC_ALLOWED=$($newDecision.semantic_analysis_allowed)"

Write-Host "CURRENT_METRIC_AVAILABLE=$($newDecision.components.metric_signal.available)"


Add-Check `
    "NEW_CURRENT_RPD_NOT_REUSED" `
    ($priorityResult.reused_existing -eq $false)


Add-Check `
    "NEW_CURRENT_RPD_ID_FORMAT" `
    ($newRpdId -match '^RPD_[0-9a-f]{32}$') `
    $newRpdId


Add-Check `
    "CURRENT_RPD_DIFFERS_FROM_STALE" `
    ($newRpdId -ne $staleRpdId) `
    "$staleRpdId->$newRpdId"


Add-Check `
    "CURRENT_FINGERPRINT_DIFFERS_FROM_STALE" `
    ($newFingerprint -ne $staleFingerprint)


Add-Check `
    "CURRENT_MODEL_CALL_FALSE" `
    ($newDecision.model_call_used -eq $false)


Add-Check `
    "CURRENT_COPYING_FORBIDDEN" `
    ($newDecision.copying_forbidden -eq $true)


Add-Check `
    "CURRENT_FOUNDATION_OVERRIDE_FALSE" `
    ($newDecision.foundation_override_allowed -eq $false)


# ============================================================
# 9. ABSOLUTE SAFETY STOP
#
# 09C6 must NOT execute Vision.
# ============================================================

if ($newDecision.semantic_analysis_allowed -eq $true) {

    Write-Host `
        "`nSEMANTIC_ANALYSIS_ALLOWED=True" `
        -ForegroundColor Red

    Write-Host `
        "VIDEO ANALYSIS WILL NOT BE CALLED." `
        -ForegroundColor Red

    throw "SM3_09C6_B4C3_ABORT_BEFORE_VISION_SEMANTIC_ALLOWED_TRUE"
}


Add-Check `
    "CURRENT_SEMANTIC_ALLOWED_FALSE" `
    ($newDecision.semantic_analysis_allowed -eq $false)


Add-Check `
    "CURRENT_DECISION_DEFER_OR_SKIP" `
    (
        $newDecision.decision -in @(
            "DEFER",
            "SKIP"
        )
    ) `
    ([string]$newDecision.decision)


# ============================================================
# 10. CURRENT RPD MUST NOW BE LATEST / THIRD
# ============================================================

$priorityAfterRefresh = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestAfterRefresh = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityAfterRefresh = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


Add-Check `
    "ITEM_RPD_COUNT_THREE_AFTER_REFRESH" `
    ($priorityAfterRefresh.count -eq 3) `
    "2->$($priorityAfterRefresh.count)"


Add-Check `
    "GLOBAL_RPD_COUNT_THREE_AFTER_REFRESH" `
    ($globalPriorityAfterRefresh -eq 3) `
    "$globalPriorityBefore->$globalPriorityAfterRefresh"


Add-Check `
    "LATEST_IS_CURRENT_RPD" `
    (
        $latestAfterRefresh.priority_decision.priority_decision_id `
        -eq $newRpdId
    )


Add-Check `
    "LATEST_FINGERPRINT_IS_CURRENT" `
    (
        $latestAfterRefresh.priority_decision.evidence_fingerprint `
        -eq $newFingerprint
    )


# ============================================================
# 11. OLD STALE RPD MUST STILL BE PHYSICALLY UNCHANGED
# ============================================================

$stalePhysicalAfterRefresh = Get-PhysicalMetadata `
    -Path $staleRpdPath


Add-Check `
    "STALE_RPD_SHA_UNCHANGED" `
    (
        $stalePhysicalAfterRefresh.sha256 `
        -eq $stalePhysicalBefore.sha256
    )


Add-Check `
    "STALE_RPD_MTIME_UNCHANGED" `
    (
        [string]$stalePhysicalAfterRefresh.mtime_ns `
        -eq [string]$stalePhysicalBefore.mtime_ns
    )


# ============================================================
# 12. CURRENT RPD PHYSICAL BASELINE
# ============================================================

$currentRpdPath = "$priorityRoot/$profileId/$itemId/$newRpdId.json"


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

    throw "SM3_09C6_B4C3_CURRENT_RPD_FILE_MISSING"
}


$currentPhysicalBeforeGuard = Get-PhysicalMetadata `
    -Path $currentRpdPath


# ============================================================
# 13. CALL VIDEO ANALYSIS
#
# Expected:
# current evidence matches new RPD
# semantic_analysis_allowed == false
#
# Therefore:
# HTTP 409
# REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:<decision>
# ============================================================

Write-Host "`n== CALL VIDEO ANALYSIS WITH CURRENT NON-ALLOWED RPD ==" -ForegroundColor Yellow


$videoRequest = @{

    reference_item_id = $itemId

    local_media_ref = $localMediaRef

    preference_signal = "UNKNOWN"

    notes = "SM3_09C6_B4C3_SEMANTIC_NOT_ALLOWED_DO_NOT_USE_FOR_LEARNING"
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
    "VIDEO_BLOCK_REASON_SEMANTIC_NOT_ALLOWED" `
    (
        $blocked.Body `
        -match 'REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:(DEFER|SKIP)'
    ) `
    $blocked.Body


Add-Check `
    "VIDEO_BLOCK_NOT_STALE" `
    (
        $blocked.Body `
        -notmatch 'REFERENCE_PRIORITY_DECISION_STALE'
    )


Add-Check `
    "VIDEO_BLOCK_NOT_DECISION_REQUIRED" `
    (
        $blocked.Body `
        -notmatch 'REFERENCE_PRIORITY_DECISION_REQUIRED'
    )


Add-Check `
    "VIDEO_BLOCK_DECISION_MATCHES_CURRENT" `
    (
        $blocked.Body `
        -match (
            'REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:' `
            + [regex]::Escape(
                [string]$newDecision.decision
            )
        )
    )


# ============================================================
# 14. POST-GUARD STATE
# ============================================================

$priorityFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityFinal = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoFinal = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$featuresFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$metricsFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$currentPhysicalFinal = Get-PhysicalMetadata `
    -Path $currentRpdPath


Add-Check `
    "PRIORITY_COUNT_STAYS_THREE" `
    (
        $priorityFinal.count -eq 3 `
        -and
        $globalPriorityFinal -eq 3
    ) `
    "3->$globalPriorityFinal"


Add-Check `
    "LATEST_STAYS_CURRENT_RPD" `
    (
        $latestFinal.priority_decision.priority_decision_id `
        -eq $newRpdId
    )


Add-Check `
    "VIDEO_COUNT_STAYS_ZERO" `
    ($videoFinal -eq $videoBefore) `
    "$videoBefore->$videoFinal"


Add-Check `
    "FEATURE_COUNT_UNCHANGED" `
    (
        [int]$featuresFinal.count `
        -eq $featureCountBefore
    ) `
    "$featureCountBefore->$($featuresFinal.count)"


Add-Check `
    "METRIC_COUNT_STAYS_TWO" `
    ($metricsFinal.count -eq 2) `
    ([string]$metricsFinal.count)


Add-Check `
    "CURRENT_RPD_SHA_UNCHANGED_BY_GUARD" `
    (
        $currentPhysicalFinal.sha256 `
        -eq $currentPhysicalBeforeGuard.sha256
    )


Add-Check `
    "CURRENT_RPD_MTIME_UNCHANGED_BY_GUARD" `
    (
        [string]$currentPhysicalFinal.mtime_ns `
        -eq [string]$currentPhysicalBeforeGuard.mtime_ns
    )


Add-Check `
    "CURRENT_RPD_INODE_UNCHANGED_BY_GUARD" `
    (
        [string]$currentPhysicalFinal.inode `
        -eq [string]$currentPhysicalBeforeGuard.inode
    )


# ============================================================
# 15. SUMMARY
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


Write-Host "`n== B4C3 CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4C3"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceItemId = $itemId

    AcquisitionId = $acquisitionId

    MechanicalAnalysisId = $rmaId

    StalePriorityDecisionId = $staleRpdId

    CurrentPriorityDecisionId = $newRpdId

    StaleEvidenceFingerprint = $staleFingerprint

    CurrentEvidenceFingerprint = $newFingerprint

    CurrentScore = $newDecision.priority_score

    CurrentDecision = $newDecision.decision

    CurrentSemanticAllowed = $newDecision.semantic_analysis_allowed

    MetricSignalAvailable = $newDecision.components.metric_signal.available

    PriorityCountBefore = $globalPriorityBefore

    PriorityCountAfterRefresh = $globalPriorityAfterRefresh

    PriorityCountFinal = $globalPriorityFinal

    MetricCount = $metricsFinal.count

    VideoCountBefore = $videoBefore

    VideoCountAfter = $videoFinal

    FeatureCountBefore = $featureCountBefore

    FeatureCountAfter = [int]$featuresFinal.count

    GuardHttpStatus = $blocked.StatusCode

    GuardResponseBody = $blocked.Body

    ExpectedGuard = "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:" + [string]$newDecision.decision

    CurrentDecisionMatchedEvidence = (
        $latestFinal.priority_decision.evidence_fingerprint `
        -eq $newFingerprint
    )

    VisionPathBlockedBeforeModel = (
        ($blocked.StatusCode -eq 409) `
        -and
        ($blocked.Body -match "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED") `
        -and
        ($videoFinal -eq 0) `
        -and
        ([int]$featuresFinal.count -eq $featureCountBefore)
    )

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B4C3 SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 16. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    current_priority_decision = $newDecision

    protected_video_response = $blocked

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
    ($readback.summary.CurrentPriorityDecisionId -eq $newRpdId),
    ($readback.summary.StalePriorityDecisionId -eq $staleRpdId),
    ($readback.summary.StalePriorityDecisionId -ne $readback.summary.CurrentPriorityDecisionId),
    ($readback.summary.StaleEvidenceFingerprint -ne $readback.summary.CurrentEvidenceFingerprint),
    ($readback.summary.CurrentSemanticAllowed -eq $false),
    ($readback.summary.PriorityCountBefore -eq 2),
    ($readback.summary.PriorityCountAfterRefresh -eq 3),
    ($readback.summary.PriorityCountFinal -eq 3),
    ($readback.summary.MetricCount -eq 2),
    ($readback.summary.VideoCountBefore -eq 0),
    ($readback.summary.VideoCountAfter -eq 0),
    ($readback.summary.GuardHttpStatus -eq 409),
    ($readback.summary.GuardResponseBody -match "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED"),
    ($readback.summary.GuardResponseBody -notmatch "REFERENCE_PRIORITY_DECISION_STALE"),
    ($readback.summary.CurrentDecisionMatchedEvidence -eq $true),
    ($readback.summary.VisionPathBlockedBeforeModel -eq $true),
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
        "`nSM3_09C6_B4C3_CURRENT_DECISION_SEMANTIC_NOT_ALLOWED_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4C3_CURRENT_DECISION_SEMANTIC_NOT_ALLOWED_FAIL" `
    -ForegroundColor Red

exit 1

