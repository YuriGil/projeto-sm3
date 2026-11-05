param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B4E_TOMBSTONE_HISTORY_PRESERVATION.json"
)


$ErrorActionPreference = "Stop"


$base = "http://127.0.0.1:8090"

$container = "deployment-media-worker-1"

$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


$profileId = "RP_0a468e360f9ae70383b235f10e445233"

$itemId = "RI_e79180852f8a54244f2bca8a6adefe61"

$acquisitionId = "RM_60dcb91d058b58498e4af25b5d566f41"

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

$artifactId = "MA_$sourceSha"

$prefix = $sourceSha.Substring(0,2)

$localMediaRef = "reference_artifacts/$prefix/$sourceSha/source"

$casPath = "/data/media/$localMediaRef"


$itemPath = "/data/media/production_state/reference_items/$profileId/$itemId.json"

$priorityRoot = "/data/media/production_state/reference_priority_decisions"

$tombstoneRoot = "/data/media/production_state/reference_item_tombstones"

$videoRoot = "/data/media/production_state/reference_video_analyses"


$rmaPath = "/data/media/production_state/reference_mechanical_analyses/$prefix/$sourceSha/$rmaId.json"


$tombstoneReason = "SM3_09C6_PRIORITY_CANARY_TEST_COMPLETED"


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
        throw "SM3_09C6_B4E_COUNT_COMMAND_FAILED"
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
        throw "SM3_09C6_B4E_METADATA_FAILED:$Path"
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
        throw ("SM3_09C6_B4E_FILE_NOT_UNIQUE:{0}:{1}" -f $FileName,$count)
    }

    $path = (
        docker exec `
            $container `
            sh -lc `
            "find /data/media/production_state -type f -name '$FileName' -print -quit" |
        Out-String
    ).Trim()

    if ([string]::IsNullOrWhiteSpace($path)) {
        throw ("SM3_09C6_B4E_FILE_PATH_MISSING:{0}" -f $FileName)
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
# 1. RUNTIME PREFLIGHT
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
    "TOMBSTONE_CONTRACT_V1" `
    (
        $health.reference_item_tombstone_contract `
        -eq "SM3_REFERENCE_ITEM_TOMBSTONE_V1"
    )


Add-Check `
    "TOMBSTONE_ACTIVE_GATE" `
    ($health.reference_item_tombstone_active_gate -eq $true)


Add-Check `
    "TOMBSTONE_HISTORY_POLICY" `
    ($health.reference_item_tombstone_preserves_history -eq $true)


Add-Check `
    "TOMBSTONE_MEDIA_POLICY" `
    ($health.reference_item_tombstone_preserves_media_provenance -eq $true)


# ============================================================
# 2. EXACT ACTIVE BASELINE
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


$mediaBefore = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/reference-media/latest" `
    -Method GET `
    -TimeoutSec 30


$globalPriorityBefore = Get-Count `
    "find '$priorityRoot' -type f -name 'RPD_*.json' 2>/dev/null | wc -l"


$globalTombstonesBefore = Get-Count `
    "find '$tombstoneRoot' -type f -name 'RIT_*.json' 2>/dev/null | wc -l"


$videoBefore = Get-Count `
    "find '$videoRoot' -type f -name '*.json' 2>/dev/null | wc -l"


Add-Check `
    "ITEM_ACTIVE_BEFORE" `
    ($itemBefore.effective_state -eq "ACTIVE") `
    ([string]$itemBefore.effective_state)


Add-Check `
    "ITEM_HAS_NO_TOMBSTONE_BEFORE" `
    ($null -eq $itemBefore.tombstone)


Add-Check `
    "PRIORITY_COUNT_THREE_BEFORE" `
    (
        $priorityBefore.count -eq 3 `
        -and
        $globalPriorityBefore -eq 3
    )


Add-Check `
    "LATEST_RPD_EXPECTED_BEFORE" `
    (
        $latestBefore.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "METRIC_COUNT_TWO_BEFORE" `
    ($metricsBefore.count -eq 2)


Add-Check `
    "VIDEO_COUNT_ZERO_BEFORE" `
    ($videoBefore -eq 0)


Add-Check `
    "FEATURE_COUNT_ZERO_BEFORE" `
    ($featuresBefore.count -eq 0)


Add-Check `
    "ACQUISITION_ID_EXPECTED_BEFORE" `
    (
        $mediaBefore.acquisition.acquisition_id `
        -eq $acquisitionId
    )


Add-Check `
    "MEDIA_ARTIFACT_EXPECTED_BEFORE" `
    (
        $mediaBefore.acquisition.media_artifact_id `
        -eq $artifactId
    )


# ============================================================
# 3. PHYSICAL HISTORY BASELINE
# ============================================================

docker exec $container test -f $itemPath

$itemExists = ($LASTEXITCODE -eq 0)

Add-Check "ITEM_FILE_EXISTS_BEFORE" $itemExists $itemPath

if (-not $itemExists) {
    throw "SM3_09C6_B4E_ITEM_FILE_MISSING"
}


$itemPhysicalBefore = Get-PhysicalMetadata `
    -Path $itemPath


$rpdBefore = @{}

foreach ($id in $rpdIds) {

    $path = "$priorityRoot/$profileId/$itemId/$id.json"

    docker exec $container test -f $path

    $exists = ($LASTEXITCODE -eq 0)

    Add-Check `
        "RPD_FILE_EXISTS_BEFORE_$id" `
        $exists `
        $path

    if (-not $exists) {
        throw ("SM3_09C6_B4E_RPD_FILE_MISSING:{0}" -f $id)
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


docker exec $container test -f $casPath

$casExists = ($LASTEXITCODE -eq 0)

docker exec $container test -f $rmaPath

$rmaExists = ($LASTEXITCODE -eq 0)


Add-Check "CAS_EXISTS_BEFORE" $casExists $casPath

Add-Check "RMA_EXISTS_BEFORE" $rmaExists $rmaPath


if (-not $casExists) {
    throw "SM3_09C6_B4E_CAS_MISSING"
}


if (-not $rmaExists) {
    throw "SM3_09C6_B4E_RMA_MISSING"
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
# 4. PREFLIGHT GATE
# ============================================================

$preflightFailed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($preflightFailed.Count -ne 0) {

    $message = "SM3_09C6_B4E_PREFLIGHT_FAILED:" + ($preflightFailed.Check -join ",")

    throw $message
}


# ============================================================
# 5. CREATE TERMINAL TOMBSTONE
# ============================================================

Write-Host "`n== CREATE TERMINAL TOMBSTONE ==" -ForegroundColor Yellow


$tombBodyObject = @{

    reason = $tombstoneReason

    scope = "ACTIVE_CORPUS"

    source = "TEST_CLEANUP"
}


$tombBody = $tombBodyObject |
    ConvertTo-Json `
        -Depth 10


$tombFirst = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/tombstone" `
    -Method POST `
    -ContentType "application/json" `
    -Body $tombBody `
    -TimeoutSec 30


$tombstone = $tombFirst.tombstone

$tombstoneId = [string]$tombstone.tombstone_id


Write-Host "TOMBSTONE_ID=$tombstoneId"

Write-Host "TOMBSTONE_REUSED_FIRST=$($tombFirst.reused_existing)"


Add-Check `
    "TOMBSTONE_FIRST_NOT_REUSED" `
    ($tombFirst.reused_existing -eq $false)


Add-Check `
    "TOMBSTONE_ID_FORMAT" `
    ($tombstoneId -match '^RIT_[0-9a-f]{32}$') `
    $tombstoneId


Add-Check `
    "TOMBSTONE_CONTRACT" `
    (
        $tombstone.contract_version `
        -eq "SM3_REFERENCE_ITEM_TOMBSTONE_V1"
    )


Add-Check `
    "TOMBSTONE_ITEM_MATCH" `
    ($tombstone.reference_item_id -eq $itemId)


Add-Check `
    "TOMBSTONE_PROFILE_MATCH" `
    ($tombstone.reference_profile_id -eq $profileId)


Add-Check `
    "TOMBSTONE_SCOPE_ACTIVE_CORPUS" `
    ($tombstone.scope -eq "ACTIVE_CORPUS")


Add-Check `
    "TOMBSTONE_REASON_MATCH" `
    ($tombstone.reason -eq $tombstoneReason)


Add-Check `
    "TOMBSTONE_SOURCE_TEST_CLEANUP" `
    ($tombstone.source -eq "TEST_CLEANUP")


Add-Check `
    "TOMBSTONE_TERMINAL" `
    ($tombstone.terminal -eq $true)


Add-Check `
    "TOMBSTONE_BLOCKS_NEW_PROCESSING" `
    ($tombstone.blocks_new_processing -eq $true)


Add-Check `
    "TOMBSTONE_PRESERVES_HISTORY" `
    ($tombstone.preserves_history -eq $true)


Add-Check `
    "TOMBSTONE_PRESERVES_MEDIA_PROVENANCE" `
    ($tombstone.preserves_media_provenance -eq $true)


Add-Check `
    "TOMBSTONE_HASH_FORMAT" `
    (
        [string]$tombstone.tombstone_sha256 `
        -match '^[0-9a-f]{64}$'
    )


# ============================================================
# 6. TOMBSTONE PHYSICAL BASELINE
# ============================================================

$tombstonePath = "$tombstoneRoot/$profileId/$itemId/$tombstoneId.json"


docker exec $container test -f $tombstonePath

$tombstoneFileExists = ($LASTEXITCODE -eq 0)


Add-Check `
    "TOMBSTONE_FILE_EXISTS" `
    $tombstoneFileExists `
    $tombstonePath


if (-not $tombstoneFileExists) {
    throw "SM3_09C6_B4E_TOMBSTONE_FILE_MISSING"
}


$tombPhysicalFirst = Get-PhysicalMetadata `
    -Path $tombstonePath


$tombstoneHashFirst = [string]$tombstone.tombstone_sha256

$tombstoneCreatedAtFirst = [string]$tombstone.created_at


# ============================================================
# 7. EFFECTIVE STATE / LISTING POLICY
# ============================================================

$itemAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId" `
    -Method GET `
    -TimeoutSec 30


$activeList = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/profile/$profileId/items" `
    -Method GET `
    -TimeoutSec 30


$historicalList = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/profile/$profileId/items?include_tombstoned=true" `
    -Method GET `
    -TimeoutSec 30


$activeMatches = @(
    $activeList.items |
    Where-Object {
        $_.reference_item_id -eq $itemId
    }
)


$historicalMatches = @(
    $historicalList.items |
    Where-Object {
        $_.reference_item_id -eq $itemId
    }
)


Add-Check `
    "ITEM_STATE_TOMBSTONED" `
    ($itemAfter.effective_state -eq "TOMBSTONED") `
    ([string]$itemAfter.effective_state)


Add-Check `
    "ITEM_TOMBSTONE_ID_MATCH" `
    (
        $itemAfter.tombstone.tombstone_id `
        -eq $tombstoneId
    )


Add-Check `
    "ACTIVE_LIST_HIDES_CANARY" `
    ($activeMatches.Count -eq 0) `
    ([string]$activeMatches.Count)


Add-Check `
    "HISTORICAL_LIST_CONTAINS_CANARY" `
    ($historicalMatches.Count -eq 1) `
    ([string]$historicalMatches.Count)


Add-Check `
    "HISTORICAL_LIST_STATE_TOMBSTONED" `
    (
        $historicalMatches.Count -eq 1 `
        -and
        $historicalMatches[0].effective_state -eq "TOMBSTONED"
    )


# ============================================================
# 8. HISTORICAL READERS MUST REMAIN AVAILABLE
# ============================================================

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


$mediaAfter = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/reference-media/latest" `
    -Method GET `
    -TimeoutSec 30


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
    "HISTORY_PRIORITY_COUNT_THREE" `
    ($priorityAfter.count -eq 3)


foreach ($id in $rpdIds) {

    Add-Check `
        "HISTORY_RPD_PRESENT_$id" `
        ($priorityIdsAfter -contains $id)
}


Add-Check `
    "HISTORY_LATEST_RPD_PRESERVED" `
    (
        $latestAfter.priority_decision.priority_decision_id `
        -eq $currentRpdId
    )


Add-Check `
    "HISTORY_LATEST_RECORD_HASH_PRESERVED" `
    (
        $latestAfter.priority_decision.priority_decision_sha256 `
        -eq
        $latestBefore.priority_decision.priority_decision_sha256
    )


Add-Check `
    "HISTORY_METRIC_COUNT_TWO" `
    ($metricsAfter.count -eq 2)


foreach ($id in $metricIds) {

    Add-Check `
        "HISTORY_METRIC_PRESENT_$id" `
        ($metricIdsAfter -contains $id)
}


Add-Check `
    "HISTORY_FEATURE_COUNT_ZERO" `
    ($featuresAfter.count -eq 0)


Add-Check `
    "HISTORY_ACQUISITION_PRESERVED" `
    (
        $mediaAfter.acquisition.acquisition_id `
        -eq $acquisitionId
    )


Add-Check `
    "HISTORY_MEDIA_ARTIFACT_PRESERVED" `
    (
        $mediaAfter.acquisition.media_artifact_id `
        -eq $artifactId
    )


# ============================================================
# 9. NEW PROCESSING MUST FAIL CLOSED
# ============================================================

Write-Host "`n== VERIFY TOMBSTONE ACTIVE GATE ==" -ForegroundColor Yellow


$priorityBlocked = Invoke-JsonPostCapture `
    -Uri "$base/production/reference-corpus/priority-decision" `
    -RequestBody @{
        reference_item_id = $itemId
        acquisition_id = $acquisitionId
        mechanical_analysis_id = $rmaId
        use_latest_acquisition = $false
    }


$mechanicalBlocked = Invoke-JsonPostCapture `
    -Uri "$base/production/reference-corpus/mechanical-analysis" `
    -RequestBody @{
        reference_item_id = $itemId
        acquisition_id = $acquisitionId
        use_latest_acquisition = $false
    }


$videoBlocked = Invoke-JsonPostCapture `
    -Uri "$base/production/reference-corpus/video-analysis" `
    -RequestBody @{
        reference_item_id = $itemId
        local_media_ref = $localMediaRef
        preference_signal = "UNKNOWN"
        notes = "SM3_09C6_B4E_TOMBSTONED_BLOCK_TEST"
    }


Write-Host "PRIORITY_BLOCK_STATUS=$($priorityBlocked.StatusCode)"

Write-Host "PRIORITY_BLOCK_BODY=$($priorityBlocked.Body)"

Write-Host "MECHANICAL_BLOCK_STATUS=$($mechanicalBlocked.StatusCode)"

Write-Host "MECHANICAL_BLOCK_BODY=$($mechanicalBlocked.Body)"

Write-Host "VIDEO_BLOCK_STATUS=$($videoBlocked.StatusCode)"

Write-Host "VIDEO_BLOCK_BODY=$($videoBlocked.Body)"


$expectedBlockedText = "REFERENCE_ITEM_TOMBSTONED:$itemId"


Add-Check `
    "PRIORITY_BLOCKED_409" `
    ($priorityBlocked.StatusCode -eq 409)


Add-Check `
    "PRIORITY_BLOCKED_TOMBSTONED" `
    ($priorityBlocked.Body -match [regex]::Escape($expectedBlockedText))


Add-Check `
    "MECHANICAL_BLOCKED_409" `
    ($mechanicalBlocked.StatusCode -eq 409)


Add-Check `
    "MECHANICAL_BLOCKED_TOMBSTONED" `
    ($mechanicalBlocked.Body -match [regex]::Escape($expectedBlockedText))


Add-Check `
    "VIDEO_BLOCKED_409" `
    ($videoBlocked.StatusCode -eq 409)


Add-Check `
    "VIDEO_BLOCKED_TOMBSTONED" `
    ($videoBlocked.Body -match [regex]::Escape($expectedBlockedText))


# ============================================================
# 10. SECOND IDENTICAL TOMBSTONE MUST REUSE, NOT REWRITE
# ============================================================

Start-Sleep -Milliseconds 1250


$tombSecond = Invoke-RestMethod `
    -Uri "$base/production/reference-corpus/item/$itemId/tombstone" `
    -Method POST `
    -ContentType "application/json" `
    -Body $tombBody `
    -TimeoutSec 30


$tombPhysicalSecond = Get-PhysicalMetadata `
    -Path $tombstonePath


Write-Host "`nTOMBSTONE_REUSED_SECOND=$($tombSecond.reused_existing)"


Add-Check `
    "TOMBSTONE_SECOND_REUSED" `
    ($tombSecond.reused_existing -eq $true)


Add-Check `
    "TOMBSTONE_SECOND_ID_SAME" `
    (
        $tombSecond.tombstone.tombstone_id `
        -eq $tombstoneId
    )


Add-Check `
    "TOMBSTONE_SECOND_HASH_SAME" `
    (
        $tombSecond.tombstone.tombstone_sha256 `
        -eq $tombstoneHashFirst
    )


Add-Check `
    "TOMBSTONE_SECOND_CREATED_AT_SAME" `
    (
        $tombSecond.tombstone.created_at `
        -eq $tombstoneCreatedAtFirst
    )


Add-Check `
    "TOMBSTONE_FILE_SHA_UNCHANGED_ON_REUSE" `
    (
        $tombPhysicalSecond.sha256 `
        -eq $tombPhysicalFirst.sha256
    )


Add-Check `
    "TOMBSTONE_FILE_MTIME_UNCHANGED_ON_REUSE" `
    (
        [string]$tombPhysicalSecond.mtime_ns `
        -eq [string]$tombPhysicalFirst.mtime_ns
    )


Add-Check `
    "TOMBSTONE_FILE_INODE_UNCHANGED_ON_REUSE" `
    (
        [string]$tombPhysicalSecond.inode `
        -eq [string]$tombPhysicalFirst.inode
    )


# ============================================================
# 11. PHYSICAL HISTORY MUST REMAIN BIT-FOR-BIT UNCHANGED
# ============================================================

$itemPhysicalAfter = Get-PhysicalMetadata `
    -Path $itemPath


Add-Check `
    "ITEM_FILE_SHA_UNCHANGED" `
    ($itemPhysicalAfter.sha256 -eq $itemPhysicalBefore.sha256)


Add-Check `
    "ITEM_FILE_MTIME_UNCHANGED" `
    (
        [string]$itemPhysicalAfter.mtime_ns `
        -eq [string]$itemPhysicalBefore.mtime_ns
    )


Add-Check `
    "ITEM_FILE_INODE_UNCHANGED" `
    (
        [string]$itemPhysicalAfter.inode `
        -eq [string]$itemPhysicalBefore.inode
    )


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

    Add-Check `
        "METRIC_INODE_UNCHANGED_$id" `
        (
            [string]$after.inode `
            -eq [string]$before.inode
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
    "CAS_INODE_UNCHANGED" `
    (
        [string]$casAfter.inode `
        -eq [string]$casBefore.inode
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


Add-Check `
    "RMA_INODE_UNCHANGED" `
    (
        [string]$rmaAfter.inode `
        -eq [string]$rmaBefore.inode
    )


# ============================================================
# 12. FINAL COUNTS
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


$globalTombstonesFinal = Get-Count `
    "find '$tombstoneRoot' -type f -name 'RIT_*.json' 2>/dev/null | wc -l"


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


Add-Check `
    "EXACTLY_ONE_NEW_TOMBSTONE" `
    (
        $globalTombstonesFinal `
        -eq ($globalTombstonesBefore + 1)
    ) `
    "$globalTombstonesBefore->$globalTombstonesFinal"


# ============================================================
# 13. SUMMARY
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


Write-Host "`n== B4E CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B4E"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    ReferenceItemId = $itemId

    EffectiveState = $itemAfter.effective_state

    TombstoneId = $tombstoneId

    TombstoneContract = $tombstone.contract_version

    TombstoneTerminal = $tombstone.terminal

    TombstoneBlocksNewProcessing = $tombstone.blocks_new_processing

    TombstonePreservesHistory = $tombstone.preserves_history

    TombstonePreservesMediaProvenance = $tombstone.preserves_media_provenance

    TombstoneSecondCallReused = $tombSecond.reused_existing

    PriorityCount = $globalPriorityFinal

    MetricCount = $metricsFinal.count

    VideoCount = $videoFinal

    FeatureCount = $featuresFinal.count

    TombstoneCountBefore = $globalTombstonesBefore

    TombstoneCountAfter = $globalTombstonesFinal

    PriorityBlockedStatus = $priorityBlocked.StatusCode

    MechanicalBlockedStatus = $mechanicalBlocked.StatusCode

    VideoBlockedStatus = $videoBlocked.StatusCode

    HistoryReadersPreserved = (
        ($priorityFinal.count -eq 3) `
        -and
        ($metricsFinal.count -eq 2) `
        -and
        ($mediaAfter.acquisition.acquisition_id -eq $acquisitionId)
    )

    PhysicalHistoryPreserved = (
        ($itemPhysicalAfter.sha256 -eq $itemPhysicalBefore.sha256) `
        -and
        ($casAfter.sha256 -eq $casBefore.sha256) `
        -and
        ($rmaAfter.sha256 -eq $rmaBefore.sha256)
    )

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B4E SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 14. REPORT
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    tombstone_first = $tombFirst

    tombstone_second = $tombSecond

    priority_block_response = $priorityBlocked

    mechanical_block_response = $mechanicalBlocked

    video_block_response = $videoBlocked

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
    ($readback.summary.ReferenceItemId -eq $itemId),
    ($readback.summary.EffectiveState -eq "TOMBSTONED"),
    ($readback.summary.TombstoneContract -eq "SM3_REFERENCE_ITEM_TOMBSTONE_V1"),
    ($readback.summary.TombstoneTerminal -eq $true),
    ($readback.summary.TombstoneBlocksNewProcessing -eq $true),
    ($readback.summary.TombstonePreservesHistory -eq $true),
    ($readback.summary.TombstonePreservesMediaProvenance -eq $true),
    ($readback.summary.TombstoneSecondCallReused -eq $true),
    ($readback.summary.PriorityCount -eq 3),
    ($readback.summary.MetricCount -eq 2),
    ($readback.summary.VideoCount -eq 0),
    ($readback.summary.FeatureCount -eq 0),
    ($readback.summary.PriorityBlockedStatus -eq 409),
    ($readback.summary.MechanicalBlockedStatus -eq 409),
    ($readback.summary.VideoBlockedStatus -eq 409),
    ($readback.summary.HistoryReadersPreserved -eq $true),
    ($readback.summary.PhysicalHistoryPreserved -eq $true),
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
        "`nSM3_09C6_B4E_TOMBSTONE_HISTORY_PRESERVATION_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B4E_TOMBSTONE_HISTORY_PRESERVATION_FAIL" `
    -ForegroundColor Red

exit 1
