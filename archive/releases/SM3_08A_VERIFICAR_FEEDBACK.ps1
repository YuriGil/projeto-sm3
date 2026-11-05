# SM3 08A - Verify persisted visual feedback for current REV4.
[CmdletBinding()]
param(
    [string]$WorkerBaseUrl = 'http://localhost:8090',
    [string]$ProjectId = 'TATTOO_0002',
    [string]$ContentId = 'CARROSSEL_0004',
    [string]$EditSessionId = $env:SM3_08A_EDIT_SESSION_ID,
    [int]$Revision = 4
)
Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($EditSessionId)) {
    throw 'SM3_08A_EDIT_SESSION_ID_REQUIRED'
}
$ErrorActionPreference = 'Stop'
$base = $WorkerBaseUrl.TrimEnd('/')

$health = Invoke-RestMethod "$base/health" -TimeoutSec 15
if ($health.version -ne '2.9.0' -or $health.visual_feedback_contract -ne 'SM3_VISUAL_FEEDBACK_V1') {
    throw 'SM3_08A_WORKER_CONTRACT_INVALID'
}

$url = "$base/production/visual-feedback/$ProjectId/$ContentId/$EditSessionId/$Revision"
$data = Invoke-RestMethod $url -TimeoutSec 20

if ($data.ok -ne $true -or
    $data.contract_version -ne 'SM3_VISUAL_FEEDBACK_V1' -or
    $data.taxonomy_version -ne 'SM3_VISUAL_ISSUES_V1' -or
    [int]$data.count -lt 1 -or
    [int]$data.summary.negative_examples -lt 1) {
    throw 'SM3_08A_FEEDBACK_HISTORY_INVALID'
}

$baseline = @($data.feedback | Where-Object {
    $_.feedback.verdict -eq 'REJECTED' -and
    $_.learning_label -eq 'NEGATIVE' -and
    $_.evidence.preview_sha256 -eq 'd4fc6f76cff6ca32cf531e3067c12d0359a8cddc71ccf08c29500265e2e539bd'
}) | Select-Object -First 1

if ($null -eq $baseline) {
    throw 'SM3_08A_REV4_BASELINE_NOT_FOUND'
}

Write-Output 'SM3_08A_VISUAL_FEEDBACK_VERIFY_PASS'
[pscustomobject]@{
    feedback_count = $data.count
    negative_examples = $data.summary.negative_examples
    feedback_id = $baseline.feedback_id
    verdict = $baseline.feedback.verdict
    issue_count = @($baseline.feedback.issues).Count
    record_sha256 = $baseline.record_sha256
}
