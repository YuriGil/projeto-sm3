# SM3 08D - Diagnose readiness/state without mutating the project.
[CmdletBinding()]
param(
    [string]$WorkerBaseUrl = 'http://localhost:8090'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$base = $WorkerBaseUrl.TrimEnd('/')
$project = 'TATTOO_0002'
$content = 'CARROSSEL_0004'
$session = $env:SM3_08D_EDIT_SESSION_ID
if ([string]::IsNullOrWhiteSpace($session)) {
    throw 'SM3_08D_EDIT_SESSION_ID_REQUIRED'
}
$revision = 4
$etag = '22f05816c38651d2126f0f9519b6f11f8c5d7368fa93331b0ee73bd152683d09'

function Get-HttpJsonState {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Url
    )
    try {
        $r = Invoke-RestMethod -Uri $Url -TimeoutSec 30
        return [pscustomobject]@{
            name = $Name
            status = 'FOUND'
            detail = ''
            data = $r
        }
    }
    catch {
        $statusCode = $null
        $detail = $null
        try {
            $statusCode = [int]$_.Exception.Response.StatusCode
        } catch {}
        try {
            $resp = $_.Exception.Response
            if ($resp) {
                $stream = $resp.GetResponseStream()
                if ($stream) {
                    $reader = [IO.StreamReader]::new($stream)
                    try {
                        $raw = $reader.ReadToEnd()
                    } finally {
                        $reader.Dispose()
                    }
                    if ($raw) {
                        try { $detail = ($raw | ConvertFrom-Json).detail }
                        catch { $detail = $raw }
                    }
                }
            }
        } catch {}
        return [pscustomobject]@{
            name = $Name
            status = if ($statusCode) { "HTTP_$statusCode" } else { 'ERROR' }
            detail = [string]$detail
            data = $null
        }
    }
}

Write-Host '== SM3 08D / STATE DIAGNOSTIC =='
Write-Host 'Read-only: does not create REV5, render, or mutate Sheets.'
Write-Host ''

$health = Invoke-RestMethod "$base/health" -TimeoutSec 15
Write-Host ("worker_version             : " + [string]$health.version)
Write-Host ("geometry_preview_contract  : " + [string]$health.geometry_preview_contract)
Write-Host ("composition_plan_contract : " + [string]$health.composition_plan_contract)

$workspace = Invoke-RestMethod "$base/production/editor-workspace/$project/$content/$session" -TimeoutSec 20
Write-Host ("current_revision           : " + [string]$workspace.current_revision)
Write-Host ("state_etag                 : " + [string]$workspace.state_etag)

if ([int]$workspace.current_revision -ne $revision -or [string]$workspace.state_etag -cne $etag) {
    throw 'SM3_08D_DIAG_WORKSPACE_CHANGED'
}

$planState = Get-HttpJsonState -Name 'composition_plan' -Url "$base/production/composition-plan/$project/$content/$session/$revision"
$previewState = Get-HttpJsonState -Name 'geometry_preview' -Url "$base/production/geometry-aware-preview/$project/$content/$session/$revision"

Write-Host ''
Write-Host ("composition_plan : " + $planState.status + $(if($planState.detail){" / "+$planState.detail}else{''}))
Write-Host ("geometry_preview : " + $previewState.status + $(if($previewState.detail){" / "+$previewState.detail}else{''}))
Write-Host ''

if ($planState.status -eq 'FOUND' -and $previewState.status -eq 'FOUND') {
    Write-Output 'SM3_08D_STATE_READY_FOR_VERIFIER'
    [pscustomobject]@{
        composition_id = $planState.data.composition_id
        plan_sha256 = $planState.data.plan_sha256
        preview_sha256 = $previewState.data.preview_sha256
        preview_bytes = $previewState.data.preview_bytes
    }
    exit 0
}

if ($planState.detail -eq 'COMPOSITION_PLAN_NOT_FOUND' -and
    ($previewState.detail -eq 'GEOMETRY_PREVIEW_MANIFEST_NOT_FOUND' -or
     $previewState.detail -eq 'GEOMETRY_PREVIEW_NOT_FOUND' -or
     $previewState.status -like 'HTTP_404')) {
    Write-Output 'SM3_08D_STATE_NOT_RENDERED'
    Write-Host 'Action: execute the n8n workflow "PROJETO SM3 — 08D — GEOMETRY-AWARE COMPOSITION — v1" once.'
    Write-Host 'Do not create REV5 and do not run the verifier until the workflow reaches its final committed node.'
    exit 10
}

if ($planState.status -eq 'FOUND' -and $previewState.status -ne 'FOUND') {
    Write-Output 'SM3_08D_STATE_PLAN_EXISTS_PREVIEW_MISSING'
    Write-Host 'The planner persisted, but rendering/preview commit did not finish. Inspect the red n8n node at or after WORKER — RENDER SAVED REVISION.'
    exit 11
}

if ($planState.status -ne 'FOUND' -and $previewState.status -eq 'FOUND') {
    Write-Output 'SM3_08D_STATE_INCONSISTENT_PREVIEW_WITHOUT_PLAN'
    Write-Host 'This is not expected by the 2.12.0 contract. Stop and inspect worker storage before rerunning.'
    exit 12
}

Write-Output 'SM3_08D_STATE_UNCLASSIFIED'
exit 13
