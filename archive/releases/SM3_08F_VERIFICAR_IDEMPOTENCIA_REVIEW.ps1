# SM3 08F - Verify stable review idempotency on Worker 2.14.1
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($env:SM3_08F_EDIT_SESSION_ID)) {
    throw 'SM3_08F_EDIT_SESSION_ID_REQUIRED'
}
$base=$WorkerBaseUrl.TrimEnd('/')

$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
if($h.version -ne '2.14.1' -or $h.art_direction_review_idempotency_stable -ne $true){
    throw 'SM3_08F_IDEMPOTENCY_FIX_HEALTH_INVALID'
}

$payload=[ordered]@{
    project_id='TATTOO_0002'
    content_id='CARROSSEL_0004'
    edit_session_id=$env:SM3_08F_EDIT_SESSION_ID
    revision=4
    state_etag='22f05816c38651d2126f0f9519b6f11f8c5d7368fa93331b0ee73bd152683d09'
    source_type='PUBLICATION_ARTIFACT'
    source_id='PA_6518d45421d29eb3fcce62e8b007dd10'
    expected_source_sha256='8ecc486518120e94edfaf153f29d55c4da5224bfd4c3dbd75f122ed4fd8f4f03'
    selected_variant_key=$null
    ranking=@()
    dimension_scores=[ordered]@{
        semantic_understanding=5
        format_understanding=5
        composition=2
        art_direction=1
        brand_alignment=1
        photo_treatment=2
        cohesion=2
    }
    positive_traits=@(
        'PROCESS_STAGE_RECOGNITION',
        'INCOMPLETE_TATTOO_NOT_MISLABELED_FINAL',
        'NATIVE_CAROUSEL_FORMAT_CORRECT',
        'REDUNDANT_STAGE_LABELS_REMOVED',
        'TATTOO_REMAINS_PROTAGONIST'
    )
    negative_traits=@(
        'UNDERDESIGNED',
        'VISUAL_HIERARCHY_WEAK',
        'BRAND_ALIGNMENT_WEAK',
        'ADAPTIVE_MATTE_UNATTRACTIVE',
        'NO_ART_DIRECTION',
        'PHOTO_TREATMENT_WEAK',
        'CROSS_SLIDE_COHESION_WEAK'
    )
    overall_comment='08E understands stencil -> early blackwork -> more developed process and correctly keeps the unfinished tattoo as process, but the visual result is still generic, underdesigned and not stylish or aligned enough with MOLOTOV.'
    learning_scope='FOUNDATION'
    source='HUMAN'
}
$json=$payload|ConvertTo-Json -Depth 20 -Compress
$bytes=[Text.Encoding]::UTF8.GetBytes($json)
$r=Invoke-RestMethod -Method POST -Uri "$base/production/art-direction-review" -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 60
if($r.ok -ne $true -or $r.review_id -ne 'AR_a6726768de114250df83550751114472' -or $r.review_sha256 -ne 'c8ffa545320d077bdde66ce30519a532d7446f553d63f460bb09b3a46fcda1c9' -or $r.reused_existing -ne $true){
    throw 'SM3_08F_REVIEW_IDEMPOTENCY_VERIFY_FAILED'
}
Write-Output 'SM3_08F_REVIEW_IDEMPOTENCY_FIX_VERIFY_PASS'
[pscustomobject]@{
 review_id=$r.review_id
 review_sha256=$r.review_sha256
 reused_existing=$r.reused_existing
}
