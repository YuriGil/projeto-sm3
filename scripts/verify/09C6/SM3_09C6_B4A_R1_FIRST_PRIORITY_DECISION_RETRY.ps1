param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4A_R1_FIRST_PRIORITY_DECISION_RETRY.json",

    [string]$FailureLog = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4A_R1_FAILURE_LOG.txt"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$acquisitionId = "RM_60dcb91d058b58498e4af25b5d566f41"

$rmaId = "RMA_0072a9689863b956298a9ec34f01bd0e"


$sourceSha = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

$artifactId = "MA_$sourceSha"

$prefix = $sourceSha.Substring(0,2)


$rmaPath = "/data/media/production_state/reference_mechanical_analyses/$prefix/$sourceSha/$rmaId.json"

$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$videoRoot = "/data/media/production_state/reference_video_analyses"


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

        throw "SM3_09C6_B4A_R1_COUNT_COMMAND_FAILED"
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

        throw "SM3_09C6_B4A_R1_RUNTIME_SHA_FAILED"
    }


    return (
        ($line -split "\s+")[0]
    ).Trim().ToLower()
}


# ============================================================
# 1. AUTHORITATIVE RUNTIME PREFLIGHT
# ============================================================

Write-Host "`n== RUNTIME PREFLIGHT ==" -ForegroundColor Yellow


$health = Invoke-RestMethod `
    -Uri "$base/health" `
    -Method GET `
    -TimeoutSec 30


$runtimeSha = Get-RuntimeSha


Add-Check `
    "WORKER_VERSION_2_23_1" `
    ($health.version -eq "2.23.1") `
    $health.version


Add-Check `
    "RUNTIME_SHA_EXPECTED" `
    ($runtimeSha -eq $expectedWorkerSha) `
    $runtimeSha


Add-Check `
    "PRIORITY_GATE_ACTIVE" `
    ($health.reference_priority_gate -eq $true)


Add-Check `
    "PRIORITY_ENGINE_DETERMINISTIC" `
    ($health.reference_priority_engine_deterministic -eq $true)


Add-Check `
    "PRIORITY_ENGINE_NO_MODEL_CALL" `
    ($health.reference_priority_engine_model_call -eq $false)


Add-Check `
    "SEMANTIC_FAIL_CLOSED" `
    ($health.reference_priority_semantic_fail_closed -eq $true)


# ============================================================
# 2. CANARY MUST BE EXACTLY THE EXISTING ONE
# ============================================================

Write-Host "`n== CANARY PREFLIGHT ==" -ForegroundColor Yellow


$item = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


Add-Check `
    "CANARY_ITEM_ID" `
    ($item.reference_item_id -eq $itemId)


Add-Check `
    "CANARY_ACTIVE" `
    ($item.effective_state -eq "ACTIVE") `
    ([string]$item.effective_state)


Add-Check `
    "CANARY_PROFILE" `
    ($item.reference_profile_id -eq $profileId)


Add-Check `
    "CANARY_DO_NOT_USE_FOR_LEARNING" `
    (
        $item.notes `
        -eq "SM3_09C6_PRIORITY_CANARY_A_DO_NOT_USE_FOR_LEARNING"
    )


# ============================================================
# 3. ACQUISITION MUST ALREADY EXIST
# ============================================================

$media = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/reference-media" `
    -Method GET `
    -TimeoutSec 30


$acquisitionMatches = @(
    $media.acquisitions |
    Where-Object {
        $_.acquisition_id -eq $acquisitionId
    }
)


Add-Check `
    "ONE_EXISTING_ACQUISITION" `
    ($acquisitionMatches.Count -eq 1) `
    ([string]$acquisitionMatches.Count)


