from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


CANDIDATE = Path(sys.argv[1])
BASELINE = Path(sys.argv[2])
FOCUSED = Path(sys.argv[3])
S1 = Path(sys.argv[4])
S2 = Path(sys.argv[5])
PRECEDENCE = Path(sys.argv[6])
FREEZE = Path(sys.argv[7])
POLICY = Path(sys.argv[8])
CLOSEOUT = Path(sys.argv[9])


EXPECTED = {
    "candidate":
        "848537b62be672c51b2ecd6c4079ad2057382c01034d2bdd2b0a50191055dc4d",

    "baseline":
        "42cbc79706a7096460553f2d3c8ac0c2ffd92d7b6b40dab91bd8dd3ddef9ce6c",

    "focused":
        "6240c58eaf7e090f3e86f9213bd6651d569d4c3e315f457c3fb1e6ceb7374c2f",

    "s1":
        "e4bf98e05d8205c3a4e277577279afa2e9f433ec43086407901c8d7118832902",

    "s2":
        "498b2f0f9c1f11ef269a2c2d652ddcf615525690ae4749ae181bf6ecae10d2ba",

    "precedence":
        "7e6ac7650011b5daa0295626819e162b9fd933553d6f24401d5ddb2e70769978",

    "freeze":
        "5d2a862320bbec095feb3e5b413685ee0944e056f6e71f911f6e7ed76451072c",
}


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load(
    path: Path,
):

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def write(
    path: Path,
    value,
):

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


actual = {
    "candidate":
        sha256(
            CANDIDATE
        ),

    "baseline":
        sha256(
            BASELINE
        ),

    "focused":
        sha256(
            FOCUSED
        ),

    "s1":
        sha256(
            S1
        ),

    "s2":
        sha256(
            S2
        ),

    "precedence":
        sha256(
            PRECEDENCE
        ),

    "freeze":
        sha256(
            FREEZE
        ),
}


if actual != EXPECTED:

    raise SystemExit(
        "S3_ARTIFACT_LINEAGE_SHA_MISMATCH:"
        + json.dumps(
            actual,
            sort_keys=True,
        )
    )


baseline = load(
    BASELINE
)

focused = load(
    FOCUSED
)

s1 = load(
    S1
)

s2 = load(
    S2
)

precedence = load(
    PRECEDENCE
)


# ============================================================
# 4. FUNCTIONAL F1 EVIDENCE
# ============================================================

functional_checks = {
    "BASELINE_28_OF_28":
        (
            baseline.get(
                "test_count"
            )
            == 28
            and
            baseline.get(
                "pass_count"
            )
            == 28
            and
            baseline.get(
                "failure_count"
            )
            == 0
            and
            baseline.get(
                "behavior_pass"
            )
            is True
        ),

    "FOCUSED_19_OF_19":
        (
            focused.get(
                "test_count"
            )
            == 19
            and
            focused.get(
                "pass_count"
            )
            == 19
            and
            focused.get(
                "failure_count"
            )
            == 0
            and
            focused.get(
                "behavior_pass"
            )
            is True
        ),

    "CANDIDATE_SHA_MATCHES_REPORT":
        focused.get(
            "engine_sha256"
        )
        == EXPECTED[
            "candidate"
        ],

    "IMPLEMENTATION_REVISION_R2":
        focused.get(
            "implementation_revision"
        )
        == "R2",

    "CAUSAL_INVARIANT_PRESERVED":
        focused.get(
            "causal_invariant_preserved"
        )
        is True,

    "BACKWARD_ERROR_COMPATIBILITY":
        focused.get(
            "backward_compatible_error_semantics"
        )
        is True,

    "AST_SIDE_EFFECT_AUDIT_PASS":
        focused.get(
            "ast_side_effect_audit_pass"
        )
        is True,

    "CONFIDENCE_DECAY_STILL_DISABLED":
        focused.get(
            "confidence_decay_applied"
        )
        is False,

    "RUNTIME_NOT_INTEGRATED":
        focused.get(
            "runtime_integrated"
        )
        is False,
}


functional_pass = all(
    functional_checks.values()
)


# ============================================================
# 5. MUTATION ATTRIBUTION EVIDENCE
# ============================================================

