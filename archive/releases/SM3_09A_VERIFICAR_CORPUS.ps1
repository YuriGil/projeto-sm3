# SM3 09A - Verify Reference Intelligence Corpus
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')

$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
$s=Invoke-RestMethod "$base/production/reference-corpus/summary" -TimeoutSec 30
if($h.version -ne '2.15.0' -or
   $h.reference_corpus -ne $true -or
   $h.reference_profile_contract -ne 'SM3_REFERENCE_PROFILE_V1' -or
   $h.reference_item_contract -ne 'SM3_REFERENCE_ITEM_V1' -or
   $h.reference_metric_contract -ne 'SM3_REFERENCE_METRIC_SNAPSHOT_V1' -or
   $h.reference_feature_contract -ne 'SM3_REFERENCE_FEATURES_V1' -or
   $h.reference_corpus_policy -ne 'SM3_REFERENCE_CORPUS_POLICY_V1' -or
   $h.reference_external_style_is_evidence_only -ne $true -or
   $h.reference_foundation_override_allowed -ne $false -or
   $h.reference_copying_allowed -ne $false -or
   $h.reference_video_learning_priority -ne $true){
    throw 'SM3_09A_REFERENCE_CORPUS_HEALTH_INVALID'
}
if($s.ok -ne $true -or $s.foundation_override_allowed -ne $false -or $s.copying_reference_pixels_or_identity -ne $false){
    throw 'SM3_09A_REFERENCE_CORPUS_POLICY_INVALID'
}
Write-Output 'SM3_09A_REFERENCE_CORPUS_VERIFY_PASS'
$s | Select-Object profile_count,item_count,metric_snapshot_count,feature_observation_count,video_learning_priority,external_style_is_evidence_only,foundation_override_allowed,copying_reference_pixels_or_identity
