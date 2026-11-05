# SM3 08F - Verify latest art-direction set and download 3x3 assets + comparison sheet.
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090',[string]$OutputRoot='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$scriptPath=$MyInvocation.MyCommand.Path; $ScriptDir=if([string]::IsNullOrWhiteSpace($scriptPath)){(Get-Location).Path}else{Split-Path -Parent $scriptPath}
if([string]::IsNullOrWhiteSpace($OutputRoot)){$OutputRoot=Join-Path $ScriptDir 'SM3_ART_DIRECTION_VARIANTS'}
$base=$WorkerBaseUrl.TrimEnd('/'); $project='TATTOO_0002';$content='CARROSSEL_0004';$session=$env:SM3_08F_EDIT_SESSION_ID;$rev=4;$etag='22f05816c38651d2126f0f9519b6f11f8c5d7368fa93331b0ee73bd152683d09'
if ([string]::IsNullOrWhiteSpace($session)) {
    throw 'SM3_08F_EDIT_SESSION_ID_REQUIRED'
}
$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
if($h.version -ne '2.14.1' -or $h.art_direction_variant_contract -ne 'SM3_ART_DIRECTION_VARIANT_SET_V1' -or $h.art_direction_variant_renderer_version -ne '2.14.0'){throw 'SM3_08F_HEALTH_INVALID'}
$w=Invoke-RestMethod "$base/production/editor-workspace/$project/$content/$session" -TimeoutSec 20
if([int]$w.current_revision -ne $rev -or $w.state_etag -cne $etag){throw 'SM3_08F_WORKSPACE_CHANGED'}
$m=Invoke-RestMethod "$base/production/art-direction-variant-lab/$project/$content/$session/$rev/latest" -TimeoutSec 45
$keys=@('PHOTO_DOMINANT','EDITORIAL_MOLOTOV','RAW_ARCHIVE')
if($m.ok -ne $true -or $m.contract_version -ne 'SM3_ART_DIRECTION_VARIANT_SET_V1' -or $m.renderer_version -ne '2.14.0' -or $m.grammar_version -ne 'SM3_ART_DIRECTION_GRAMMAR_V1' -or [string]$m.set_sha256 -cnotmatch '^[a-f0-9]{64}$' -or @($m.variants).Count -ne 3){throw 'SM3_08F_VARIANT_MANIFEST_INVALID'}
$out=Join-Path $OutputRoot $m.variant_set_id; New-Item -ItemType Directory -Path $out -Force|Out-Null
$results=@()
foreach($v in $m.variants){ if($keys -notcontains $v.variant_key){throw 'SM3_08F_VARIANT_KEY_INVALID'}; $vd=Join-Path $out $v.variant_key;New-Item -ItemType Directory -Path $vd -Force|Out-Null; foreach($a in $v.assets){$dest=Join-Path $vd ($a.asset_id+'.jpg'); Invoke-WebRequest -UseBasicParsing -Uri ($base+$a.asset_url) -OutFile $dest -TimeoutSec 180; $hash=(Get-FileHash $dest -Algorithm SHA256).Hash.ToLowerInvariant(); $bytes=(Get-Item $dest).Length; if($hash -cne $a.sha256 -or $bytes -ne [long]$a.bytes){throw ('SM3_08F_ASSET_BYTES_MISMATCH:'+$a.asset_id)}; $results += [pscustomobject]@{variant=$v.variant_key;asset_id=$a.asset_id;media_id=$a.media_id;sha256=$hash;bytes=$bytes;file=(Resolve-Path $dest).Path}} }
$review=Join-Path $out 'ART_DIRECTION_COMPARISON.jpg';Invoke-WebRequest -UseBasicParsing -Uri ($base+$m.review_asset.asset_url) -OutFile $review -TimeoutSec 180;$rh=(Get-FileHash $review -Algorithm SHA256).Hash.ToLowerInvariant();if($rh -cne $m.review_asset.sha256){throw 'SM3_08F_REVIEW_HASH_MISMATCH'}
# Preserve 08E baseline exactly.
$b=Invoke-RestMethod "$base/production/native-publication-artifact/$project/$content/$session/$rev" -TimeoutSec 30
if($b.manifest_sha256 -cne '8ecc486518120e94edfaf153f29d55c4da5224bfd4c3dbd75f122ed4fd8f4f03'){throw 'SM3_08F_08E_BASELINE_CHANGED'}
Write-Output 'SM3_08F_ART_DIRECTION_VARIANT_VERIFY_PASS'
[pscustomobject]@{revision=$rev;variant_set_id=$m.variant_set_id;set_sha256=$m.set_sha256;variant_count=@($m.variants).Count;asset_count=$results.Count;review_file=(Resolve-Path $review).Path;baseline_08e_sha256=$b.manifest_sha256}
$results|Format-Table -AutoSize