if ($acquisitionMatches.Count -eq 1) {

    $acquisition = $acquisitionMatches[0]


    Add-Check `
        "ACQUISITION_ITEM_MATCH" `
        ($acquisition.reference_item_id -eq $itemId)


    Add-Check `
        "ACQUISITION_V2" `
        (
            $acquisition.contract_version `
            -eq "SM3_REFERENCE_MEDIA_ACQUISITION_V2"
        )


    Add-Check `
        "ACQUISITION_SOURCE_SHA" `
        ($acquisition.source_sha256 -eq $sourceSha)


    Add-Check `
        "ACQUISITION_MEDIA_ARTIFACT" `
        ($acquisition.media_artifact_id -eq $artifactId)

}
else {

    Add-Check "ACQUISITION_ITEM_MATCH" $false
    Add-Check "ACQUISITION_V2" $false
    Add-Check "ACQUISITION_SOURCE_SHA" $false
    Add-Check "ACQUISITION_MEDIA_ARTIFACT" $false
}


# ============================================================
# 4. RMA + CONTACT SHEET PHYSICAL EVIDENCE
# ============================================================

docker exec `
    $container `
    test -f `
    $rmaPath


$rmaExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "RMA_EXISTS" `
    $rmaExists


if (-not $rmaExists) {

    throw "SM3_09C6_B4A_R1_RMA_MISSING"
}


$rmaJson = (
    docker exec `
        $container `
        cat `
        $rmaPath |
    Out-String
)


$rma = $rmaJson |
    ConvertFrom-Json


Add-Check `
    "RMA_CONTRACT_V1" `
    (
        $rma.contract_version `
        -eq "SM3_REFERENCE_MECHANICAL_ANALYSIS_V1"
    )


Add-Check `
    "RMA_ID_MATCH" `
    ($rma.mechanical_analysis_id -eq $rmaId)


Add-Check `
    "RMA_SOURCE_SHA_MATCH" `
    ($rma.source_sha256 -eq $sourceSha)


$rmaRecordHash = [string]$rma.mechanical_analysis_sha256

$mechanicalConfidence = [double]$rma.mechanical_confidence

$contactPath = [string]$rma.contact_sheet_path

$contactExpectedSha = [string]$rma.contact_sheet_sha256


docker exec `
    $container `
    test -f `
    $contactPath


$contactExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "CONTACT_SHEET_EXISTS" `
    $contactExists


$contactActualSha = ""


if ($contactExists) {

    $contactShaLine = (
        docker exec `
            $container `
            sha256sum `
            $contactPath |
        Out-String
    ).Trim()


    $contactActualSha = (
        ($contactShaLine -split "\s+")[0]
    ).Trim().ToLower()
}


Add-Check `
    "CONTACT_SHEET_SHA_VERIFIED" `
    ($contactActualSha -eq $contactExpectedSha) `
    $contactActualSha


# ============================================================
# 5. CURRENT HUMAN PRIORITY
# ============================================================

$profiles = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/profiles" `
    -Method GET `
    -TimeoutSec 30


$profileMatches = @(
    $profiles.profiles |
    Where-Object {
        $_.reference_profile_id -eq $profileId
    }
)


Add-Check `
    "PROFILE_FOUND" `
    ($profileMatches.Count -eq 1) `
    ([string]$profileMatches.Count)


if ($profileMatches.Count -ne 1) {

    throw "SM3_09C6_B4A_R1_PROFILE_INVALID"
}


$humanPriority = [double]$profileMatches[0].human_priority


