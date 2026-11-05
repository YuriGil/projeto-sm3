# SM3 07F - verifies and downloads the preview for the CURRENT persisted revision.
# Fail-closed: derives revision/state_etag from the persisted workspace, then verifies
# the preview manifest and exact downloaded bytes. Does not mutate n8n or edit state.

[CmdletBinding()]
param(
    [string]$WorkerBaseUrl = 'http://localhost:8090',
    [string]$ProjectId = 'TATTOO_0002',
    [string]$ContentId = 'CARROSSEL_0004',
    [string]$EditSessionId = $env:SM3_07F_PREVIEW_V6_EDIT_SESSION_ID,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'SM3_PREVIEWS')
)

Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($EditSessionId)) {
    throw 'SM3_07F_PREVIEW_V6_EDIT_SESSION_ID_REQUIRED'
}
$ErrorActionPreference = 'Stop'

$base = $WorkerBaseUrl.TrimEnd('/')
$project = $ProjectId
$content = $ContentId
$session = $EditSessionId

function Assert-Same {
    param([string]$Code, $Actual, $Expected)
    if ([string]$Actual -cne [string]$Expected) {
        throw ("${Code}: actual='" + [string]$Actual + "' expected='" + [string]$Expected + "'")
    }
}

function Get-JsonErrorDetail {
    param($ErrorRecord)
    try {
        $response = $ErrorRecord.Exception.Response
        if ($null -eq $response) { return $null }
        $stream = $response.GetResponseStream()
        if ($null -eq $stream) { return $null }
        $reader = [System.IO.StreamReader]::new($stream)
        try {
            $raw = $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
        if (-not $raw) { return $null }
        try {
            return (($raw | ConvertFrom-Json).detail)
        } catch {
            return $raw
        }
    } catch {
        return $null
    }
}

function Assert-Workspace {
    param($Workspace, [int]$ExpectedRevision, [string]$ExpectedEtag)
    Assert-Same 'WORKSPACE_PROJECT' $Workspace.project_id $project
    Assert-Same 'WORKSPACE_CONTENT' $Workspace.content_id $content
    Assert-Same 'WORKSPACE_SESSION' $Workspace.edit_session_id $session
    Assert-Same 'WORKSPACE_REVISION' $Workspace.current_revision $ExpectedRevision
    Assert-Same 'WORKSPACE_STATUS' $Workspace.status 'SAVED'
    Assert-Same 'WORKSPACE_ETAG' $Workspace.state_etag $ExpectedEtag

    if ($Workspace.ok -ne $true -or $Workspace.read_only -ne $false) {
        throw 'SM3_07F_WORKSPACE_CONTRACT_INVALID'
    }
    if ($Workspace.state_etag -cnotmatch '^[a-f0-9]{64}$') {
        throw 'SM3_07F_WORKSPACE_ETAG_INVALID'
    }
}

function Assert-Preview {
    param($Preview, $Workspace, [int]$ExpectedRevision, [string]$ExpectedPreviewPath)

    Assert-Same 'PREVIEW_CONTRACT' $Preview.contract_version 'SM3_EDIT_PREVIEW_V3'
    Assert-Same 'PREVIEW_RENDERER' $Preview.renderer_version '2.8.0'
    Assert-Same 'PREVIEW_PROJECT' $Preview.project_id $project
    Assert-Same 'PREVIEW_CONTENT' $Preview.content_id $content
    Assert-Same 'PREVIEW_SESSION' $Preview.edit_session_id $session
    Assert-Same 'PREVIEW_REVISION' $Preview.revision $ExpectedRevision
    Assert-Same 'PREVIEW_ETAG' $Preview.state_etag $Workspace.state_etag
    Assert-Same 'PREVIEW_ASSET_URL' $Preview.asset_url ($ExpectedPreviewPath + '/asset')

    if ($Preview.ok -ne $true -or
        $Preview.final_render -ne $false -or
        $Preview.publish_from_preview_forbidden -ne $true -or
        $Preview.preview_grade -ne 'LOW_RES_REVIEW') {
        throw 'SM3_07F_PREVIEW_CONTRACT_INVALID'
    }

    if ($Preview.preview_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
        $Preview.cover_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
        [long]$Preview.preview_bytes -le 100 -or
        -not $Preview.source_hashes) {
        throw 'SM3_07F_MANIFEST_INCOMPLETE'
    }


    Assert-Same 'IDENTITY_BINDING_CONTRACT' $Preview.identity_asset_binding_contract 'SM3_IDENTITY_ASSET_BINDING_V1'
    $identity = $Workspace.recipe.identity_application
    $expectedRoles = @()
    foreach ($role in @('logo','stamp','texture','frame')) {
        if ($identity.$role -eq $true) { $expectedRoles += $role }
    }
    $expectedRoles = @($expectedRoles | Sort-Object)
    $hashRoles = @()
    if ($null -ne $Preview.identity_asset_hashes) {
        $hashRoles = @($Preview.identity_asset_hashes.PSObject.Properties.Name | Sort-Object)
    }
    $assetRoles = @($Preview.identity_assets | ForEach-Object { [string]$_.role } | Sort-Object)
    if (($expectedRoles -join ',') -cne ($hashRoles -join ',') -or
        ($expectedRoles -join ',') -cne ($assetRoles -join ',')) {
        throw ("SM3_07F_IDENTITY_ROLE_SET_MISMATCH: expected=" + ($expectedRoles -join ',') +
               " hashes=" + ($hashRoles -join ',') + " assets=" + ($assetRoles -join ','))
    }
    foreach ($role in $expectedRoles) {
        $hash = [string]$Preview.identity_asset_hashes.$role
        if ($hash -cnotmatch '^[a-f0-9]{64}$') { throw "SM3_07F_IDENTITY_HASH_INVALID:$role" }
        if (-not @($Preview.rendered_operations) -or
            -not (@($Preview.rendered_operations) -contains ('identity_' + $role))) {
            throw "SM3_07F_IDENTITY_OPERATION_MISSING:$role"
        }
    }
}

$health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 20
Assert-Same 'WORKER_VERSION' $health.version '2.10.0'
Assert-Same 'WORKER_RENDERER_VERSION' $health.edit_preview_renderer_version '2.8.0'
Assert-Same 'WORKER_VISUAL_FEEDBACK' $health.visual_feedback_contract 'SM3_VISUAL_FEEDBACK_V2'
Assert-Same 'WORKER_DIRECTION_PROFILE' $health.direction_profile_contract 'SM3_DIRECTION_PROFILE_V1'
Assert-Same 'WORKER_PROFILE_BINDING' $health.profile_binding_contract 'SM3_PROFILE_BINDING_V1'
Assert-Same 'WORKER_LEARNING_ROUTER' $health.learning_router_contract 'SM3_LEARNING_ROUTER_V1'
Assert-Same 'WORKER_PREVIEW_CONTRACT' $health.edit_preview_contract 'SM3_EDIT_PREVIEW_V3'
Assert-Same 'WORKER_IDENTITY_BINDING_CONTRACT' $health.identity_asset_binding_contract 'SM3_IDENTITY_ASSET_BINDING_V1'
if ($health.edit_preview_identity_assets -ne $true) { throw 'SM3_07F_IDENTITY_RENDERER_NOT_ENABLED' }

$workspaceUrl = "$base/production/editor-workspace/$project/$content/$session"
$workspace = Invoke-RestMethod -Uri $workspaceUrl -TimeoutSec 30

if ($workspace.ok -ne $true -or $workspace.status -ne 'SAVED') {
    throw 'SM3_07F_WORKSPACE_NOT_SAVED'
}
if ([int]$workspace.current_revision -lt 2) {
    throw 'SM3_07F_NO_EDIT_REVISION_TO_VERIFY'
}
if ([string]$workspace.state_etag -cnotmatch '^[a-f0-9]{64}$') {
    throw 'SM3_07F_WORKSPACE_ETAG_INVALID'
}

$revision = [int]$workspace.current_revision
$initialEtag = [string]$workspace.state_etag
Assert-Workspace $workspace $revision $initialEtag

$previewPath = "/production/edit-session/preview/$project/$content/$session/$revision"
$previewUrl = $base + $previewPath
$editorUrl = "$base/production/editor/$project/$content/$session"

try {
    $preview = Invoke-RestMethod -Uri $previewUrl -TimeoutSec 30
}
catch {
    $detail = Get-JsonErrorDetail $_
    if ($detail -eq 'EDIT_PREVIEW_NOT_CURRENT_REVISION' -or
        $detail -eq 'EDIT_PREVIEW_NOT_FOUND' -or
        $detail -eq 'EDIT_PREVIEW_MANIFEST_NOT_FOUND' -or
        $detail -eq 'EDIT_PREVIEW_STATE_ETAG_MISMATCH') {
        throw ("SM3_07F_CURRENT_PREVIEW_NOT_READY: current revision=$revision state_etag=$initialEtag. " +
               "Execute 'PROJETO SM3 — 07F — EDIT PREVIEWS — v3 VERIFIED IDENTITY RENDER' once, then rerun this verifier. Worker detail=$detail")
    }
    throw
}

Assert-Preview $preview $workspace $revision $previewPath

$OutputDir = Join-Path $OutputRoot ("EDIT_REV" + $revision)
$null = New-Item -ItemType Directory -Path $OutputDir -Force

$destination = Join-Path $OutputDir ("{0}_REV{1}_VERIFICADO.mp4" -f $content, $revision)
$temp = Join-Path $OutputDir ('.sm3_' + [guid]::NewGuid().ToString('N') + '.partial')
$reusedLocal = $false

try {
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $actualHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        $actualBytes = (Get-Item -LiteralPath $destination).Length
        if ($actualHash -cne $preview.preview_sha256 -or
            $actualBytes -ne [long]$preview.preview_bytes) {
            throw 'SM3_07F_LOCAL_FILE_CONFLICT: existing destination differs from verified manifest'
        }
        $reusedLocal = $true
    }
    else {
        Invoke-WebRequest -Uri ($base + $preview.asset_url) -OutFile $temp -UseBasicParsing -TimeoutSec 180 | Out-Null
        $actualHash = (Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant()
        $actualBytes = (Get-Item -LiteralPath $temp).Length
        Assert-Same 'SM3_07F_DOWNLOADED_SHA256' $actualHash $preview.preview_sha256
        Assert-Same 'SM3_07F_DOWNLOADED_BYTES' $actualBytes $preview.preview_bytes
    }

    # A save occurring during download must invalidate this result before promotion.
    $again = Invoke-RestMethod -Uri $workspaceUrl -TimeoutSec 30
    Assert-Workspace $again $revision $initialEtag

    try {
        $manifestAgain = Invoke-RestMethod -Uri $previewUrl -TimeoutSec 30
    }
    catch {
        $detail = Get-JsonErrorDetail $_
        throw ("SM3_07F_PREVIEW_INVALIDATED_DURING_DOWNLOAD: " + [string]$detail)
    }

    Assert-Preview $manifestAgain $again $revision $previewPath
    Assert-Same 'SM3_07F_ETAG_CHANGED_DURING_DOWNLOAD' $again.state_etag $workspace.state_etag
    Assert-Same 'SM3_07F_PREVIEW_CHANGED_DURING_DOWNLOAD' $manifestAgain.preview_sha256 $preview.preview_sha256

    if (-not $reusedLocal) {
        Move-Item -LiteralPath $temp -Destination $destination
    }
}
finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Force
    }
}

Write-Output 'SM3_07F_V6_CURRENT_PREVIEW_PROFILE_COMPAT_VERIFIED'
[pscustomobject]@{
    project_id = $project
    content_id = $content
    edit_session_id = $session
    revision = $revision
    state_etag = $initialEtag
    preview_sha256 = $preview.preview_sha256
    preview_bytes = [long]$preview.preview_bytes
    identity_roles = (@($preview.identity_assets | ForEach-Object { $_.role }) -join ',')
    direction_profile = [string]$workspace.direction_profile.profile_id
    reused_local = $reusedLocal
    file = (Resolve-Path -LiteralPath $destination).Path
    editor_url = $editorUrl
}
