param(
    [string]$Root = "D:\MOLOTOV_SOCIAL_OS_RC7",

    [string]$ReportFile = "D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C7\SM3_09C7_A2_SEMANTIC_CONTRACT_FREEZE.json"
)


$ErrorActionPreference = "Stop"


$worker = Join-Path `
    $Root `
    "worker\worker_service.py"


$a1Report = Join-Path `
    $Root `
    "reports\09C7\SM3_09C7_A1_SEMANTIC_ARCHITECTURE_MAP.txt"


$container = "deployment-media-worker-1"

$base = "http://127.0.0.1:8090"


$expectedWorkerSha = "3af5412234de7a7faa0e8b23116027b7cad25fe308698ca9188649ca3b1df8ba"


# ============================================================
# 1. SOURCE / RUNTIME PREFLIGHT
# ============================================================

if (-not (Test-Path -LiteralPath $worker)) {
    throw "SM3_09C7_A2_WORKER_NOT_FOUND"
}


if (-not (Test-Path -LiteralPath $a1Report)) {
    throw "SM3_09C7_A2_A1_REPORT_NOT_FOUND"
}


$hostShaBefore = (
    Get-FileHash `
        -LiteralPath $worker `
        -Algorithm SHA256
).Hash.ToLower()


$runtimeShaLine = (
    docker exec `
        $container `
        sha256sum `
        /app/worker_service.py |
    Out-String
).Trim()


$runtimeShaBefore = (
    ($runtimeShaLine -split "\s+")[0]
).Trim().ToLower()


$health = Invoke-RestMethod `
    -Uri "$base/health" `
    -Method GET `
    -TimeoutSec 30


$a1Text = Get-Content `
    -LiteralPath $a1Report `
    -Raw


$a1Sha = (
    Get-FileHash `
        -LiteralPath $a1Report `
        -Algorithm SHA256
).Hash.ToLower()


if ($hostShaBefore -ne $expectedWorkerSha) {
    throw "SM3_09C7_A2_HOST_SHA_INVALID"
}


if ($runtimeShaBefore -ne $expectedWorkerSha) {
    throw "SM3_09C7_A2_RUNTIME_SHA_INVALID"
}


if ($health.version -ne "2.23.1") {
    throw "SM3_09C7_A2_WORKER_VERSION_INVALID"
}


if (
    $a1Text -notmatch `
    "SM3_09C7_A1_SEMANTIC_ARCHITECTURE_MAP_PASS"
) {
    throw "SM3_09C7_A2_A1_NOT_PASS"
}


# ============================================================
# 2. BASELINE COUNTS
# ============================================================

$priorityBefore = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_priority_decisions -type f -name 'RPD_*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$videoBefore = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_video_analyses -type f -name '*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$featureBefore = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_features -type f -name '*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$semanticBefore = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_semantic_analyses -type f -name 'RSA_*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


# ============================================================
# 3. FREEZE
# ============================================================

$freeze = [PSCustomObject]@{

    phase = "09C7-A2"

    status = "FROZEN"

    source = [PSCustomObject]@{

        worker_version = "2.23.1"

        worker_sha256 = $expectedWorkerSha

        architecture_map_report = $a1Report

        architecture_map_sha256 = $a1Sha
    }


    contracts = [PSCustomObject]@{

        semantic_analysis_contract = "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1"

        semantic_analyzer_version = "SM3_REFERENCE_SEMANTIC_ANALYZER_V1"

        semantic_schema_version = "SM3_REFERENCE_SEMANTIC_SCHEMA_V1"

        semantic_prompt_version = "SM3_REFERENCE_SEMANTIC_PROMPT_V1"

        semantic_provider_contract = "SM3_REFERENCE_SEMANTIC_PROVIDER_V1"
    }


    request = [PSCustomObject]@{

        required_fields = @(
            "reference_item_id",
            "acquisition_id",
            "mechanical_analysis_id",
            "priority_decision_id"
        )

        forbidden_fields = @(
            "local_media_ref",
            "source_resolved_path",
            "preference_signal",
            "notes",
            "use_latest_acquisition",
            "use_latest_mechanical",
            "use_latest_priority"
        )

        implicit_latest_resolution_allowed = $false
    }


    identity = [PSCustomObject]@{

        record_prefix = "RSA_"

        fields = @(
            "reference_item_id",
            "source_sha256",
            "mechanical_analysis_id",
            "mechanical_analysis_sha256",
            "semantic_analyzer_version",
            "semantic_schema_version",
            "semantic_prompt_version",
            "vision_provider",
            "vision_model"
        )

        explicitly_excluded = @(
            "acquisition_id",
            "priority_decision_id",
            "local_media_ref",
            "source_resolved_path",
            "preference_signal",
            "notes",
            "created_at",
            "provider_response_id"
        )
    }


    storage = [PSCustomObject]@{

        root = "production_state/reference_semantic_analyses"

        item_context_specific = $true

        immutable = $true

        write_once = $true

        canonical_hash_required = $true
    }


    routes = [PSCustomObject]@{

        create = "/production/reference-corpus/semantic-analysis"

        list = "/production/reference-corpus/item/{item_id}/semantic-analyses"

        latest = "/production/reference-corpus/item/{item_id}/semantic-analysis/latest"
    }


    eligibility = [PSCustomObject]@{

        active_item_required = $true

        video_item_required = $true

        acquisition_item_match_required = $true

        acquisition_source_sha_required = $true

        mechanical_analysis_required = $true

        mechanical_source_match_required = $true

        mechanical_hash_verified = $true

        canonical_contact_sheet_required = $true

        canonical_contact_sheet_hash_verified = $true

        current_priority_decision_required = $true

        requested_priority_must_be_current = $true

        priority_source_match_required = $true

        priority_mechanical_match_required = $true

        priority_evidence_fingerprint_current = $true

        semantic_analysis_allowed_required = $true

        fail_closed = $true
    }


    mechanical_policy = [PSCustomObject]@{

        canonical_rma_is_source_of_truth = $true

        recalculate_mechanical = $false

        regenerate_contact_sheet = $false

        recalculate_cut_metrics = $false

        recalculate_audio_onsets = $false

        recalculate_color_stats = $false

        blend_semantic_and_mechanical_confidence = $false
    }


    model_policy = [PSCustomObject]@{

        model_call_only_after_priority_allow = $true

        provider_boundary_required = $true

        engine_direct_http_provider_call_allowed = $false

        descriptive_only = $true

        copying_forbidden = $true

        foundation_override_allowed = $false

        person_identification_allowed = $false

        external_reference_is_evidence_only = $true
    }


    semantic_schema = [PSCustomObject]@{

        fields = @(
            "hook_duration_s",
            "camera_motion",
            "subject_scale",
            "subject_coverage",
            "text_density",
            "text_position",
            "transition_style",
            "speed_ramp",
            "identity_usage",
            "tattoo_presentation",
            "story_structure",
            "analysis_confidence",
            "notes"
        )

        objective_mechanical_fields_forbidden = @(
            "cuts_per_10s",
            "median_shot_s",
            "beat_sync",
            "color_contrast",
            "color_saturation",
            "color_temperature",
            "sharpness_grain"
        )

        unknown_when_not_observable = $true
    }


    provenance = [PSCustomObject]@{

        acquisition_id_persisted = $true

        media_artifact_id_persisted = $true

        source_sha256_persisted = $true

        mechanical_analysis_id_persisted = $true

        mechanical_analysis_sha256_persisted = $true

        authorizing_priority_decision_id_persisted = $true

        authorizing_evidence_fingerprint_persisted = $true

        provider_persisted = $true

        model_persisted = $true

        provider_response_id_persisted = $true

        local_paths_persisted = $false
    }


    feature_memory_boundary = [PSCustomObject]@{

        semantic_analysis_writes_feature_observation = $false

        semantic_analysis_writes_preference_signal = $false

        semantic_analysis_updates_learning_memory = $false

        objective_feature_memory_deferred_to = "09C8"

        preference_memory_deferred_to = "09C8"
    }


    legacy = [PSCustomObject]@{

        historical_video_analysis_get_preserved = $true

        legacy_video_analysis_new_generation_allowed = $false

        legacy_video_analysis_disable_code = "REFERENCE_VIDEO_ANALYSIS_LEGACY_WRITE_DISABLED_USE_SEMANTIC_ANALYSIS"

        legacy_video_analysis_may_call_vision_after_09C7 = $false

        legacy_video_analysis_may_write_feature_after_09C7 = $false

        existing_feature_observations_preserved = $true
    }


    output_record = [PSCustomObject]@{

        required_provenance = @(
            "semantic_analysis_id",
            "contract_version",
            "analyzer_version",
            "semantic_schema_version",
            "semantic_prompt_version",
            "reference_item_id",
            "reference_profile_id",
            "acquisition_id",
            "media_artifact_id",
            "source_sha256",
            "mechanical_analysis_id",
            "mechanical_analysis_sha256",
            "priority_decision_id",
            "priority_evidence_fingerprint",
            "vision_provider",
            "vision_model",
            "vision_response_id",
            "semantic_confidence",
            "semantic",
            "created_at",
            "copying_forbidden",
            "foundation_override_allowed",
            "semantic_analysis_sha256"
        )
    }
}


# ============================================================
# 4. ARCHITECTURAL ASSERTIONS
# ============================================================

$checks = @()


function Add-Check {

    param(
        [string]$Name,
        [bool]$Pass
    )

    $script:checks += [PSCustomObject]@{
        Check = $Name
        Pass  = $Pass
    }
}


Add-Check `
    "REQUEST_EXPLICIT_IDS_ONLY" `
    (
        $freeze.request.required_fields.Count -eq 4 `
        -and
        $freeze.request.implicit_latest_resolution_allowed -eq $false
    )


Add-Check `
    "NO_LOCAL_PATH_INPUT" `
    (
        $freeze.request.forbidden_fields -contains "local_media_ref"
    )


Add-Check `
    "NO_PREFERENCE_INPUT" `
    (
        $freeze.request.forbidden_fields -contains "preference_signal"
    )


Add-Check `
    "IDENTITY_EXCLUDES_ACQUISITION" `
    (
        $freeze.identity.explicitly_excluded -contains "acquisition_id"
    )


Add-Check `
    "IDENTITY_EXCLUDES_PRIORITY_AUTHORIZATION" `
    (
        $freeze.identity.explicitly_excluded -contains "priority_decision_id"
    )


Add-Check `
    "IDENTITY_EXCLUDES_LOCAL_PATH" `
    (
        $freeze.identity.explicitly_excluded -contains "local_media_ref"
    )


Add-Check `
    "RMA_IS_CANONICAL" `
    ($freeze.mechanical_policy.canonical_rma_is_source_of_truth -eq $true)


Add-Check `
    "NO_MECHANICAL_RECOMPUTE" `
    (
        $freeze.mechanical_policy.recalculate_mechanical -eq $false `
        -and
        $freeze.mechanical_policy.recalculate_cut_metrics -eq $false `
        -and
        $freeze.mechanical_policy.recalculate_audio_onsets -eq $false `
        -and
        $freeze.mechanical_policy.recalculate_color_stats -eq $false
    )


Add-Check `
    "NO_CONTACT_REGENERATION" `
    ($freeze.mechanical_policy.regenerate_contact_sheet -eq $false)


Add-Check `
    "PRIORITY_REQUIRED" `
    (
        $freeze.eligibility.current_priority_decision_required -eq $true `
        -and
        $freeze.eligibility.semantic_analysis_allowed_required -eq $true
    )


Add-Check `
    "PROVIDER_BOUNDARY_REQUIRED" `
    (
        $freeze.model_policy.provider_boundary_required -eq $true `
        -and
        $freeze.model_policy.engine_direct_http_provider_call_allowed -eq $false
    )


Add-Check `
    "MODEL_ONLY_AFTER_GATE" `
    ($freeze.model_policy.model_call_only_after_priority_allow -eq $true)


Add-Check `
    "SEMANTIC_DOES_NOT_WRITE_FEATURE_MEMORY" `
    (
        $freeze.feature_memory_boundary.semantic_analysis_writes_feature_observation -eq $false `
        -and
        $freeze.feature_memory_boundary.semantic_analysis_updates_learning_memory -eq $false
    )


Add-Check `
    "SEMANTIC_DOES_NOT_WRITE_PREFERENCE" `
    (
        $freeze.feature_memory_boundary.semantic_analysis_writes_preference_signal -eq $false
    )


Add-Check `
    "LEGACY_NEW_VISION_DISABLED" `
    (
        $freeze.legacy.legacy_video_analysis_new_generation_allowed -eq $false `
        -and
        $freeze.legacy.legacy_video_analysis_may_call_vision_after_09C7 -eq $false
    )


Add-Check `
    "LEGACY_HISTORY_PRESERVED" `
    ($freeze.legacy.historical_video_analysis_get_preserved -eq $true)


Add-Check `
    "SAFETY_COPYING_FORBIDDEN" `
    ($freeze.model_policy.copying_forbidden -eq $true)


Add-Check `
    "SAFETY_FOUNDATION_OVERRIDE_FALSE" `
    ($freeze.model_policy.foundation_override_allowed -eq $false)


Add-Check `
    "LOCAL_PATH_NOT_PERSISTED" `
    ($freeze.provenance.local_paths_persisted -eq $false)


Add-Check `
    "OBJECTIVE_FIELDS_NOT_MODEL_OUTPUT" `
    (
        $freeze.semantic_schema.objective_mechanical_fields_forbidden.Count `
        -ge 7
    )


$failed = @(
    $checks |
    Where-Object {
        $_.Pass -ne $true
    }
)


if ($failed.Count -ne 0) {

    throw ("SM3_09C7_A2_FREEZE_ASSERTION_FAILED:{0}" -f ($failed.Check -join ","))
}


# ============================================================
# 5. WRITE FREEZE REPORT
# ============================================================

$report = [PSCustomObject]@{

    freeze = $freeze

    checks = $checks
}


$report |
    ConvertTo-Json `
        -Depth 40 |
    Set-Content `
        -LiteralPath $ReportFile `
        -Encoding UTF8


# ============================================================
# 6. READBACK
# ============================================================

$readback = Get-Content `
    -LiteralPath $ReportFile `
    -Raw |
    ConvertFrom-Json


$readbackChecks = @(
    ($readback.freeze.phase -eq "09C7-A2"),
    ($readback.freeze.status -eq "FROZEN"),
    ($readback.freeze.contracts.semantic_analysis_contract -eq "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1"),
    ($readback.freeze.contracts.semantic_analyzer_version -eq "SM3_REFERENCE_SEMANTIC_ANALYZER_V1"),
    ($readback.freeze.contracts.semantic_schema_version -eq "SM3_REFERENCE_SEMANTIC_SCHEMA_V1"),
    ($readback.freeze.contracts.semantic_prompt_version -eq "SM3_REFERENCE_SEMANTIC_PROMPT_V1"),
    ($readback.freeze.contracts.semantic_provider_contract -eq "SM3_REFERENCE_SEMANTIC_PROVIDER_V1"),
    ($readback.freeze.request.required_fields.Count -eq 4),
    ($readback.freeze.request.implicit_latest_resolution_allowed -eq $false),
    ($readback.freeze.mechanical_policy.recalculate_mechanical -eq $false),
    ($readback.freeze.mechanical_policy.regenerate_contact_sheet -eq $false),
    ($readback.freeze.feature_memory_boundary.semantic_analysis_writes_feature_observation -eq $false),
    ($readback.freeze.legacy.legacy_video_analysis_new_generation_allowed -eq $false),
    ($readback.freeze.model_policy.copying_forbidden -eq $true),
    ($readback.freeze.model_policy.foundation_override_allowed -eq $false)
)


$readbackValid = (
    $readbackChecks -notcontains $false
)


if (-not $readbackValid) {
    throw "SM3_09C7_A2_REPORT_READBACK_INVALID"
}


# ============================================================
# 7. PROVE ZERO OPERATIONAL MUTATION
# ============================================================

$hostShaAfter = (
    Get-FileHash `
        -LiteralPath $worker `
        -Algorithm SHA256
).Hash.ToLower()


$runtimeShaAfterLine = (
    docker exec `
        $container `
        sha256sum `
        /app/worker_service.py |
    Out-String
).Trim()


