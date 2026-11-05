# SM3 08E R3 - read-only diagnostic for native artifact transaction state.
[CmdletBinding()]
param([string]$WorkerBaseUrl='http://localhost:8090')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$base=$WorkerBaseUrl.TrimEnd('/')
$project='TATTOO_0002'; $content='CARROSSEL_0004'
$session=$env:SM3_08E_EDIT_SESSION_ID; $rev=4
if ([string]::IsNullOrWhiteSpace($session)) {
  throw 'SM3_08E_EDIT_SESSION_ID_REQUIRED'
}

Write-Host '== SM3 08E R3 / NATIVE ARTIFACT STATE =='
$h=Invoke-RestMethod "$base/health" -TimeoutSec 15
[pscustomobject]@{
 worker_version=$h.version
 artifact_renderer=$h.publication_artifact_renderer_version
 atomic_manifest_paths=$h.publication_atomic_manifest_paths
 legacy_failed_commit_recovery=$h.publication_2_13_0_failed_commit_recovery
} | Format-List

foreach($u in @(
 "$base/production/editorial-plan/$project/$content/$session/$rev",
 "$base/production/native-publication-artifact/$project/$content/$session/$rev"
)){
  try {
    $x=Invoke-RestMethod $u -TimeoutSec 30
    Write-Host ("FOUND: "+$u)
    if($x.editorial_plan_id){Write-Host ("  editorial_plan_id: "+$x.editorial_plan_id)}
    if($x.artifact_id){Write-Host ("  artifact_id: "+$x.artifact_id)}
    if($x.manifest_sha256){Write-Host ("  manifest_sha256: "+$x.manifest_sha256)}
  } catch {
    $status=''
    try{$status=[int]$_.Exception.Response.StatusCode}catch{}
    Write-Host ("NOT READY: "+$u+" HTTP "+$status)
  }
}
Write-Output 'SM3_08E_R3_DIAGNOSTIC_COMPLETE'
