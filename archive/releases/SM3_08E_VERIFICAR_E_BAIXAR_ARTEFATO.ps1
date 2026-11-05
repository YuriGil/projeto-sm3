# SM3 08E — verify and download native-format publication artifact candidate.
[CmdletBinding()]
param(
    [string]$WorkerBaseUrl = 'http://localhost:8090',
    [string]$ProjectId = 'TATTOO_0002',
    [string]$ContentId = 'CARROSSEL_0004',
    [string]$EditSessionId = $env:SM3_08E_EDIT_SESSION_ID,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'SM3_PUBLICATION_CANDIDATES')
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($EditSessionId)) {
    throw 'SM3_08E_EDIT_SESSION_ID_REQUIRED'
}
$base=$WorkerBaseUrl.TrimEnd('/')
$expectedRev=4
$expectedEtag='22f05816c38651d2126f0f9519b6f11f8c5d7368fa93331b0ee73bd152683d09'
$canonicalBaseline='d4fc6f76cff6ca32cf531e3067c12d0359a8cddc71ccf08c29500265e2e539bd'
$geometryBaseline='bd9f5885a7c8a856c0c5b3a1223f2e5c5ac5b5e2182e39dc1ce7848de225cd3d'

function Assert-Same { param([string]$Code,$Actual,$Expected)
 if([string]$Actual -cne [string]$Expected){throw "${Code}: actual='$Actual' expected='$Expected'"}
}
function Download-Verified { param([string]$Url,[string]$Path,[string]$ExpectedHash,[long]$ExpectedBytes)
 $dir=Split-Path -Parent $Path; New-Item -ItemType Directory -Path $dir -Force | Out-Null
 if(Test-Path -LiteralPath $Path -PathType Leaf){
   $h=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant();$b=(Get-Item -LiteralPath $Path).Length
   if($h -eq $ExpectedHash -and $b -eq $ExpectedBytes){return $true}
   throw "SM3_08E_LOCAL_FILE_CONFLICT:$Path"
 }
 $tmp=$Path+'.partial'; if(Test-Path $tmp){Remove-Item $tmp -Force}
 try {
   Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing -TimeoutSec 180 | Out-Null
   $h=(Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant();$b=(Get-Item -LiteralPath $tmp).Length
   Assert-Same 'SM3_08E_DOWNLOADED_SHA256' $h $ExpectedHash; Assert-Same 'SM3_08E_DOWNLOADED_BYTES' $b $ExpectedBytes
   Move-Item -LiteralPath $tmp -Destination $Path
 } finally {if(Test-Path $tmp){Remove-Item $tmp -Force}}
 return $false
}

$health=Invoke-RestMethod "$base/health" -TimeoutSec 15
Assert-Same 'WORKER_VERSION' $health.version '2.13.0'
Assert-Same 'EDITORIAL_INTENT_CONTRACT' $health.editorial_intent_contract 'SM3_EDITORIAL_INTENT_V1'
Assert-Same 'PUBLICATION_ARTIFACT_CONTRACT' $health.publication_artifact_contract 'SM3_PUBLICATION_ARTIFACT_V1'
Assert-Same 'PUBLICATION_ARTIFACT_RENDERER' $health.publication_artifact_renderer_version '2.13.0'

$workspace=Invoke-RestMethod "$base/production/editor-workspace/$ProjectId/$ContentId/$EditSessionId" -TimeoutSec 20
Assert-Same 'REVISION' $workspace.current_revision $expectedRev; Assert-Same 'ETAG' $workspace.state_etag $expectedEtag

$plan=Invoke-RestMethod "$base/production/editorial-plan/$ProjectId/$ContentId/$EditSessionId/$expectedRev" -TimeoutSec 20
Assert-Same 'PLAN_CONTRACT' $plan.contract_version 'SM3_EDITORIAL_INTENT_V1'
Assert-Same 'PLAN_PLANNER' $plan.planner_version 'SM3_NATIVE_FORMAT_PLANNER_V1'
Assert-Same 'PLAN_FORMAT' $plan.content_format 'CARROSSEL'
Assert-Same 'PLAN_ARTIFACT_TYPE' $plan.artifact_type 'CAROUSEL_IMAGE_SET'
Assert-Same 'PLAN_TEXT' $plan.text_decision 'NONE_REDUNDANT_VISUAL_LABELS'
if($plan.no_fixed_duration_for_non_temporal_format -ne $true -or $plan.review_artifact_separate_from_native_product -ne $true){throw 'SM3_08E_PLAN_POLICY_INVALID'}
if(@($plan.slide_plans).Count -ne 3){throw 'SM3_08E_PLAN_SLIDE_COUNT_INVALID'}
$expectedMedia=@('M0083','M0085','M0086')
for($i=0;$i -lt 3;$i++){Assert-Same "SLIDE_ORDER_$i" $plan.slide_plans[$i].media_id $expectedMedia[$i];if($null -ne $plan.slide_plans[$i].duration_seconds){throw "SM3_08E_DURATION_PRESENT_ON_CAROUSEL:$($expectedMedia[$i])"}}

$m=Invoke-RestMethod "$base/production/native-publication-artifact/$ProjectId/$ContentId/$EditSessionId/$expectedRev" -TimeoutSec 30
Assert-Same 'ARTIFACT_CONTRACT' $m.contract_version 'SM3_PUBLICATION_ARTIFACT_V1'
Assert-Same 'ARTIFACT_RENDERER' $m.renderer_version '2.13.0'
Assert-Same 'ARTIFACT_TYPE' $m.artifact_type 'CAROUSEL_IMAGE_SET'
Assert-Same 'ARTIFACT_PLAN_HASH' $m.editorial_plan_sha256 $plan.plan_sha256
if($m.no_timeline_for_carousel -ne $true -or $m.no_generic_footer -ne $true -or $m.no_redundant_stage_labels -ne $true -or $m.human_approval_required -ne $true -or $m.auto_publish_allowed -ne $false){throw 'SM3_08E_ARTIFACT_POLICY_INVALID'}
if(@($m.assets).Count -ne 3){throw 'SM3_08E_ARTIFACT_ASSET_COUNT_INVALID'}

$outDir=Join-Path $OutputRoot 'CARROSSEL_0004_REV4_08E_NATIVE'
$results=@()
for($i=0;$i -lt @($m.assets).Count;$i++){
 $a=$m.assets[$i];$mid=$expectedMedia[$i];Assert-Same "ASSET_MEDIA_$i" $a.media_id $mid
 Assert-Same "ASSET_WIDTH_$i" $a.width 1080;Assert-Same "ASSET_HEIGHT_$i" $a.height 1350
 if([string]$a.sha256 -cnotmatch '^[a-f0-9]{64}$' -or [long]$a.bytes -lt 1000){throw "SM3_08E_ASSET_MANIFEST_INVALID:$mid"}
 $dest=Join-Path $outDir ("{0}_SLIDE_{1:D2}_{2}.jpg" -f $ContentId,($i+1),$mid)
 $reused=Download-Verified ($base+$a.asset_url) $dest $a.sha256 ([long]$a.bytes)
 $results += [pscustomobject]@{index=$i+1;media_id=$mid;strategy=$a.render.rendered_strategy;sha256=$a.sha256;bytes=[long]$a.bytes;reused=$reused;file=(Resolve-Path $dest).Path}
}
$r=$m.review_asset
$reviewDest=Join-Path $outDir ($ContentId+'_REVIEW_CONTACT_SHEET.jpg')
$reviewReused=Download-Verified ($base+$r.asset_url) $reviewDest $r.sha256 ([long]$r.bytes)

# Confirm previous evidence was not replaced.
$canonical=Invoke-RestMethod "$base/production/edit-session/preview/$ProjectId/$ContentId/$EditSessionId/$expectedRev" -TimeoutSec 20
Assert-Same 'CANONICAL_BASELINE_PRESERVED' $canonical.preview_sha256 $canonicalBaseline
$geom=Invoke-RestMethod "$base/production/geometry-aware-preview/$ProjectId/$ContentId/$EditSessionId/$expectedRev" -TimeoutSec 20
Assert-Same '08D_BASELINE_PRESERVED' $geom.preview_sha256 $geometryBaseline

Write-Output 'SM3_08E_NATIVE_FORMAT_ARTIFACT_VERIFY_PASS'
[pscustomobject]@{
 revision=$expectedRev;state_etag=$expectedEtag;editorial_plan_id=$plan.editorial_plan_id;plan_sha256=$plan.plan_sha256
 artifact_id=$m.artifact_id;manifest_sha256=$m.manifest_sha256;artifact_type=$m.artifact_type;text_decision=$m.text_decision
 slide_count=@($m.assets).Count;review_file=(Resolve-Path $reviewDest).Path;review_reused=$reviewReused
 canonical_rev4_sha256=$canonical.preview_sha256;geometry_08d_sha256=$geom.preview_sha256
}
$results | Format-Table -AutoSize
