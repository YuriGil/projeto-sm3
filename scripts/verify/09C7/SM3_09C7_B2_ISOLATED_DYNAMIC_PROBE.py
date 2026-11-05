from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(
    0,
    "/app",
)

from fastapi import HTTPException

import worker_service as ws


EXPECTED_SOURCE_SHA = (
    "8ca08d498d41cb732341c368d8aaa03e"
    "252a4c6eeef81a430201199a2e05f882"
)

REPORT = Path(
    "/tmp/SM3_09C7_B2_ISOLATED_DYNAMIC_PROBE.json"
)


checks = []


def add(
    name: str,
    passed: bool,
    detail="",
) -> None:

    checks.append({
        "check":
            name,

        "pass":
            bool(passed),

        "detail":
            str(detail),
    })


# ============================================================
# 1. IMAGE SOURCE IDENTITY
# ============================================================

worker_path = Path(
    "/app/worker_service.py"
)

source_sha = hashlib.sha256(
    worker_path.read_bytes()
).hexdigest()


add(
    "IMAGE_SOURCE_SHA_MATCH",
    source_sha
    == EXPECTED_SOURCE_SHA,
    source_sha,
)


add(
    "WORKER_VERSION_2_24_0",
    ws.WORKER_VERSION
    == "2.24.0",
    ws.WORKER_VERSION,
)


# ============================================================
# 2. CONTRACT EXPORTS
# ============================================================

add(
    "SEMANTIC_CONTRACT_V1",
    ws.REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION
    == "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",
)


add(
    "SEMANTIC_ANALYZER_V1",
    ws.REFERENCE_SEMANTIC_ANALYZER_VERSION
    == "SM3_REFERENCE_SEMANTIC_ANALYZER_V1",
)


add(
    "SEMANTIC_SCHEMA_V1",
    ws.REFERENCE_SEMANTIC_SCHEMA_VERSION
    == "SM3_REFERENCE_SEMANTIC_SCHEMA_V1",
)


add(
    "SEMANTIC_PROMPT_V1",
    ws.REFERENCE_SEMANTIC_PROMPT_VERSION
    == "SM3_REFERENCE_SEMANTIC_PROMPT_V1",
)


add(
    "SEMANTIC_PROVIDER_CONTRACT_V1",
    ws.REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION
    == "SM3_REFERENCE_SEMANTIC_PROVIDER_V1",
)


add(
    "SEMANTIC_STORAGE_ROOT_CREATED",
    (
        ws.PRODUCTION_REFERENCE_SEMANTIC_ANALYSES.exists()
        and
        ws.PRODUCTION_REFERENCE_SEMANTIC_ANALYSES.is_dir()
    ),
    ws.PRODUCTION_REFERENCE_SEMANTIC_ANALYSES,
)


# ============================================================
# 3. REQUEST MODEL
# ============================================================

request_model = (
    ws.ReferenceSemanticAnalysisRequest
)


if hasattr(
    request_model,
    "model_fields",
):
    request_fields = list(
        request_model.model_fields.keys()
    )

else:
    request_fields = list(
        request_model.__fields__.keys()
    )


expected_request_fields = [
    "reference_item_id",
    "acquisition_id",
    "mechanical_analysis_id",
    "priority_decision_id",
]


add(
    "REQUEST_FIELDS_EXACT",
    request_fields
    == expected_request_fields,
    request_fields,
)


# ============================================================
# 4. ROUTES REGISTERED IN REAL FASTAPI APP
# ============================================================

def route_exists(
    path: str,
    method: str,
) -> bool:

    for route in ws.app.routes:

        if getattr(
            route,
            "path",
            None,
        ) != path:
            continue

        methods = (
            getattr(
                route,
                "methods",
                set(),
            )
            or set()
        )

        if method.upper() in methods:
            return True

    return False


add(
    "POST_SEMANTIC_ROUTE_REGISTERED",
    route_exists(
        "/production/reference-corpus/semantic-analysis",
        "POST",
    ),
)


add(
    "GET_SEMANTIC_LIST_ROUTE_REGISTERED",
    route_exists(
        "/production/reference-corpus/item/{item_id}/semantic-analyses",
        "GET",
    ),
)


add(
    "GET_SEMANTIC_LATEST_ROUTE_REGISTERED",
    route_exists(
        "/production/reference-corpus/item/{item_id}/semantic-analysis/latest",
        "GET",
    ),
)


# ============================================================
# 5. BUILD SYNTHETIC VALID RSA
# ============================================================

source_hash = "1" * 64

mechanical_hash = "2" * 64

priority_fingerprint = "3" * 64


