# Register one external reference item into SM3 09A.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ReferenceProfileId,
    [Parameter(Mandatory=$true)][ValidateSet('instagram','tiktok')][string]$Network,
    [Parameter(Mandatory=$true)][ValidateSet('REEL','POST','CAROUSEL','STORY','VIDEO')][string]$ItemType,
    [Parameter(Mandatory=$true)][string]$Url,
    [string]$PlatformItemId='',
    [string]$Caption='',
    [string]$PublishedAt='',
    [ValidateSet('METRICOOL','MANUAL_URL','DRIVE_UPLOAD','CHATGPT')][string]$Source='MANUAL_URL',
    [string]$LocalMediaRef='',
    [string]$Notes='',
    [string]$WorkerBaseUrl='http://localhost:8090'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$payload=[ordered]@{
 reference_profile_id=$ReferenceProfileId; network=$Network; item_type=$ItemType
 platform_item_id=if($PlatformItemId){$PlatformItemId}else{$null}; url=$Url; caption=$Caption
 published_at=if($PublishedAt){$PublishedAt}else{$null}; source=$Source
 local_media_ref=if($LocalMediaRef){$LocalMediaRef}else{$null}; notes=$Notes
}
$bytes=[Text.Encoding]::UTF8.GetBytes(($payload|ConvertTo-Json -Depth 10 -Compress))
$r=Invoke-RestMethod -Method POST -Uri ($WorkerBaseUrl.TrimEnd('/')+'/production/reference-corpus/item') -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 60
if($r.ok -ne $true -or $r.contract_version -ne 'SM3_REFERENCE_ITEM_V1'){ throw 'SM3_09A_REFERENCE_ITEM_REGISTER_INVALID' }
Write-Output 'SM3_09A_REFERENCE_ITEM_REGISTERED'
$r | Select-Object reference_item_id,reference_profile_id,item_type,url,item_sha256,reused_existing