Add-Check `
    "HUMAN_PRIORITY_RANGE" `
    (
        $humanPriority -ge 0 `
        -and
        $humanPriority -le 100
    ) `
    ([string]$humanPriority)


# ============================================================
# 6. STATE BEFORE POST
# ============================================================

$priorityListBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$priorityGlobalBefore = Get-ContainerCount `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountBefore = Get-ContainerCount `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


Add-Check `
    "ITEM_PRIORITY_COUNT_ZERO_BEFORE" `
    ($priorityListBefore.count -eq 0) `
    ([string]$priorityListBefore.count)


Add-Check `
    "GLOBAL_PRIORITY_COUNT_ZERO_BEFORE" `
    ($priorityGlobalBefore -eq 0) `
    ([string]$priorityGlobalBefore)


Add-Check `
    "VIDEO_ANALYSIS_COUNT_ZERO_BEFORE" `
    ($videoCountBefore -eq 0) `
    ([string]$videoCountBefore)


$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4A_R1_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 7. INDEPENDENT EXPECTATION
#
# No metric snapshot exists for this canary.
#
# available weights:
# human      0.30
# mechanical 0.20
#
# normalized:
# human      0.60
# mechanical 0.40
# ============================================================

$mechanicalScore = [Math]::Max(
    0.0,
    [Math]::Min(
        100.0,
        $mechanicalConfidence
    )
)


# Contact has just been physically verified.
# Therefore the engine must not apply its 60-point cap.

$expectedHumanWeight = 0.6

$expectedMechanicalWeight = 0.4


$expectedScore = [Math]::Round(
    (
        ($humanPriority * $expectedHumanWeight) `
        +
        ($mechanicalScore * $expectedMechanicalWeight)
    ),
    4
)


if ($expectedScore -ge 70.0) {

    $expectedDecision = "SEMANTIC_ANALYSIS"

    $expectedThresholdReason = "PRIORITY_ABOVE_SEMANTIC_THRESHOLD"
}
elseif ($expectedScore -ge 40.0) {

    $expectedDecision = "DEFER"

    $expectedThresholdReason = "PRIORITY_IN_DEFER_RANGE"
}
else {

    $expectedDecision = "SKIP"

    $expectedThresholdReason = "PRIORITY_BELOW_SKIP_THRESHOLD"
}


$expectedSemanticAllowed = (
    $expectedDecision -eq "SEMANTIC_ANALYSIS"
)


if ($mechanicalScore -ge 80.0) {

    $expectedMechanicalReason = "MECHANICAL_EVIDENCE_HIGH"
}
else {

    $expectedMechanicalReason = "MECHANICAL_EVIDENCE_PARTIAL"
}


Write-Host "`n== EXPECTED PRIORITY RESULT ==" -ForegroundColor Yellow

Write-Host "HUMAN_PRIORITY=$humanPriority"

Write-Host "MECHANICAL_SCORE=$mechanicalScore"

Write-Host "EXPECTED_HUMAN_WEIGHT=$expectedHumanWeight"

Write-Host "EXPECTED_MECHANICAL_WEIGHT=$expectedMechanicalWeight"

Write-Host "EXPECTED_SCORE=$expectedScore"

Write-Host "EXPECTED_DECISION=$expectedDecision"

Write-Host "EXPECTED_SEMANTIC_ALLOWED=$expectedSemanticAllowed"


# ============================================================
# 8. RETRY EXACT FAILED POST
# ============================================================

Write-Host "`n== POST PRIORITY DECISION ==" -ForegroundColor Yellow


$body = @{

    reference_item_id = $itemId

    acquisition_id = $acquisitionId

    mechanical_analysis_id = $rmaId

    use_latest_acquisition = $false

} | ConvertTo-Json -Depth 10


$priorityResult = $null