$runtimeShaAfter = (
    ($runtimeShaAfterLine -split "\s+")[0]
).Trim().ToLower()


$priorityAfter = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_priority_decisions -type f -name 'RPD_*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$videoAfter = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_video_analyses -type f -name '*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$featureAfter = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_features -type f -name '*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$semanticAfter = [int]((
    docker exec `
        $container `
        sh -lc `
        "find /data/media/production_state/reference_semantic_analyses -type f -name 'RSA_*.json' 2>/dev/null | wc -l" |
    Out-String
).Trim())


$stateChecks = @(
    ($hostShaAfter -eq $hostShaBefore),
    ($runtimeShaAfter -eq $runtimeShaBefore),
    ($priorityAfter -eq $priorityBefore),
    ($videoAfter -eq $videoBefore),
    ($featureAfter -eq $featureBefore),
    ($semanticAfter -eq $semanticBefore)
)


$stateUnchanged = (
    $stateChecks -notcontains $false
)


if (-not $stateUnchanged) {
    throw "SM3_09C7_A2_OPERATIONAL_STATE_CHANGED"
}


# ============================================================
# 8. SUMMARY
# ============================================================

Write-Host "`n=== 09C7-A2 FREEZE ===" -ForegroundColor Yellow

Write-Host "SEMANTIC_CONTRACT=SM3_REFERENCE_SEMANTIC_ANALYSIS_V1"
Write-Host "SEMANTIC_ANALYZER=SM3_REFERENCE_SEMANTIC_ANALYZER_V1"
Write-Host "SEMANTIC_SCHEMA=SM3_REFERENCE_SEMANTIC_SCHEMA_V1"
Write-Host "SEMANTIC_PROMPT=SM3_REFERENCE_SEMANTIC_PROMPT_V1"
Write-Host "SEMANTIC_PROVIDER=SM3_REFERENCE_SEMANTIC_PROVIDER_V1"

