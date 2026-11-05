from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


plan_path = Path(sys.argv[1])
evidence_path = Path(sys.argv[2])

expected_binding_sha = sys.argv[3]
expected_reattack_data_sha = sys.argv[4]
expected_reattack_report_sha = sys.argv[5]
expected_sequence_sha = sys.argv[6]
expected_worker_sha = sys.argv[7]
expected_temporal_sha = sys.argv[8]


def load(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


plan = load(plan_path)
evidence = load(evidence_path)


# ============================================================
# CONTRACT / LINEAGE
# ============================================================

contract_exact = (
    plan.get("contract_version")
    == "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_V1"
    and plan.get("requirement_id")
    == "A5-R04"
    and plan.get("implementation_unit")
    == "A5-I01"
    and plan.get("implementation_name")
    == "TEMPORAL_CONSUMER_ENFORCEMENT"
)


source_hash_lineage_pass = (
    plan.get("source_binding_contract_v2_sha256")
    == expected_binding_sha
    and plan.get("source_binding_adversarial_reattack_data_sha256")
    == expected_reattack_data_sha
    and plan.get("source_binding_adversarial_reattack_report_sha256")
    == expected_reattack_report_sha
    and plan.get("source_sequence_freeze_sha256")
    == expected_sequence_sha
    and plan.get("source_worker_sha256")
    == expected_worker_sha
    and plan.get("source_temporal_sha256")
    == expected_temporal_sha
)


# ============================================================
# HANDLER ANCHORS
# ============================================================

handlers = plan.get(
    "handler_evidence",
    {}
)


expected_handlers = {
    "EVIDENCE": {
        "handler":
            "production_platform_dynamics_evidence_ingest",

        "request_model":
            "PlatformDynamicsEvidenceRequest",

        "request_parameter":
            "req",

        "validator":
            "validate_evidence_temporal",

        "line_start":
            22423,

        "line_end":
            22486,

        "source_sha256":
            "bc6743813ac14616c196a491af9f2749fb8e293379f7259ab8467a83875a007a",

        "first_mutation_line":
            22439,

        "first_mutation_line_sha256":
            "303e67553fa6550892b75c0ce5b8d9c95b6a79ccc899f06e72eb2fcbf7ea2fd7",
    },

    "PREFERENCE_SIGNAL": {
        "handler":
            "production_platform_preference_signal_ingest",

        "request_model":
            "PlatformPreferenceSignalRequest",

        "request_parameter":
            "req",

        "validator":
            "validate_signal_temporal",

        "line_start":
            22490,

        "line_end":
            22556,

        "source_sha256":
            "5978cab3b57e254f67ac511335eeb2e92aadff67f8dbf38d85c8a031084a9c9c",

        "first_mutation_line":
            22535,

        "first_mutation_line_sha256":
            "9f77784f1107aca689652b696eb78a0d166575a777a5c767b7fc2fb543fd2455",
    },

    "SNAPSHOT": {
        "handler":
            "production_platform_dynamics_snapshot_build",

        "request_model":
            "PlatformDynamicsSnapshotRequest",

        "request_parameter":
            "req",

        "validator":
            "validate_snapshot_temporal_inputs",

        "line_start":
            22560,

        "line_end":
            22632,

        "source_sha256":
            "0508630cf407b5b06528c70cb6ba42a741ea2d552089c5a1eb63aaddb99922bf",

        "first_mutation_line":
            22585,

        "first_mutation_line_sha256":
            "658f44dca8213ac6bed11d4ebf742269de24b1b2cba5cd195b108da3c0deab95",
    },
}


handler_anchor_pass = (
    set(handlers)
    == set(expected_handlers)
)


if handler_anchor_pass:

    for consumer, expected in expected_handlers.items():

        actual = handlers[consumer]

        for key, expected_value in expected.items():

            if actual.get(key) != expected_value:

                handler_anchor_pass = False


# ============================================================
# OPERATIONS
# ============================================================

operations_list = plan.get(
    "operations",
    []
)

operations = {
    item.get("consumer"):
        item
    for item in operations_list
}


operations_exact = (
    plan.get("operation_count") == 3
    and len(operations_list) == 3
    and set(operations)
    == {
        "EVIDENCE",
        "PREFERENCE_SIGNAL",
        "SNAPSHOT",
    }
)


if operations_exact:

    evidence_op = operations["EVIDENCE"]
    signal_op = operations["PREFERENCE_SIGNAL"]
    snapshot_op = operations["SNAPSHOT"]


    operations_exact = all([
        evidence_op.get("operation_id")
        == "A5-I01-P01",

        evidence_op.get("validator")
        == "validate_evidence_temporal",

        evidence_op.get("request_parameter")
        == "req",

        evidence_op.get("temporal_input_fields")
        == [
            "source_date",
            "observed_at",
            "valid_until",
        ],

        evidence_op.get("as_of_binding")
        == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        evidence_op.get("first_mutation_line")
        == 22439,

        signal_op.get("operation_id")
        == "A5-I01-P02",

        signal_op.get("validator")
        == "validate_signal_temporal",

        signal_op.get("request_parameter")
        == "req",

        signal_op.get("temporal_input_fields")
        == [
            "window_started_at",
            "window_ended_at",
        ],

        signal_op.get("as_of_binding")
        == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        signal_op.get("first_mutation_line")
        == 22535,

        snapshot_op.get("operation_id")
        == "A5-I01-P03",

        snapshot_op.get("validator")
        == "validate_snapshot_temporal_inputs",

        snapshot_op.get("request_parameter")
        == "req",

        snapshot_op.get("call_style")
        == "KEYWORD_ONLY_EXACT",

        snapshot_op.get("keyword_argument_order")
        == [
            "as_of",
            "evidence",
            "signals",
        ],

        snapshot_op.get(
            "keyword_argument_bindings",
            {}
        ).get("as_of")
        == "request.as_of",

        snapshot_op.get("first_mutation_line")
        == 22585,
    ])


# ============================================================
# COMMON OPERATION SAFETY
# ============================================================

common_operation_policy_pass = (
    operations_exact
)


if common_operation_policy_pass:

    for item in operations_list:

        if (
            item.get("validator_result_policy")
            != "VALIDATION_GATE_ONLY_DO_NOT_REWRITE_EXISTING_PERSISTED_RECORD_SEMANTICS"
        ):
            common_operation_policy_pass = False


        if (
            item.get("error_policy")
            != "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION"
        ):
            common_operation_policy_pass = False


# ============================================================
# DIFF BUDGET
# ============================================================

diff_budget = plan.get(
    "diff_budget",
    {}
)


diff_budget_pass = all([
    diff_budget.get("candidate_worker_only") is True,
    diff_budget.get("canonical_worker_mutation_allowed") is False,
    diff_budget.get("temporal_module_mutation_allowed") is False,
    diff_budget.get("dockerfile_mutation_allowed") is False,
    diff_budget.get("request_model_schema_change_allowed") is False,
    diff_budget.get("route_change_allowed") is False,
    diff_budget.get("response_contract_change_allowed") is False,
    diff_budget.get("storage_schema_change_allowed") is False,
    diff_budget.get("existing_persistence_semantics_change_allowed") is False,
    diff_budget.get("provider_call_change_allowed") is False,
    diff_budget.get("model_call_change_allowed") is False,
    diff_budget.get("external_scraping_change_allowed") is False,
    diff_budget.get("worker_version_change_in_candidate_allowed") is False,
])


# ============================================================
# IMPLEMENTATION STRATEGY
# ============================================================

strategy = plan.get(
    "implementation_strategy",
    {}
)


strategy_pass = all([
    strategy.get("line_number_only_patch_allowed") is False,
    strategy.get("handler_source_hash_authority") is True,
    strategy.get("first_mutation_fingerprint_authority") is True,
    strategy.get("server_utc_clock_semantics") == "TIMEZONE_AWARE_UTC",
    strategy.get("server_utc_clock_capture_frequency") == "EXACTLY_ONCE_PER_INGEST_HANDLER_INVOCATION",
    strategy.get("server_utc_clock_not_request_controlled") is True,
    strategy.get("validator_calls_must_precede_mutation") is True,
    strategy.get("snapshot_record_resolution_may_precede_validator") is True,
    strategy.get("snapshot_state_mutation_may_precede_validator") is False,
    strategy.get("validation_failure_state_delta") == 0,
    strategy.get("temporal_public_api_only") is True,
    strategy.get("private_temporal_helper_calls_allowed") is False,
    strategy.get("preserve_existing_success_path") is True,
    strategy.get("preserve_existing_idempotence") is True,
])


# ============================================================
# STATIC ASSERTIONS
# ============================================================

static_assertions = plan.get(
    "static_assertions",
    []
)


required_static_assertions = {
    "CANONICAL_WORKER_SHA_REMAINS_SOURCE_ANCHOR",
    "TEMPORAL_MODULE_SHA_UNCHANGED",
    "ONLY_THREE_TARGET_HANDLER_BODIES_MAY_CHANGE",
    "NO_ROUTE_DECORATOR_CHANGE",
    "NO_REQUEST_MODEL_SCHEMA_CHANGE",
    "NO_RESPONSE_MODEL_CONTRACT_CHANGE",
    "EVIDENCE_HANDLER_CALLS_VALIDATE_EVIDENCE_TEMPORAL",
    "SIGNAL_HANDLER_CALLS_VALIDATE_SIGNAL_TEMPORAL",
    "SNAPSHOT_HANDLER_CALLS_VALIDATE_SNAPSHOT_TEMPORAL_INPUTS",
    "EVIDENCE_TEMPORAL_CALL_DOMINATES_FIRST_MUTATION",
    "SIGNAL_TEMPORAL_CALL_DOMINATES_FIRST_MUTATION",
    "SNAPSHOT_TEMPORAL_CALL_DOMINATES_FIRST_MUTATION",
    "SNAPSHOT_VALIDATOR_CALL_USES_KEYWORD_ONLY_AS_OF_EVIDENCE_SIGNALS",
    "NO_PRIVATE_TEMPORAL_PARSER_DIRECT_CALL",
    "NO_PROVIDER_CALL_ADDED",
    "NO_MODEL_CALL_ADDED",
    "NO_EXTERNAL_SCRAPING_ADDED",
}


static_assertions_pass = (
    len(static_assertions) == 17
    and set(static_assertions)
    == required_static_assertions
)


# ============================================================
# DYNAMIC TEST MATRIX
# ============================================================

dynamic_tests = plan.get(
    "dynamic_test_matrix",
    []
)


expected_test_ids = {
    "A5-I01-D01",
    "A5-I01-D02",
    "A5-I01-D03",
    "A5-I01-D04",
    "A5-I01-D05",
    "A5-I01-D06",
    "A5-I01-D07",
    "A5-I01-D08",
}


dynamic_test_matrix_pass = (
    len(dynamic_tests) == 8
    and {
        item.get("test_id")
        for item in dynamic_tests
    }
    == expected_test_ids
)


invalid_expected = []


for item in dynamic_tests:

    if item.get("expected") not in {
        "EXISTING_SUCCESS_PATH_PRESERVED",
        "TEMPORAL_VALIDITY_ERROR_AND_ZERO_STATE_MUTATION",
        "ZERO_PARTIAL_STATE_AND_NO_DUPLICATE_SIDE_EFFECT",
    }:

        invalid_expected.append(
            item.get("test_id")
        )


if invalid_expected:
    dynamic_test_matrix_pass = False


# ============================================================
# CANDIDATE POLICY
# ============================================================

candidate = plan.get(
    "candidate_policy",
    {}
)


candidate_policy_pass = all([
    candidate.get("candidate_root")
    == "worker/candidates/A5_I01_temporal_consumer_enforcement",

    candidate.get("candidate_worker_relative_path")
    == "worker/candidates/A5_I01_temporal_consumer_enforcement/worker_service.py",

    candidate.get("candidate_manifest_relative_path")
    == "worker/candidates/A5_I01_temporal_consumer_enforcement/manifest.json",

    candidate.get("candidate_generation_authorized") is False,

    candidate.get("candidate_execution_authorized") is False,

    candidate.get("candidate_container_authorized") is False,

    candidate.get("canonical_materialization_authorized") is False,

    candidate.get("production_deployment_authorized") is False,

    candidate.get("candidate_generation_requires_plan_adversarial_review") is True,
])


# ============================================================
# GLOBAL SAFETY / AUTHORIZATION
# ============================================================

global_safety = plan.get(
    "global_safety",
    {}
)


global_safety_pass = all([
    global_safety.get("canonical_worker_read_only") is True,
    global_safety.get("temporal_module_read_only") is True,
    global_safety.get("production_read_only") is True,
    global_safety.get("no_build") is True,
    global_safety.get("no_container_creation") is True,
    global_safety.get("no_container_recreation") is True,
    global_safety.get("no_provider_call") is True,
    global_safety.get("no_model_call") is True,
    global_safety.get("no_external_scraping") is True,
    global_safety.get(
        "semantic_priority_decision_cache_hit_audit_still_required_before_any_real_semantic_model_call"
    ) is True,
])


authorization_closed = all([
    plan.get("implementation_plan_frozen") is True,
    plan.get("implementation_authorized") is False,
    plan.get("candidate_generation_authorized") is False,
    plan.get("candidate_execution_authorized") is False,
    plan.get("canonical_source_mutation_authorized") is False,
    plan.get("production_mutation_authorized") is False,
])


# ============================================================
# EVIDENCE ARTIFACT
# ============================================================

evidence_pass = all([
    evidence.get("contract_version")
    == "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_FREEZE_EVIDENCE_V1",

    evidence.get("source_worker_sha256")
    == expected_worker_sha,

    evidence.get("source_temporal_sha256")
    == expected_temporal_sha,

    evidence.get("source_binding_contract_v2_sha256")
    == expected_binding_sha,

    evidence.get("source_binding_reattack_data_sha256")
    == expected_reattack_data_sha,

    evidence.get("source_binding_reattack_report_sha256")
    == expected_reattack_report_sha,

    evidence.get("lineage_authorized") is True,
    evidence.get("i01_exact") is True,
    evidence.get("temporal_import_pass") is True,
    evidence.get("binding_exact") is True,
    evidence.get("handler_count") == 3,
    evidence.get("operation_count") == 3,
    evidence.get("static_assertion_count") == 17,
    evidence.get("dynamic_test_count") == 8,
    evidence.get("plan_freeze_pass") is True,
    evidence.get("persistence_pass") is True,
    evidence.get("implementation_plan_frozen") is True,
    evidence.get("implementation_authorized") is False,
    evidence.get("candidate_generation_authorized") is False,
    evidence.get("production_mutation_authorized") is False,
])


# ============================================================
# FINAL VERDICT
# ============================================================

checks = [
    contract_exact,
    source_hash_lineage_pass,
    handler_anchor_pass,
    operations_exact,
    common_operation_policy_pass,
    diff_budget_pass,
    strategy_pass,
    static_assertions_pass,
    dynamic_test_matrix_pass,
    candidate_policy_pass,
    global_safety_pass,
    authorization_closed,
    evidence_pass,
]


plan_verify_pass = all(
    checks
)


print(
    "PLAN_SHA256="
    + sha(plan_path)
)

print(
    "EVIDENCE_SHA256="
    + sha(evidence_path)
)

print(
    "PLAN_CONTRACT_EXACT="
    + str(contract_exact)
)

print(
    "SOURCE_HASH_LINEAGE_PASS="
    + str(source_hash_lineage_pass)
)

print(
    "HANDLER_ANCHOR_PASS="
    + str(handler_anchor_pass)
)

print(
    "OPERATIONS_EXACT="
    + str(operations_exact)
)

print(
    "COMMON_OPERATION_POLICY_PASS="
    + str(common_operation_policy_pass)
)

print(
    "DIFF_BUDGET_PASS="
    + str(diff_budget_pass)
)

print(
    "IMPLEMENTATION_STRATEGY_PASS="
    + str(strategy_pass)
)

print(
    "STATIC_ASSERTION_COUNT="
    + str(len(static_assertions))
)

print(
    "STATIC_ASSERTIONS_PASS="
    + str(static_assertions_pass)
)

print(
    "DYNAMIC_TEST_COUNT="
    + str(len(dynamic_tests))
)

print(
    "DYNAMIC_TEST_MATRIX_PASS="
    + str(dynamic_test_matrix_pass)
)

print(
    "CANDIDATE_POLICY_PASS="
    + str(candidate_policy_pass)
)

print(
    "GLOBAL_SAFETY_PASS="
    + str(global_safety_pass)
)

print(
    "AUTHORIZATION_CLOSED="
    + str(authorization_closed)
)

print(
    "EVIDENCE_ARTIFACT_PASS="
    + str(evidence_pass)
)

print(
    "PLAN_VERIFY_PASS="
    + str(plan_verify_pass)
)


raise SystemExit(
    0 if plan_verify_pass else 1
)