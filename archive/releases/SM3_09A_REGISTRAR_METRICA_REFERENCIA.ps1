# Register one immutable reference metric snapshot.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ReferenceItemId,
    [ValidateSet('METRICOOL','MANUAL')][string]$Provider='METRICOOL',
    [Nullable[int]]$Likes=$null,
    [Nullable[int]]$Comments=$null,
    [Nullable[int]]$Interactions=$null,
    [Nullable[double]]$Engagement=$null,
    [string]$CapturedAt='',
    [ValidateSet('METRICOOL','MANUAL','CHATGPT')][string]$Source='METRICOOL',
    [string]$Notes='',
    [string]$WorkerBaseUrl='http://localhost:8090'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$payload=[ordered]@{
 reference_item_id=$ReferenceItemId; provider=$Provider
 likes=$Likes; comments=$Comments; interactions=$Interactions; engagement=$Engagement
 raw_metrics=@{}; captured_at=if($CapturedAt){$CapturedAt}else{$null}
 source=$Source; notes=$Notes
}
$bytes=[Text.Encoding]::UTF8.GetBytes(($payload|ConvertTo-Json -Depth 10 -Compress))
$r=Invoke-RestMethod -Method POST -Uri ($WorkerBaseUrl.TrimEnd('/')+'/production/reference-corpus/metric-snapshot') -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 60
if($r.ok -ne $true -or $r.contract_version -ne 'SM3_REFERENCE_METRIC_SNAPSHOT_V1'){ throw 'SM3_09A_REFERENCE_METRIC_REGISTER_INVALID' }
Write-Output 'SM3_09A_REFERENCE_METRIC_SNAPSHOT_REGISTERED'
$r | Select-Object snapshot_id,reference_item_id,likes,comments,interactions,engagement,captured_at,snapshot_sha256,reused_existing
