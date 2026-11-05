param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4D_RESTART_PERSISTENCE_GUARD.json"
)


$ErrorActionPreference = "Stop"

$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"

$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$rmaId = "RMA_0072a9689863b956298a9ec34f01bd0e"


$rpdIds = @(
    "RPD_c8182a42801dea53ae04497ce6e94cf8",
    "RPD_e79a9e07fd53fd856b95fc25f6564626",
    "RPD_c426ad8f8c144fd58a6f822c07ba5dd4"
)


$currentRpdId = "RPD_c426ad8f8c144fd58a6f822c07ba5dd4"


$metricIds = @(
    "RMS_3d62d8716eba2f0b6b47dbd52a4bb5f9",
    "RMS_605b8d285820af00a725bdda3b135b31"
)


$sourceSha = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

$prefix = $sourceSha.Substring(0,2)


$localMediaRef = "reference_artifacts/$prefix/$sourceSha/source"

$casPath = "/data/media/$localMediaRef"

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
        throw "SM3_09C6_B4D_COUNT_FAILED"
    }

    return [int]$raw
}


function Get-RuntimeSha {

    $raw = (
        docker exec `
            $container `
            sha256sum `
            /app/worker_service.py |
        Out-String
    ).Trim()

    if ($LASTEXITCODE -ne 0) {
        throw "SM3_09C6_B4D_RUNTIME_SHA_FAILED"
    }

    return (
        ($raw -split "\s+")[0]
    ).Trim().ToLower()
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
        throw "SM3_09C6_B4D_METADATA_FAILED:$Path"
    }

    return (
        $raw |
        ConvertFrom-Json
    )
}


function Find-UniqueFile {

    param(
        [string]$FileName
    )

    $count = Get-Count `
        "find /data/media/production_state -type f -name '$FileName' 2>/dev/null | wc -l"

    if ($count -ne 1) {
        throw ("SM3_09C6_B4D_FILE_NOT_UNIQUE:{0}:{1}" -f $FileName, $count)
    }

    $path = (
        docker exec `
            $container `
            sh -lc `
            "find /data/media/production_state -type f -name '$FileName' -print -quit" |
        Out-String
    ).Trim()

    if ([string]::IsNullOrWhiteSpace($path)) {
        throw "SM3_09C6_B4D_FILE_PATH_MISSING:$FileName"
    }

    return $path
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

            $responseText = $response.Content.ReadAsStringAsync(
            ).GetAwaiter().GetResult()

            return [PSCustomObject]@{
                StatusCode = [int]$response.StatusCode
                Body       = [string]$responseText
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
# 1. PRE-RESTART RUNTIME
# ============================================================

Write-Host "`n== PRE-RESTART RUNTIME ==" -ForegroundColor Yellow


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


$startedAtBefore = (
    docker inspect `
        -f "{{.State.StartedAt}}" `
        $container |
    Out-String
).Trim()


Add-Check `
    "VERSION_BEFORE_2_23_1" `
    ($healthBefore.version -eq "2.23.1") `
    $healthBefore.version


Add-Check `
    "RUNTIME_SHA_BEFORE_EXPECTED" `
    ($runtimeShaBefore -eq $expectedWorkerSha) `
    $runtimeShaBefore


# ============================================================
# 2. LOGICAL STATE BEFORE
# ============================================================

$itemBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


$priorityBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$metricsBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$featuresBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityBefore = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$priorityIdsBefore = @(
    $priorityBefore.priority_decisions |
    ForEach-Object {
        $_.priority_decision_id
    }
)


$metricIdsBefore = @(
    $metricsBefore.snapshots |
    ForEach-Object {
        $_.snapshot_id
    }
)


Add-Check `
    "ITEM_ACTIVE_BEFORE" `
    ($itemBefore.effective_state -eq "ACTIVE") `
    ([string]$itemBefore.effective_state)


Add-Check `
    "ITEM_PRIORITY_COUNT_THREE_BEFORE" `
    ($priorityBefore.count -eq 3) `
    ([string]$priorityBefore.count)


Add-Check `
    "GLOBAL_PRIORITY_COUNT_THREE_BEFORE" `
    ($globalPriorityBefore -eq 3) `
    ([string]$globalPriorityBefore)


Add-Check `
    "METRIC_COUNT_TWO_BEFORE" `
    ($metricsBefore.count -eq 2) `
    ([string]$metricsBefore.count)


Add-Check `
    "VIDEO_COUNT_ZERO_BEFORE" `
    ($videoBefore -eq 0) `
    ([string]$videoBefore)


Add-Check `
    "FEATURE_COUNT_ZERO_BEFORE" `
    ($featuresBefore.count -eq 0) `
    ([string]$featuresBefore.count)


foreach ($id in $rpdIds) {

    Add-Check `
        "RPD_PRESENT_BEFORE_$id" `
        ($priorityIdsBefore -contains $id)
}


foreach ($id in $metricIds) {

    Add-Check `
        "METRIC_PRESENT_BEFORE_$id" `
        ($metricIdsBefore -contains $id)
}


Add-Check `
    "LATEST_CURRENT_RPD_BEFORE" `
    (
        $latestBefore.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "LATEST_DECISION_DEFER_BEFORE" `
    (
        $latestBefore.priority_decision.decision `
        -eq "DEFER"
    )


Add-Check `
    "LATEST_SEMANTIC_FALSE_BEFORE" `
    (
        $latestBefore.priority_decision.semantic_analysis_allowed `
        -eq $false
    )


# ============================================================
# 3. PHYSICAL STATE BEFORE
# ============================================================

$rpdBefore = @{}

foreach ($id in $rpdIds) {

    $path = "$priorityRoot/$profileId/$itemId/$id.json"

    docker exec `
        $container `
        test -f `
        $path

    $exists = (
        $LASTEXITCODE -eq 0
    )

    Add-Check `
        "RPD_FILE_EXISTS_BEFORE_$id" `
        $exists `
        $path

    if (-not $exists) {
        throw "SM3_09C6_B4D_RPD_FILE_MISSING:$id"
    }

    $rpdBefore[$id] = Get-PhysicalMetadata `
        -Path $path
}


$metricPaths = @{}
$metricBefore = @{}

foreach ($id in $metricIds) {

    $path = Find-UniqueFile `
        -FileName "$id.json"

    $metricPaths[$id] = $path

    $metricBefore[$id] = Get-PhysicalMetadata `
        -Path $path

    Add-Check `
        "METRIC_FILE_EXISTS_BEFORE_$id" `
        $true `
        $path
}


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
    "CAS_EXISTS_BEFORE" `
    $casExistsBefore


Add-Check `
    "RMA_EXISTS_BEFORE" `
    $rmaExistsBefore


if (-not $casExistsBefore) {
    throw "SM3_09C6_B4D_CAS_MISSING"
}


if (-not $rmaExistsBefore) {
    throw "SM3_09C6_B4D_RMA_MISSING"
}


$casBefore = Get-PhysicalMetadata `
    -Path $casPath


$rmaBefore = Get-PhysicalMetadata `
    -Path $rmaPath


Add-Check `
    "CAS_SHA_EXPECTED_BEFORE" `
    ($casBefore.sha256 -eq $sourceSha) `
    $casBefore.sha256


# ============================================================
# 4. PREFLIGHT
# ============================================================

$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4D_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 5. RESTART WORKER
# ============================================================

Write-Host "`n== RESTART WORKER ==" -ForegroundColor Yellow


docker restart `
    $container


if ($LASTEXITCODE -ne 0) {
    throw "SM3_09C6_B4D_DOCKER_RESTART_FAILED"
}


# ============================================================
# 6. WAIT FOR EXACT RUNTIME
# ============================================================

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
            $candidate.version -eq "2.23.1"
        ) {

            $healthAfter = $candidate

            break
        }

    }
    catch {
    }


    Start-Sleep -Seconds 2
}


if ($null -eq $healthAfter) {
    throw "SM3_09C6_B4D_HEALTH_NOT_RECOVERED"
}


$runtimeShaAfter = Get-RuntimeSha


$containerIdAfter = (
    docker inspect `
        -f "{{.Id}}" `
        $container |
    Out-String
).Trim()


$startedAtAfter = (
    docker inspect `
        -f "{{.State.StartedAt}}" `
        $container |
    Out-String
).Trim()


$statusAfter = (
    docker inspect `
        -f "{{.State.Status}}" `
        $container |
    Out-String
).Trim()


Add-Check `
    "CONTAINER_RUNNING_AFTER" `
    ($statusAfter -eq "running") `
    $statusAfter


Add-Check `
    "CONTAINER_ID_PRESERVED_ON_RESTART" `
    ($containerIdAfter -eq $containerIdBefore)


Add-Check `
    "STARTED_AT_CHANGED" `
    ($startedAtAfter -ne $startedAtBefore) `
    "$startedAtBefore->$startedAtAfter"


Add-Check `
    "VERSION_AFTER_2_23_1" `
    ($healthAfter.version -eq "2.23.1") `
    $healthAfter.version


Add-Check `
    "RUNTIME_SHA_AFTER_EXPECTED" `
    ($runtimeShaAfter -eq $expectedWorkerSha) `
    $runtimeShaAfter


Add-Check `
    "RUNTIME_SHA_UNCHANGED" `
    ($runtimeShaAfter -eq $runtimeShaBefore)


# ============================================================
# 7. LOGICAL STATE AFTER RESTART
# ============================================================

$itemAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


$priorityAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
    -Method GET `
    -TimeoutSec 30


$latestAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decision/latest" `
    -Method GET `
    -TimeoutSec 30


$metricsAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/metric-snapshots" `
    -Method GET `
    -TimeoutSec 30


$featuresAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/features" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityAfter = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$videoAfter = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


$priorityIdsAfter = @(
    $priorityAfter.priority_decisions |
    ForEach-Object {
        $_.priority_decision_id
    }
)


$metricIdsAfter = @(
    $metricsAfter.snapshots |
    ForEach-Object {
        $_.snapshot_id
    }
)


Add-Check `
    "ITEM_ACTIVE_AFTER" `
    ($itemAfter.effective_state -eq "ACTIVE") `
    ([string]$itemAfter.effective_state)


Add-Check `
    "ITEM_PRIORITY_COUNT_THREE_AFTER" `
    ($priorityAfter.count -eq 3) `
    ([string]$priorityAfter.count)


Add-Check `
    "GLOBAL_PRIORITY_COUNT_THREE_AFTER" `
    ($globalPriorityAfter -eq 3) `
    ([string]$globalPriorityAfter)


Add-Check `
    "METRIC_COUNT_TWO_AFTER" `
    ($metricsAfter.count -eq 2) `
    ([string]$metricsAfter.count)


Add-Check `
    "VIDEO_COUNT_ZERO_AFTER_RESTART" `
    ($videoAfter -eq 0) `
    ([string]$videoAfter)


Add-Check `
    "FEATURE_COUNT_ZERO_AFTER_RESTART" `
    ($featuresAfter.count -eq 0) `
    ([string]$featuresAfter.count)


foreach ($id in $rpdIds) {

    Add-Check `
        "RPD_PERSISTED_$id" `
        ($priorityIdsAfter -contains $id)
}


foreach ($id in $metricIds) {

    Add-Check `
        "METRIC_PERSISTED_$id" `
        ($metricIdsAfter -contains $id)
}


Add-Check `
    "LATEST_CURRENT_RPD_AFTER" `
    (
        $latestAfter.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "LATEST_DEFER_AFTER" `
    (
        $latestAfter.priority_decision.decision `
        -eq "DEFER"
    )


Add-Check `
    "LATEST_SEMANTIC_FALSE_AFTER" `
    (
        $latestAfter.priority_decision.semantic_analysis_allowed `
        -eq $false
    )


Add-Check `
    "LATEST_RECORD_HASH_PRESERVED" `
    (
        $latestAfter.priority_decision.priority_decision_sha256 `
        -eq
        $latestBefore.priority_decision.priority_decision_sha256
    )


Add-Check `
    "LATEST_EVIDENCE_FINGERPRINT_PRESERVED" `
    (
        $latestAfter.priority_decision.evidence_fingerprint `
        -eq
        $latestBefore.priority_decision.evidence_fingerprint
    )


# ============================================================
# 8. PHYSICAL STATE AFTER RESTART
# ============================================================

foreach ($id in $rpdIds) {

    $path = "$priorityRoot/$profileId/$itemId/$id.json"

    $after = Get-PhysicalMetadata `
        -Path $path

    $before = $rpdBefore[$id]

    Add-Check `
        "RPD_SHA_UNCHANGED_$id" `
        ($after.sha256 -eq $before.sha256)

    Add-Check `
        "RPD_MTIME_UNCHANGED_$id" `
        (
            [string]$after.mtime_ns `
            -eq [string]$before.mtime_ns
        )

    Add-Check `
        "RPD_INODE_UNCHANGED_$id" `
        (
            [string]$after.inode `
            -eq [string]$before.inode
        )
}


foreach ($id in $metricIds) {

    $after = Get-PhysicalMetadata `
        -Path $metricPaths[$id]

    $before = $metricBefore[$id]

    Add-Check `
        "METRIC_SHA_UNCHANGED_$id" `
        ($after.sha256 -eq $before.sha256)

    Add-Check `
        "METRIC_MTIME_UNCHANGED_$id" `
        (
            [string]$after.mtime_ns `
            -eq [string]$before.mtime_ns
        )
}


$casAfter = Get-PhysicalMetadata `
    -Path $casPath


$rmaAfter = Get-PhysicalMetadata `
    -Path $rmaPath


Add-Check `
    "CAS_SHA_UNCHANGED" `
    ($casAfter.sha256 -eq $casBefore.sha256)


Add-Check `
    "CAS_MTIME_UNCHANGED" `
    (
        [string]$casAfter.mtime_ns `
        -eq [string]$casBefore.mtime_ns
    )


Add-Check `
    "RMA_SHA_UNCHANGED" `
    ($rmaAfter.sha256 -eq $rmaBefore.sha256)


Add-Check `
    "RMA_MTIME_UNCHANGED" `
    (
        [string]$rmaAfter.mtime_ns `
        -eq [string]$rmaBefore.mtime_ns
    )


# ============================================================
# 9. GUARD MUST STILL WORK AFTER RESTART
# ============================================================

Write-Host "`n== VERIFY GUARD AFTER RESTART ==" -ForegroundColor Yellow


$videoRequest = @{

    reference_item_id = $itemId

    local_media_ref = $localMediaRef

    preference_signal = "UNKNOWN"

    notes = "SM3_09C6_B4D_POST_RESTART_GUARD_DO_NOT_USE_FOR_LEARNING"
}


$blocked = Invoke-JsonPostCapture `
    -Uri "$base/production/reference-corpus/video-analysis" `
    -RequestBody $videoRequest


Write-Host "VIDEO_HTTP_STATUS=$($blocked.StatusCode)"

Write-Host "VIDEO_HTTP_BODY=$($blocked.Body)"


Add-Check `
    "POST_RESTART_GUARD_HTTP_409" `
    ($blocked.StatusCode -eq 409) `
    ([string]$blocked.StatusCode)


Add-Check `
    "POST_RESTART_GUARD_SEMANTIC_NOT_ALLOWED_DEFER" `
    (
        $blocked.Body `
        -match 'REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER'
    ) `
    $blocked.Body


Add-Check `
    "POST_RESTART_GUARD_NOT_STALE" `
    (
        $blocked.Body `
        -notmatch 'REFERENCE_PRIORITY_DECISION_STALE'
    )


# ============================================================
# 10. FINAL NO-MUTATION CHECK
# ============================================================

$priorityFinal = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/priority-decisions" `
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


Add-Check `
    "FINAL_PRIORITY_COUNT_THREE" `
    (
        $priorityFinal.count -eq 3 `
        -and
        $globalPriorityFinal -eq 3
    )


Add-Check `
    "FINAL_METRIC_COUNT_TWO" `
    ($metricsFinal.count -eq 2)


Add-Check `
    "FINAL_VIDEO_COUNT_ZERO" `
    ($videoFinal -eq 0)


Add-Check `
    "FINAL_FEATURE_COUNT_ZERO" `
    ($featuresFinal.count -eq 0)


# ============================================================
# 11. SUMMARY
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


Write-Host "`n== B4D CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4D"

    WorkerVersionBefore = $healthBefore.version

    WorkerVersionAfter = $healthAfter.version

    RuntimeSHA256Before = $runtimeShaBefore

    RuntimeSHA256After = $runtimeShaAfter

    ContainerIdBefore = $containerIdBefore

    ContainerIdAfter = $containerIdAfter

    StartedAtBefore = $startedAtBefore

    StartedAtAfter = $startedAtAfter

    ReferenceItemId = $itemId

    CurrentPriorityDecisionId = $currentRpdId

    PriorityCountBefore = $globalPriorityBefore

    PriorityCountAfter = $globalPriorityFinal

    MetricCountBefore = $metricsBefore.count

    MetricCountAfter = $metricsFinal.count

    VideoCountBefore = $videoBefore

    VideoCountAfter = $videoFinal

    FeatureCountBefore = $featuresBefore.count

    FeatureCountAfter = $featuresFinal.count

    GuardHttpStatus = $blocked.StatusCode

    GuardResponseBody = $blocked.Body

    PersistenceAfterRestart = (
        ($globalPriorityFinal -eq 3) `
        -and
        ($metricsFinal.count -eq 2) `
        -and
        ($videoFinal -eq 0)
    )

    GuardRecoveredAfterRestart = (
        ($blocked.StatusCode -eq 409) `
        -and
        ($blocked.Body -match "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER")
    )

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B4D SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 12. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    rpd_ids = $rpdIds

    metric_snapshot_ids = $metricIds

    latest_priority_decision = (
        $latestAfter.priority_decision
    )

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
    ($readback.summary.WorkerVersionBefore -eq "2.23.1"),
    ($readback.summary.WorkerVersionAfter -eq "2.23.1"),
    ($readback.summary.RuntimeSHA256Before -eq $expectedWorkerSha),
    ($readback.summary.RuntimeSHA256After -eq $expectedWorkerSha),
    ($readback.summary.CurrentPriorityDecisionId -eq $currentRpdId),
    ($readback.summary.PriorityCountBefore -eq 3),
    ($readback.summary.PriorityCountAfter -eq 3),
    ($readback.summary.MetricCountBefore -eq 2),
    ($readback.summary.MetricCountAfter -eq 2),
    ($readback.summary.VideoCountBefore -eq 0),
    ($readback.summary.VideoCountAfter -eq 0),
    ($readback.summary.GuardHttpStatus -eq 409),
    ($readback.summary.GuardResponseBody -match "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:DEFER"),
    ($readback.summary.PersistenceAfterRestart -eq $true),
    ($readback.summary.GuardRecoveredAfterRestart -eq $true),
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
        "`nSM3_09C6_B4D_RESTART_PERSISTENCE_GUARD_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4D_RESTART_PERSISTENCE_GUARD_FAIL" `
    -ForegroundColor Red

exit 1

