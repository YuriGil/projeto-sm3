from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ORIGINAL = Path(sys.argv[1])
ATTACK = Path(sys.argv[2])
REVISED = Path(sys.argv[3])
AMENDMENT = Path(sys.argv[4])


EXPECTED_ORIGINAL_SHA = (
    "6836d4b91db168dcfba74f60314d1081"
    "880686b60262d6c52831c004aa828535"
)

EXPECTED_ATTACK_SHA = (
    "4020ef0c5b6e2a84a00cd318812d994c"
    "ce4d1b9ca790d0d2f559c033fccf11c5"
)


def file_sha256(path: Path) -> str:
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


original_sha = file_sha256(
    ORIGINAL
)

attack_sha = file_sha256(
    ATTACK
)


if original_sha != EXPECTED_ORIGINAL_SHA:
    raise SystemExit(
        "ORIGINAL_FREEZE_SHA_MISMATCH:"
        + original_sha
    )


if attack_sha != EXPECTED_ATTACK_SHA:
    raise SystemExit(
        "ATTACK_REPORT_SHA_MISMATCH:"
        + attack_sha
    )


freeze = load_json(
    ORIGINAL
)

attack = load_json(
    ATTACK
)


attack_checks = [
    attack.get("status")
    == "STATIC_CONTRACT_ATTACK_COMPLETE",

    attack.get("attack_count")
    == 31,

    attack.get("passed_count")
    == 20,

    attack.get("critical_gap_count")
    == 0,

    attack.get("high_gap_count")
    == 11,

    attack.get("implementation_ready")
    is False,
]


if not all(
    attack_checks
):
    raise SystemExit(
        "ATTACK_REPORT_PRECONDITION_FAILED"
    )


# ============================================================
# REVISION METADATA
# ============================================================

freeze["revision_metadata"] = {
    "revision":
        "R1",

    "amendment_phase":
        "09C7-B3E-A3-R1-R1",

    "parent_freeze_sha256":
        original_sha,

    "static_attack_sha256":
        attack_sha,

    "critical_gaps_before":
        0,

    "high_gaps_before":
        11,

    "purpose":
        (
            "Resolve all HIGH gaps found by "
            "09C7-B3E-A3 before implementation"
        ),

    "production_source_modified":
        False,

    "production_state_modified":
        False,
}


# ============================================================
# C002
# CONFIDENCE RANGE
# ============================================================

hypothesis = freeze[
    "hypothesis"
]

hypothesis[
    "source_confidence_range"
] = [
    0,
    100,
]

hypothesis[
    "effective_confidence_range"
] = [
    0,
    100,
]

hypothesis[
    "effective_confidence_must_not_exceed_source_confidence"
] = True


# ============================================================
# E002
# SUPPORT / COUNTER OVERLAP
# ============================================================

hypothesis[
    "support_counter_overlap_forbidden"
] = True

hypothesis[
    "evidence_role_overlap_forbidden"
] = True

hypothesis[
    "signal_role_overlap_forbidden"
] = True


# ============================================================
# E003
# HYPOTHESIS / REVISION IDENTITY
# ============================================================

hypothesis[
    "identity_rule"
] = {
    "hypothesis_id_algorithm":
        "CANONICAL_SHA256_PREFIX_32",

    "hypothesis_id_fields": [
        "platform",
        "surface",
        "claim_family",
        "normalized_statement",
        "target_behavior",
    ],

    "statement_normalization": [
        "TRIM",
        "COLLAPSE_INTERNAL_WHITESPACE",
    ],

    "revision_type":
        "POSITIVE_MONOTONIC_INTEGER",

    "revision_minimum":
        1,

    "revision_must_increase":
        True,

    "revision_identity_fields": [
        "hypothesis_id",
        "revision",
        "supporting_evidence_ids_sorted",
        "counterevidence_ids_sorted",
        "supporting_signal_ids_sorted",
        "counter_signal_ids_sorted",
        "source_confidence",
        "effective_confidence",
        "status",
    ],

    "timestamps_excluded_from_identity":
        True,

    "revision_record_immutable":
        True,
}


