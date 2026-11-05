param(
    [string]$Base = "http://127.0.0.1:8090",

    [string]$Container = "deployment-media-worker-1",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C6\SM3_09C6_B3B_OPENAPI_RUNTIME_CONTRACT.json"
)


$ErrorActionPreference = "Stop"


$expectedVersion = "2.23.0"

$expectedSha = "227ecf9eefcdb020f1da6917a30d32717d8f10d7addc2d615d044b4ef7ce39d7"


# ============================================================
# HELPERS
# ============================================================

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


function Get-OpenApiPath {

    param(
        [object]$OpenApi,
        [string]$Path
    )

    $property = $OpenApi.paths.PSObject.Properties |
        Where-Object {
            $_.Name -eq $Path
        } |
        Select-Object -First 1

    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}


# ============================================================
# 1. RUNTIME PREFLIGHT
# ============================================================

$health = Invoke-RestMethod `
    -Uri "$Base/health" `
    -Method GET `
    -TimeoutSec 30


$containerStatus = (
    docker inspect `
        -f "{{.State.Status}}" `
        $Container |
    Out-String
).Trim()


$runtimeShaLine = (
    docker exec `
        $Container `
        sha256sum `
        /app/worker_service.py |
    Out-String
).Trim()


$runtimeSha = (
    ($runtimeShaLine -split "\s+")[0]
).Trim().ToLower()


Add-Check `
    "RUNTIME_HEALTH_OK" `
    ($health.ok -eq $true)


Add-Check `
    "RUNTIME_VERSION_2_23" `
    ($health.version -eq $expectedVersion) `
    $health.version


Add-Check `
    "CONTAINER_RUNNING" `
    ($containerStatus -eq "running") `
    $containerStatus


Add-Check `
    "RUNTIME_SHA_EXPECTED" `
    ($runtimeSha -eq $expectedSha) `
    $runtimeSha


Add-Check `
    "PRIORITY_GATE_HEALTH_EXPORTED" `
    ($health.reference_priority_gate -eq $true)


Add-Check `
    "PRIORITY_CONTRACT_HEALTH_EXPORTED" `
    (
        $health.reference_priority_decision_contract `
        -eq "SM3_REFERENCE_PRIORITY_DECISION_V1"
    )


Add-Check `
    "PRIORITY_ENGINE_HEALTH_EXPORTED" `
    (
        $health.reference_priority_engine_version `
        -eq "SM3_REFERENCE_PRIORITY_ENGINE_V1"
    )


Add-Check `
    "PRIORITY_SEMANTIC_FAIL_CLOSED" `
    (
        $health.reference_priority_semantic_fail_closed `
        -eq $true
    )


# ============================================================
# 2. PRIORITY STATE MUST REMAIN UNTOUCHED
# ============================================================

$priorityCountBeforeText = (
    docker exec `
        $Container `
        sh -lc `
        "find /data/media/production_state/reference_priority_decisions -type f -name 'RPD_*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim()


$priorityCountBefore = [int]$priorityCountBeforeText


# ============================================================
# 3. OPENAPI FROM LIVE FASTAPI
# ============================================================

$openapi = Invoke-RestMethod `
    -Uri "$Base/openapi.json" `
    -Method GET `
    -TimeoutSec 30


Add-Check `
    "OPENAPI_AVAILABLE" `
    ($null -ne $openapi)


Add-Check `
    "OPENAPI_APP_VERSION_2_23" `
    ($openapi.info.version -eq "2.23.0") `
    $openapi.info.version


# ============================================================
# 4. ROUTES
# ============================================================

$postRoute = "/production/reference-corpus/priority-decision"

$listRoute = "/production/reference-corpus/item/{item_id}/priority-decisions"

$latestRoute = "/production/reference-corpus/item/{item_id}/priority-decision/latest"

$videoRoute = "/production/reference-corpus/video-analysis"

$mechanicalRoute = "/production/reference-corpus/mechanical-analysis"


$postPath = Get-OpenApiPath `
    -OpenApi $openapi `
    -Path $postRoute


$listPath = Get-OpenApiPath `
    -OpenApi $openapi `
    -Path $listRoute


$latestPath = Get-OpenApiPath `
    -OpenApi $openapi `
    -Path $latestRoute


$videoPath = Get-OpenApiPath `
    -OpenApi $openapi `
    -Path $videoRoute


$mechanicalPath = Get-OpenApiPath `
    -OpenApi $openapi `
    -Path $mechanicalRoute


Add-Check `
    "PRIORITY_POST_PATH_REGISTERED" `
    ($null -ne $postPath)


Add-Check `
    "PRIORITY_POST_METHOD_REGISTERED" `
    (
        ($null -ne $postPath) `
        -and
        ($null -ne $postPath.post)
    )


