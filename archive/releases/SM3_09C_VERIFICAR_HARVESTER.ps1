# SM3 09C - Verify Automated Reference Harvester
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')
$h=Invoke-RestMethod "$base/health" -TimeoutSec 20
$s=Invoke-RestMethod "$base/production/reference-corpus/summary" -TimeoutSec 30
$r=Invoke-RestMethod "$base/production/reference-corpus/harvest/runs" -TimeoutSec 30
if($h.version -ne '2.17.0' -or $h.reference_harvester -ne $true -or $h.reference_harvest_contract -ne 'SM3_REFERENCE_HARVEST_V1' -or $h.reference_harvest_scorer_version -ne 'SM3_REFERENCE_HARVEST_SCORER_V1' -or $h.reference_harvest_within_creator_percentiles -ne $true -or $h.reference_harvest_auto_promotion_bounded -ne $true -or $h.reference_harvest_requires_remote_scraping -ne $false -or $h.reference_harvest_inactive_profiles_can_collect -ne $true -or $h.reference_harvest_inactive_profiles_influence_priors -ne $false -or $h.reference_foundation_override_allowed -ne $false -or $h.reference_copying_allowed -ne $false){throw 'SM3_09C_AUTOMATED_REFERENCE_HARVESTER_HEALTH_INVALID'}
if($s.ok -ne $true -or $r.ok -ne $true){throw 'SM3_09C_HARVESTER_STATE_INVALID'}
Write-Output 'SM3_09C_AUTOMATED_REFERENCE_HARVESTER_VERIFY_PASS'
[pscustomobject]@{worker_version=$h.version;profile_count=$s.profile_count;item_count=$s.item_count;metric_snapshot_count=$s.metric_snapshot_count;feature_observation_count=$s.feature_observation_count;harvest_run_count=$s.harvest_run_count;harvest_candidate_count=$s.harvest_candidate_count;persisted_harvest_runs=$r.count;harvest_contract=$h.reference_harvest_contract;scorer=$h.reference_harvest_scorer_version;within_creator_percentiles=$h.reference_harvest_within_creator_percentiles;bounded_auto_promotion=$h.reference_harvest_auto_promotion_bounded;inactive_profiles_can_collect=$h.reference_harvest_inactive_profiles_can_collect;inactive_profiles_influence_priors=$h.reference_harvest_inactive_profiles_influence_priors}