# ============================================================
# F002
# PREDICTION OUTCOME CONTRACT
# ============================================================

freeze[
    "v2"
][
    "prediction_outcome"
] = (
    "SM3_PLATFORM_PREDICTION_OUTCOME_V1"
)


hypothesis_prediction = freeze[
    "prediction"
]


hypothesis_prediction[
    "outcome_contract"
] = {
    "contract":
        "SM3_PLATFORM_PREDICTION_OUTCOME_V1",

    "required_fields": [
        "outcome_id",
        "prediction_id",
        "hypothesis_id",
        "hypothesis_revision",
        "platform",
        "surface",
        "content_ref",
        "metric_name",
        "outcome_status",
        "outcome_window_end",
        "captured_at",
        "source_signal_ids",
        "actual_value",
        "actual_direction",
        "prediction_error",
    ],

    "statuses": [
        "OBSERVED",
        "UNAVAILABLE",
        "INVALIDATED",
    ],

    "actual_value_nullable_when_unavailable":
        True,

    "unavailable_metric_must_not_be_zero":
        True,

    "observed_outcome_requires_source_signal":
        True,

    "captured_at_must_not_precede_outcome_window_end":
        True,

    "prediction_identity_must_match":
        True,

    "metric_name_must_match_prediction":
        True,

    "platform_surface_must_match_prediction":
        True,

    "prediction_error_types": [
        "DIRECTIONAL",
        "NUMERIC",
    ],

    "directional_error_supported":
        True,

    "numeric_error_requires_numeric_prediction":
        True,

    "immutable":
        True,

    "failed_prediction_preserved":
        True,

    "record_hash_required":
        True,
}


# ============================================================
# G002
# DRIFT PROVENANCE
# ============================================================

drift = freeze[
    "drift"
]

drift[
    "provenance_fields"
] = [
    "source_prediction_ids",
    "source_outcome_ids",
    "source_signal_ids",
    "source_evidence_ids",
    "evaluation_window_started_at",
    "evaluation_window_ended_at",
]

drift[
    "at_least_one_source_reference_required"
] = True

drift[
    "provenance_immutable"
] = True

drift[
    "evaluation_window_required"
] = True


# ============================================================
# H001 / H002
# EXPERIMENT INVARIANTS
# ============================================================

experiment = freeze[
    "experiment"
]

experiment[
    "control_treatment_must_differ"
] = True

experiment[
    "controlled_changed_overlap_forbidden"
] = True

experiment[
    "changed_variables_minimum_count"
] = 1

experiment[
    "duplicate_variable_names_forbidden"
] = True

experiment[
    "experiment_scope_must_match_hypothesis_scope"
] = True


# ============================================================
# I002 / I003 / I004
# TEMPORAL SIGNATURE
# ============================================================

freeze[
    "v2"
][
    "temporal_signature_schema"
] = (
    "SM3_CONTENT_TEMPORAL_SIGNATURE_SCHEMA_V1"
)


temporal = freeze[
    "temporal_signature"
]


temporal[
    "schema_version"
] = (
    "SM3_CONTENT_TEMPORAL_SIGNATURE_SCHEMA_V1"
)


temporal[
    "required_fields"
] = [
    "signature_id",
    "contract_version",
    "schema_version",
    "source_content_hash",
    "analyzer_version",
    "media_duration_ms",
    "events",
    "derived_features",
]


temporal[
    "media_duration_ms_required"
] = True

temporal[
    "media_duration_ms_must_be_positive"
] = True

temporal[
    "negative_timestamp_forbidden"
] = True

temporal[
    "events_must_be_within_media_duration"
] = True

temporal[
    "canonical_event_ordering_required"
] = True

temporal[
    "duplicate_identical_event_forbidden"
] = True


temporal_identity_fields = [
    "contract_version",
    "schema_version",
    "source_content_hash",
    "analyzer_version",
]


temporal[
    "identity_fields"
] = temporal_identity_fields