attribution_checks = {
    "S1_EXECUTION_CLEAN":
        (
            s1.get(
                "status"
            )
            == "PRODUCTION_STATE_CONCURRENT_WRITER_AUDIT_COMPLETE"
            and
            s1.get(
                "added_count"
            )
            == 0
            and
            s1.get(
                "removed_count"
            )
            == 0
            and
            s1.get(
                "changed_count"
            )
            == 0
        ),

    "F1_EXACTLY_ONE_WATCHDOG_SNAPSHOT":
        s2.get(
            "watchdog_snapshot_count_in_f1_window"
        )
        == 1,

    "F1_NO_OTHER_PRODUCTION_STATE_RECORD":
        s2.get(
            "other_production_state_record_count_in_f1_window"
        )
        == 0,

    "EXACT_PLUS_ONE_WATCHDOG_CANDIDATE":
        s2.get(
            "exact_plus_one_watchdog_candidate"
        )
        is True,

    "NO_UNATTRIBUTED_INCREMENT":
        s2.get(
            "unattributed_increment_candidate_count"
        )
        == 0,

    "WATCHDOG_PERIODIC_PATTERN":
        s2.get(
            "watchdog_periodic_5m_pattern"
        )
        is True,

    "WATCHDOG_IMPLEMENTATION_IN_RUNTIME":
        s2.get(
            "runtime_watchdog_implementation_present"
        )
        is True,

    "DELTA_ATTRIBUTED_TO_WATCHDOG":
        s2.get(
            "f1_count_delta_attributable_to_watchdog"
        )
        is True,

    "CANDIDATE_EXONERATED":
        s2.get(
            "f1_candidate_exonerated_from_count_delta"
        )
        is True,

    "GLOBAL_COUNT_INVARIANT_REJECTED":
        s2.get(
            "total_file_count_equality_is_valid_global_invariant"
        )
        is False,

    "SCOPE_ACCOUNTING_REQUIRED":
        s2.get(
            "scope_aware_mutation_accounting_required"
        )
        is True,
}


attribution_pass = all(
    attribution_checks.values()
)


# ============================================================
# 6. PRECEDENCE CONTRACT STILL AUTHORITATIVE
# ============================================================

precedence_checks = {
    "PRECEDENCE_FREEZE_VALID":
        precedence.get(
            "status"
        )
        == "TEMPORAL_ERROR_PRECEDENCE_CONTRACT_FROZEN",

    "CAUSAL_INVARIANT_PRESERVED":
        precedence.get(
            "causal_invariant_preserved"
        )
        is True,

    "BACKWARD_COMPATIBILITY_REQUIRED":
        precedence.get(
            "backward_compatible_error_semantics_required"
        )
        is True,
}


precedence_pass = all(
    precedence_checks.values()
)


# ============================================================
# 7. SCOPE-AWARE MUTATION ACCOUNTING POLICY
# ============================================================

policy = {
    "contract_version":
        "SM3_TEST_MUTATION_ACCOUNTING_POLICY_V1",

    "status":
        "FROZEN",

    "purpose":
        (
            "Prevent false isolation failures in a production-state "
            "tree containing independently scheduled background writers "
            "while preserving fail-closed mutation detection."
        ),

    "global_file_count_equality": {
        "required":
            False,

        "use":
            "INFORMATIONAL_ONLY",

        "reason":
            (
                "Known append-only background stores may legitimately "
                "change total production_state file count during an "
                "otherwise isolated test."
            ),
    },

    "mandatory_invariants": {
        "worker_runtime_sha_immutable":
            True,

        "canonical_source_sha_immutable_when_not_under_test":
            True,

        "candidate_sha_immutable_after_freeze":
            True,

        "protected_scope_hash_accounting_required":
            True,

        "unknown_mutation_fails_closed":
            True,

        "background_mutation_requires_explicit_attribution":
            True,

        "background_allowance_must_not_mask_protected_scope":
            True,
    },

    "currently_recognized_background_writer": {
        "writer_id":
            "SM3_RUNNER_WATCHDOG_V1",

        "store_version":
            "SM3_RUNNER_WATCHDOG_STORE_V1",

        "observed_period_seconds_approx":
            300,

        "allowed_mutations": [
            {
                "path_pattern":
                    "culture_runner_watchdog/snapshots/*.json",

                "mutation_type":
                    "APPEND_NEW_IMMUTABLE_SNAPSHOT",

                "requirements": [
                    "contract_version == SM3_RUNNER_WATCHDOG_V1",
                    "store_version == SM3_RUNNER_WATCHDOG_STORE_V1",
                    "new path must be outside declared protected scope",
                ],
            },
            {
                "path":
                    "culture_runner_watchdog/latest.json",

                "mutation_type":
                    "MUTABLE_POINTER_UPDATE",

                "requirements": [
                    "contract_version == SM3_RUNNER_WATCHDOG_V1",
                    "pointer mutation must be outside declared protected scope",
                ],
            },
        ],
    },

    "not_globally_allowlisted": [
        "culture_runner_control/**",
        "all other production_state paths",
    ],

    "future_gate_algorithm": [
        "capture runtime SHA",
        "declare exact protected production-state scopes",
        "inventory protected scopes before execution",
        "execute test",
        "inventory protected scopes after execution",
        "classify all observed production-state mutations",
        "allow only explicitly attributed recognized background mutations outside protected scopes",
        "fail closed on unknown or protected-scope mutation",
        "verify runtime SHA",
    ],

    "forbidden_shortcuts": [
        "IGNORE_ALL_BACKGROUND_CHANGES",
        "ALLOW_ANY_CULTURE_RUNNER_MUTATION",
        "USE_GLOBAL_FILE_COUNT_AS_SOLE_ISOLATION_PROOF",
        "ALLOW_WATCHDOG_MUTATION_INSIDE_PROTECTED_SCOPE",
        "IGNORE_UNKNOWN_MUTATION",
    ],

    "evidence": {
        "s1_report_sha256":
            EXPECTED[
                "s1"
            ],

        "s2_report_sha256":
            EXPECTED[
                "s2"
            ],
    },
}


