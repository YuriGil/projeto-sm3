from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


binding_path = Path(sys.argv[1])
reattack_data_path = Path(sys.argv[2])
reattack_report_path = Path(sys.argv[3])
sequence_path = Path(sys.argv[4])
worker_path = Path(sys.argv[5])
temporal_path = Path(sys.argv[6])
plan_path = Path(sys.argv[7])
evidence_path = Path(sys.argv[8])


def load(path: Path) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def sha(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def segment_sha(text: str) -> str:

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def source_segment(
    lines: list[str],
    start: int | None,
    end: int | None,
) -> str:

    if start is None:
        return ""

    if end is None:
        end = start

    return "\n".join(
        lines[start - 1:end]
    )


def annotation_text(
    node: ast.AST | None,
) -> str | None:

    if node is None:
        return None

    try:
        return ast.unparse(node)
    except Exception:
        return None


def call_name(
    node: ast.Call,
) -> str | None:

    if isinstance(
        node.func,
        ast.Name,
    ):
        return node.func.id

    if isinstance(
        node.func,
        ast.Attribute,
    ):
        return node.func.attr

    return None


def call_names(
    node: ast.AST,
) -> set[str]:

    result = set()

    for child in ast.walk(node):

        if isinstance(
            child,
            ast.Call,
        ):

            name = call_name(child)

            if name:
                result.add(name)

    return result


binding = load(binding_path)
reattack = load(reattack_data_path)
reattack_report = load(reattack_report_path)
sequence = load(sequence_path)


# ============================================================
# 1. LINEAGE AUTHORIZATION
# ============================================================

lineage_checks = [
    binding.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V2",

    binding.get(
        "revision"
    )
    == 2,

    binding.get(
        "requirement_id"
    )
    == "A5-R04",

    binding.get(
        "implementation_unit"
    )
    == "A5-I01",

    reattack.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REATTACK_V1",

    reattack.get(
        "review_complete"
    )
    is True,

    reattack.get(
        "finding_count"
    )
    == 0,

    reattack.get(
        "high_finding_count"
    )
    == 0,

    reattack.get(
        "medium_finding_count"
    )
    == 0,

    reattack.get(
        "contract_accepted_without_revision"
    )
    is True,

    reattack.get(
        "authorization_closed"
    )
    is True,

    reattack_report.get(
        "a5_i01_a2_a1_r1_pass"
    )
    is True,

    reattack_report.get(
        "classification"
    )
    == "A5_I01_REMEDIATED_TEMPORAL_BINDING_CONTRACT_SURVIVED_ADVERSARIAL_REATTACK",

    reattack_report.get(
        "next_gate"
    )
    == "09C7-B3E-A5-I01-A3_CANDIDATE_IMPLEMENTATION_PLAN_FREEZE",

    sequence.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_FREEZE_V2",
]


sequence_units = {
    item["unit_id"]:
        item
    for item in sequence.get(
        "sequence",
        [],
    )
}


i01 = sequence_units.get(
    "A5-I01"
)


i01_exact = (
    i01 is not None
    and i01.get(
        "order"
    )
    == 1
    and i01.get(
        "requirement_id"
    )
    == "A5-R04"
    and i01.get(
        "classification"
    )
    == "PARTIAL"
    and i01.get(
        "name"
    )
    == "TEMPORAL_CONSUMER_ENFORCEMENT"
    and list(
        i01.get(
            "prerequisites",
            [],
        )
        or []
    )
    == []
    and i01.get(
        "mutation_scope"
    )
    == "WORKER_CANDIDATE_ONLY"
)


lineage_authorized = (
    all(
        lineage_checks
    )
    and i01_exact
)


if not lineage_authorized:

    raise RuntimeError(
        "A5_I01_A3_LINEAGE_NOT_AUTHORIZED"
    )


# ============================================================
# 2. PARSE CURRENT WORKER
# ============================================================

worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_lines = worker_source.splitlines()

worker_tree = ast.parse(
    worker_source,
    filename=str(
        worker_path
    ),
)


functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


classes: dict[
    str,
    ast.ClassDef,
] = {}


for node in worker_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        functions[
            node.name
        ] = node

    elif isinstance(
        node,
        ast.ClassDef,
    ):

        classes[
            node.name
        ] = node


# ============================================================
# 3. TEMPORAL IMPORT AUTHORITY
# ============================================================

temporal_imports: dict[
    str,
    str,
] = {}


for node in worker_tree.body:

    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):

        for alias in node.names:

            temporal_imports[
                alias.asname
                or alias.name
            ] = alias.name


