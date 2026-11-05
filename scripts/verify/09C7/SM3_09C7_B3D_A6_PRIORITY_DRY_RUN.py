from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


ITEM_ID = "RI_500f8618a5796dc9b1fbded2f3bfff2e"

ACQUISITION_ID = "RM_9c95d071c89707fefd62105c9eb05452"

SOURCE_SHA = (
    "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"
)

MECHANICAL_ID = "RMA_0072a9689863b956298a9ec34f01bd0e"

REPORT = Path(
    "/tmp/SM3_09C7_B3D_A6_PRIORITY_DRY_RUN.json"
)


# ============================================================
# 1. ACTIVE ITEM
# ============================================================

item = ws._require_reference_item_active(
    ITEM_ID
)


# ============================================================
# 2. EXACT V2 ACQUISITION
# ============================================================

profile_id = item[
    "reference_profile_id"
]

acquisition_path = ws._reference_media_path(
    profile_id,
    ITEM_ID,
    ACQUISITION_ID,
)

if not acquisition_path.exists():
    raise RuntimeError(
        "TARGET_ACQUISITION_NOT_FOUND"
    )

acquisition = ws._verify_reference_media_acquisition(
    json.loads(
        acquisition_path.read_text(
            encoding="utf-8"
        )
    )
)

if acquisition.get("reference_item_id") != ITEM_ID:
    raise RuntimeError(
        "ACQUISITION_ITEM_MISMATCH"
    )

if acquisition.get("contract_version") != "SM3_REFERENCE_MEDIA_ACQUISITION_V2":
    raise RuntimeError(
        "ACQUISITION_NOT_V2"
    )


# ============================================================
# 3. SOURCE / CAS
# ============================================================

source, media_artifact = (
    ws._resolve_reference_acquisition_source(
        acquisition
    )
)

source_sha = ws.sha256_file(
    source
).lower()

if source_sha != SOURCE_SHA:
    raise RuntimeError(
        "SOURCE_SHA_UNEXPECTED:"
        + source_sha
    )

if source_sha != str(
    acquisition.get(
        "source_sha256"
    )
    or ""
).lower():
    raise RuntimeError(
        "ACQUISITION_SHA_MISMATCH"
    )


# ============================================================
# 4. MECHANICAL ANALYSIS
# ============================================================

mechanical_path = (
    ws._reference_mechanical_analysis_path(
        source_sha,
        MECHANICAL_ID,
    )
)

if not mechanical_path.exists():
    raise RuntimeError(
        "MECHANICAL_NOT_FOUND"
    )

mechanical = (
    ws._verify_reference_mechanical_analysis(
        json.loads(
            mechanical_path.read_text(
                encoding="utf-8"
            )
        )
    )
)

if str(
    mechanical.get(
        "source_sha256"
    )
    or ""
).lower() != source_sha:
    raise RuntimeError(
        "MECHANICAL_SOURCE_MISMATCH"
    )


# ============================================================
# 5. EXACT ENGINE EVIDENCE
# ============================================================

evidence = (
    ws._reference_priority_current_evidence(
        item,
        mechanical,
    )
)

priority_score, effective_weights = (
    ws._reference_priority_score(
        evidence
    )
)


# ============================================================
# 6. DERIVE DECISION USING RUNTIME THRESHOLDS
# ============================================================

if (
    priority_score
    >= ws.REFERENCE_PRIORITY_SEMANTIC_THRESHOLD
):
    expected_decision = "SEMANTIC_ANALYSIS"

elif (
    priority_score
    >= ws.REFERENCE_PRIORITY_DEFER_THRESHOLD
):
    expected_decision = "DEFER"

else:
    expected_decision = "SKIP"


semantic_allowed = (
    expected_decision
    == "SEMANTIC_ANALYSIS"
)


# ============================================================
# 7. EXPECTED DETERMINISTIC RPD ID
# ============================================================

identity = {
    "reference_item_id":
        ITEM_ID,

    "source_sha256":
        source_sha,

    "mechanical_analysis_id":
        mechanical.get(
            "mechanical_analysis_id"
        ),

    "mechanical_analysis_sha256":
        mechanical.get(
            "mechanical_analysis_sha256"
        ),

    "evidence_fingerprint":
        evidence[
            "evidence_fingerprint"
        ],

    "priority_engine_version":
        ws.REFERENCE_PRIORITY_ENGINE_VERSION,
}


expected_rpd_id = (
    "RPD_"
    + ws._canonical_sha256(
        identity
    )[:32]
)


