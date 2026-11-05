param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4B_IMMUTABLE_IDEMPOTENCE.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$acquisitionId = "RM_60dcb91d058b58498e4af25b5d566f41"

$rmaId = "RMA_0072a9689863b956298a9ec34f01bd0e"

$expectedRpdId = "RPD_c8182a42801dea53ae04497ce6e94cf8"


$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$videoRoot = "/data/media/production_state/reference_video_analyses"


$decisionPath = "$priorityRoot/$profileId/$itemId/$expectedRpdId.json"


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

        throw "SM3_09C6_B4B_COUNT_FAILED"
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

        throw "SM3_09C6_B4B_METADATA_FAILED:$Path"
    }


    return (
        $raw |
        ConvertFrom-Json
    )
}


# ============================================================
# 1. RUNTIME
# ============================================================

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
# 2. BASELINE — EXACTLY ONE EXISTING DECISION
# ============================================================

$listBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalCountBefore = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


docker exec `
    $container `
    test -f `
    $decisionPath


$fileExistsBefore = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "ONE_ITEM_DECISION_BEFORE" `
    ($listBefore.count -eq 1) `
    ([string]$listBefore.count)


Add-Check `
    "ONE_GLOBAL_DECISION_BEFORE" `
    ($globalCountBefore -eq 1) `
    ([string]$globalCountBefore)


Add-Check `
    "EXPECTED_RPD_BEFORE" `
    (
        $latestBefore.priority_decision.priority_decision_id `
        -eq $expectedRpdId
    )


Add-Check `
    "DECISION_FILE_EXISTS_BEFORE" `
    $fileExistsBefore


Add-Check `
    "VIDEO_COUNT_ZERO_BEFORE" `
    ($videoCountBefore -eq 0) `
    ([string]$videoCountBefore)


if (-not $fileExistsBefore) {

    throw "SM3_09C6_B4B_DECISION_FILE_MISSING"
}


$recordBeforeJson = (
    docker exec `
        $container `
        cat `
        $decisionPath |
    Out-String
)


$recordBefore = $recordBeforeJson |
    ConvertFrom-Json


$physicalBefore = Get-PhysicalMetadata `
    -Path $decisionPath


Add-Check `
    "BASELINE_RPD_ID_EXACT" `
    ($recordBefore.priority_decision_id -eq $expectedRpdId)


Add-Check `
    "BASELINE_SCORE_66" `
    (
        [Math]::Abs(
            [double]$recordBefore.priority_score - 66.0
        ) -lt 0.0001
    )


Add-Check `
    "BASELINE_DECISION_DEFER" `
    ($recordBefore.decision -eq "DEFER")


Add-Check `
    "BASELINE_SEMANTIC_FALSE" `
    ($recordBefore.semantic_analysis_allowed -eq $false)


$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4B_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 3. ENSURE A REWRITE WOULD BE OBSERVABLE EVEN ON COARSE FS
# ============================================================

Start-Sleep -Milliseconds 1250


# ============================================================
# 4. EXACT SAME POST
# ============================================================

Write-Host "`n== REPEAT IDENTICAL PRIORITY POST ==" -ForegroundColor Yellow


$body = @{

    reference_item_id = $itemId

    acquisition_id = $acquisitionId

    mechanical_analysis_id = $rmaId

    use_latest_acquisition = $false

} | ConvertTo-Json -Depth 10


$result = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/priority-decision" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body `
    -TimeoutSec 60


$decisionAfterResponse = $result.priority_decision


if ($null -eq $decisionAfterResponse) {

    throw "SM3_09C6_B4B_RESPONSE_DECISION_MISSING"
}


# ============================================================
# 5. PHYSICAL + API STATE AFTER
# ============================================================

$physicalAfter = Get-PhysicalMetadata `
    -Path $decisionPath


$recordAfterJson = (
    docker exec `
        $container `
        cat `
        $decisionPath |
    Out-String
)


$recordAfter = $recordAfterJson |
    ConvertFrom-Json


$listAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$globalCountAfter = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoCountAfter = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


# ============================================================
# 6. IDEMPOTENCE ASSERTIONS
# ============================================================

Add-Check `
    "RESPONSE_OK" `
    ($result.ok -eq $true)


Add-Check `
    "REUSED_EXISTING_TRUE" `
    ($result.reused_existing -eq $true)


Add-Check `
    "SAME_RPD_ID_RESPONSE" `
    (
        $decisionAfterResponse.priority_decision_id `
        -eq $expectedRpdId
    )


Add-Check `
    "SAME_RECORD_HASH_RESPONSE" `
    (
        $decisionAfterResponse.priority_decision_sha256 `
        -eq $recordBefore.priority_decision_sha256
    )


Add-Check `
    "SAME_EVIDENCE_FINGERPRINT_RESPONSE" `
    (
        $decisionAfterResponse.evidence_fingerprint `
        -eq $recordBefore.evidence_fingerprint
    )


Add-Check `
    "SAME_CREATED_AT_RESPONSE" `
    (
        $decisionAfterResponse.created_at `
        -eq $recordBefore.created_at
    )


Add-Check `
    "SAME_SCORE_RESPONSE" `
    (
        [double]$decisionAfterResponse.priority_score `
        -eq [double]$recordBefore.priority_score
    )


Add-Check `
    "SAME_DECISION_RESPONSE" `
    (
        $decisionAfterResponse.decision `
        -eq $recordBefore.decision
    )


# ============================================================
# 7. PHYSICAL FILE MUST BE UNTOUCHED
# ============================================================

Add-Check `
    "FILE_SHA_UNCHANGED" `
    ($physicalAfter.sha256 -eq $physicalBefore.sha256) `
    "$($physicalBefore.sha256)->$($physicalAfter.sha256)"


Add-Check `
    "FILE_MTIME_NS_UNCHANGED" `
    (
        [string]$physicalAfter.mtime_ns `
        -eq [string]$physicalBefore.mtime_ns
    ) `
    "$($physicalBefore.mtime_ns)->$($physicalAfter.mtime_ns)"


Add-Check `
    "FILE_SIZE_UNCHANGED" `
    (
        [string]$physicalAfter.size `
        -eq [string]$physicalBefore.size
    )


