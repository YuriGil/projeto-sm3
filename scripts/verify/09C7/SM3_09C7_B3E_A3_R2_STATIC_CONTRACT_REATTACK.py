from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


FREEZE = Path(sys.argv[1])
AMENDMENT = Path(sys.argv[2])
REPORT = Path(sys.argv[3])


EXPECTED_FREEZE_SHA = (
    "3c6ad11d8d6240158c8c890fe7c7428a"
    "e0d9dd323be17c52fbdce738b0a21399"
)

EXPECTED_AMENDMENT_SHA = (
    "94b77f25c4430b569425ae5749a383638"
    "89d3cfc120ddb45ad5cd4075e2a5d8f"
)

EXPECTED_PARENT_SHA = (
    "6836d4b91db168dcfba74f60314d1081"
    "880686b60262d6c52831c004aa828535"
)

EXPECTED_ATTACK_SHA = (
    "4020ef0c5b6e2a84a00cd318812d994c"
    "ce4d1b9ca790d0d2f559c033fccf11c5"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


freeze_sha = sha256(
    FREEZE
)

amendment_sha = sha256(
    AMENDMENT
)


if freeze_sha != EXPECTED_FREEZE_SHA:
    raise SystemExit(
        "R2_FREEZE_SHA_MISMATCH:"
        + freeze_sha
    )


if amendment_sha != EXPECTED_AMENDMENT_SHA:
    raise SystemExit(
        "R2_AMENDMENT_SHA_MISMATCH:"
        + amendment_sha
    )


f = load(
    FREEZE
)

a = load(
    AMENDMENT
)


# ============================================================
# LINEAGE
# ============================================================

revision = f.get(
    "revision_metadata",
    {}
)


lineage_checks = {
    "revision_is_r1":
        revision.get(
            "revision"
        )
        == "R1",

    "parent_freeze_matches":
        revision.get(
            "parent_freeze_sha256"
        )
        == EXPECTED_PARENT_SHA,

    "attack_report_matches":
        revision.get(
            "static_attack_sha256"
        )
        == EXPECTED_ATTACK_SHA,

    "amendment_parent_matches":
        a.get(
            "parent_freeze_sha256"
        )
        == EXPECTED_PARENT_SHA,

    "amendment_attack_matches":
        a.get(
            "attack_report_sha256"
        )
        == EXPECTED_ATTACK_SHA,

    "amendment_revised_matches":
        a.get(
            "revised_freeze_sha256"
        )
        == freeze_sha,

    "all_high_gaps_resolved":
        a.get(
            "all_high_gaps_resolved"
        )
        is True,

    "high_gap_count_resolved":
        a.get(
            "high_gaps_resolved"
        )
        == 11,
}


if not all(
    lineage_checks.values()
):
    print(
        json.dumps(
            lineage_checks,
            indent=2,
        )
    )

    raise SystemExit(
        "R2_LINEAGE_PRECONDITION_FAILED"
    )


# ============================================================
# ATTACK ENGINE
# ============================================================

results = []


def attack(
    attack_id,
    severity,
    title,
    condition,
):

    passed = bool(
        condition
    )

    results.append({
        "attack_id":
            attack_id,

        "severity":
            severity,

        "title":
            title,

        "passed":
            passed,

        "finding":
            (
                "PASS"
                if passed
                else "GAP"
            ),
    })


# ============================================================
# A — CORE
# ============================================================

attack(
    "A001",
    "CRITICAL",
    "V2 engine identity frozen",
    f.get(
        "v2",
        {}
    ).get(
        "engine"
    )
    == "SM3_BLACK_BOX_DYNAMICS_ENGINE_V2",
)


attack(
    "A002",
    "CRITICAL",
    "V1 evidence preserved without destructive migration",
    (
        f.get(
            "preserve",
            {},
        ).get(
            "existing_evidence_immutable"
        )
        is True
        and
        f.get(
            "migration",
            {},
        ).get(
            "destructive_migration"
        )
        is False
        and
        f.get(
            "migration",
            {},
        ).get(
            "existing_evidence_preserved"
        )
        is True
    ),
)


# ============================================================
# B — TEMPORAL VALIDITY
# ============================================================

tv = f[
    "temporal_validity"
]


attack(
    "B001",
    "CRITICAL",
    "Future evidence forbidden",
    (
        tv.get(
            "future_evidence_forbidden"
        )
        is True
        and
        tv.get(
            "evidence_source_date_must_not_exceed_as_of"
        )
        is True
        and
        tv.get(
            "evidence_observed_at_must_not_exceed_as_of"
        )
        is True
    ),
)


attack(
    "B002",
    "CRITICAL",
    "Future preference signal windows forbidden",
    (
        tv.get(
            "future_signal_forbidden"
        )
        is True
        and
        tv.get(
            "signal_window_end_must_not_exceed_as_of"
        )
        is True
        and
        tv.get(
            "signal_window_start_must_precede_end"
        )
        is True
    ),
)


attack(
    "B003",
    "CRITICAL",
    "Expired evidence cannot enter new state",
    (
        tv.get(
            "expired_evidence_forbidden"
        )
        is True
        and
        tv.get(
            "valid_until_checked_against_as_of"
        )
        is True
        and
        tv.get(
            "expired_input_behavior"
        )
        == "FAIL_CLOSED"
    ),
)


# ============================================================
# C — CONFIDENCE
# ============================================================

ca = f[
    "confidence_aging"
]

hyp = f[
    "hypothesis"
]


attack(
    "C001",
    "CRITICAL",
    "Source and effective confidence separated",
    (
        ca.get(
            "source_confidence_preserved"
        )
        is True
        and
        ca.get(
            "effective_confidence_separate_from_source_confidence"
        )
        is True
        and
        ca.get(
            "effective_confidence_must_not_exceed_source_confidence"
        )
        is True
    ),
)


attack(
    "C002",
    "HIGH",
    "Hypothesis confidence numeric range explicitly frozen",
    (
        hyp.get(
            "source_confidence_range"
        )
        == [0, 100]
        and
        hyp.get(
            "effective_confidence_range"
        )
        == [0, 100]
    ),
)


# ============================================================
# D — SIGNAL SEMANTICS
# ============================================================

sv = f[
    "signal_vector"
]


attack(
    "D001",
    "CRITICAL",
    "Descriptive vector cannot masquerade as ranking weights",
    (
        sv.get(
            "current_vector_is_platform_ranking_weight"
        )
        is False
        and
        sv.get(
            "equal_mean_does_not_imply_equal_algorithm_importance"
        )
        is True
        and
        sv.get(
            "fixed_platform_metric_weights_forbidden"
        )
        is True
        and
        sv.get(
            "signal_importance_must_be_learned_from_outcomes"
        )
        is True
    ),
)


# ============================================================
# E — HYPOTHESIS
# ============================================================

hyp_fields = set(
    hyp.get(
        "required_fields",
        [],
    )
)

identity_rule = hyp.get(
    "identity_rule",
    {}
)


attack(
    "E001",
    "CRITICAL",
    "Hypothesis has immutable revision identity",
    (
        "hypothesis_id"
        in hyp_fields
        and
        "revision"
        in hyp_fields
        and
        hyp.get(
            "immutable_revisions"
        )
        is True
    ),
)


attack(
    "E002",
    "HIGH",
    "Same evidence cannot support and counter one revision",
    (
        hyp.get(
            "support_counter_overlap_forbidden"
        )
        is True
        and
        hyp.get(
            "evidence_role_overlap_forbidden"
        )
        is True
        and
        hyp.get(
            "signal_role_overlap_forbidden"
        )
        is True
    ),
)


attack(
    "E003",
    "HIGH",
    "Hypothesis/revision deterministic identity frozen",
    (
        isinstance(
            identity_rule,
            dict,
        )
        and
        identity_rule.get(
            "hypothesis_id_algorithm"
        )
        == "CANONICAL_SHA256_PREFIX_32"
        and
        len(
            identity_rule.get(
                "hypothesis_id_fields",
                [],
            )
        )
        >= 5
        and
        len(
            identity_rule.get(
                "revision_identity_fields",
                [],
            )
        )
        >= 8
        and
        identity_rule.get(
            "revision_record_immutable"
        )
        is True
    ),
)


attack(
    "E004",
    "CRITICAL",
    "Cross-network and cross-surface transfer fail closed",
    (
        hyp.get(
            "cross_surface_transfer_default"
        )
        == "FORBIDDEN"
        and
        hyp.get(
            "cross_platform_transfer_default"
        )
        == "FORBIDDEN"
    ),
)


# ============================================================
# F — PREDICTION / OUTCOME
# ============================================================

pred = f[
    "prediction"
]

outcome = pred.get(
    "outcome_contract",
    {}
)


attack(
    "F001",
    "CRITICAL",
    "Prediction committed before outcome closes",
    pred.get(
        "prediction_must_exist_before_outcome_window_closes"
    )
    is True,
)


attack(
    "F002",
    "HIGH",
    "Prediction outcome has immutable explicit contract",
    (
        f.get(
            "v2",
            {},
        ).get(
            "prediction_outcome"
        )
        == "SM3_PLATFORM_PREDICTION_OUTCOME_V1"
        and
        outcome.get(
            "contract"
        )
        == "SM3_PLATFORM_PREDICTION_OUTCOME_V1"
        and
        outcome.get(
            "immutable"
        )
        is True
        and
        outcome.get(
            "record_hash_required"
        )
        is True
    ),
)


attack(
    "F003",
    "CRITICAL",
    "Failed predictions remain evidence",
    (
        pred.get(
            "prediction_error_recorded"
        )
        is True
        and
        pred.get(
            "inaccurate_prediction_must_not_be_deleted"
        )
        is True
    ),
)


# ============================================================
# G — DRIFT
# ============================================================

drift = f[
    "drift"
]


attack(
    "G001",
    "CRITICAL",
    "Single post cannot establish platform drift",
    drift.get(
        "single_content_result_can_confirm_drift"
    )
    is False,
)


attack(
    "G002",
    "HIGH",
    "Drift provenance explicitly frozen",
    (
        len(
            drift.get(
                "provenance_fields",
                [],
            )
        )
        >= 6
        and
        drift.get(
            "at_least_one_source_reference_required"
        )
        is True
        and
        drift.get(
            "provenance_immutable"
        )
        is True
        and
        drift.get(
            "evaluation_window_required"
        )
        is True
    ),
)


attack(
    "G003",
    "CRITICAL",
    "Confirmed drift creates revision instead of rewriting history",
    (
        drift.get(
            "old_network_state_never_silently_overwritten"
        )
        is True
        and
        drift.get(
            "confirmed_drift_creates_new_state_revision"
        )
        is True
    ),
)


# ============================================================
# H — EXPERIMENT
# ============================================================

exp = f[
    "experiment"
]


attack(
    "H001",
    "HIGH",
    "Experiment control and treatment must be distinct",
    exp.get(
        "control_treatment_must_differ"
    )
    is True,
)


attack(
    "H002",
    "HIGH",
    "Controlled and changed variable sets are disjoint",
    (
        exp.get(
            "controlled_changed_overlap_forbidden"
        )
        is True
        and
        exp.get(
            "changed_variables_minimum_count"
        )
        == 1
        and
        exp.get(
            "duplicate_variable_names_forbidden"
        )
        is True
    ),
)


attack(
    "H003",
    "CRITICAL",
    "Experiment cannot bypass publication approval",
    exp.get(
        "publication_requires_existing_approval_policy"
    )
    is True,
)


# ============================================================
# I — MICRO-TEMPORAL SIGNATURE
# ============================================================

ts = f[
    "temporal_signature"
]


attack(
    "I001",
    "CRITICAL",
    "Micro-timing descriptive until correlated with outcomes",
    (
        ts.get(
            "earlier_event_is_not_automatically_better"
        )
        is True
        and
        ts.get(
            "feature_requires_real_outcome_correlation"
        )
        is True
        and
        ts.get(
            "feature_does_not_imply_preference"
        )
        is True
    ),
)


attack(
    "I002",
    "HIGH",
    "Temporal signature freezes media duration",
    (
        ts.get(
            "media_duration_ms_required"
        )
        is True
        and
        ts.get(
            "media_duration_ms_must_be_positive"
        )
        is True
        and
        "media_duration_ms"
        in ts.get(
            "required_fields",
            [],
        )
    ),
)


attack(
    "I003",
    "HIGH",
    "Temporal events bounded by media duration",
    (
        ts.get(
            "negative_timestamp_forbidden"
        )
        is True
        and
        ts.get(
            "events_must_be_within_media_duration"
        )
        is True
        and
        ts.get(
            "canonical_event_ordering_required"
        )
        is True
        and
        ts.get(
            "duplicate_identical_event_forbidden"
        )
        is True
    ),
)


attack(
    "I004",
    "HIGH",
    "Temporal signature deterministic identity frozen",
    (
        ts.get(
            "schema_version"
        )
        == "SM3_CONTENT_TEMPORAL_SIGNATURE_SCHEMA_V1"
        and
        len(
            ts.get(
                "identity_fields",
                [],
            )
        )
        == 4
        and
        ts.get(
            "identity_rule",
            {},
        ).get(
            "algorithm"
        )
        == "CANONICAL_SHA256_PREFIX_32"
    ),
)


# ============================================================
# J — SNAPSHOT
# ============================================================

snap = f[
    "snapshot_v2"
]


attack(
    "J001",
    "CRITICAL",
    "Snapshot V2 deterministic immutable and offline",
    (
        snap.get(
            "immutable"
        )
        is True
        and
        snap.get(
            "rebuildable_from_input_ids"
        )
        is True
        and
        snap.get(
            "no_network_calls"
        )
        is True
        and
        snap.get(
            "no_model_calls"
        )
        is True
    ),
)


attack(
    "J002",
    "HIGH",
    "Snapshot V2 deterministic identity frozen",
    (
        len(
            snap.get(
                "identity_fields",
                [],
            )
        )
        >= 10
        and
        snap.get(
            "input_ids_sorted_before_identity"
        )
        is True
        and
        snap.get(
            "duplicate_input_ids_forbidden"
        )
        is True
        and
        snap.get(
            "identity_algorithm"
        )
        == "CANONICAL_SHA256_PREFIX_32"
    ),
)


# ============================================================
# K — TASTE BOUNDARY
# ============================================================

taste = f[
    "taste_boundary"
]


attack(
    "K001",
    "CRITICAL",
    "Platform optimization cannot rewrite MOLÖTOV taste",
    (
        taste.get(
            "taste_model_inside_platform_dynamics"
        )
        is False
        and
        taste.get(
            "platform_success_may_not_overwrite_brand_preference"
        )
        is True
        and
        taste.get(
            "platform_model_and_taste_model_fused_only_in_strategy"
        )
        is True
    ),
)


# ============================================================
# L — FORBIDDEN SHORTCUTS
# ============================================================

forbidden = set(
    f.get(
        "forbidden_shortcuts",
        [],
    )
)


required_forbidden = {
    "ASSUME_PLATFORM_INTERNAL_WEIGHTS",
    "INTERPRET_ARITHMETIC_MEAN_AS_ALGORITHM_WEIGHT",
    "USE_EXPIRED_EVIDENCE_IN_NEW_SNAPSHOT",
    "USE_FUTURE_EVIDENCE_IN_HISTORICAL_SNAPSHOT",
    "DELETE_COUNTEREVIDENCE",
    "DELETE_FAILED_PREDICTION",
    "CONFIRM_DRIFT_FROM_ONE_POST",
    "TURN_CORRELATION_DIRECTLY_INTO_CAUSATION",
    "ASSUME_EARLIER_HOOK_IS_ALWAYS_BETTER",
    "SYNTHESIZE_MISSING_METRIC",
    "ALLOW_PLATFORM_MODEL_TO_OVERWRITE_MOLOTOV_TASTE",
}


attack(
    "L001",
    "CRITICAL",
    "Critical shortcut prohibitions frozen",
    required_forbidden.issubset(
        forbidden
    ),
)


# ============================================================
# M — STORAGE / MIGRATION
# ============================================================

storage = f[
    "storage"
]

migration = f[
    "migration"
]


attack(
    "M001",
    "CRITICAL",
    "New records immutable hashed and atomic",
    (
        storage.get(
            "immutable_records"
        )
        is True
        and
        storage.get(
            "record_hash_required"
        )
        is True
        and
        storage.get(
            "atomic_write_required"
        )
        is True
    ),
)


attack(
    "M002",
    "CRITICAL",
    "No destructive migration of Platform Dynamics V1",
    (
        migration.get(
            "destructive_migration"
        )
        is False
        and
        migration.get(
            "existing_evidence_preserved"
        )
        is True
        and
        migration.get(
            "v1_snapshot_read_compatibility_required"
        )
        is True
    ),
)


# ============================================================
# CLASSIFICATION
# ============================================================

if len(
    results
) != 31:
    raise SystemExit(
        "R2_ATTACK_COUNT_INTERNAL_ERROR:"
        + str(
            len(
                results
            )
        )
    )


critical_gaps = [
    row
    for row in results
    if (
        not row[
            "passed"
        ]
        and
        row[
            "severity"
        ]
        == "CRITICAL"
    )
]


high_gaps = [
    row
    for row in results
    if (
        not row[
            "passed"
        ]
        and
        row[
            "severity"
        ]
        == "HIGH"
    )
]


passed = [
    row
    for row in results
    if row[
        "passed"
    ]
]


contract_ready = (
    len(
        passed
    )
    == 31
    and
    not critical_gaps
    and
    not high_gaps
)


next_phase = (
    "09C7-B3E-A4_TEMPORAL_VALIDITY_ENGINE"
    if contract_ready
    else
    "CONTRACT_REMEDIATION_REQUIRED"
)


report = {
    "phase":
        "09C7-B3E-A3-R2",

    "status":
        "STATIC_CONTRACT_REATTACK_COMPLETE",

    "freeze_sha256":
        freeze_sha,

    "amendment_sha256":
        amendment_sha,

    "lineage_checks":
        lineage_checks,

    "attack_count":
        len(
            results
        ),

    "passed_count":
        len(
            passed
        ),

    "critical_gap_count":
        len(
            critical_gaps
        ),

    "high_gap_count":
        len(
            high_gaps
        ),

    "contract_implementation_ready":
        contract_ready,

    "runtime_v2_implemented":
        False,

    "next_phase":
        next_phase,

    "confidence_decay_numeric_policy_deferred":
        (
            f.get(
                "confidence_aging",
                {},
            ).get(
                "numeric_decay_parameters_frozen_in_this_phase"
            )
            is False
        ),

    "results":
        results,

    "production_write_performed":
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


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== STATIC CONTRACT REATTACK ==="
)

print(
    "ATTACK_COUNT="
    + str(
        report[
            "attack_count"
        ]
    )
)

print(
    "PASSED_COUNT="
    + str(
        report[
            "passed_count"
        ]
    )
)

print(
    "CRITICAL_GAP_COUNT="
    + str(
        report[
            "critical_gap_count"
        ]
    )
)

print(
    "HIGH_GAP_COUNT="
    + str(
        report[
            "high_gap_count"
        ]
    )
)

print(
    "CONTRACT_IMPLEMENTATION_READY="
    + str(
        report[
            "contract_implementation_ready"
        ]
    )
)

print(
    "RUNTIME_V2_IMPLEMENTED=False"
)

print(
    "CONFIDENCE_DECAY_NUMERIC_POLICY_DEFERRED="
    + str(
        report[
            "confidence_decay_numeric_policy_deferred"
        ]
    )
)

print(
    "NEXT_PHASE="
    + report[
        "next_phase"
    ]
)


print(
    "\n=== FINDINGS ==="
)

for row in results:

    print(
        row[
            "attack_id"
        ]
        + " "
        + row[
            "severity"
        ]
        + " "
        + row[
            "finding"
        ]
        + " :: "
        + row[
            "title"
        ]
    )


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
)

print(
    "ROUTE_CALLED=False"
)

print(
    "NETWORK_REQUEST_PERFORMED=False"
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
    "SM3_09C7_B3E_A3_R2_STATIC_CONTRACT_REATTACK_COMPLETE"
)