Write-Host ""
Write-Host "REQUEST_REQUIRED_IDS=4"
Write-Host "LOCAL_MEDIA_REF_ALLOWED=False"
Write-Host "PREFERENCE_SIGNAL_ALLOWED=False"
Write-Host "IMPLICIT_LATEST_ALLOWED=False"

Write-Host ""
Write-Host "RECALCULATE_MECHANICAL=False"
Write-Host "REGENERATE_CONTACT_SHEET=False"
Write-Host "SEMANTIC_WRITES_FEATURE_OBSERVATION=False"
Write-Host "SEMANTIC_WRITES_PREFERENCE=False"
Write-Host "LEGACY_NEW_VIDEO_ANALYSIS_ALLOWED=False"

Write-Host ""
Write-Host "FREEZE_CHECK_COUNT=$($checks.Count)"
Write-Host "FREEZE_PASS_COUNT=$($checks.Count)"
Write-Host "FREEZE_FAIL_COUNT=0"

Write-Host ""
Write-Host "HOST_SHA=$hostShaBefore->$hostShaAfter"
Write-Host "RUNTIME_SHA=$runtimeShaBefore->$runtimeShaAfter"
Write-Host "PRIORITY_COUNT=$priorityBefore->$priorityAfter"
Write-Host "VIDEO_COUNT=$videoBefore->$videoAfter"
Write-Host "FEATURE_COUNT=$featureBefore->$featureAfter"
Write-Host "SEMANTIC_COUNT=$semanticBefore->$semanticAfter"
Write-Host "STATE_UNCHANGED=$stateUnchanged"

Write-Host ""
Write-Host "REPORT=$ReportFile"
Write-Host "REPORT_READBACK_VALID=$readbackValid"


Write-Host `
    "`nSM3_09C7_A2_SEMANTIC_CONTRACT_FREEZE_PASS" `
    -ForegroundColor Green