Add-Check `
    "FILE_INODE_UNCHANGED" `
    (
        [string]$physicalAfter.inode `
        -eq [string]$physicalBefore.inode
    ) `
    "$($physicalBefore.inode)->$($physicalAfter.inode)"


# ============================================================
# 8. PERSISTED LOGICAL RECORD MUST BE IDENTICAL
# ============================================================

Add-Check `
    "PERSISTED_RPD_ID_UNCHANGED" `
    ($recordAfter.priority_decision_id -eq $recordBefore.priority_decision_id)


Add-Check `
    "PERSISTED_RECORD_HASH_UNCHANGED" `
    (
        $recordAfter.priority_decision_sha256 `
        -eq $recordBefore.priority_decision_sha256
    )


Add-Check `
    "PERSISTED_EVIDENCE_FINGERPRINT_UNCHANGED" `
    (
        $recordAfter.evidence_fingerprint `
        -eq $recordBefore.evidence_fingerprint
    )


Add-Check `
    "PERSISTED_CREATED_AT_UNCHANGED" `
    ($recordAfter.created_at -eq $recordBefore.created_at)


Add-Check `
    "PERSISTED_SCORE_UNCHANGED" `
    (
        [double]$recordAfter.priority_score `
        -eq [double]$recordBefore.priority_score
    )


Add-Check `
    "PERSISTED_DECISION_UNCHANGED" `
    ($recordAfter.decision -eq $recordBefore.decision)


# ============================================================
# 9. NO SECOND RECORD / NO VISION SIDE EFFECT
# ============================================================

Add-Check `
    "ITEM_DECISION_COUNT_STILL_ONE" `
    ($listAfter.count -eq 1) `
    "$($listBefore.count)->$($listAfter.count)"


Add-Check `
    "GLOBAL_DECISION_COUNT_STILL_ONE" `
    ($globalCountAfter -eq 1) `
    "$globalCountBefore->$globalCountAfter"


Add-Check `
    "LATEST_RPD_STILL_SAME" `
    (
        $latestAfter.priority_decision.priority_decision_id `
        -eq $expectedRpdId
    )


Add-Check `
    "VIDEO_COUNT_UNCHANGED_ZERO" `
    ($videoCountAfter -eq $videoCountBefore) `
    "$videoCountBefore->$videoCountAfter"


# ============================================================
# 10. SUMMARY
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


Write-Host "`n== B4B CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4B"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceItemId = $itemId

    AcquisitionId = $acquisitionId

    MechanicalAnalysisId = $rmaId

    PriorityDecisionId = $expectedRpdId

    ReusedExisting = $result.reused_existing

    DecisionCountBefore = $globalCountBefore

    DecisionCountAfter = $globalCountAfter

    VideoCountBefore = $videoCountBefore

    VideoCountAfter = $videoCountAfter

    FileSHA256Before = $physicalBefore.sha256

    FileSHA256After = $physicalAfter.sha256

    FileMtimeNsBefore = [string]$physicalBefore.mtime_ns

    FileMtimeNsAfter = [string]$physicalAfter.mtime_ns

    FileInodeBefore = [string]$physicalBefore.inode

    FileInodeAfter = [string]$physicalAfter.inode

    RecordHashBefore = $recordBefore.priority_decision_sha256

    RecordHashAfter = $recordAfter.priority_decision_sha256

    EvidenceFingerprintBefore = $recordBefore.evidence_fingerprint

    EvidenceFingerprintAfter = $recordAfter.evidence_fingerprint

    CreatedAtBefore = $recordBefore.created_at

    CreatedAtAfter = $recordAfter.created_at

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B4B SUMMARY ==" -ForegroundColor Yellow

$summary |
    Format-List


# ============================================================
# 11. REPORT + READBACK
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    decision_before = $recordBefore

    decision_after = $recordAfter

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
    ($readback.summary.PriorityDecisionId -eq $expectedRpdId),
    ($readback.summary.ReusedExisting -eq $true),
    ($readback.summary.DecisionCountBefore -eq 1),
    ($readback.summary.DecisionCountAfter -eq 1),
    ($readback.summary.VideoCountBefore -eq 0),
    ($readback.summary.VideoCountAfter -eq 0),
    ($readback.summary.FileSHA256Before -eq $readback.summary.FileSHA256After),
    ($readback.summary.FileMtimeNsBefore -eq $readback.summary.FileMtimeNsAfter),
    ($readback.summary.RecordHashBefore -eq $readback.summary.RecordHashAfter),
    ($readback.summary.CreatedAtBefore -eq $readback.summary.CreatedAtAfter),
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
        "`nSM3_09C6_B4B_IMMUTABLE_IDEMPOTENCE_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4B_IMMUTABLE_IDEMPOTENCE_FAIL" `
    -ForegroundColor Red

exit 1