Add-Check `
    "PRIORITY_LIST_PATH_REGISTERED" `
    ($null -ne $listPath)


Add-Check `
    "PRIORITY_LIST_GET_REGISTERED" `
    (
        ($null -ne $listPath) `
        -and
        ($null -ne $listPath.get)
    )


Add-Check `
    "PRIORITY_LATEST_PATH_REGISTERED" `
    ($null -ne $latestPath)


Add-Check `
    "PRIORITY_LATEST_GET_REGISTERED" `
    (
        ($null -ne $latestPath) `
        -and
        ($null -ne $latestPath.get)
    )


Add-Check `
    "VIDEO_ANALYSIS_ROUTE_PRESERVED" `
    (
        ($null -ne $videoPath) `
        -and
        ($null -ne $videoPath.post)
    )


Add-Check `
    "MECHANICAL_ROUTE_PRESERVED" `
    (
        ($null -ne $mechanicalPath) `
        -and
        ($null -ne $mechanicalPath.post)
    )


# ============================================================
# 5. OPERATION IDS MUST MATCH IMPLEMENTATION
# ============================================================

$postOperationId = ""

$listOperationId = ""

$latestOperationId = ""


if ($null -ne $postPath) {
    $postOperationId = [string]$postPath.post.operationId
}


if ($null -ne $listPath) {
    $listOperationId = [string]$listPath.get.operationId
}


if ($null -ne $latestPath) {
    $latestOperationId = [string]$latestPath.get.operationId
}


