# SM3 09A.3 - Import one local reference video into the canonical media volume.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ReferenceItemId,
  [Parameter(Mandatory=$true)][string]$SourceFile,
  [ValidateSet('LOCAL_IMPORT','DRIVE_UPLOAD','MANUAL_DOWNLOAD')][string]$SourceKind='LOCAL_IMPORT',
  [string]$Notes='',
  [switch]$CleanupInbox,
  [string]$ProjectRoot=(Get-Location).Path,
  [string]$WorkerBaseUrl='http://localhost:8090'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($ReferenceItemId -notmatch '^RI_[a-f0-9]{32}$'){throw 'SM3_09A3_REFERENCE_ITEM_ID_INVALID'}
$SourceFile=(Resolve-Path -LiteralPath $SourceFile).Path
if(-not(Test-Path -LiteralPath $SourceFile -PathType Leaf)){throw 'SM3_09A3_SOURCE_FILE_NOT_FOUND'}
$base=$WorkerBaseUrl.TrimEnd('/')
$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
if($h.version -ne '2.16.1' -or $h.reference_media_acquisition -ne $true){throw 'SM3_09A3_WORKER_NOT_READY'}
$item=Invoke-RestMethod "$base/production/reference-corpus/item/$ReferenceItemId" -TimeoutSec 20
if($item.item.item_type -notin @('REEL','VIDEO','STORY')){throw 'SM3_09A3_REFERENCE_ITEM_NOT_VIDEO'}
$sha=(Get-FileHash -LiteralPath $SourceFile -Algorithm SHA256).Hash.ToLowerInvariant()
$ext=[IO.Path]::GetExtension($SourceFile).ToLowerInvariant()
if([string]::IsNullOrWhiteSpace($ext)){$ext='.bin'}
$inboxName="${ReferenceItemId}__${sha}$ext"
$composeBase=Join-Path $ProjectRoot 'deployment\docker-compose.yml'
$composeWorker=Join-Path $ProjectRoot 'deployment\docker-compose.worker.yml'
foreach($p in @($composeBase,$composeWorker)){if(-not(Test-Path -LiteralPath $p)){throw "SM3_09A3_COMPOSE_FILE_NOT_FOUND:$p"}}
$cid=(& docker compose -f $composeBase -f $composeWorker ps -q media-worker | Select-Object -First 1).Trim()
if([string]::IsNullOrWhiteSpace($cid)){throw 'SM3_09A3_MEDIA_WORKER_CONTAINER_NOT_FOUND'}
& docker exec $cid sh -lc 'mkdir -p /data/media/reference_inbox'
if($LASTEXITCODE -ne 0){throw 'SM3_09A3_REFERENCE_INBOX_CREATE_FAILED'}
$dest="$cid`:/data/media/reference_inbox/$inboxName"
& docker cp $SourceFile $dest
if($LASTEXITCODE -ne 0){throw 'SM3_09A3_DOCKER_CP_FAILED'}
$payload=[ordered]@{
 reference_item_id=$ReferenceItemId
 inbox_media_ref="reference_inbox/$inboxName"
 source_kind=$SourceKind
 original_filename=[IO.Path]::GetFileName($SourceFile)
 notes=$Notes
 cleanup_inbox_after_commit=[bool]$CleanupInbox
}
$bytes=[Text.Encoding]::UTF8.GetBytes(($payload|ConvertTo-Json -Depth 10 -Compress))
$r=Invoke-RestMethod -Method POST -Uri "$base/production/reference-corpus/reference-media/acquire" -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 120
if($r.ok -ne $true -or $r.acquisition.contract_version -ne 'SM3_REFERENCE_MEDIA_ACQUISITION_V1'){throw 'SM3_09A3_REFERENCE_MEDIA_ACQUIRE_INVALID'}
Write-Output 'SM3_09A3_REFERENCE_MEDIA_ACQUIRED'
[pscustomobject]@{
 acquisition_id=$r.acquisition.acquisition_id
 reference_item_id=$r.acquisition.reference_item_id
 source_sha256=$r.acquisition.source_sha256
 duration_seconds=$r.acquisition.duration_seconds
 has_audio=$r.acquisition.has_audio
 local_media_ref=$r.acquisition.canonical_local_media_ref
 reused_existing=$r.reused_existing
}