try {

    $priorityResult = Invoke-RestMethod `
        -Uri "$base/production/reference-corpus/priority-decision" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 60

}
catch {

    Write-Host "`nPRIORITY_POST_FAILED=True" -ForegroundColor Red

    Write-Host "HTTP_ERROR=$($_.Exception.Message)"


    $priorityAfterFailure = Get-ContainerCount `
        "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


    $videoAfterFailure = Get-ContainerCount `
        "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


    Write-Host "PRIORITY_COUNT_AFTER_FAILURE=$priorityAfterFailure"

    Write-Host "VIDEO_COUNT_AFTER_FAILURE=$videoAfterFailure"


    docker logs `
        --tail 220 `
        $container `
        2>&1 |
    Set-Content `
        -LiteralPath $FailureLog `
        -Encoding UTF8


    Write-Host "FAILURE_LOG=$FailureLog"


    $failureMessage = "SM3_09C6_B4A_R1_PRIORITY_POST_FAILED;PRIORITY_COUNT=$priorityAfterFailure;VIDEO_COUNT=$videoAfterFailure"

    throw $failureMessage
}


# ============================================================
# 9. RESPONSE MUST EXIST
# ============================================================

if ($null -eq $priorityResult) {

    throw "SM3_09C6_B4A_R1_NULL_RESPONSE"
}


$decision = $priorityResult.priority_decision


if ($null -eq $decision) {

    throw "SM3_09C6_B4A_R1_DECISION_MISSING"
}


$priorityDecisionId = [string]$decision.priority_decision_id


Write-Host "`nPRIORITY_DECISION_ID=$priorityDecisionId"

Write-Host "ACTUAL_SCORE=$($decision.priority_score)"

Write-Host "ACTUAL_DECISION=$($decision.decision)"

Write-Host "SEMANTIC_ALLOWED=$($decision.semantic_analysis_allowed)"


# ============================================================
# 10. RESPONSE CONTRACT
# ============================================================

Add-Check `
    "FIRST_DECISION_NOT_REUSED" `
    ($priorityResult.reused_existing -eq $false)


Add-Check `
    "RPD_ID_FORMAT" `
    ($priorityDecisionId -match '^RPD_[0-9a-f]{32}$') `
    $priorityDecisionId


Add-Check `
    "PRIORITY_CONTRACT_V1" `
    (
        $decision.contract_version `
        -eq "SM3_REFERENCE_PRIORITY_DECISION_V1"
    )


Add-Check `
    "PRIORITY_ENGINE_V1" `
    (
        $decision.engine_version `
        -eq "SM3_REFERENCE_PRIORITY_ENGINE_V1"
    )


Add-Check `
    "DECISION_ITEM_MATCH" `
    ($decision.reference_item_id -eq $itemId)


Add-Check `
    "DECISION_PROFILE_MATCH" `
    ($decision.reference_profile_id -eq $profileId)


Add-Check `
    "DECISION_ACQUISITION_MATCH" `
    ($decision.acquisition_id -eq $acquisitionId)


Add-Check `
    "DECISION_ARTIFACT_MATCH" `
    ($decision.media_artifact_id -eq $artifactId)


Add-Check `
    "DECISION_SOURCE_SHA_MATCH" `
    ($decision.source_sha256 -eq $sourceSha)


Add-Check `
    "DECISION_RMA_ID_MATCH" `
    ($decision.mechanical_analysis_id -eq $rmaId)


Add-Check `
    "DECISION_RMA_RECORD_HASH_MATCH" `
    (
        $decision.mechanical_analysis_sha256 `
        -eq $rmaRecordHash
    )


Add-Check `
    "EVIDENCE_FINGERPRINT_FORMAT" `
    (
        [string]$decision.evidence_fingerprint `
        -match '^[0-9a-f]{64}$'
    )


Add-Check `
    "DECISION_RECORD_HASH_FORMAT" `
    (
        [string]$decision.priority_decision_sha256 `
        -match '^[0-9a-f]{64}$'
    )


# ============================================================
# 11. EVIDENCE / WEIGHTS / SCORE
# ============================================================

Add-Check `
    "METRIC_SIGNAL_UNAVAILABLE" `
    (
        $decision.components.metric_signal.available `
        -eq $false
    )


Add-Check `
    "HUMAN_COMPONENT_MATCH" `
    (
        [Math]::Abs(
            [double]$decision.components.human_priority.score `
            - $humanPriority
        ) -lt 0.0001
    )


Add-Check `
    "MECHANICAL_COMPONENT_MATCH" `
    (
        [Math]::Abs(
            [double]$decision.components.mechanical_evidence_quality.score `
            - $mechanicalScore
        ) -lt 0.0001
    )


Add-Check `
    "HUMAN_WEIGHT_RENORMALIZED_060" `
    (
        [Math]::Abs(
            [double]$decision.effective_weights.human_priority `
            - $expectedHumanWeight
        ) -lt 0.000001
    )


