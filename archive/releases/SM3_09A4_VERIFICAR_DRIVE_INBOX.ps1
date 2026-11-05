# SM3 09A.4 - Verify Drive reference inbox automation capability
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')

$h=Invoke-RestMethod "$base/health" -TimeoutSec 20
$s=Invoke-RestMethod "$base/production/reference-corpus/summary" -TimeoutSec 30

if($h.version -ne '2.16.2' -or
   $h.reference_drive_upload -ne $true -or
   $h.reference_drive_upload_contract -ne 'SM3_REFERENCE_DRIVE_UPLOAD_V1' -or
   $h.reference_drive_upload_version -ne 'SM3_REFERENCE_DRIVE_UPLOAD_ENGINE_V1' -or
   $h.reference_drive_upload_streaming -ne $true -or
   $h.reference_media_acquisition_contract -ne 'SM3_REFERENCE_MEDIA_ACQUISITION_V1' -or
   $h.reference_video_analysis_contract -ne 'SM3_REFERENCE_VIDEO_ANALYSIS_V1' -or
   $h.reference_feature_idempotency_stable -ne $true -or
   $h.reference_foundation_override_allowed -ne $false -or
   $h.reference_copying_allowed -ne $false){
    throw 'SM3_09A4_DRIVE_REFERENCE_INBOX_HEALTH_INVALID'
}

Write-Output 'SM3_09A4_DRIVE_REFERENCE_INBOX_VERIFY_PASS'
[pscustomobject]@{
 worker_version=$h.version
 profile_count=$s.profile_count
 item_count=$s.item_count
 media_acquisition_count=$s.media_acquisition_count
 feature_observation_count=$s.feature_observation_count
 upload_contract=$h.reference_drive_upload_contract
 upload_engine=$h.reference_drive_upload_version
 streaming_upload=$h.reference_drive_upload_streaming
 max_upload_bytes=$h.reference_drive_upload_max_bytes
 analyzer_contract=$h.reference_video_analysis_contract
 feature_idempotency_stable=$h.reference_feature_idempotency_stable
}
