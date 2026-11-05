# SM3 08D - verify the geometry-aware experimental preview and download exact bytes.
[CmdletBinding()]
param(
    [string]$WorkerBaseUrl='http://localhost:8090',
    [string]$OutputRoot=(Join-Path $PSScriptRoot 'SM3_PREVIEWS\GEOMETRY_AWARE')
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Assert-Same { param([string]$Code,$Actual,$Expected)
 if([string]$Actual -cne [string]$Expected){throw ("${Code}: actual='"+[string]$Actual+"' expected='"+[string]$Expected+"'")}
}
$base=$WorkerBaseUrl.TrimEnd('/')
$project='TATTOO_0002';$content='CARROSSEL_0004';$session=$env:SM3_08D_EDIT_SESSION_ID;$revision=4
if ([string]::IsNullOrWhiteSpace($session)) {
 throw 'SM3_08D_EDIT_SESSION_ID_REQUIRED'
}
$etag='22f05816c38651d2126f0f9519b6f11f8c5d7368fa93331b0ee73bd152683d09'
$baselineSha='d4fc6f76cff6ca32cf531e3067c12d0359a8cddc71ccf08c29500265e2e539bd'
$health=Invoke-RestMethod "$base/health" -TimeoutSec 15
Assert-Same 'WORKER_VERSION' $health.version '2.12.0'
Assert-Same '08D_CONTRACT' $health.geometry_preview_contract 'SM3_GEOMETRY_PREVIEW_V1'
Assert-Same '08D_RENDERER' $health.geometry_preview_renderer_version '2.12.0'
$w=Invoke-RestMethod "$base/production/editor-workspace/$project/$content/$session" -TimeoutSec 20
Assert-Same 'REVISION_UNCHANGED' $w.current_revision $revision
Assert-Same 'ETAG_UNCHANGED' $w.state_etag $etag

# Baseline must still exist and remain byte-identical in its manifest.
$baseline=Invoke-RestMethod "$base/production/edit-session/preview/$project/$content/$session/$revision" -TimeoutSec 20
Assert-Same 'CANONICAL_BASELINE_SHA_CHANGED' $baseline.preview_sha256 $baselineSha

$plan=Invoke-RestMethod "$base/production/composition-plan/$project/$content/$session/$revision" -TimeoutSec 20
Assert-Same 'PLAN_CONTRACT' $plan.contract_version 'SM3_COMPOSITION_PLAN_V1'
Assert-Same 'PLANNER' $plan.planner_version 'SM3_GEOMETRY_AWARE_COMPOSITOR_V1'
Assert-Same 'PLAN_REVISION' $plan.revision $revision
Assert-Same 'PLAN_ETAG' $plan.state_etag $etag
if([string]$plan.plan_sha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'SM3_08D_PLAN_HASH_INVALID'}
if($plan.no_new_edit_revision -ne $true -or $plan.canonical_edit_preview_unchanged -ne $true){throw 'SM3_08D_PLAN_MUTATION_FLAG_INVALID'}
$mp=@{};foreach($x in $plan.media_plans){$mp[[string]$x.media_id]=$x}
Assert-Same 'M0083_STRATEGY' $mp['M0083'].render_strategy 'SEMANTIC_CROP'
Assert-Same 'M0085_STRATEGY' $mp['M0085'].render_strategy 'CONTAIN_SOLID'
Assert-Same 'M0086_STRATEGY' $mp['M0086'].render_strategy 'SEMANTIC_CROP'
if([double]$mp['M0083'].verified_protected_coverage_percent -lt 88 -or [double]$mp['M0086'].verified_protected_coverage_percent -lt 88){throw 'SM3_08D_SAFE_CROP_COVERAGE_INVALID'}
$applied=@($plan.identity_decisions.applied|ForEach-Object{$_.role})
$suppressed=@($plan.identity_decisions.suppressed|ForEach-Object{$_.role})
if($applied -notcontains 'stamp' -or $suppressed -notcontains 'frame' -or $suppressed -notcontains 'texture' -or $suppressed -notcontains 'logo'){
 throw 'SM3_08D_IDENTITY_DECISION_UNEXPECTED'
}

$m=Invoke-RestMethod "$base/production/geometry-aware-preview/$project/$content/$session/$revision" -TimeoutSec 30
Assert-Same 'PREVIEW_CONTRACT' $m.contract_version 'SM3_GEOMETRY_PREVIEW_V1'
Assert-Same 'PREVIEW_RENDERER' $m.renderer_version '2.12.0'
Assert-Same 'PREVIEW_PLAN_HASH' $m.plan_sha256 $plan.plan_sha256
Assert-Same 'PREVIEW_REVISION' $m.revision $revision
Assert-Same 'PREVIEW_ETAG' $m.state_etag $etag
if($m.experimental_geometry_preview -ne $true -or $m.canonical_edit_preview_unchanged -ne $true -or $m.no_new_edit_revision -ne $true -or $m.final_render -ne $false){throw 'SM3_08D_PREVIEW_FLAGS_INVALID'}
$ops=@($m.rendered_operations)
foreach($op in @('semantic_geometry','semantic_crop_or_safe_contain','solid_matte_no_blur','protected_subject_enforcement','routed_learning_constraints')){if($ops -notcontains $op){throw "SM3_08D_OPERATION_MISSING:$op"}}
if([string]$m.preview_sha256 -cnotmatch '^[a-f0-9]{64}$' -or [long]$m.preview_bytes -lt 1000){throw 'SM3_08D_PREVIEW_MANIFEST_INVALID'}

$outDir=Join-Path $OutputRoot 'REV4'
New-Item -ItemType Directory -Path $outDir -Force|Out-Null
$dest=Join-Path $outDir 'CARROSSEL_0004_REV4_08D_GEOMETRY_AWARE.mp4'
$tmp=Join-Path $outDir ('.download_'+[guid]::NewGuid().ToString('N')+'.partial')
try{
 Invoke-WebRequest -Uri ($base+$m.asset_url) -OutFile $tmp -UseBasicParsing -TimeoutSec 300|Out-Null
 $sha=(Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant();$bytes=(Get-Item $tmp).Length
 Assert-Same 'DOWNLOADED_SHA256' $sha $m.preview_sha256
 Assert-Same 'DOWNLOADED_BYTES' $bytes $m.preview_bytes
 Move-Item -LiteralPath $tmp -Destination $dest -Force
}finally{if(Test-Path $tmp){Remove-Item $tmp -Force}}
Write-Output 'SM3_08D_GEOMETRY_AWARE_PREVIEW_VERIFY_PASS'
[pscustomobject]@{
 revision=$revision; state_etag=$etag; composition_id=$plan.composition_id; plan_sha256=$plan.plan_sha256
 preview_sha256=$m.preview_sha256; preview_bytes=[long]$m.preview_bytes; baseline_sha256=$baselineSha
 m0083=$mp['M0083'].render_strategy; m0085=$mp['M0085'].render_strategy; m0086=$mp['M0086'].render_strategy
 identity_applied=($applied -join ','); identity_suppressed=($suppressed -join ','); file=(Resolve-Path $dest).Path
}
