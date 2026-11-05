# SM3 09A.1 - Verify spreadsheet-driven mutable current profile state + immutable history.
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')
$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
if($h.version -ne '2.15.1' -or
   $h.reference_profile_sync_contract -ne 'SM3_REFERENCE_PROFILE_SYNC_V1' -or
   $h.reference_profile_history_contract -ne 'SM3_REFERENCE_PROFILE_HISTORY_V1' -or
   $h.reference_spreadsheet_sync -ne $true -or
   $h.reference_mutable_current_state -ne $true -or
   $h.reference_immutable_preference_history -ne $true -or
   $h.reference_external_style_is_evidence_only -ne $true -or
   $h.reference_foundation_override_allowed -ne $false -or
   $h.reference_copying_allowed -ne $false){
    throw 'SM3_09A1_REFERENCE_SYNC_HEALTH_INVALID'
}
$s=Invoke-RestMethod "$base/production/reference-corpus/summary" -TimeoutSec 30
$p=Invoke-RestMethod "$base/production/reference-corpus/profiles" -TimeoutSec 30
if($s.ok -ne $true -or $s.spreadsheet_driven_profile_sync -ne $true -or $s.mutable_current_state_with_immutable_history -ne $true){
    throw 'SM3_09A1_REFERENCE_SYNC_SUMMARY_INVALID'
}
$totalHistory=0
foreach($profile in @($p.profiles)){
    if([int]$profile.preference_version -lt 1 -or [string]$profile.profile_sha256 -cnotmatch '^[a-f0-9]{64}$'){
        throw ('SM3_09A1_PROFILE_INVALID:'+ $profile.reference_profile_id)
    }
    $hist=Invoke-RestMethod "$base/production/reference-corpus/profile/$($profile.reference_profile_id)/history" -TimeoutSec 30
    if($hist.ok -ne $true -or $hist.contract_version -ne 'SM3_REFERENCE_PROFILE_HISTORY_V1' -or [int]$hist.count -lt 1){
        throw ('SM3_09A1_PROFILE_HISTORY_INVALID:'+ $profile.reference_profile_id)
    }
    $versions=@($hist.history | ForEach-Object {[int]$_.preference_version})
    $max=($versions | Measure-Object -Maximum).Maximum
    if([int]$max -ne [int]$profile.preference_version){
        throw ('SM3_09A1_PROFILE_HISTORY_VERSION_MISMATCH:'+ $profile.reference_profile_id)
    }
    $totalHistory += [int]$hist.count
}
if([int]$totalHistory -ne [int]$s.profile_history_snapshot_count){ throw 'SM3_09A1_HISTORY_COUNT_MISMATCH' }
Write-Output 'SM3_09A1_SPREADSHEET_REFERENCE_SYNC_VERIFY_PASS'
[pscustomobject]@{
 worker_version=$h.version
 profile_count=$s.profile_count
 profile_history_snapshot_count=$s.profile_history_snapshot_count
 item_count=$s.item_count
 metric_snapshot_count=$s.metric_snapshot_count
 feature_observation_count=$s.feature_observation_count
 spreadsheet_driven_profile_sync=$s.spreadsheet_driven_profile_sync
 mutable_current_state_with_immutable_history=$s.mutable_current_state_with_immutable_history
}
