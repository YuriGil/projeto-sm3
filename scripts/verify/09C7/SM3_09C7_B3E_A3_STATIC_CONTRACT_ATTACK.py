from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


FREEZE_PATH = Path(
    "/tmp/SM3_09C7_B3E_A2_BLACK_BOX_DYNAMICS_V2_FREEZE.json"
)

REPORT_PATH = Path(
    "/tmp/SM3_09C7_B3E_A3_STATIC_CONTRACT_ATTACK.json"
)


freeze = json.loads(
    FREEZE_PATH.read_text(
        encoding="utf-8-sig"
    )
)


# ============================================================
# ATTACK RESULT HELPERS
# ============================================================

results = []


def add(
    attack_id,
    severity,
    title,
    passed,
    evidence,
    required_fix=None,
):
    results.append({
        "attack_id":
            attack_id,

        "severity":
            severity,

        "title":
            title,

        "passed":
            bool(
                passed
            ),

        "evidence":
            evidence,

        "required_fix":
            required_fix,
    })


def has_fields(
    values,
    required,
):
    values = set(
        values
        or []
    )

    return all(
        item in values
        for item in required
    )


# ============================================================
# A. BASE CONTRACT
# ============================================================

add(
    "A001",
    "CRITICAL",
    "V2 engine identity frozen",
    freeze.get("v2", {}).get("engine")
    == "SM3_BLACK_BOX_DYNAMICS_ENGINE_V2",
    {
        "engine":
            freeze.get("v2", {}).get("engine")
    },
)


add(
    "A002",
    "CRITICAL",
    "V1 evidence preserved without destructive migration",
    (
        freeze.get("preserve", {}).get(
            "existing_evidence_immutable"
        ) is True
        and
        freeze.get("migration", {}).get(
            "destructive_migration"
        ) is False
        and
        freeze.get("migration", {}).get(
            "existing_evidence_preserved"
        ) is True
    ),
    {
        "existing_evidence_immutable":
            freeze.get("preserve", {}).get(
                "existing_evidence_immutable"
            ),

        "destructive_migration":
            freeze.get("migration", {}).get(
                "destructive_migration"
            ),

        "existing_evidence_preserved":
            freeze.get("migration", {}).get(
                "existing_evidence_preserved"
            ),
    },
)


# ============================================================
# B. TEMPORAL VALIDITY
# ============================================================

tv = freeze.get(
    "temporal_validity",
    {}
)


add(
    "B001",
    "CRITICAL",
    "Future evidence forbidden",
    (
        tv.get(
            "future_evidence_forbidden"
        ) is True
        and
        tv.get(
            "evidence_source_date_must_not_exceed_as_of"
        ) is True
        and
        tv.get(
            "evidence_observed_at_must_not_exceed_as_of"
        ) is True
    ),
    {
        "future_evidence_forbidden":
            tv.get(
                "future_evidence_forbidden"
            ),

        "source_date_lte_as_of":
            tv.get(
                "evidence_source_date_must_not_exceed_as_of"
            ),

        "observed_at_lte_as_of":
            tv.get(
                "evidence_observed_at_must_not_exceed_as_of"
            ),
    },
)


add(
    "B002",
    "CRITICAL",
    "Future preference signal windows forbidden",
    (
        tv.get(
            "future_signal_forbidden"
        ) is True
        and
        tv.get(
            "signal_window_end_must_not_exceed_as_of"
        ) is True
        and
        tv.get(
            "signal_window_start_must_precede_end"
        ) is True
    ),
    {
        "future_signal_forbidden":
            tv.get(
                "future_signal_forbidden"
            ),

        "window_end_lte_as_of":
            tv.get(
                "signal_window_end_must_not_exceed_as_of"
            ),

        "window_start_lt_end":
            tv.get(
                "signal_window_start_must_precede_end"
            ),
    },
)


add(
    "B003",
    "CRITICAL",
    "Expired evidence cannot enter new state",
    (
        tv.get(
            "expired_evidence_forbidden"
        ) is True
        and
        tv.get(
            "valid_until_checked_against_as_of"
        ) is True
        and
        tv.get(
            "expired_input_behavior"
        ) == "FAIL_CLOSED"
    ),
    {
        "expired_evidence_forbidden":
            tv.get(
                "expired_evidence_forbidden"
            ),

        "valid_until_checked":
            tv.get(
                "valid_until_checked_against_as_of"
            ),

        "behavior":
            tv.get(
                "expired_input_behavior"
            ),
    },
)


