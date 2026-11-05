[CmdletBinding()]
param([string]$WorkerBaseUrl = 'http://localhost:8090')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$project = 'TATTOO_0002'
$content = 'CARROSSEL_0004'
$session = $env:SM3_07F_EDIT_SESSION_ID
if ([string]::IsNullOrWhiteSpace($session)) {
    throw 'SM3_07F_EDIT_SESSION_ID_REQUIRED'
}
$workspace = Invoke-RestMethod -Uri "$WorkerBaseUrl/production/editor-workspace/$project/$content/$session" -TimeoutSec 30
if ($workspace.status -ne 'SAVED' -or $workspace.current_revision -lt 2) {
    throw '07F_PREFLIGHT_SAVED_REVISION_REQUIRED'
}
if ($workspace.preview.verified -ne $true) { throw '07F_PREFLIGHT_BASE_PREVIEW_INVALID' }
$recipe = $workspace.recipe
if ($recipe.text_overlays.Count -gt 0) { throw '07F_PREFLIGHT_TEXT_RENDERER_NOT_READY' }
$identity = $recipe.identity_application
if ($identity.logo -or $identity.stamp -or $identity.texture -or $identity.frame) {
    throw '07F_PREFLIGHT_IDENTITY_ASSET_RENDERER_NOT_READY'
}
if (([string]$recipe.transition_style).ToUpperInvariant() -notin @('CUT', 'HARD_CUT', 'NONE')) {
    throw "07F_PREFLIGHT_TRANSITION_UNSUPPORTED: $($recipe.transition_style)"
}
if (([string]$recipe.audio_strategy).ToUpperInvariant() -notin @('ORIGINAL_MUTED', 'MUTED', 'NONE', 'SILENT')) {
    throw "07F_PREFLIGHT_AUDIO_UNSUPPORTED: $($recipe.audio_strategy)"
}
foreach ($frame in $recipe.framing) {
    if (([string]$frame.mode).ToUpperInvariant() -ne 'CONTAIN' -or $frame.preserve_subject -ne $true -or
        [double]$frame.zoom_start -ne 1 -or [double]$frame.zoom_end -ne 1) {
        throw "07F_PREFLIGHT_SUBJECT_GEOMETRY_REQUIRED: $($frame.media_id)"
    }
}
$color = $recipe.color_treatment
if ([double]$color.exposure_delta -lt -0.3 -or [double]$color.exposure_delta -gt 0.3 -or
    [double]$color.contrast_delta -lt -0.4 -or [double]$color.contrast_delta -gt 0.6 -or
    [double]$color.saturation_delta -lt -1 -or [double]$color.saturation_delta -gt 1) {
    throw '07F_PREFLIGHT_COLOR_RANGE_UNSUPPORTED'
}
Write-Host 'SM3_07F_PREFLIGHT_PASS'
Write-Host "content=$content revision=$($workspace.current_revision) etag=$($workspace.state_etag)"