Add-Check `
    "MECHANICAL_WEIGHT_RENORMALIZED_040" `
    (
        [Math]::Abs(
            [double]$decision.effective_weights.mechanical_evidence_quality `
            - $expectedMechanicalWeight
        ) -lt 0.000001
    )


Add-Check `
    "METRIC_WEIGHT_NOT_PRESENT" `
    ($null -eq $decision.effective_weights.metric_signal)


Add-Check `
    "PRIORITY_SCORE_REPRODUCED" `
    (
        [Math]::Abs(
            [double]$decision.priority_score `
            - $expectedScore
        ) -lt 0.0001
    ) `
    "$expectedScore->$($decision.priority_score)"


Add-Check `
    "DECISION_REPRODUCED" `
    ($decision.decision -eq $expectedDecision) `
    "$expectedDecision->$($decision.decision)"


Add-Check `
    "SEMANTIC_ALLOWED_REPRODUCED" `
    (
        $decision.semantic_analysis_allowed `
        -eq $expectedSemanticAllowed
    )


Add-Check `
    "ELIGIBILITY_ELIGIBLE" `
    ($decision.eligibility -eq "ELIGIBLE")


# ============================================================
# 12. ENGINE / SAFETY INVARIANTS
# ============================================================

Add-Check `
    "MODEL_CALL_USED_FALSE" `
    ($decision.model_call_used -eq $false)


Add-Check `
    "NOVELTY_SCORE_NULL" `
    ($null -eq $decision.novelty_score)


Add-Check `
    "COPYING_FORBIDDEN" `
    ($decision.copying_forbidden -eq $true)


Add-Check `
    "FOUNDATION_OVERRIDE_FALSE" `
    ($decision.foundation_override_allowed -eq $false)


# ============================================================
# 13. REASON CODES
# ============================================================

$reasonCodes = @(
    $decision.reason_codes
)


$requiredReasons = @(
    "ITEM_ACTIVE",
    "ACQUISITION_VERIFIED",
    "SOURCE_SHA_VERIFIED",
    "MECHANICAL_ANALYSIS_AVAILABLE",
    "MECHANICAL_SOURCE_MATCH",
    "HUMAN_PRIORITY_APPLIED",
    "METRIC_SIGNAL_UNAVAILABLE",
    $expectedMechanicalReason,
    $expectedThresholdReason
)


foreach ($reason in $requiredReasons) {

    Add-Check `
        "REASON_$reason" `
        ($reasonCodes -contains $reason)
}


# ============================================================
# 14. API READERS
# ============================================================

$listResult = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestResult = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


Add-Check `
    "LIST_COUNT_ONE" `
    ($listResult.count -eq 1) `
    ([string]$listResult.count)


Add-Check `
    "LIST_ID_MATCH" `
    (
        $listResult.priority_decisions[0].priority_decision_id `
        -eq $priorityDecisionId
    )


Add-Check `
    "LATEST_ID_MATCH" `
    (
        $latestResult.priority_decision.priority_decision_id `
        -eq $priorityDecisionId
    )


# ============================================================
# 15. PHYSICAL PERSISTENCE
# ============================================================

$decisionPath = "$priorityRoot/$profileId/$itemId/$priorityDecisionId.json"


docker exec `
    $container `
    test -f `
    $decisionPath


$decisionFileExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "DECISION_FILE_EXISTS" `
    $decisionFileExists `
    $decisionPath


if (-not $decisionFileExists) {

    throw "SM3_09C6_B4A_R1_DECISION_FILE_NOT_FOUND"
}


$persistedJson = (
    docker exec `
        $container `
        cat `
        $decisionPath |
    Out-String
)


$persistedDecision = $persistedJson |
    ConvertFrom-Json