write(
    POLICY,
    policy,
)


policy_sha = sha256(
    POLICY
)


# ============================================================
# 8. F1 CLOSEOUT
# ============================================================

f1_closeout_pass = (
    functional_pass
    and
    attribution_pass
    and
    precedence_pass
)


closeout = {
    "phase":
        "09C7-B3E-A4-R2-F1-S3",

    "status":
        (
            "F1_CLOSED_PASS"
            if f1_closeout_pass
            else
            "F1_CLOSEOUT_BLOCKED"
        ),

    "original_f1_result_preserved":
        True,

    "original_f1_final_gate":
        "FAIL",

    "original_f1_failure_reason":
        "GLOBAL_PRODUCTION_STATE_FILE_COUNT_CHANGED_601_TO_602",

    "failure_reclassified_as":
        "ISOLATION_GATE_METHODOLOGY_FALSE_POSITIVE",

    "functional_candidate_status":
        "PASS",

    "functional_checks":
        functional_checks,

    "functional_pass":
        functional_pass,

    "mutation_attribution_checks":
        attribution_checks,

    "mutation_attribution_pass":
        attribution_pass,

    "precedence_checks":
        precedence_checks,

    "precedence_pass":
        precedence_pass,

    "candidate_sha256":
        EXPECTED[
            "candidate"
        ],

    "candidate_revision":
        "R2",

    "f1_count_delta":
        1,

    "f1_count_delta_attributed_to":
        "SM3_RUNNER_WATCHDOG_V1",

    "candidate_exonerated_from_delta":
        attribution_pass,

    "runtime_v2_integrated":
        False,

    "runtime_integration_allowed_after_this_closeout":
        False,

    "scope_aware_mutation_policy_version":
        policy[
            "contract_version"
        ],

    "scope_aware_mutation_policy_sha256":
        policy_sha,

    "next_gate":
        (
            "09C7-B3E-A4-A2_TEMPORAL_ADVERSARIAL_REATTACK"
            if f1_closeout_pass
            else
            "F1_CLOSEOUT_REMEDIATION_REQUIRED"
        ),

    "artifact_lineage": actual,

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


write(
    CLOSEOUT,
    closeout,
)


closeout_sha = sha256(
    CLOSEOUT
)


print(
    "=== F1 FUNCTIONAL CLOSEOUT ==="
)


for name,value in functional_checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print(
    "\nFUNCTIONAL_PASS="
    + str(
        functional_pass
    )
)


print(
    "\n=== MUTATION ATTRIBUTION ==="
)


for name,value in attribution_checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print(
    "\nMUTATION_ATTRIBUTION_PASS="
    + str(
        attribution_pass
    )
)


print(
    "\n=== MUTATION ACCOUNTING POLICY ==="
)

print(
    "POLICY_VERSION="
    + policy[
        "contract_version"
    ]
)

print(
    "GLOBAL_FILE_COUNT_EQUALITY_REQUIRED=False"
)

print(
    "UNKNOWN_MUTATION_FAILS_CLOSED=True"
)

print(
    "PROTECTED_SCOPE_ACCOUNTING_REQUIRED=True"
)

print(
    "WATCHDOG_BACKGROUND_WRITER_RECOGNIZED=True"
)

print(
    "POLICY_SHA256="
    + policy_sha
)


print(
    "\n=== F1 VERDICT ==="
)

print(
    "ORIGINAL_F1_RESULT_PRESERVED=True"
)

print(
    "ORIGINAL_F1_FINAL_GATE=FAIL"
)

print(
    "FAILURE_RECLASSIFIED_AS="
    "ISOLATION_GATE_METHODOLOGY_FALSE_POSITIVE"
)

print(
    "CANDIDATE_EXONERATED_FROM_DELTA="
    + str(
        attribution_pass
    )
)

print(
    "F1_CLOSED_PASS="
    + str(
        f1_closeout_pass
    )
)

print(
    "RUNTIME_V2_INTEGRATED=False"
)

print(
    "RUNTIME_INTEGRATION_ALLOWED=False"
)

print(
    "NEXT_GATE="
    + closeout[
        "next_gate"
    ]
)

print(
    "CLOSEOUT_SHA256="
    + closeout_sha
)

print(
    "SM3_09C7_B3E_A4_R2_F1_S3_CLOSEOUT_COMPLETE"
)


if not f1_closeout_pass:

    raise SystemExit(
        1
    )