required_imports = {
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
}


temporal_import_pass = (
    required_imports
    .issubset(
        set(
            temporal_imports.values()
        )
    )
)


if not temporal_import_pass:

    raise RuntimeError(
        "REQUIRED_TEMPORAL_IMPORTS_NOT_PRESENT"
    )


# ============================================================
# 4. TARGET HANDLERS
# ============================================================

targets = {
    "EVIDENCE": {
        "handler":
            "production_platform_dynamics_evidence_ingest",

        "request_model":
            "PlatformDynamicsEvidenceRequest",

        "validator":
            "validate_evidence_temporal",

        "route":
            "/production/culture-intelligence/platform-dynamics/evidence",
    },

    "PREFERENCE_SIGNAL": {
        "handler":
            "production_platform_preference_signal_ingest",

        "request_model":
            "PlatformPreferenceSignalRequest",

        "validator":
            "validate_signal_temporal",

        "route":
            "/production/culture-intelligence/platform-preference-signals",
    },

    "SNAPSHOT": {
        "handler":
            "production_platform_dynamics_snapshot_build",

        "request_model":
            "PlatformDynamicsSnapshotRequest",

        "validator":
            "validate_snapshot_temporal_inputs",

        "route":
            "/production/culture-intelligence/platform-dynamics/snapshots",
    },
}


handler_evidence = {}


for consumer, spec in targets.items():

    handler = functions.get(
        spec["handler"]
    )


    if handler is None:

        raise RuntimeError(
            "TARGET_HANDLER_MISSING:"
            + spec["handler"]
        )


    request_parameters = []


    for arg in handler.args.args:

        annotation = (
            annotation_text(
                arg.annotation
            )
        )


        if annotation == spec[
            "request_model"
        ]:

            request_parameters.append(
                arg.arg
            )


    if len(
        request_parameters
    ) != 1:

        raise RuntimeError(
            "REQUEST_PARAMETER_CARDINALITY_INVALID:"
            + consumer
        )


    request_parameter = (
        request_parameters[0]
    )


    source = source_segment(
        worker_lines,
        getattr(
            handler,
            "lineno",
            None,
        ),
        getattr(
            handler,
            "end_lineno",
            None,
        ),
    )


    current_calls = call_names(
        handler
    )


    if spec[
        "validator"
    ] in current_calls:

        raise RuntimeError(
            "CURRENT_CANONICAL_HANDLER_ALREADY_CALLS_VALIDATOR:"
            + consumer
        )


    frozen_boundary = (
        binding[
            "bindings"
        ][
            consumer
        ][
            "first_mutation_boundary"
        ]
    )


    boundary_line = (
        frozen_boundary[
            "current_line"
        ]
    )


    current_boundary_line = (
        worker_lines[
            boundary_line - 1
        ]
    )


    current_boundary_sha = (
        segment_sha(
            current_boundary_line
        )
    )


    boundary_pass = (
        current_boundary_sha
        == frozen_boundary[
            "current_statement_line_sha256"
        ]
    )


    if not boundary_pass:

        raise RuntimeError(
            "FIRST_MUTATION_BOUNDARY_DRIFT:"
            + consumer
        )


    handler_evidence[
        consumer
    ] = {
        "handler":
            spec[
                "handler"
            ],

        "route":
            spec[
                "route"
            ],

        "request_model":
            spec[
                "request_model"
            ],

        "request_parameter":
            request_parameter,

        "validator":
            spec[
                "validator"
            ],

        "line_start":
            getattr(
                handler,
                "lineno",
                None,
            ),

        "line_end":
            getattr(
                handler,
                "end_lineno",
                None,
            ),

        "source_sha256":
            segment_sha(
                source
            ),

        "first_mutation_line":
            boundary_line,

        "first_mutation_line_sha256":
            current_boundary_sha,

        "validator_currently_called":
            False,
    }