semantic = {
    "hook_duration_s":
        None,

    "camera_motion":
        "UNKNOWN",

    "subject_scale":
        "UNKNOWN",

    "subject_coverage":
        None,

    "text_density":
        "UNKNOWN",

    "text_position":
        "UNKNOWN",

    "transition_style":
        "UNKNOWN",

    "speed_ramp":
        "UNKNOWN",

    "identity_usage":
        "UNKNOWN",

    "tattoo_presentation":
        "UNKNOWN",

    "story_structure":
        "UNKNOWN",

    "analysis_confidence":
        88,

    "notes":
        "UNKNOWN",
}


identity = {
    "reference_item_id":
        "RI_B2_SYNTHETIC",

    "source_sha256":
        source_hash,

    "mechanical_analysis_id":
        "RMA_B2_SYNTHETIC",

    "mechanical_analysis_sha256":
        mechanical_hash,

    "semantic_analyzer_version":
        ws.REFERENCE_SEMANTIC_ANALYZER_VERSION,

    "semantic_schema_version":
        ws.REFERENCE_SEMANTIC_SCHEMA_VERSION,

    "semantic_prompt_version":
        ws.REFERENCE_SEMANTIC_PROMPT_VERSION,

    "vision_provider":
        ws.VISION_PROVIDER,

    "vision_model":
        ws.VISION_MODEL,
}


analysis_id = (
    "RSA_"
    + ws._canonical_sha256(
        identity
    )[:32]
)


record = {
    "ok":
        True,

    "semantic_analysis_id":
        analysis_id,

    "contract_version":
        ws.REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION,

    "analyzer_version":
        ws.REFERENCE_SEMANTIC_ANALYZER_VERSION,

    "semantic_schema_version":
        ws.REFERENCE_SEMANTIC_SCHEMA_VERSION,

    "semantic_prompt_version":
        ws.REFERENCE_SEMANTIC_PROMPT_VERSION,

    "provider_contract_version":
        ws.REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,

    "reference_item_id":
        "RI_B2_SYNTHETIC",

    "reference_profile_id":
        "RP_B2_SYNTHETIC",

    "acquisition_id":
        "RM_B2_SYNTHETIC",

    "media_artifact_id":
        "MA_B2_SYNTHETIC",

    "source_sha256":
        source_hash,

    "mechanical_analysis_id":
        "RMA_B2_SYNTHETIC",

    "mechanical_analysis_sha256":
        mechanical_hash,

    "priority_decision_id":
        "RPD_B2_SYNTHETIC",

    "priority_evidence_fingerprint":
        priority_fingerprint,

    "vision_provider":
        ws.VISION_PROVIDER,

    "vision_model":
        ws.VISION_MODEL,

    "vision_response_id":
        None,

    "semantic_confidence":
        88,

    "semantic":
        semantic,

    "created_at":
        "2026-09-23T20:00:00+00:00",

    "copying_forbidden":
        True,

    "foundation_override_allowed":
        False,
}


record[
    "semantic_analysis_sha256"
] = ws._canonical_sha256(
    record
)


# ============================================================
# 6. VALID RECORD MUST PASS
# ============================================================

try:

    verified = (
        ws._verify_reference_semantic_analysis(
            copy.deepcopy(
                record
            )
        )
    )

    add(
        "VALID_RSA_ACCEPTED",
        (
            verified[
                "semantic_analysis_id"
            ]
            == analysis_id
        ),
        verified.get(
            "semantic_analysis_id"
        ),
    )

except Exception as exc:

    add(
        "VALID_RSA_ACCEPTED",
        False,
        (
            type(exc).__name__
            + ":"
            + str(exc)
        ),
    )


# ============================================================
# 7. FAIL-CLOSED NEGATIVE TEST HELPER
# ============================================================

def expect_409(
    name,
    mutate,
    expected_detail,
):

    candidate = copy.deepcopy(
        record
    )

    mutate(
        candidate
    )

    try:

        ws._verify_reference_semantic_analysis(
            candidate
        )

    except HTTPException as exc:

        add(
            name,
            (
                exc.status_code == 409
                and
                exc.detail == expected_detail
            ),
            (
                str(exc.status_code)
                + ":"
                + str(exc.detail)
            ),
        )

        return

    except Exception as exc:

        add(
            name,
            False,
            (
                type(exc).__name__
                + ":"
                + str(exc)
            ),
        )

        return

    add(
        name,
        False,
        "NO_EXCEPTION",
    )


# ============================================================
# 8. PROVIDER CONTRACT FAIL-CLOSED
# ============================================================

expect_409(
    "INVALID_PROVIDER_CONTRACT_REJECTED",
    lambda rec: rec.__setitem__(
        "provider_contract_version",
        "BROKEN_PROVIDER_CONTRACT",
    ),
    "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_MISMATCH",
)