Add-Check `
    "PERSISTED_ID_MATCH" `
    (
        $persistedDecision.priority_decision_id `
        -eq $priorityDecisionId
    )


Add-Check `
    "PERSISTED_RECORD_HASH_MATCH" `
    (
        $persistedDecision.priority_decision_sha256 `
        -eq $decision.priority_decision_sha256
    )


Add-Check `
    "PERSISTED_EVIDENCE_HASH_MATCH" `
    (
        $persistedDecision.evidence_fingerprint `
        -eq $decision.evidence_fingerprint
    )


Add-Check `
    "PERSISTED_SCORE_MATCH" `
    (
        [double]$persistedDecision.priority_score `
        -eq
        [double]$decision.priority_score
    )


Add-Check `
    "PERSISTED_DECISION_MATCH" `
    (
        $persistedDecision.decision `
        -eq $decision.decision
    )


# ============================================================
# 16. POST-STATE — EXACTLY ONE RPD, ZERO VIDEO
# ============================================================

$priorityGlobalAfter = Get-ContainerCount `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountAfter = Get-ContainerCount `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


Add-Check `
    "EXACTLY_ONE_PRIORITY_DECISION_EXISTS" `
    ($priorityGlobalAfter -eq 1) `
    "$priorityGlobalBefore->$priorityGlobalAfter"


Add-Check `
    "NO_VIDEO_ANALYSIS_CREATED" `
    ($videoCountAfter -eq $videoCountBefore) `
    "$videoCountBefore->$videoCountAfter"


# ============================================================
# 17. SUMMARY
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


Write-Host "`n== B4A-R1 CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4A-R1"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceProfileId = $profileId

    ReferenceItemId = $itemId

    AcquisitionId = $acquisitionId

    MediaArtifactId = $artifactId

    MechanicalAnalysisId = $rmaId

    PriorityDecisionId = $priorityDecisionId

    HumanPriority = $humanPriority

    MechanicalEvidenceQuality = $mechanicalScore

    MetricSignalAvailable = (
        $decision.components.metric_signal.available
    )

    ExpectedScore = $expectedScore

    ActualScore = $decision.priority_score

    ExpectedDecision = $expectedDecision

    ActualDecision = $decision.decision

    SemanticAnalysisAllowed = (
        $decision.semantic_analysis_allowed
    )

    PriorityCountBefore = $priorityGlobalBefore

    PriorityCountAfter = $priorityGlobalAfter

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


Write-Host "`n== B4A-R1 SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 18. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    priority_decision = $decision

    required_reason_codes = $requiredReasons

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


$readbackChecks = @(
    ($readback.summary.WorkerVersion -eq "2.23.1"),
    ($readback.summary.RuntimeSHA256 -eq $expectedWorkerSha),
    ($readback.summary.ReferenceItemId -eq $itemId),
    ($readback.summary.AcquisitionId -eq $acquisitionId),
    ($readback.summary.PriorityDecisionId -eq $priorityDecisionId),
    ($readback.summary.PriorityCountBefore -eq 0),
    ($readback.summary.PriorityCountAfter -eq 1),
    ($readback.summary.VideoAnalysisCountBefore -eq $videoCountBefore),
    ($readback.summary.VideoAnalysisCountAfter -eq $videoCountBefore),
    ($readback.summary.ExpectedScore -eq $expectedScore),
    ($readback.summary.ActualScore -eq $decision.priority_score),
    ($readback.summary.ExpectedDecision -eq $expectedDecision),
    ($readback.summary.ActualDecision -eq $expectedDecision),
    ($readback.summary.AllPassed -eq $true)
)


$reportValid = (
    $readbackChecks -notcontains $false
)


Write-Host "`nREPORT=$ReportFile"

Write-Host "REPORT_READBACK_VALID=$reportValid"


if (
    $allPassed `
    -and
    $reportValid
) {

    Write-Host `
        "`nSM3_09C6_B4A_R1_FIRST_PRIORITY_DECISION_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4A_R1_FIRST_PRIORITY_DECISION_FAIL" `
    -ForegroundColor Red

exit 1
