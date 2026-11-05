from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


PARENT = Path(sys.argv[1])
REVISED = Path(sys.argv[2])
REPORT = Path(sys.argv[3])


EXPECTED_PARENT_SHA = (
    "2f917c1854f45bd8dedae4653a7c62ee"
    "5ecd192dce803cb3ce5ffc302058ad70"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def write_json(path: Path, value):
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


parent_sha = sha256(
    PARENT
)


if parent_sha != EXPECTED_PARENT_SHA:
    raise SystemExit(
        "A4_R2_D1_PARENT_SHA_MISMATCH:"
        + parent_sha
    )


parent = load_json(
    PARENT
)

revised = copy.deepcopy(
    parent
)


previous_revision = copy.deepcopy(
    revised.get(
        "revision_metadata",
        {}
    )
)


revised[
    "revision_metadata"
] = {
    "revision":
        "R3",

    "amendment_phase":
        "09C7-B3E-A4-R2-D1",

    "parent_revised_freeze_sha256":
        parent_sha,

    "previous_revision":
        previous_revision.get(
            "revision"
        ),

    "reason":
        (
            "Freeze deterministic semantic error precedence "
            "for records violating multiple temporal invariants"
        ),

    "production_source_modified":
        False,

    "production_state_modified":
        False,
}


temporal = revised[
    "temporal_validity"
]


temporal[
    "timestamp_validation_precedes_semantic_validation"
] = True


temporal[
    "semantic_error_precedence"
] = [
    "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE",
    "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE",
    "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_AFTER_OBSERVATION",
    "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED",
]


temporal[
    "multiple_semantic_violation_behavior"
] = (
    "FIRST_MATCH_BY_FROZEN_PRECEDENCE"
)


temporal[
    "source_after_observation_checked_after_as_of_bounds"
] = True


temporal[
    "backward_compatible_error_semantics_required"
] = True


temporal[
    "age_calculation_after_all_semantic_validation"
] = True


temporal[
    "evidence_temporal_order"
] = (
    "source_date <= observed_at <= as_of"
)


# The causal invariant remains mandatory.
# Only error selection for overlapping invalid states is frozen.

temporal[
    "causal_invariant_relaxed"
] = False


revised[
    "rollout"
] = [
    "A4_R2_F1_TEMPORAL_ENGINE_ERROR_PRECEDENCE_REMEDIATION",
    "A4_A2_TEMPORAL_ADVERSARIAL_REATTACK",
    "A4_A3_INTEGRATION_PREFLIGHT",
    "A5_HYPOTHESIS_STORE",
    "A6_PREDICTION_OUTCOME_AND_ERROR",
    "A7_DRIFT_ENGINE",
    "A8_EXPERIMENT_STORE",
    "A9_TEMPORAL_SIGNATURE",
    "A10_SNAPSHOT_V2",
    "A11_METRIC_ACQUISITION_BINDING",
    "A12_REAL_SIGNAL_POPULATION",
    "A13_TASTE_MODEL_FREEZE",
    "A14_STRATEGY_FUSION",
]


write_json(
    REVISED,
    revised,
)


revised_sha = sha256(
    REVISED
)


loaded = load_json(
    REVISED
)

tv = loaded[
    "temporal_validity"
]


expected_precedence = [
    "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE",
    "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE",
    "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_AFTER_OBSERVATION",
    "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED",
]


checks = {
    "TIMESTAMP_VALIDATION_FIRST":
        tv.get(
            "timestamp_validation_precedes_semantic_validation"
        )
        is True,

    "ERROR_PRECEDENCE_EXACT":
        tv.get(
            "semantic_error_precedence"
        )
        == expected_precedence,

    "MULTIPLE_VIOLATION_FIRST_MATCH":
        tv.get(
            "multiple_semantic_violation_behavior"
        )
        == "FIRST_MATCH_BY_FROZEN_PRECEDENCE",

    "AS_OF_BOUNDS_BEFORE_CAUSAL_ORDER":
        tv.get(
            "source_after_observation_checked_after_as_of_bounds"
        )
        is True,

    "BACKWARD_COMPATIBILITY_REQUIRED":
        tv.get(
            "backward_compatible_error_semantics_required"
        )
        is True,

    "CAUSAL_ORDER_STILL_FROZEN":
        tv.get(
            "evidence_temporal_order"
        )
        == "source_date <= observed_at <= as_of",

    "CAUSAL_INVARIANT_NOT_RELAXED":
        tv.get(
            "causal_invariant_relaxed"
        )
        is False,

    "AGE_AFTER_SEMANTIC_VALIDATION":
        tv.get(
            "age_calculation_after_all_semantic_validation"
        )
        is True,
}


if not all(
    checks.values()
):
    raise SystemExit(
        "A4_R2_D1_CONTRACT_VERIFY_FAILED"
    )


report = {
    "phase":
        "09C7-B3E-A4-R2-D1",

    "status":
        "TEMPORAL_ERROR_PRECEDENCE_CONTRACT_FROZEN",

    "parent_freeze_sha256":
        parent_sha,

    "revised_freeze_sha256":
        revised_sha,

    "contract_checks":
        checks,

    "semantic_error_precedence":
        expected_precedence,

    "causal_invariant_preserved":
        True,

    "backward_compatible_error_semantics_required":
        True,

    "failed_candidate_must_remain_immutable":
        True,

    "runtime_integration_allowed":
        False,

    "next_gate":
        (
            "09C7-B3E-A4-R2-F1_"
            "TEMPORAL_ENGINE_ERROR_PRECEDENCE_REMEDIATION"
        ),

    "production_source_modified":
        False,

    "production_state_modified":
        False,

    "route_called":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


write_json(
    REPORT,
    report,
)


print(
    "=== TEMPORAL ERROR PRECEDENCE CONTRACT ==="
)


for name,value in checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print("")
print(
    "SEMANTIC_ERROR_PRECEDENCE="
    + " > ".join(
        expected_precedence
    )
)

print(
    "CAUSAL_INVARIANT_PRESERVED=True"
)

print(
    "BACKWARD_COMPATIBLE_ERROR_SEMANTICS_REQUIRED=True"
)

print(
    "RUNTIME_INTEGRATION_ALLOWED=False"
)

print(
    "NEXT_GATE="
    "09C7-B3E-A4-R2-F1_"
    "TEMPORAL_ENGINE_ERROR_PRECEDENCE_REMEDIATION"
)

print(
    "REVISED_FREEZE_SHA256="
    + revised_sha
)

print(
    "SM3_09C7_B3E_A4_R2_D1_TEMPORAL_ERROR_PRECEDENCE_CONTRACT_FREEZE_COMPLETE"
)