# ============================================================
# C. CONFIDENCE MODEL
# ============================================================

ca = freeze.get(
    "confidence_aging",
    {}
)


add(
    "C001",
    "CRITICAL",
    "Source and effective confidence separated",
    (
        ca.get(
            "source_confidence_preserved"
        ) is True
        and
        ca.get(
            "effective_confidence_separate_from_source_confidence"
        ) is True
        and
        ca.get(
            "effective_confidence_must_not_exceed_source_confidence"
        ) is True
    ),
    {
        "source_preserved":
            ca.get(
                "source_confidence_preserved"
            ),

        "effective_separate":
            ca.get(
                "effective_confidence_separate_from_source_confidence"
            ),

        "effective_lte_source":
            ca.get(
                "effective_confidence_must_not_exceed_source_confidence"
            ),
    },
)


hyp = freeze.get(
    "hypothesis",
    {}
)

hyp_fields = set(
    hyp.get(
        "required_fields"
    )
    or []
)


confidence_range_defined = (
    "confidence_range"
    in hyp
    or
    "source_confidence_range"
    in hyp
    or
    "effective_confidence_range"
    in hyp
)


add(
    "C002",
    "HIGH",
    "Hypothesis confidence numeric range explicitly frozen",
    confidence_range_defined,
    {
        "hypothesis_keys":
            sorted(
                hyp.keys()
            )
    },
    (
        None
        if confidence_range_defined
        else
        "Freeze explicit source_confidence and effective_confidence ranges before implementation."
    ),
)


# ============================================================
# D. SIGNAL SEMANTICS
# ============================================================

sv = freeze.get(
    "signal_vector",
    {}
)


add(
    "D001",
    "CRITICAL",
    "Descriptive vector cannot masquerade as platform ranking weights",
    (
        sv.get(
            "current_vector_is_platform_ranking_weight"
        ) is False
        and
        sv.get(
            "equal_mean_does_not_imply_equal_algorithm_importance"
        ) is True
        and
        sv.get(
            "fixed_platform_metric_weights_forbidden"
        ) is True
        and
        sv.get(
            "signal_importance_must_be_learned_from_outcomes"
        ) is True
    ),
    {
        "ranking_weight":
            sv.get(
                "current_vector_is_platform_ranking_weight"
            ),

        "equal_mean_not_equal_importance":
            sv.get(
                "equal_mean_does_not_imply_equal_algorithm_importance"
            ),

        "fixed_weights_forbidden":
            sv.get(
                "fixed_platform_metric_weights_forbidden"
            ),

        "learned_from_outcomes":
            sv.get(
                "signal_importance_must_be_learned_from_outcomes"
            ),
    },
)


# ============================================================
# E. HYPOTHESIS CONTRACT
# ============================================================

add(
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
        ) is True
    ),
    {
        "required_fields":
            sorted(
                hyp_fields
            ),

        "immutable_revisions":
            hyp.get(
                "immutable_revisions"
            ),
    },
)


support_counter_overlap_policy = any(
    key in hyp
    for key in (
        "support_counter_overlap_forbidden",
        "evidence_role_overlap_forbidden",
        "same_evidence_cannot_support_and_counter",
    )
)


add(
    "E002",
    "HIGH",
    "Same evidence cannot support and contradict one hypothesis revision",
    support_counter_overlap_policy,
    {
        "hypothesis_keys":
            sorted(
                hyp.keys()
            )
    },
    (
        None
        if support_counter_overlap_policy
        else
        "Add explicit support/counter evidence and signal overlap prohibition."
    ),
)


identity_rule_defined = any(
    key in hyp
    for key in (
        "identity_fields",
        "identity_rule",
        "hypothesis_identity",
        "revision_identity",
    )
)


add(
    "E003",
    "HIGH",
    "Hypothesis and revision deterministic identity explicitly defined",
    identity_rule_defined,
    {
        "hypothesis_keys":
            sorted(
                hyp.keys()
            )
    },
    (
        None
        if identity_rule_defined
        else
        "Freeze deterministic hypothesis_id/revision identity inputs before writing storage code."
    ),
)


add(
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
    {
        "cross_surface":
            hyp.get(
                "cross_surface_transfer_default"
            ),

        "cross_platform":
            hyp.get(
                "cross_platform_transfer_default"
            ),
    },
)