temporal[
    "identity_rule"
] = {
    "algorithm":
        "CANONICAL_SHA256_PREFIX_32",

    "identity_fields":
        temporal_identity_fields,

    "event_timestamp_unit":
        "INTEGER_MILLISECONDS",

    "event_order":
        "TIMESTAMP_ASC_THEN_EVENT_TYPE_ASC",

    "content_hash_algorithm":
        "SHA256",
}


# ============================================================
# J002
# SNAPSHOT V2 IDENTITY
# ============================================================

freeze[
    "v2"
][
    "temporal_validity_policy"
] = (
    "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
)


snapshot = freeze[
    "snapshot_v2"
]


snapshot[
    "identity_fields"
] = [
    "contract_version",
    "engine_version",
    "platform",
    "surface",
    "sorted_evidence_ids",
    "sorted_preference_signal_ids",
    "sorted_active_hypothesis_revision_ids",
    "as_of",
    "minimum_distinct_origins",
    "minimum_mean_evidence_confidence",
    "confidence_decay_policy_version",
    "temporal_validity_policy_version",
]


snapshot[
    "input_ids_sorted_before_identity"
] = True

snapshot[
    "duplicate_input_ids_forbidden"
] = True

snapshot[
    "identity_algorithm"
] = (
    "CANONICAL_SHA256_PREFIX_32"
)


# ============================================================
# ROLLOUT ORDER
# ============================================================

