# SM3 09A.2 - Verify reference item intake readiness/state
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')
$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
$s=Invoke-RestMethod "$base/production/reference-corpus/summary" -TimeoutSec 30
if($h.version -ne '2.15.1' -or
   $h.reference_item_contract -ne 'SM3_REFERENCE_ITEM_V1' -or
   $h.reference_corpus_policy -ne 'SM3_REFERENCE_CORPUS_POLICY_V1' -or
   $h.reference_foundation_override_allowed -ne $false -or
   $h.reference_copying_allowed -ne $false){
  throw 'SM3_09A2_REFERENCE_ITEM_INTAKE_HEALTH_INVALID'
}
if([int]$s.profile_count -lt 1){throw 'SM3_09A2_NO_REFERENCE_PROFILES'}
Write-Output 'SM3_09A2_REFERENCE_ITEM_INTAKE_VERIFY_PASS'
[pscustomobject]@{
 worker_version=$h.version
 profile_count=$s.profile_count
 item_count=$s.item_count
 metric_snapshot_count=$s.metric_snapshot_count
 feature_observation_count=$s.feature_observation_count
 item_contract=$h.reference_item_contract
 video_learning_priority=$h.reference_video_learning_priority
}