# ============================================================
# 9. DETERMINISTIC IDENTITY FAIL-CLOSED
# ============================================================

expect_409(
    "INVALID_RSA_IDENTITY_REJECTED",
    lambda rec: rec.__setitem__(
        "vision_model",
        "DIFFERENT_MODEL",
    ),
    "REFERENCE_SEMANTIC_ANALYSIS_IDENTITY_MISMATCH",
)


# ============================================================
# 10. PAYLOAD ADDITIONAL FIELD FAIL-CLOSED
# ============================================================

def mutate_payload_extra(
    rec,
):

    rec["semantic"][
        "unexpected_field"
    ] = "INVALID"


expect_409(
    "INVALID_SEMANTIC_FIELDS_REJECTED",
    mutate_payload_extra,
    "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID",
)


# ============================================================
# 11. CONFIDENCE CROSS-CHECK FAIL-CLOSED
# ============================================================

expect_409(
    "CONFIDENCE_MISMATCH_REJECTED",
    lambda rec: rec.__setitem__(
        "semantic_confidence",
        87,
    ),
    "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH",
)


# ============================================================
# 12. LOCAL PATH PERSISTENCE FAIL-CLOSED
# ============================================================

expect_409(
    "LOCAL_PATH_PERSISTENCE_REJECTED",
    lambda rec: rec.__setitem__(
        "local_media_ref",
        "/tmp/forbidden.mp4",
    ),
    "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD:local_media_ref",
)


# ============================================================
# 13. COPYING POLICY FAIL-CLOSED
# ============================================================

expect_409(
    "COPYING_POLICY_VIOLATION_REJECTED",
    lambda rec: rec.__setitem__(
        "copying_forbidden",
        False,
    ),
    "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID",
)


# ============================================================
# 14. CANONICAL RECORD HASH FAIL-CLOSED
# ============================================================

expect_409(
    "RECORD_HASH_MUTATION_REJECTED",
    lambda rec: rec.__setitem__(
        "created_at",
        "2026-09-23T21:00:00+00:00",
    ),
    "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED",
)


# ============================================================
# 15. PROVIDER BOUNDARY EXISTS BUT IS NEVER CALLED HERE
# ============================================================

add(
    "PROVIDER_BOUNDARY_PRESENT",
    callable(
        ws._reference_semantic_provider_analyze
    ),
)


add(
    "LEGACY_VIDEO_FUNCTION_PRESENT",
    callable(
        ws.production_reference_video_analysis
    ),
)


# ============================================================
# RESULT
# ============================================================

failed = [
    row
    for row in checks
    if not row["pass"]
]


report = {
    "phase":
        "09C7-B2",

    "environment":
        "ISOLATED_EPHEMERAL_CONTAINER",

    "image_source_sha256":
        source_sha,

    "worker_version":
        ws.WORKER_VERSION,

    "check_count":
        len(checks),

    "pass_count":
        len(checks)
        - len(failed),

    "fail_count":
        len(failed),

    "failed_checks":[
        row["check"]
        for row in failed
    ],

    "valid_rsa_id":
        analysis_id,

    "request_fields":
        request_fields,

    "production_volume_mounted":
        False,

    "semantic_api_called":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "production_record_created":
        False,

    "checks":
        checks,

    "all_passed":
        not failed,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== SM3 09C7-B2 ISOLATED DYNAMIC CHECKS ==="
)


for row in checks:

    print(
        (
            row["check"]
            + "="
            + str(
                row["pass"]
            )
            + (
                (
                    " | "
                    + row["detail"]
                )
                if row["detail"]
                else ""
            )
        )
    )


print()

print(
    "CHECK_COUNT="
    + str(
        len(checks)
    )
)

print(
    "PASS_COUNT="
    + str(
        len(checks)
        - len(failed)
    )
)

print(
    "FAIL_COUNT="
    + str(
        len(failed)
    )
)

print(
    "FAILED_CHECKS="
    + ",".join(
        row["check"]
        for row in failed
    )
)

print(
    "IMAGE_SOURCE_SHA256="
    + source_sha
)

print(
    "WORKER_VERSION="
    + ws.WORKER_VERSION
)

print(
    "VALID_RSA_ID="
    + analysis_id
)

print(
    "PRODUCTION_VOLUME_MOUNTED=False"
)

print(
    "SEMANTIC_API_CALLED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "PRODUCTION_RECORD_CREATED=False"
)

print(
    "REPORT="
    + str(REPORT)
)


if failed:

    print(
        "SM3_09C7_B2_ISOLATED_DYNAMIC_PROBE_FAIL"
    )

    sys.exit(1)


print(
    "SM3_09C7_B2_ISOLATED_DYNAMIC_PROBE_PASS"
)

sys.exit(0)