# ============================================================
# F. PREDICTION / OUTCOME
# ============================================================

pred = freeze.get(
    "prediction",
    {}
)

pred_fields = set(
    pred.get(
        "required_fields"
    )
    or []
)


add(
    "F001",
    "CRITICAL",
    "Prediction is committed before outcome closes",
    pred.get(
        "prediction_must_exist_before_outcome_window_closes"
    ) is True,
    {
        "rule":
            pred.get(
                "prediction_must_exist_before_outcome_window_closes"
            )
    },
)


outcome_contract_defined = any(
    value
    for key,value
    in freeze.get(
        "v2",
        {}
    ).items()
    if (
        "outcome"
        in key.lower()
        or
        (
            isinstance(
                value,
                str,
            )
            and
            "OUTCOME"
            in value
        )
    )
)


add(
    "F002",
    "HIGH",
    "Prediction outcome has explicit immutable contract",
    outcome_contract_defined,
    {
        "v2_contracts":
            freeze.get(
                "v2",
                {}
            ),

        "actual_result_written_separately":
            pred.get(
                "actual_result_written_separately"
            ),
    },
    (
        None
        if outcome_contract_defined
        else
        "Define an immutable PLATFORM_PREDICTION_OUTCOME contract before implementing prediction error."
    ),
)


add(
    "F003",
    "CRITICAL",
    "Failed predictions remain evidence",
    (
        pred.get(
            "prediction_error_recorded"
        ) is True
        and
        pred.get(
            "inaccurate_prediction_must_not_be_deleted"
        ) is True
    ),
    {
        "prediction_error_recorded":
            pred.get(
                "prediction_error_recorded"
            ),

        "failed_prediction_retained":
            pred.get(
                "inaccurate_prediction_must_not_be_deleted"
            ),
    },
)


# ============================================================
# G. DRIFT
# ============================================================

drift = freeze.get(
    "drift",
    {}
)


add(
    "G001",
    "CRITICAL",
    "Single post cannot establish platform drift",
    drift.get(
        "single_content_result_can_confirm_drift"
    ) is False,
    {
        "single_content_result_can_confirm_drift":
            drift.get(
                "single_content_result_can_confirm_drift"
            )
    },
)


drift_provenance_defined = any(
    key in drift
    for key in (
        "required_evidence_links",
        "source_prediction_ids",
        "source_signal_ids",
        "provenance_fields",
        "supporting_ids",
    )
)


add(
    "G002",
    "HIGH",
    "Drift signal provenance explicitly frozen",
    drift_provenance_defined,
    {
        "drift_keys":
            sorted(
                drift.keys()
            )
    },
    (
        None
        if drift_provenance_defined
        else
        "Add immutable source prediction/signal/evidence references to every drift signal."
    ),
)


add(
    "G003",
    "CRITICAL",
    "Confirmed drift creates revision instead of rewriting history",
    (
        drift.get(
            "old_network_state_never_silently_overwritten"
        ) is True
        and
        drift.get(
            "confirmed_drift_creates_new_state_revision"
        ) is True
    ),
    {
        "history_preserved":
            drift.get(
                "old_network_state_never_silently_overwritten"
            ),

        "new_revision":
            drift.get(
                "confirmed_drift_creates_new_state_revision"
            ),
    },
)


# ============================================================
# H. EXPERIMENT
# ============================================================

exp = freeze.get(
    "experiment",
    {}
)

exp_fields = set(
    exp.get(
        "required_fields"
    )
    or []
)


control_treatment_rule = any(
    key in exp
    for key in (
        "control_treatment_must_differ",
        "control_and_treatment_distinct",
        "same_content_forbidden",
    )
)


add(
    "H001",
    "HIGH",
    "Experiment control and treatment must be distinct",
    control_treatment_rule,
    {
        "experiment_keys":
            sorted(
                exp.keys()
            )
    },
    (
        None
        if control_treatment_rule
        else
        "Freeze explicit control_content_ref != treatment_content_ref validation."
    ),
)


variable_overlap_rule = any(
    key in exp
    for key in (
        "controlled_changed_overlap_forbidden",
        "variable_role_overlap_forbidden",
    )
)


add(
    "H002",
    "HIGH",
    "A variable cannot be both controlled and changed",
    variable_overlap_rule,
    {
        "experiment_keys":
            sorted(
                exp.keys()
            )
    },
    (
        None
        if variable_overlap_rule
        else
        "Freeze disjoint controlled_variables / changed_variables sets."
    ),
)


