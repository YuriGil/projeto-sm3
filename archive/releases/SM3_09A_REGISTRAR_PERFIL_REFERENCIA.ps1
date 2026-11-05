# Register one reference profile into SM3 09A.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('instagram','tiktok')][string]$Network,
    [Parameter(Mandatory=$true)][string]$Handle,
    [string]$ProfileUrl='',
    [string]$Label='',
    [string[]]$UserInterest=@(),
    [string]$StyleNotes='',
    [string]$DislikeNotes='',
    [ValidateSet('HUMAN','METRICOOL','CHATGPT')][string]$Source='HUMAN',
    [string]$WorkerBaseUrl='http://localhost:8090'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$payload=[ordered]@{
 network=$Network; handle=$Handle
 profile_url=if($ProfileUrl){$ProfileUrl}else{$null}
 label=if($Label){$Label}else{$null}
 user_interest=@($UserInterest)
 style_notes=$StyleNotes; dislike_notes=$DislikeNotes
 source=$Source; active=$true
}
$json=$payload|ConvertTo-Json -Depth 10 -Compress
$bytes=[Text.Encoding]::UTF8.GetBytes($json)
$r=Invoke-RestMethod -Method POST -Uri ($WorkerBaseUrl.TrimEnd('/')+'/production/reference-corpus/profile') -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 60
if($r.ok -ne $true -or $r.contract_version -ne 'SM3_REFERENCE_PROFILE_V1'){ throw 'SM3_09A_REFERENCE_PROFILE_REGISTER_INVALID' }
Write-Output 'SM3_09A_REFERENCE_PROFILE_REGISTERED'
$r | Select-Object reference_profile_id,network,handle,label,user_interest,profile_sha256,reused_existing
