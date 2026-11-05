# SM3 09A.3 - Verify Reference Media Acquisition
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')
$h=Invoke-RestMethod "$base/health" -TimeoutSec 20
$s=Invoke-RestMethod "$base/production/reference-corpus/summary" -TimeoutSec 30
$m=Invoke-RestMethod "$base/production/reference-corpus/reference-media" -TimeoutSec 30
if($h.version -ne '2.16.1' -or
   $h.reference_media_acquisition -ne $true -or
   $h.reference_media_acquisition_contract -ne 'SM3_REFERENCE_MEDIA_ACQUISITION_V1' -or
   $h.reference_media_acquirer_version -ne 'SM3_REFERENCE_MEDIA_ACQUIRER_V1' -or
   $h.reference_media_canonical_copy_verified -ne $true -or
   $h.reference_media_remote_scraping_required -ne $false -or
   $h.reference_media_source_immutable -ne $true -or
   $h.reference_foundation_override_allowed -ne $false -or
   $h.reference_copying_allowed -ne $false){throw 'SM3_09A3_REFERENCE_MEDIA_HEALTH_INVALID'}
if($m.ok -ne $true -or $m.contract_version -ne 'SM3_REFERENCE_MEDIA_ACQUISITION_V1'){throw 'SM3_09A3_REFERENCE_MEDIA_LIST_INVALID'}
Write-Output 'SM3_09A3_REFERENCE_MEDIA_ACQUISITION_VERIFY_PASS'
[pscustomobject]@{
 worker_version=$h.version
 profile_count=$s.profile_count
 item_count=$s.item_count
 media_acquisition_count=$m.count
 feature_observation_count=$s.feature_observation_count
 acquisition_contract=$h.reference_media_acquisition_contract
 acquirer_version=$h.reference_media_acquirer_version
 canonical_copy_verified=$h.reference_media_canonical_copy_verified
 remote_scraping_required=$h.reference_media_remote_scraping_required
 source_immutable=$h.reference_media_source_immutable
}
