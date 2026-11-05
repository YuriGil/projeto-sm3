[CmdletBinding()]
param(
    [string]$WorkerBaseUrl = "http://localhost:8090"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)][string]$Code,
        [AllowNull()]$Actual,
        [AllowNull()]$Expected
    )
    if ([string]$Actual -ne [string]$Expected) {
        throw "${Code}: actual='$Actual' expected='$Expected'"
    }
}

$health = Invoke-RestMethod -Uri "$WorkerBaseUrl/health" -TimeoutSec 10
Assert-Equal -Code "WORKER_VERSION_MISMATCH" -Actual $health.version -Expected "2.5.0"
Assert-Equal -Code "WORKSPACE_CONTRACT_MISMATCH" -Actual $health.editor_workspace_contract -Expected "SM3_EDITOR_WORKSPACE_V1"
Assert-Equal -Code "SAVE_CONTRACT_MISMATCH" -Actual $health.edit_session_save_contract -Expected "SM3_EDIT_SAVE_V1"

$sessions = @(
foreach ($requiredSessionVariable in @('SM3_EDIT_SESSION_CARROSSEL_0004', 'SM3_EDIT_SESSION_REEL_0006')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($requiredSessionVariable))) {
        throw "Required environment variable is not set: $requiredSessionVariable"
    }
}

    @{
        ProjectId = "TATTOO_0002"
        ContentId = "CARROSSEL_0004"
        EditSessionId = $env:SM3_EDIT_SESSION_CARROSSEL_0004
    },
    @{
        ProjectId = "TATTOO_0002"
        ContentId = "REEL_0006"
        EditSessionId = $env:SM3_EDIT_SESSION_REEL_0006
    }
)

$verified = @()
foreach ($session in $sessions) {
    $p = [uri]::EscapeDataString($session.ProjectId)
    $c = [uri]::EscapeDataString($session.ContentId)
    $s = [uri]::EscapeDataString($session.EditSessionId)
    $workspaceUrl = "$WorkerBaseUrl/production/editor-workspace/$p/$c/$s"
    $editorUrl = "$WorkerBaseUrl/production/editor/$p/$c/$s"
    $assetUrl = "$workspaceUrl/base-preview"

    $workspace = Invoke-RestMethod -Uri $workspaceUrl -TimeoutSec 30
    Assert-Equal -Code "WORKSPACE_OK_MISMATCH" -Actual $workspace.ok -Expected $true
    Assert-Equal -Code "WORKSPACE_PROJECT_MISMATCH" -Actual $workspace.project_id -Expected $session.ProjectId
    Assert-Equal -Code "WORKSPACE_CONTENT_MISMATCH" -Actual $workspace.content_id -Expected $session.ContentId
    Assert-Equal -Code "WORKSPACE_SESSION_MISMATCH" -Actual $workspace.edit_session_id -Expected $session.EditSessionId
    Assert-Equal -Code "WORKSPACE_CONTRACT_MISMATCH" -Actual $workspace.workspace_contract_version -Expected "SM3_EDITOR_WORKSPACE_V1"
    Assert-Equal -Code "WORKSPACE_READ_ONLY_MISMATCH" -Actual $workspace.read_only -Expected $false
    Assert-Equal -Code "SAVE_CONTRACT_MISMATCH" -Actual $workspace.save_contract_version -Expected "SM3_EDIT_SAVE_V1"
    Assert-Equal -Code "WORKSPACE_PREVIEW_VERIFICATION_MISMATCH" -Actual $workspace.preview.verified -Expected $true
    if ([string]$workspace.preview.sha256 -notmatch '^[a-f0-9]{64}$') {
        throw "WORKSPACE_PREVIEW_HASH_INVALID: $($workspace.preview.sha256)"
    }
    if ([string]$workspace.state_etag -notmatch '^[a-f0-9]{64}$') {
        throw "WORKSPACE_STATE_ETAG_INVALID: $($workspace.state_etag)"
    }

    $tempFile = Join-Path ([System.IO.Path]::GetTempPath()) ("sm3_07d_" + [guid]::NewGuid().ToString("N") + ".mp4")
    try {
        Invoke-WebRequest -Uri $assetUrl -OutFile $tempFile -TimeoutSec 120 | Out-Null
        $downloadedHash = (Get-FileHash -LiteralPath $tempFile -Algorithm SHA256).Hash.ToLowerInvariant()
        Assert-Equal -Code "WORKSPACE_DOWNLOADED_PREVIEW_HASH_MISMATCH" -Actual $downloadedHash -Expected ([string]$workspace.preview.sha256).ToLowerInvariant()
        $downloadedBytes = (Get-Item -LiteralPath $tempFile).Length
        Assert-Equal -Code "WORKSPACE_DOWNLOADED_PREVIEW_SIZE_MISMATCH" -Actual $downloadedBytes -Expected $workspace.preview.bytes
    }
    finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }

    $verified += [pscustomobject]@{
        content_id = $workspace.content_id
        edit_session_id = $workspace.edit_session_id
        base_variant_id = $workspace.base_variant_id
        current_revision = $workspace.current_revision
        state_etag = $workspace.state_etag
        preview_sha256 = $workspace.preview.sha256
        editor_url = $editorUrl
    }
}

Write-Host "SM3_07E_EDITOR_WORKSPACES_PASS"
$verified | Format-List
$verified | ConvertTo-Json -Depth 10