add(
    "H003",
    "CRITICAL",
    "Experiment cannot bypass publication approval",
    exp.get(
        "publication_requires_existing_approval_policy"
    ) is True,
    {
        "approval_required":
            exp.get(
                "publication_requires_existing_approval_policy"
            )
    },
)


# ============================================================
# I. MICRO-TEMPORAL SIGNATURE
# ============================================================

ts = freeze.get(
    "temporal_signature",
    {}
)


add(
    "I001",
    "CRITICAL",
    "Micro-timing remains descriptive until correlated with outcomes",
    (
        ts.get(
            "earlier_event_is_not_automatically_better"
        ) is True
        and
        ts.get(
            "feature_requires_real_outcome_correlation"
        ) is True
        and
        ts.get(
            "feature_does_not_imply_preference"
        ) is True
    ),
    {
        "earlier_not_automatically_better":
            ts.get(
                "earlier_event_is_not_automatically_better"
            ),

        "real_outcome_required":
            ts.get(
                "feature_requires_real_outcome_correlation"
            ),

        "feature_not_preference":
            ts.get(
                "feature_does_not_imply_preference"
            ),
    },
)


duration_rule_defined = any(
    key in ts
    for key in (
        "media_duration_ms_required",
        "duration_ms_required",
        "media_duration_required",
    )
)


add(
    "I002",
    "HIGH",
    "Temporal signature freezes media duration",
    duration_rule_defined,
    {
        "temporal_signature_keys":
            sorted(
                ts.keys()
            )
    },
    (
        None
        if duration_rule_defined
        else
        "Add media_duration_ms to validate event boundaries."
    ),
)


event_boundary_rule = any(
    key in ts
    for key in (
        "events_must_be_within_media_duration",
        "event_boundary_validation",
        "negative_timestamp_forbidden",
    )
)


add(
    "I003",
    "HIGH",
    "Temporal events cannot be negative or exceed media duration",
    event_boundary_rule,
    {
        "temporal_signature_keys":
            sorted(
                ts.keys()
            )
    },
    (
        None
        if event_boundary_rule
        else
        "Freeze 0 <= event_timestamp_ms <= media_duration_ms and canonical ordering."
    ),
)


signature_identity_defined = any(
    key in ts
    for key in (
        "identity_fields",
        "identity_rule",
        "signature_identity",
    )
)


add(
    "I004",
    "HIGH",
    "Temporal signature deterministic identity explicitly frozen",
    signature_identity_defined,
    {
        "source_content_hash_required":
            ts.get(
                "source_content_hash_required"
            ),

        "analyzer_version_required":
            ts.get(
                "analyzer_version_required"
            ),

        "temporal_signature_keys":
            sorted(
                ts.keys()
            ),
    },
    (
        None
        if signature_identity_defined
        else
        "Freeze signature identity from source_content_hash + analyzer_version + schema/contract version."
    ),
)


# ============================================================
# J. SNAPSHOT V2
# ============================================================

snap = freeze.get(
    "snapshot_v2",
    {}
)


add(
    "J001",
    "CRITICAL",
    "Snapshot V2 is deterministic, immutable and offline",
    (
        snap.get(
            "immutable"
        ) is True
        and
        snap.get(
            "rebuildable_from_input_ids"
        ) is True
        and
        snap.get(
            "no_network_calls"
        ) is True
        and
        snap.get(
            "no_model_calls"
        ) is True
    ),
    {
        "immutable":
            snap.get(
                "immutable"
            ),

        "rebuildable":
            snap.get(
                "rebuildable_from_input_ids"
            ),

        "network_calls":
            snap.get(
                "no_network_calls"
            ),

        "model_calls":
            snap.get(
                "no_model_calls"
            ),
    },
)


snapshot_identity_defined = any(
    key in snap
    for key in (
        "identity_fields",
        "identity_rule",
        "snapshot_identity",
    )
)


add(
    "J002",
    "HIGH",
    "Snapshot V2 identity inputs explicitly frozen",
    snapshot_identity_defined,
    {
        "snapshot_keys":
            sorted(
                snap.keys()
            )
    },
    (
        None
        if snapshot_identity_defined
        else
        "Freeze deterministic snapshot identity including engine, scope, sorted input IDs, as_of and policy versions."
    ),
)


# ============================================================
# K. TASTE BOUNDARY
# ============================================================

taste = freeze.get(
    "taste_boundary",
    {}
)