# ============================================================
# 8. CHECK WHETHER THIS RPD ALREADY EXISTS
# ============================================================

expected_path = (
    ws._reference_priority_decision_path(
        profile_id,
        ITEM_ID,
        expected_rpd_id,
    )
)

already_exists = (
    expected_path.exists()
)


# ============================================================
# 9. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3D-A6",

    "status":
        "PRIORITY_ENGINE_DRY_RUN_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "priority_engine_version":
        ws.REFERENCE_PRIORITY_ENGINE_VERSION,

    "reference_item_id":
        ITEM_ID,

    "acquisition_id":
        ACQUISITION_ID,

    "acquisition_contract":
        acquisition.get(
            "contract_version"
        ),

    "media_artifact_id":
        acquisition.get(
            "media_artifact_id"
        ),

    "source_sha256":
        source_sha,

    "mechanical_analysis_id":
        mechanical.get(
            "mechanical_analysis_id"
        ),

    "mechanical_analysis_sha256":
        mechanical.get(
            "mechanical_analysis_sha256"
        ),

    "evidence":
        evidence,

    "effective_weights":
        effective_weights,

    "priority_score":
        priority_score,

    "semantic_threshold":
        ws.REFERENCE_PRIORITY_SEMANTIC_THRESHOLD,

    "defer_threshold":
        ws.REFERENCE_PRIORITY_DEFER_THRESHOLD,

    "expected_decision":
        expected_decision,

    "expected_eligibility":
        "ELIGIBLE",

    "expected_semantic_analysis_allowed":
        semantic_allowed,

    "expected_priority_decision_id":
        expected_rpd_id,

    "expected_priority_decision_path":
        str(
            expected_path
        ),

    "priority_decision_already_exists":
        already_exists,

    "production_write_performed":
        False,

    "priority_api_called":
        False,

    "semantic_api_called":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


# ============================================================
# 10. CONSOLE
# ============================================================

print(
    "=== SM3 09C7-B3D-A6 PRIORITY ENGINE DRY RUN ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)

print(
    "ENGINE_VERSION="
    + str(
        ws.REFERENCE_PRIORITY_ENGINE_VERSION
    )
)

print(
    "ITEM_ID="
    + ITEM_ID
)

print(
    "ACQUISITION_ID="
    + ACQUISITION_ID
)

print(
    "ACQUISITION_CONTRACT="
    + str(
        acquisition.get(
            "contract_version"
        )
    )
)

print(
    "MEDIA_ARTIFACT_ID="
    + str(
        acquisition.get(
            "media_artifact_id"
        )
    )
)

print(
    "SOURCE_SHA="
    + source_sha
)

print(
    "MECHANICAL_ID="
    + str(
        mechanical.get(
            "mechanical_analysis_id"
        )
    )
)

print(
    "MECHANICAL_SHA="
    + str(
        mechanical.get(
            "mechanical_analysis_sha256"
        )
    )
)


print(
    "\n=== CURRENT EVIDENCE ==="
)

print(
    json.dumps(
        evidence,
        indent=2,
        ensure_ascii=False,
    )
)


print(
    "\n=== EFFECTIVE WEIGHTS ==="
)

print(
    json.dumps(
        effective_weights,
        indent=2,
        ensure_ascii=False,
    )
)


print(
    "\nPRIORITY_SCORE="
    + str(
        priority_score
    )
)

print(
    "SEMANTIC_THRESHOLD="
    + str(
        ws.REFERENCE_PRIORITY_SEMANTIC_THRESHOLD
    )
)

print(
    "DEFER_THRESHOLD="
    + str(
        ws.REFERENCE_PRIORITY_DEFER_THRESHOLD
    )
)

print(
    "EXPECTED_ELIGIBILITY=ELIGIBLE"
)

print(
    "EXPECTED_DECISION="
    + expected_decision
)

print(
    "EXPECTED_SEMANTIC_ALLOWED="
    + str(
        semantic_allowed
    )
)

print(
    "EVIDENCE_FINGERPRINT="
    + str(
        evidence[
            "evidence_fingerprint"
        ]
    )
)

print(
    "EXPECTED_RPD_ID="
    + expected_rpd_id
)

print(
    "EXPECTED_RPD_ALREADY_EXISTS="
    + str(
        already_exists
    )
)


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
)

print(
    "PRIORITY_API_CALLED=False"
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
    "REPORT="
    + str(
        REPORT
    )
)

print(
    "SM3_09C7_B3D_A6_PRIORITY_ENGINE_DRY_RUN_COMPLETE"
)