freeze[
    "rollout"
] = [
    "A3_R2_REATTACK",
    "A4_TEMPORAL_VALIDITY_ENGINE",
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


# ============================================================
# WRITE REVISED FREEZE
# ============================================================

write_json(
    REVISED,
    freeze,
)


revised_sha = file_sha256(
    REVISED
)


# ============================================================
# VERIFY THE 11 HIGH GAPS
# ============================================================

h = freeze[
    "hypothesis"
]

p = freeze[
    "prediction"
]

d = freeze[
    "drift"
]

e = freeze[
    "experiment"
]

t = freeze[
    "temporal_signature"
]

s = freeze[
    "snapshot_v2"
]


gap_checks = {
    "C002_CONFIDENCE_RANGE":
        (
            h.get(
                "source_confidence_range"
            )
            == [0, 100]
            and
            h.get(
                "effective_confidence_range"
            )
            == [0, 100]
        ),

    "E002_SUPPORT_COUNTER_OVERLAP":
        (
            h.get(
                "support_counter_overlap_forbidden"
            )
            is True
            and
            h.get(
                "evidence_role_overlap_forbidden"
            )
            is True
            and
            h.get(
                "signal_role_overlap_forbidden"
            )
            is True
        ),

    "E003_HYPOTHESIS_IDENTITY":
        (
            isinstance(
                h.get(
                    "identity_rule"
                ),
                dict,
            )
            and
            len(
                h[
                    "identity_rule"
                ].get(
                    "hypothesis_id_fields",
                    [],
                )
            )
            >= 5
            and
            len(
                h[
                    "identity_rule"
                ].get(
                    "revision_identity_fields",
                    [],
                )
            )
            >= 8
        ),

    "F002_PREDICTION_OUTCOME":
        (
            freeze[
                "v2"
            ].get(
                "prediction_outcome"
            )
            == "SM3_PLATFORM_PREDICTION_OUTCOME_V1"
            and
            p.get(
                "outcome_contract",
                {},
            ).get(
                "contract"
            )
            == "SM3_PLATFORM_PREDICTION_OUTCOME_V1"
            and
            p.get(
                "outcome_contract",
                {},
            ).get(
                "immutable"
            )
            is True
        ),

    "G002_DRIFT_PROVENANCE":
        (
            len(
                d.get(
                    "provenance_fields",
                    [],
                )
            )
            >= 6
            and
            d.get(
                "at_least_one_source_reference_required"
            )
            is True
            and
            d.get(
                "provenance_immutable"
            )
            is True
        ),

    "H001_CONTROL_TREATMENT":
        e.get(
            "control_treatment_must_differ"
        )
        is True,

    "H002_VARIABLE_ROLE_OVERLAP":
        (
            e.get(
                "controlled_changed_overlap_forbidden"
            )
            is True
            and
            e.get(
                "changed_variables_minimum_count"
            )
            == 1
        ),

    "I002_MEDIA_DURATION":
        (
            t.get(
                "media_duration_ms_required"
            )
            is True
            and
            t.get(
                "media_duration_ms_must_be_positive"
            )
            is True
            and
            "media_duration_ms"
            in t.get(
                "required_fields",
                [],
            )
        ),

    "I003_EVENT_BOUNDARIES":
        (
            t.get(
                "negative_timestamp_forbidden"
            )
            is True
            and
            t.get(
                "events_must_be_within_media_duration"
            )
            is True
            and
            t.get(
                "canonical_event_ordering_required"
            )
            is True
        ),

    "I004_TEMPORAL_IDENTITY":
        (
            len(
                t.get(
                    "identity_fields",
                    [],
                )
            )
            == 4
            and
            t.get(
                "schema_version"
            )
            == "SM3_CONTENT_TEMPORAL_SIGNATURE_SCHEMA_V1"
        ),

    "J002_SNAPSHOT_IDENTITY":
        (
            len(
                s.get(
                    "identity_fields",
                    [],
                )
            )
            >= 10
            and
            s.get(
                "input_ids_sorted_before_identity"
            )
            is True
            and
            s.get(
                "duplicate_input_ids_forbidden"
            )
            is True
        ),
}


resolved_count = sum(
    1
    for value in gap_checks.values()
    if value
)


all_resolved = all(
    gap_checks.values()
)


if resolved_count != 11:
    raise SystemExit(
        "HIGH_GAP_RESOLUTION_COUNT_INVALID:"
        + str(
            resolved_count
        )
    )


if not all_resolved:
    raise SystemExit(
        "HIGH_GAPS_NOT_ALL_RESOLVED"
    )


# ============================================================
# AMENDMENT REPORT
# ============================================================

amendment = {
    "phase":
        "09C7-B3E-A3-R1-R1",

    "status":
        "BLACK_BOX_DYNAMICS_V2_CONTRACT_HARDENED",

    "parent_freeze_sha256":
        original_sha,

    "attack_report_sha256":
        attack_sha,

    "revised_freeze_sha256":
        revised_sha,

    "critical_gaps_before":
        0,

    "high_gaps_before":
        11,

    "high_gap_checks":
        gap_checks,

    "high_gaps_resolved":
        resolved_count,

    "all_high_gaps_resolved":
        all_resolved,

    "implementation_ready_claimed":
        False,

    "next_required_gate":
        "09C7-B3E-A3-R2_STATIC_CONTRACT_REATTACK",

    "production_source_modified":
        False,

    "production_state_modified":
        False,

    "production_restart_executed":
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
    AMENDMENT,
    amendment,
)


amendment_sha = file_sha256(
    AMENDMENT
)


# ============================================================
# OUTPUT
# ============================================================

print(
    "=== HIGH GAP RESOLUTION ==="
)

for name,value in gap_checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print("")
print(
    "HIGH_GAPS_BEFORE=11"
)

print(
    "HIGH_GAPS_RESOLVED="
    + str(
        resolved_count
    )
)

print(
    "ALL_HIGH_GAPS_RESOLVED="
    + str(
        all_resolved
    )
)

print(
    "IMPLEMENTATION_READY_CLAIMED=False"
)

print(
    "NEXT_REQUIRED_GATE="
    "09C7-B3E-A3-R2_STATIC_CONTRACT_REATTACK"
)

print(
    "REVISED_FREEZE_SHA256="
    + revised_sha
)

print(
    "AMENDMENT_REPORT_SHA256="
    + amendment_sha
)

print(
    "SM3_09C7_B3E_A3_R1_R1_CONTRACT_HARDENING_COMPLETE"
)