add(
    "K001",
    "CRITICAL",
    "Platform optimization cannot rewrite MOLÖTOV taste",
    (
        taste.get(
            "taste_model_inside_platform_dynamics"
        ) is False
        and
        taste.get(
            "platform_success_may_not_overwrite_brand_preference"
        ) is True
        and
        taste.get(
            "platform_model_and_taste_model_fused_only_in_strategy"
        ) is True
    ),
    {
        "taste_inside_platform":
            taste.get(
                "taste_model_inside_platform_dynamics"
            ),

        "may_not_overwrite":
            taste.get(
                "platform_success_may_not_overwrite_brand_preference"
            ),

        "fusion_only_in_strategy":
            taste.get(
                "platform_model_and_taste_model_fused_only_in_strategy"
            ),
    },
)


# ============================================================
# L. FORBIDDEN SHORTCUT COVERAGE
# ============================================================

forbidden = set(
    freeze.get(
        "forbidden_shortcuts"
    )
    or []
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


missing_forbidden = sorted(
    required_forbidden
    - forbidden
)


add(
    "L001",
    "CRITICAL",
    "Critical shortcut prohibitions frozen",
    not missing_forbidden,
    {
        "missing":
            missing_forbidden
    },
)


# ============================================================
# M. STORAGE / MIGRATION
# ============================================================

storage = freeze.get(
    "storage",
    {}
)

migration = freeze.get(
    "migration",
    {}
)


add(
    "M001",
    "CRITICAL",
    "New records are immutable, hashed and atomic",
    (
        storage.get(
            "immutable_records"
        ) is True
        and
        storage.get(
            "record_hash_required"
        ) is True
        and
        storage.get(
            "atomic_write_required"
        ) is True
    ),
    {
        "immutable":
            storage.get(
                "immutable_records"
            ),

        "hash":
            storage.get(
                "record_hash_required"
            ),

        "atomic":
            storage.get(
                "atomic_write_required"
            ),
    },
)


add(
    "M002",
    "CRITICAL",
    "No destructive migration of existing Platform Dynamics V1",
    (
        migration.get(
            "destructive_migration"
        ) is False
        and
        migration.get(
            "existing_evidence_preserved"
        ) is True
        and
        migration.get(
            "v1_snapshot_read_compatibility_required"
        ) is True
    ),
    {
        "destructive_migration":
            migration.get(
                "destructive_migration"
            ),

        "existing_evidence_preserved":
            migration.get(
                "existing_evidence_preserved"
            ),

        "v1_read":
            migration.get(
                "v1_snapshot_read_compatibility_required"
            ),
    },
)


# ============================================================
# N. REPORT CLASSIFICATION
# ============================================================

for row in results:

    row[
        "finding"
    ] = (
        "PASS"
        if row[
            "passed"
        ]
        else "GAP"
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


medium_gaps = [
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
        == "MEDIUM"
    )
]


passed_checks = [
    row
    for row in results
    if row[
        "passed"
    ]
]


freeze_sha = hashlib.sha256(
    FREEZE_PATH.read_bytes()
).hexdigest()


report = {
    "phase":
        "09C7-B3E-A3",

    "status":
        "STATIC_CONTRACT_ATTACK_COMPLETE",

    "freeze_sha256":
        freeze_sha,

    "attack_count":
        len(
            results
        ),

    "passed_count":
        len(
            passed_checks
        ),

    "critical_gap_count":
        len(
            critical_gaps
        ),

    "high_gap_count":
        len(
            high_gaps
        ),

    "medium_gap_count":
        len(
            medium_gaps
        ),

    "implementation_ready":
        (
            len(
                critical_gaps
            )
            == 0
            and
            len(
                high_gaps
            )
            == 0
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


REPORT_PATH.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== STATIC CONTRACT ATTACK ==="
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
    "MEDIUM_GAP_COUNT="
    + str(
        report[
            "medium_gap_count"
        ]
    )
)

print(
    "IMPLEMENTATION_READY="
    + str(
        report[
            "implementation_ready"
        ]
    )
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

    if (
        not row[
            "passed"
        ]
        and
        row.get(
            "required_fix"
        )
    ):

        print(
            "  REQUIRED_FIX="
            + row[
                "required_fix"
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
        REPORT_PATH
    )
)

print(
    "SM3_09C7_B3E_A3_STATIC_CONTRACT_ATTACK_COMPLETE"
)