Add-Check `
    "POST_OPERATION_ID_MATCHES_FUNCTION" `
    (
        $postOperationId `
        -like "production_reference_priority_decision_*"
    ) `
    $postOperationId


Add-Check `
    "LIST_OPERATION_ID_MATCHES_FUNCTION" `
    (
        $listOperationId `
        -like "production_reference_priority_decisions_*"
    ) `
    $listOperationId


Add-Check `
    "LATEST_OPERATION_ID_MATCHES_FUNCTION" `
    (
        $latestOperationId `
        -like "production_reference_priority_decision_latest_*"
    ) `
    $latestOperationId


# ============================================================
# 6. REQUEST SCHEMA
# ============================================================

$schema = $openapi.components.schemas.ReferencePriorityDecisionRequest


Add-Check `
    "PRIORITY_REQUEST_SCHEMA_EXISTS" `
    ($null -ne $schema)


$schemaPropertyNames = @()

$requiredFields = @()


if ($null -ne $schema) {

    $schemaPropertyNames = @(
        $schema.properties.PSObject.Properties |
        ForEach-Object {
            $_.Name
        }
    )

    $requiredFields = @(
        $schema.required
    )
}


foreach ($field in @(
    "reference_item_id",
    "acquisition_id",
    "mechanical_analysis_id",
    "use_latest_acquisition"
)) {

    Add-Check `
        "SCHEMA_FIELD_$($field.ToUpper())" `
        ($schemaPropertyNames -contains $field)
}


Add-Check `
    "REFERENCE_ITEM_ID_REQUIRED" `
    ($requiredFields -contains "reference_item_id")


Add-Check `
    "ACQUISITION_ID_OPTIONAL" `
    (-not ($requiredFields -contains "acquisition_id"))


Add-Check `
    "MECHANICAL_ANALYSIS_ID_OPTIONAL" `
    (-not ($requiredFields -contains "mechanical_analysis_id"))


Add-Check `
    "USE_LATEST_ACQUISITION_OPTIONAL" `
    (-not ($requiredFields -contains "use_latest_acquisition"))


$latestDefault = $null


if (
    $null -ne $schema `
    -and
    $null -ne $schema.properties.use_latest_acquisition
) {

    $latestDefault = (
        $schema.properties.use_latest_acquisition.default
    )
}


Add-Check `
    "USE_LATEST_ACQUISITION_DEFAULT_TRUE" `
    ($latestDefault -eq $true) `
    ([string]$latestDefault)


# ============================================================
# 7. POST REQUEST BODY MUST REFERENCE THE CORRECT SCHEMA
# ============================================================

$requestSchemaRef = ""


if (
    $null -ne $postPath `
    -and
    $null -ne $postPath.post `
    -and
    $null -ne $postPath.post.requestBody
) {

    $jsonContent = (
        $postPath.post.requestBody.content.PSObject.Properties |
        Where-Object {
            $_.Name -eq "application/json"
        } |
        Select-Object -First 1
    )


    if ($null -ne $jsonContent) {

        $requestSchemaRef = [string](
            $jsonContent.Value.schema.'$ref'
        )
    }
}


Add-Check `
    "POST_REQUEST_SCHEMA_REF_CORRECT" `
    (
        $requestSchemaRef `
        -eq "#/components/schemas/ReferencePriorityDecisionRequest"
    ) `
    $requestSchemaRef


# ============================================================
# 8. STARTUP STORAGE ROOT EXISTS
# ============================================================

$priorityRootExistsText = (
    docker exec `
        $Container `
        sh -lc `
        "if [ -d /data/media/production_state/reference_priority_decisions ]; then echo true; else echo false; fi" |
    Out-String
).Trim()


Add-Check `
    "PRIORITY_STATE_ROOT_EXISTS" `
    ($priorityRootExistsText -eq "true") `
    $priorityRootExistsText


# ============================================================
# 9. PROVE THIS TEST DID NOT CREATE A PRIORITY DECISION
# ============================================================

$priorityCountAfterText = (
    docker exec `
        $Container `
        sh -lc `
        "find /data/media/production_state/reference_priority_decisions -type f -name 'RPD_*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim()


$priorityCountAfter = [int]$priorityCountAfterText


Add-Check `
    "PRIORITY_DECISION_COUNT_UNCHANGED" `
    (
        $priorityCountAfter `
        -eq $priorityCountBefore
    ) `
    "$priorityCountBefore->$priorityCountAfter"


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
$failCount  = [int]$failed.Count
$passCount  = [int]($checkCount - $failCount)


$allPassed = (
    $failCount -eq 0
)


Write-Host "`n== B3B CHECKS ==" -ForegroundColor Yellow


$checks |
    Format-Table `
        Check,
        Pass,
        Detail `
        -AutoSize


$summary = [PSCustomObject]@{

    Phase = "09C6-B3B"

    WorkerVersion = $health.version

    RuntimeSHA256 = $runtimeSha

    CheckCount = $checkCount

    PassCount = $passCount

    FailCount = $failCount

    PriorityPostRoute = $postRoute

    PriorityListRoute = $listRoute

    PriorityLatestRoute = $latestRoute

    RequestSchema = "ReferencePriorityDecisionRequest"

    PriorityDecisionCountBefore = $priorityCountBefore

    PriorityDecisionCountAfter = $priorityCountAfter

    CorpusMutated = (
        $priorityCountBefore `
        -ne $priorityCountAfter
    )

    VisionCalled = $false

    FailedChecks = (
        $failed.Check -join ","
    )

    AllPassed = $allPassed
}


Write-Host "`n== B3B SUMMARY ==" -ForegroundColor Yellow


$summary |
    Format-List


# ============================================================
# 11. PERSIST FULL EVIDENCE
# ============================================================

$report = [PSCustomObject]@{

    summary = $summary

    operation_ids = [PSCustomObject]@{
        priority_post = $postOperationId
        priority_list = $listOperationId
        priority_latest = $latestOperationId
    }

    request_schema = [PSCustomObject]@{
        properties = $schemaPropertyNames
        required = $requiredFields
        use_latest_acquisition_default = $latestDefault
        post_schema_ref = $requestSchemaRef
    }

    checks = $checks
}


$report |
    ConvertTo-Json `
        -Depth 20 |
    Set-Content `
        -LiteralPath $ReportFile `
        -Encoding UTF8


# ============================================================
# 12. READ-BACK
# ============================================================

$persisted = Get-Content `
    -LiteralPath $ReportFile `
    -Raw |
    ConvertFrom-Json


$reportValid = (
    ($persisted.summary.WorkerVersion -eq "2.23.0") `
    -and
    ($persisted.summary.RuntimeSHA256 -eq $expectedSha) `
    -and
    ($persisted.summary.FailCount -eq 0) `
    -and
    ($persisted.summary.CorpusMutated -eq $false) `
    -and
    ($persisted.summary.VisionCalled -eq $false) `
    -and
    ($persisted.summary.AllPassed -eq $true)
)


Write-Host "`nREPORT=$ReportFile" -ForegroundColor Cyan

Write-Host "REPORT_READBACK_VALID=$reportValid"


if (
    $allPassed `
    -and $reportValid
) {

    Write-Host `
        "`nSM3_09C6_B3B_OPENAPI_RUNTIME_CONTRACT_PASS" `
        -ForegroundColor Green

    exit 0
}


Write-Host `
    "`nSM3_09C6_B3B_OPENAPI_RUNTIME_CONTRACT_FAIL" `
    -ForegroundColor Red

exit 1