# ============================================================
# 5. BINDING CONTRACT EXACTNESS
# ============================================================

b = binding[
    "bindings"
]


binding_exact = all([
    b[
        "EVIDENCE"
    ][
        "temporal_input_fields"
    ]
    == [
        "source_date",
        "observed_at",
        "valid_until",
    ],

    b[
        "PREFERENCE_SIGNAL"
    ][
        "temporal_input_fields"
    ]
    == [
        "window_started_at",
        "window_ended_at",
    ],

    b[
        "EVIDENCE"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    b[
        "PREFERENCE_SIGNAL"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    b[
        "SNAPSHOT"
    ][
        "as_of_binding"
    ]
    == "request.as_of",

    b[
        "SNAPSHOT"
    ][
        "call_style"
    ]
    == "KEYWORD_ONLY_EXACT",

    b[
        "SNAPSHOT"
    ][
        "required_keyword_only_parameters"
    ]
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    b[
        "SNAPSHOT"
    ][
        "keyword_argument_bindings"
    ][
        "as_of"
    ]
    == "request.as_of",

    b[
        "SNAPSHOT"
    ][
        "internal_as_of_forwarding_evidence_proven"
    ]
    is True,

    b[
        "SNAPSHOT"
    ][
        "internal_as_of_forwarding_signal_proven"
    ]
    is True,
])


if not binding_exact:

    raise RuntimeError(
        "BINDING_CONTRACT_NOT_EXACT"
    )


# ============================================================
# 6. CANDIDATE PATCH OPERATIONS
# ============================================================

operations = [
    {
        "operation_id":
            "A5-I01-P01",

        "consumer":
            "EVIDENCE",

        "handler":
            targets[
                "EVIDENCE"
            ][
                "handler"
            ],

        "validator":
            "validate_evidence_temporal",

        "request_parameter":
            handler_evidence[
                "EVIDENCE"
            ][
                "request_parameter"
            ],

        "payload_binding":
            "FULL_REQUEST_MODEL_MAPPING",

        "payload_serialization_policy":
            "PYDANTIC_FULL_MODEL_MAPPING_PRESERVE_ALL_EXISTING_REQUEST_FIELDS",

        "temporal_input_fields":
            [
                "source_date",
                "observed_at",
                "valid_until",
            ],

        "as_of_binding":
            "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        "server_clock_policy":
            "ONE_TIMEZONE_AWARE_UTC_CAPTURE_PER_HANDLER_INVOCATION",

        "validator_result_policy":
            "VALIDATION_GATE_ONLY_DO_NOT_REWRITE_EXISTING_PERSISTED_RECORD_SEMANTICS",

        "placement":
            "AFTER_REQUEST_ENTRY_BEFORE_FIRST_STATE_MUTATION",

        "first_mutation_line":
            handler_evidence[
                "EVIDENCE"
            ][
                "first_mutation_line"
            ],

        "error_policy":
            "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION",
    },


    {
        "operation_id":
            "A5-I01-P02",

        "consumer":
            "PREFERENCE_SIGNAL",

        "handler":
            targets[
                "PREFERENCE_SIGNAL"
            ][
                "handler"
            ],

        "validator":
            "validate_signal_temporal",

        "request_parameter":
            handler_evidence[
                "PREFERENCE_SIGNAL"
            ][
                "request_parameter"
            ],

        "payload_binding":
            "FULL_REQUEST_MODEL_MAPPING",

        "payload_serialization_policy":
            "PYDANTIC_FULL_MODEL_MAPPING_PRESERVE_ALL_EXISTING_REQUEST_FIELDS",

        "temporal_input_fields":
            [
                "window_started_at",
                "window_ended_at",
            ],

        "as_of_binding":
            "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        "server_clock_policy":
            "ONE_TIMEZONE_AWARE_UTC_CAPTURE_PER_HANDLER_INVOCATION",

        "validator_result_policy":
            "VALIDATION_GATE_ONLY_DO_NOT_REWRITE_EXISTING_PERSISTED_RECORD_SEMANTICS",

        "placement":
            "AFTER_REQUEST_ENTRY_BEFORE_FIRST_STATE_MUTATION",

        "first_mutation_line":
            handler_evidence[
                "PREFERENCE_SIGNAL"
            ][
                "first_mutation_line"
            ],

        "error_policy":
            "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION",
    },


    {
        "operation_id":
            "A5-I01-P03",

        "consumer":
            "SNAPSHOT",

        "handler":
            targets[
                "SNAPSHOT"
            ][
                "handler"
            ],

        "validator":
            "validate_snapshot_temporal_inputs",

        "request_parameter":
            handler_evidence[
                "SNAPSHOT"
            ][
                "request_parameter"
            ],

        "call_style":
            "KEYWORD_ONLY_EXACT",

        "keyword_argument_order":
            [
                "as_of",
                "evidence",
                "signals",
            ],

        "keyword_argument_bindings": {
            "as_of":
                "request.as_of",

            "evidence":
                "RESOLVED_EVIDENCE_RECORDS_FROM_REQUEST_EVIDENCE_IDS",

            "signals":
                "RESOLVED_PREFERENCE_SIGNAL_RECORDS_FROM_REQUEST_PREFERENCE_SIGNAL_IDS",
        },

        "resolution_policy":
            "RESOLVE_EXISTING_REFERENCED_RECORDS_BEFORE_VALIDATION_NO_NEW_STATE",

        "validator_result_policy":
            "VALIDATION_GATE_ONLY_DO_NOT_REWRITE_EXISTING_PERSISTED_RECORD_SEMANTICS",

        "placement":
            "AFTER_REFERENCED_RECORD_RESOLUTION_BEFORE_FIRST_STATE_MUTATION",

        "first_mutation_line":
            handler_evidence[
                "SNAPSHOT"
            ][
                "first_mutation_line"
            ],

        "error_policy":
            "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION",
    },
]


# ============================================================
# 7. DIFF BUDGET
# ============================================================

diff_budget = {
    "candidate_worker_only":
        True,

    "canonical_worker_mutation_allowed":
        False,

    "temporal_module_mutation_allowed":
        False,

    "dockerfile_mutation_allowed":
        False,

    "request_model_schema_change_allowed":
        False,

    "route_change_allowed":
        False,

    "response_contract_change_allowed":
        False,

    "storage_schema_change_allowed":
        False,

    "existing_persistence_semantics_change_allowed":
        False,

    "provider_call_change_allowed":
        False,

    "model_call_change_allowed":
        False,

    "external_scraping_change_allowed":
        False,

    "allowed_handler_body_changes":
        [
            targets[
                "EVIDENCE"
            ][
                "handler"
            ],

            targets[
                "PREFERENCE_SIGNAL"
            ][
                "handler"
            ],

            targets[
                "SNAPSHOT"
            ][
                "handler"
            ],
        ],

    "optional_standard_library_import_change":
        "UTC_CLOCK_SUPPORT_ONLY_IF_REQUIRED_BY_CANDIDATE_IMPLEMENTATION",

    "worker_version_change_in_candidate_allowed":
        False,

    "worker_version_change_policy":
        "DEFER_TO_CANONICAL_MATERIALIZATION_GATE",
}


# ============================================================
# 8. IMPLEMENTATION STRATEGY
# ============================================================

implementation_strategy = {
    "patch_method":
        "FUNCTION_SCOPED_AST_AWARE_OR_EXACT_SOURCE_ANCHOR_REWRITE",

    "line_number_only_patch_allowed":
        False,

    "handler_source_hash_authority":
        True,

    "first_mutation_fingerprint_authority":
        True,

    "server_utc_clock_semantics":
        "TIMEZONE_AWARE_UTC",

    "server_utc_clock_capture_frequency":
        "EXACTLY_ONCE_PER_INGEST_HANDLER_INVOCATION",

    "server_utc_clock_not_request_controlled":
        True,

    "request_payload_mapping":
        "FULL_PYDANTIC_MODEL_MAPPING",

    "validator_calls_must_precede_mutation":
        True,

    "snapshot_record_resolution_may_precede_validator":
        True,

    "snapshot_state_mutation_may_precede_validator":
        False,

    "validation_failure_state_delta":
        0,

    "temporal_public_api_only":
        True,

    "private_temporal_helper_calls_allowed":
        False,

    "preserve_existing_success_path":
        True,

    "preserve_existing_idempotence":
        True,
}


# ============================================================
# 9. REQUIRED STATIC ASSERTIONS
# ============================================================

static_assertions = [
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
]


# ============================================================
# 10. REQUIRED ISOLATED DYNAMIC TEST MATRIX
# ============================================================

dynamic_tests = [
    {
        "test_id":
            "A5-I01-D01",

        "consumer":
            "EVIDENCE",

        "scenario":
            "TEMPORALLY_VALID_EVIDENCE",

        "expected":
            "EXISTING_SUCCESS_PATH_PRESERVED",
    },

    {
        "test_id":
            "A5-I01-D02",

        "consumer":
            "EVIDENCE",

        "scenario":
            "TEMPORALLY_INVALID_EVIDENCE",

        "expected":
            "TEMPORAL_VALIDITY_ERROR_AND_ZERO_STATE_MUTATION",
    },

    {
        "test_id":
            "A5-I01-D03",

        "consumer":
            "PREFERENCE_SIGNAL",

        "scenario":
            "TEMPORALLY_VALID_SIGNAL",

        "expected":
            "EXISTING_SUCCESS_PATH_PRESERVED",
    },

    {
        "test_id":
            "A5-I01-D04",

        "consumer":
            "PREFERENCE_SIGNAL",

        "scenario":
            "TEMPORALLY_INVALID_SIGNAL",

        "expected":
            "TEMPORAL_VALIDITY_ERROR_AND_ZERO_STATE_MUTATION",
    },

    {
        "test_id":
            "A5-I01-D05",

        "consumer":
            "SNAPSHOT",

        "scenario":
            "VALID_REFERENCED_RECORDS_AT_REQUEST_AS_OF",

        "expected":
            "EXISTING_SUCCESS_PATH_PRESERVED",
    },

    {
        "test_id":
            "A5-I01-D06",

        "consumer":
            "SNAPSHOT",

        "scenario":
            "INVALID_REFERENCED_EVIDENCE_AT_REQUEST_AS_OF",

        "expected":
            "TEMPORAL_VALIDITY_ERROR_AND_ZERO_STATE_MUTATION",
    },

    {
        "test_id":
            "A5-I01-D07",

        "consumer":
            "SNAPSHOT",

        "scenario":
            "INVALID_REFERENCED_SIGNAL_AT_REQUEST_AS_OF",

        "expected":
            "TEMPORAL_VALIDITY_ERROR_AND_ZERO_STATE_MUTATION",
    },

    {
        "test_id":
            "A5-I01-D08",

        "consumer":
            "GLOBAL",

        "scenario":
            "TEMPORAL_FAILURE_IDEMPOTENT_RETRY",

        "expected":
            "ZERO_PARTIAL_STATE_AND_NO_DUPLICATE_SIDE_EFFECT",
    },
]


# ============================================================
# 11. CANDIDATE OUTPUT POLICY
# ============================================================

candidate_policy = {
    "candidate_root":
        "worker/candidates/A5_I01_temporal_consumer_enforcement",

    "candidate_worker_relative_path":
        "worker/candidates/A5_I01_temporal_consumer_enforcement/worker_service.py",

    "candidate_manifest_relative_path":
        "worker/candidates/A5_I01_temporal_consumer_enforcement/manifest.json",

    "candidate_generation_authorized":
        False,

    "candidate_execution_authorized":
        False,

    "candidate_container_authorized":
        False,

    "canonical_materialization_authorized":
        False,

    "production_deployment_authorized":
        False,

    "candidate_generation_requires_plan_adversarial_review":
        True,
}


# ============================================================
# 12. GLOBAL SAFETY
# ============================================================

global_safety = {
    "canonical_worker_read_only":
        True,

    "temporal_module_read_only":
        True,

    "production_read_only":
        True,

    "no_build":
        True,

    "no_container_creation":
        True,

    "no_container_recreation":
        True,

    "no_provider_call":
        True,

    "no_model_call":
        True,

    "no_external_scraping":
        True,

    "semantic_priority_decision_cache_hit_audit_still_required_before_any_real_semantic_model_call":
        True,
}


# ============================================================
# 13. PLAN
# ============================================================

plan = {
    "contract_version":
        "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_V1",

    "requirement_id":
        "A5-R04",

    "implementation_unit":
        "A5-I01",

    "implementation_name":
        "TEMPORAL_CONSUMER_ENFORCEMENT",

    "source_worker_sha256":
        sha(
            worker_path
        ),

    "source_temporal_sha256":
        sha(
            temporal_path
        ),

    "source_binding_contract_v2_sha256":
        sha(
            binding_path
        ),

    "source_binding_adversarial_reattack_data_sha256":
        sha(
            reattack_data_path
        ),

    "source_binding_adversarial_reattack_report_sha256":
        sha(
            reattack_report_path
        ),

    "source_sequence_freeze_sha256":
        sha(
            sequence_path
        ),

    "current_runtime_version":
        "2.36.1",

    "operation_count":
        len(
            operations
        ),

    "operations":
        operations,

    "handler_evidence":
        handler_evidence,

    "diff_budget":
        diff_budget,

    "implementation_strategy":
        implementation_strategy,

    "static_assertions":
        static_assertions,

    "dynamic_test_matrix":
        dynamic_tests,

    "candidate_policy":
        candidate_policy,

    "global_safety":
        global_safety,

    "implementation_plan_frozen":
        True,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "candidate_execution_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "next_gate":
        "09C7-B3E-A5-I01-A3-A1_CANDIDATE_IMPLEMENTATION_PLAN_ADVERSARIAL_REVIEW",
}


# ============================================================
# 14. PLAN VALIDATION
# ============================================================

plan_checks = [
    lineage_authorized,

    i01_exact,

    temporal_import_pass,

    binding_exact,

    len(
        handler_evidence
    )
    == 3,

    len(
        operations
    )
    == 3,

    {
        item[
            "consumer"
        ]
        for item in operations
    }
    == {
        "EVIDENCE",
        "PREFERENCE_SIGNAL",
        "SNAPSHOT",
    },

    all(
        item[
            "validator_result_policy"
        ]
        == "VALIDATION_GATE_ONLY_DO_NOT_REWRITE_EXISTING_PERSISTED_RECORD_SEMANTICS"
        for item in operations
    ),

    all(
        item[
            "error_policy"
        ]
        == "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION"
        for item in operations
    ),

    diff_budget[
        "canonical_worker_mutation_allowed"
    ]
    is False,

    diff_budget[
        "temporal_module_mutation_allowed"
    ]
    is False,

    implementation_strategy[
        "validation_failure_state_delta"
    ]
    == 0,

    implementation_strategy[
        "temporal_public_api_only"
    ]
    is True,

    len(
        static_assertions
    )
    >= 10,

    len(
        dynamic_tests
    )
    == 8,

    candidate_policy[
        "candidate_generation_authorized"
    ]
    is False,

    candidate_policy[
        "candidate_generation_requires_plan_adversarial_review"
    ]
    is True,

    global_safety[
        "canonical_worker_read_only"
    ]
    is True,

    global_safety[
        "production_read_only"
    ]
    is True,

    plan[
        "implementation_authorized"
    ]
    is False,

    plan[
        "production_mutation_authorized"
    ]
    is False,
]


plan_freeze_pass = (
    all(
        plan_checks
    )
)


if not plan_freeze_pass:

    raise RuntimeError(
        "A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_FREEZE_FAILED"
    )


# ============================================================
# 15. WRITE / READ BACK
# ============================================================

plan_path.write_text(
    json.dumps(
        plan,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


persisted = load(
    plan_path
)


persistence_pass = (
    persisted
    == plan
)


if not persistence_pass:

    raise RuntimeError(
        "A5_I01_PLAN_PERSISTENCE_MISMATCH"
    )


# ============================================================
# 16. EVIDENCE
# ============================================================

evidence = {
    "contract_version":
        "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_FREEZE_EVIDENCE_V1",

    "source_worker_sha256":
        sha(
            worker_path
        ),

    "source_temporal_sha256":
        sha(
            temporal_path
        ),

    "source_binding_contract_v2_sha256":
        sha(
            binding_path
        ),

    "source_binding_reattack_data_sha256":
        sha(
            reattack_data_path
        ),

    "source_binding_reattack_report_sha256":
        sha(
            reattack_report_path
        ),

    "lineage_authorized":
        lineage_authorized,

    "i01_exact":
        i01_exact,

    "temporal_import_pass":
        temporal_import_pass,

    "binding_exact":
        binding_exact,

    "handler_count":
        len(
            handler_evidence
        ),

    "operation_count":
        len(
            operations
        ),

    "handler_evidence":
        handler_evidence,

    "static_assertion_count":
        len(
            static_assertions
        ),

    "dynamic_test_count":
        len(
            dynamic_tests
        ),

    "plan_freeze_pass":
        plan_freeze_pass,

    "persistence_pass":
        persistence_pass,

    "implementation_plan_frozen":
        True,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "classification":
        "A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_FROZEN",

    "next_gate":
        "09C7-B3E-A5-I01-A3-A1_CANDIDATE_IMPLEMENTATION_PLAN_ADVERSARIAL_REVIEW",
}


evidence_path.write_text(
    json.dumps(
        evidence,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "LINEAGE_AUTHORIZED="
    + str(
        lineage_authorized
    )
)

print(
    "I01_EXACT="
    + str(
        i01_exact
    )
)

print(
    "TEMPORAL_IMPORT_PASS="
    + str(
        temporal_import_pass
    )
)

print(
    "BINDING_EXACT="
    + str(
        binding_exact
    )
)

print(
    "HANDLER_COUNT="
    + str(
        len(
            handler_evidence
        )
    )
)

print(
    "OPERATION_COUNT="
    + str(
        len(
            operations
        )
    )
)


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
    "SNAPSHOT",
):

    item = handler_evidence[
        consumer
    ]

    print("")

    print(
        "CONSUMER="
        + consumer
    )

    print(
        "HANDLER="
        + item[
            "handler"
        ]
    )

    print(
        "REQUEST_MODEL="
        + item[
            "request_model"
        ]
    )

    print(
        "REQUEST_PARAMETER="
        + item[
            "request_parameter"
        ]
    )

    print(
        "VALIDATOR="
        + item[
            "validator"
        ]
    )

    print(
        "HANDLER_LINES="
        + str(
            item[
                "line_start"
            ]
        )
        + "-"
        + str(
            item[
                "line_end"
            ]
        )
    )

    print(
        "HANDLER_SOURCE_SHA256="
        + item[
            "source_sha256"
        ]
    )

    print(
        "FIRST_MUTATION_LINE="
        + str(
            item[
                "first_mutation_line"
            ]
        )
    )

    print(
        "FIRST_MUTATION_LINE_SHA256="
        + item[
            "first_mutation_line_sha256"
        ]
    )


print("")

print(
    "STATIC_ASSERTION_COUNT="
    + str(
        len(
            static_assertions
        )
    )
)

print(
    "DYNAMIC_TEST_COUNT="
    + str(
        len(
            dynamic_tests
        )
    )
)

print(
    "PLAN_FREEZE_PASS="
    + str(
        plan_freeze_pass
    )
)

print(
    "PERSISTENCE_PASS="
    + str(
        persistence_pass
    )
)

print(
    "IMPLEMENTATION_PLAN_FROZEN=True"
)

print(
    "IMPLEMENTATION_AUTHORIZED=False"
)

print(
    "CANDIDATE_GENERATION_AUTHORIZED=False"
)

print(
    "CANONICAL_SOURCE_MUTATION_AUTHORIZED=False"
)

print(
    "PRODUCTION_MUTATION_AUTHORIZED=False"
)

print(
    "NEXT_GATE="
    + plan[
        "next_gate"
    ]
)