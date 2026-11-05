param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4C3_R2_RECOVERY_VERIFY_GUARD.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$currentRpdId = "RPD_c426ad8f8c144fd58a6f822c07ba5dd4"


$sourceSha = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

$prefix = $sourceSha.Substring(0,2)

$localMediaRef = "reference_artifacts/$prefix/$sourceSha/source"


$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$videoRoot = "/data/media/production_state/reference_video_analyses"


$currentRpdPath = "$priorityRoot/$profileId/$itemId/$currentRpdId.json"


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

        throw "SM3_09C6_B4C3_R2_COUNT_COMMAND_FAILED"
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

        throw "SM3_09C6_B4C3_R2_METADATA_FAILED:$Path"
    }


    return (
        $raw |
        ConvertFrom-Json
    )
}


function Invoke-JsonPostCapture {

    param(
        [string]$Uri,
        [hashtable]$RequestBody
    )


    Add-Type `
        -AssemblyName System.Net.Http `
        -ErrorAction SilentlyContinue


    $json = $RequestBody |
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

Write-Host "`n== RUNTIME IDENTITY ==" -ForegroundColor Yellow


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
    ($health.reference_priority_semantic_fail_closed -eq $true)


# ============================================================
# 2. RECOVER CURRENT PARTIAL STATE
# ============================================================

Write-Host "`n== RECOVER PARTIAL B4C3 STATE ==" -ForegroundColor Yellow


$priority = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latest = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$metrics = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$featuresBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$globalPriority = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


Add-Check `
    "ITEM_RPD_COUNT_THREE" `
    ($priority.count -eq 3) `
    ([string]$priority.count)


Add-Check `
    "GLOBAL_RPD_COUNT_THREE" `
    ($globalPriority -eq 3) `
    ([string]$globalPriority)


Add-Check `
    "METRIC_COUNT_TWO" `
    ($metrics.count -eq 2) `
    ([string]$metrics.count)


Add-Check `
    "VIDEO_COUNT_ZERO" `
    ($videoBefore -eq 0) `
    ([string]$videoBefore)


Add-Check `
    "LATEST_RPD_IS_PARTIAL_SUCCESS_RPD" `
    (
        $latest.priority_decision.priority_decision_id `
        -eq $currentRpdId
    ) `
    ([string]$latest.priority_decision.priority_decision_id)


Add-Check `
    "CURRENT_DECISION_DEFER" `
    (
        $latest.priority_decision.decision `
        -eq "DEFER"
    ) `
    ([string]$latest.priority_decision.decision)


Add-Check `
    "CURRENT_SEMANTIC_ALLOWED_FALSE" `
    (
        $latest.priority_decision.semantic_analysis_allowed `
        -eq $false
    )


Add-Check `
    "CURRENT_SCORE_66" `
    (
        [Math]::Abs(
            [double]$latest.priority_decision.priority_score `
            - 66.0
        ) -lt 0.0001
    ) `
    ([string]$latest.priority_decision.priority_score)


# ============================================================
# 3. CURRENT RPD PHYSICAL BASELINE
# ============================================================

docker exec `
    $container `
    test -f `
    $currentRpdPath


$rpdExists = (
    $LASTEXITCODE -eq 0
)


Add-Check `
    "CURRENT_RPD_FILE_EXISTS" `
    $rpdExists `
    $currentRpdPath


if (-not $rpdExists) {

    throw "SM3_09C6_B4C3_R2_CURRENT_RPD_FILE_MISSING"
}


$rpdPhysicalBefore = Get-PhysicalMetadata `
    -Path $currentRpdPath


$featureCountBefore = [int]$featuresBefore.count


# ============================================================
# 4. STOP IF RECOVERED STATE IS NOT EXACT
# ============================================================

$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4C3_R2_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


Write-Host "RECOVERED_RPD_ID=$currentRpdId"

Write-Host "RECOVERED_DECISION=$($latest.priority_decision.decision)"

Write-Host "RECOVERED_SCORE=$($latest.priority_decision.priority_score)"

Write-Host "RECOVERED_SEMANTIC_ALLOWED=$($latest.priority_decision.semantic_analysis_allowed)"


# ============================================================
# 5. REPEAT ONLY THE PROTECTED VIDEO CALL
#
# NO PRIORITY RECALCULATION HERE.
# ============================================================

Write-Host "`n== VERIFY CURRENT NON-ALLOWED GUARD ==" -ForegroundColor Yellow


$videoRequest = @{

    reference_item_id = $itemId

    local_media_ref = $localMediaRef

    preference_signal = "UNKNOWN"

    notes = "SM3_09C6_B4C3_R2_GUARD_RECOVERY_DO_NOT_USE_FOR_LEARNING"
}


$blocked = Invoke-JsonPostCapture `
    -Uri "$base/production/reference-corpus/video-analysis" `
    -RequestBody $videoRequest


Write-Host "VIDEO_HTTP_STATUS=$($blocked.StatusCode)"

Write-Host "VIDEO_HTTP_BODY=$($blocked.Body)"


Add-Check `
    "VIDEO_BLOCKED_HTTP_409" `
    ($blocked.StatusCode -eq 409) `
    ([string]$blocked.StatusCode)


Add-Check `
    "VIDEO_BLOCK_REASON_SEMANTIC_NOT_ALLOWED_DEFER" `
    (
        $blocked.Body `
        -match 'REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER'
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


# ============================================================
# 6. FINAL STATE
# ============================================================

$priorityFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$metricsFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$featuresFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityFinal = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoFinal = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$rpdPhysicalFinal = Get-PhysicalMetadata `
    -Path $currentRpdPath


Add-Check `
    "ITEM_RPD_COUNT_STAYS_THREE" `
    ($priorityFinal.count -eq 3) `
    "3->$($priorityFinal.count)"


Add-Check `
    "GLOBAL_RPD_COUNT_STAYS_THREE" `
    ($globalPriorityFinal -eq 3) `
    "3->$globalPriorityFinal"


Add-Check `
    "LATEST_RPD_STAYS_CURRENT" `
    (
        $latestFinal.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "METRIC_COUNT_STAYS_TWO" `
    ($metricsFinal.count -eq 2) `
    ([string]$metricsFinal.count)


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
    "CURRENT_RPD_SHA_UNCHANGED_BY_GUARD" `
    (
        $rpdPhysicalFinal.sha256 `
        -eq $rpdPhysicalBefore.sha256
    )


Add-Check `
    "CURRENT_RPD_MTIME_UNCHANGED_BY_GUARD" `
    (
        [string]$rpdPhysicalFinal.mtime_ns `
        -eq [string]$rpdPhysicalBefore.mtime_ns
    )


Add-Check `
    "CURRENT_RPD_INODE_UNCHANGED_BY_GUARD" `
    (
        [string]$rpdPhysicalFinal.inode `
        -eq [string]$rpdPhysicalBefore.inode
    )


# ============================================================
# 7. SUMMARY
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


Write-Host "`n== B4C3-R2 CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4C3-R2"

    RecoveryReason = "R1_CAPTURE_HELPER_VARIABLE_TYPE_COLLISION"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceItemId = $itemId

    CurrentPriorityDecisionId = $currentRpdId

    PriorityScore = $latestFinal.priority_decision.priority_score

    PriorityDecision = $latestFinal.priority_decision.decision

    SemanticAnalysisAllowed = $latestFinal.priority_decision.semantic_analysis_allowed

    PriorityCount = $globalPriorityFinal

    MetricCount = $metricsFinal.count

    VideoCountBefore = $videoBefore

    VideoCountAfter = $videoFinal

    FeatureCountBefore = $featureCountBefore

    FeatureCountAfter = [int]$featuresFinal.count

    GuardHttpStatus = $blocked.StatusCode

    GuardResponseBody = $blocked.Body

    ExpectedGuard = "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER"

    VisionPathBlockedBeforeModel = (
        ($blocked.StatusCode -eq 409) `
        -and
        ($blocked.Body -match "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER") `
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


Write-Host "`n== B4C3-R2 SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 8. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    current_priority_decision = $latestFinal.priority_decision

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
    ($readback.summary.CurrentPriorityDecisionId -eq $currentRpdId),
    ($readback.summary.PriorityDecision -eq "DEFER"),
    ($readback.summary.SemanticAnalysisAllowed -eq $false),
    ($readback.summary.PriorityCount -eq 3),
    ($readback.summary.MetricCount -eq 2),
    ($readback.summary.VideoCountBefore -eq 0),
    ($readback.summary.VideoCountAfter -eq 0),
    ($readback.summary.GuardHttpStatus -eq 409),
    ($readback.summary.GuardResponseBody -match "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER"),
    ($readback.summary.GuardResponseBody -notmatch "REFERENCE_PRIORITY_DECISION_STALE"),
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
        "`nSM3_09C6_B4C3_R2_RECOVERY_VERIFY_GUARD_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4C3_R2_RECOVERY_VERIFY_GUARD_FAIL" `
    -ForegroundColor Red

exit 1
