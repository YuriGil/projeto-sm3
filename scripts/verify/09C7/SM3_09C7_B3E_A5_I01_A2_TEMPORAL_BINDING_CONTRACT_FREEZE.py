from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


a1_evidence_path = Path(sys.argv[1])
a1_report_path = Path(sys.argv[2])
sequence_freeze_path = Path(sys.argv[3])
matrix_path = Path(sys.argv[4])
worker_path = Path(sys.argv[5])
temporal_path = Path(sys.argv[6])
contract_path = Path(sys.argv[7])
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


def segment_sha(
    text: str,
) -> str:

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


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


def function_signature_detail(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:

    positional = []

    for arg in (
        list(fn.args.posonlyargs)
        + list(fn.args.args)
    ):

        positional.append({
            "name":
                arg.arg,

            "annotation":
                annotation_text(
                    arg.annotation
                ),
        })


    keyword_only = []

    for index, arg in enumerate(
        fn.args.kwonlyargs
    ):

        default_node = (
            fn.args.kw_defaults[index]
            if index
            < len(fn.args.kw_defaults)
            else None
        )

        keyword_only.append({
            "name":
                arg.arg,

            "annotation":
                annotation_text(
                    arg.annotation
                ),

            "required":
                default_node is None,
        })


    return {
        "name":
            fn.name,

        "positional":
            positional,

        "keyword_only":
            keyword_only,

        "vararg":
            (
                fn.args.vararg.arg
                if fn.args.vararg
                else None
            ),

        "kwarg":
            (
                fn.args.kwarg.arg
                if fn.args.kwarg
                else None
            ),

        "return_annotation":
            annotation_text(
                fn.returns
            ),

        "line_start":
            getattr(
                fn,
                "lineno",
                None,
            ),

        "line_end":
            getattr(
                fn,
                "end_lineno",
                None,
            ),
    }


def all_parameter_names(
    detail: dict[str, Any],
) -> list[str]:

    result = []

    for item in detail[
        "positional"
    ]:
        result.append(
            item["name"]
        )

    for item in detail[
        "keyword_only"
    ]:
        result.append(
            item["name"]
        )

    return result


def request_model_fields(
    class_node: ast.ClassDef,
) -> list[str]:

    result = []

    for statement in class_node.body:

        if (
            isinstance(
                statement,
                ast.AnnAssign,
            )
            and isinstance(
                statement.target,
                ast.Name,
            )
        ):

            result.append(
                statement.target.id
            )

    return result


def mapping_keys_read(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter_name: str,
) -> list[str]:

    result: set[str] = set()


    for node in ast.walk(fn):

        # param.get("field")
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr == "get"
            and isinstance(
                node.func.value,
                ast.Name,
            )
            and node.func.value.id
            == parameter_name
            and len(node.args) >= 1
            and isinstance(
                node.args[0],
                ast.Constant,
            )
            and isinstance(
                node.args[0].value,
                str,
            )
        ):

            result.add(
                node.args[0].value
            )


        # param["field"]
        if (
            isinstance(
                node,
                ast.Subscript,
            )
            and isinstance(
                node.value,
                ast.Name,
            )
            and node.value.id
            == parameter_name
        ):

            slice_node = node.slice

            if (
                isinstance(
                    slice_node,
                    ast.Constant,
                )
                and isinstance(
                    slice_node.value,
                    str,
                )
            ):

                result.add(
                    slice_node.value
                )


    return sorted(
        result
    )


def role_parameter(
    parameters: list[str],
    tokens: tuple[str, ...],
) -> str | None:

    matches = []

    for name in parameters:

        lowered = name.lower()

        if any(
            token in lowered
            for token in tokens
        ):
            matches.append(
                name
            )


    if len(matches) == 1:
        return matches[0]

    return None


def statement_source_by_line(
    worker_lines: list[str],
    line_number: int,
) -> str:

    if (
        line_number <= 0
        or line_number > len(worker_lines)
    ):
        return ""

    return worker_lines[
        line_number - 1
    ]


a1 = load(
    a1_evidence_path
)

a1_report = load(
    a1_report_path
)

sequence_freeze = load(
    sequence_freeze_path
)

matrix = load(
    matrix_path
)


# ============================================================
# 1. LINEAGE
# ============================================================

lineage_checks = [
    a1.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_CONSUMER_ENFORCEMENT_PREFLIGHT_V1",

    a1.get(
        "preflight_complete"
    )
    is True,

    a1.get(
        "consumer_count"
    )
    == 3,

    a1.get(
        "route_map_pass"
    )
    is True,

    a1.get(
        "source_map_complete"
    )
    is True,

    a1.get(
        "temporal_contract_exact"
    )
    is True,

    a1.get(
        "all_current_temporal_call_free"
    )
    is True,

    a1.get(
        "implementation_authorized"
    )
    is False,

    a1.get(
        "candidate_generation_authorized"
    )
    is False,

    a1_report.get(
        "a5_i01_a1_pass"
    )
    is True,

    a1_report.get(
        "classification"
    )
    == "A5_I01_TEMPORAL_CONSUMER_ENFORCEMENT_PREFLIGHT_COMPLETE",

    a1_report.get(
        "next_gate"
    )
    == "09C7-B3E-A5-I01-A2_TEMPORAL_BINDING_CONTRACT_FREEZE",

    sequence_freeze.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_FREEZE_V2",

    matrix.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_RUNTIME_GAP_MATRIX_V2",
]


lineage_authorized = all(
    lineage_checks
)


if not lineage_authorized:
    raise RuntimeError(
        "A2_LINEAGE_NOT_AUTHORIZED"
    )


# ============================================================
# 2. PARSE WORKER / TEMPORAL
# ============================================================

worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_lines = (
    worker_source.splitlines()
)

worker_tree = ast.parse(
    worker_source,
    filename=str(worker_path),
)


temporal_source = temporal_path.read_text(
    encoding="utf-8-sig"
)

temporal_lines = (
    temporal_source.splitlines()
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(temporal_path),
)


worker_functions = {}

worker_classes = {}


for node in worker_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        worker_functions[
            node.name
        ] = node

    elif isinstance(
        node,
        ast.ClassDef,
    ):
        worker_classes[
            node.name
        ] = node


temporal_functions = {}


for node in temporal_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        temporal_functions[
            node.name
        ] = node


# ============================================================
# 3. REQUIRED PUBLIC VALIDATORS
# ============================================================

required_validators = {
    "EVIDENCE":
        "validate_evidence_temporal",

    "PREFERENCE_SIGNAL":
        "validate_signal_temporal",

    "SNAPSHOT":
        "validate_snapshot_temporal_inputs",
}


validator_details = {}


for consumer_id, validator_name in required_validators.items():

    fn = temporal_functions.get(
        validator_name
    )

    if fn is None:
        raise RuntimeError(
            "VALIDATOR_MISSING:"
            + validator_name
        )


    detail = function_signature_detail(
        fn
    )

    source = source_segment(
        temporal_lines,
        detail[
            "line_start"
        ],
        detail[
            "line_end"
        ],
    )

    detail[
        "source_sha256"
    ] = segment_sha(
        source
    )

    detail[
        "source"
    ] = source

    validator_details[
        consumer_id
    ] = detail


# ============================================================
# 4. EXACT PARAMETER ROLE DISCOVERY
# ============================================================

evidence_params = all_parameter_names(
    validator_details[
        "EVIDENCE"
    ]
)

signal_params = all_parameter_names(
    validator_details[
        "PREFERENCE_SIGNAL"
    ]
)

snapshot_params = all_parameter_names(
    validator_details[
        "SNAPSHOT"
    ]
)


evidence_payload_param = role_parameter(
    evidence_params,
    (
        "evidence",
    ),
)

evidence_as_of_param = role_parameter(
    evidence_params,
    (
        "as_of",
    ),
)


signal_payload_param = role_parameter(
    signal_params,
    (
        "signal",
    ),
)

signal_as_of_param = role_parameter(
    signal_params,
    (
        "as_of",
    ),
)


snapshot_evidence_param = role_parameter(
    snapshot_params,
    (
        "evidence",
    ),
)

snapshot_signal_param = role_parameter(
    snapshot_params,
    (
        "signal",
        "preference",
    ),
)

snapshot_as_of_param = role_parameter(
    snapshot_params,
    (
        "as_of",
    ),
)


role_discovery_pass = all([
    evidence_payload_param
    is not None,

    evidence_as_of_param
    is not None,

    signal_payload_param
    is not None,

    signal_as_of_param
    is not None,

    snapshot_evidence_param
    is not None,

    snapshot_signal_param
    is not None,

    snapshot_as_of_param
    is not None,
])


if not role_discovery_pass:

    raise RuntimeError(
        "VALIDATOR_PARAMETER_ROLE_DISCOVERY_FAILED"
        + ":E="
        + repr(evidence_params)
        + ":S="
        + repr(signal_params)
        + ":SN="
        + repr(snapshot_params)
    )


# ============================================================
# 5. VALIDATOR INPUT KEY DISCOVERY
# ============================================================

evidence_validator_fn = temporal_functions[
    "validate_evidence_temporal"
]

signal_validator_fn = temporal_functions[
    "validate_signal_temporal"
]


evidence_keys = mapping_keys_read(
    evidence_validator_fn,
    evidence_payload_param,
)

signal_keys = mapping_keys_read(
    signal_validator_fn,
    signal_payload_param,
)


# ============================================================
# 6. REQUEST MODEL FIELD INVENTORY
# ============================================================

expected_models = {
    "EVIDENCE":
        "PlatformDynamicsEvidenceRequest",

    "PREFERENCE_SIGNAL":
        "PlatformPreferenceSignalRequest",

    "SNAPSHOT":
        "PlatformDynamicsSnapshotRequest",
}


request_fields = {}


for consumer_id, class_name in expected_models.items():

    class_node = worker_classes.get(
        class_name
    )

    if class_node is None:
        raise RuntimeError(
            "REQUEST_MODEL_MISSING:"
            + class_name
        )


    request_fields[
        consumer_id
    ] = request_model_fields(
        class_node
    )


evidence_field_coverage = set(
    evidence_keys
).issubset(
    set(
        request_fields[
            "EVIDENCE"
        ]
    )
)


signal_field_coverage = set(
    signal_keys
).issubset(
    set(
        request_fields[
            "PREFERENCE_SIGNAL"
        ]
    )
)


snapshot_required_request_fields = {
    "evidence_ids",
    "preference_signal_ids",
    "as_of",
}


snapshot_field_coverage = (
    snapshot_required_request_fields
    .issubset(
        set(
            request_fields[
                "SNAPSHOT"
            ]
        )
    )
)


request_coverage_pass = all([
    evidence_field_coverage,
    signal_field_coverage,
    snapshot_field_coverage,
])


if not request_coverage_pass:

    raise RuntimeError(
        "REQUEST_FIELD_COVERAGE_FAILED"
    )


# ============================================================
# 7. A1 CONSUMER AUTHORITY
# ============================================================

a1_consumers = {
    item["consumer_id"]:
        item
    for item in a1.get(
        "consumers",
        [],
    )
}


required_consumer_ids = {
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
    "SNAPSHOT",
}


if set(
    a1_consumers
) != required_consumer_ids:

    raise RuntimeError(
        "A1_CONSUMER_SET_INVALID"
    )


# ============================================================
# 8. FIRST MUTATION FINGERPRINTS
# ============================================================

mutation_boundaries = {}


for consumer_id in sorted(
    required_consumer_ids
):

    item = a1_consumers[
        consumer_id
    ]

    line = item.get(
        "first_mutation_candidate_line"
    )


    if not isinstance(
        line,
        int,
    ):

        raise RuntimeError(
            "FIRST_MUTATION_LINE_MISSING:"
            + consumer_id
        )


    statement_line = statement_source_by_line(
        worker_lines,
        line,
    )


    mutation_boundaries[
        consumer_id
    ] = {
        "current_line":
            line,

        "current_statement_line":
            statement_line,

        "current_statement_line_sha256":
            segment_sha(
                statement_line
            ),

        "policy":
            "TEMPORAL_VALIDATION_MUST_COMPLETE_BEFORE_FIRST_STATE_MUTATION",
    }


# ============================================================
# 9. EXACT BINDING CONTRACT
#
# Ingest:
# - as_of is the authoritative current UTC time at handler entry.
#   It MUST NOT be derived from the submitted observed/window time.
#
# Snapshot:
# - uses request.as_of
# - validates the already-resolved evidence and signal records.
# ============================================================

bindings = {
    "EVIDENCE": {
        "route":
            "/production/culture-intelligence/platform-dynamics/evidence",

        "handler":
            "production_platform_dynamics_evidence_ingest",

        "request_model":
            "PlatformDynamicsEvidenceRequest",

        "validator":
            "validate_evidence_temporal",

        "validator_payload_parameter":
            evidence_payload_param,

        "validator_as_of_parameter":
            evidence_as_of_param,

        "payload_binding":
            "FULL_REQUEST_MODEL_MAPPING",

        "as_of_binding":
            "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        "as_of_must_not_bind_to":
            [
                "request.source_date",
                "request.observed_at",
                "request.valid_until",
            ],

        "validator_mapping_keys":
            evidence_keys,

        "request_fields_cover_validator_keys":
            evidence_field_coverage,

        "must_execute_before_first_mutation":
            True,

        "first_mutation_boundary":
            mutation_boundaries[
                "EVIDENCE"
            ],

        "error_policy":
            "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION",
    },


    "PREFERENCE_SIGNAL": {
        "route":
            "/production/culture-intelligence/platform-preference-signals",

        "handler":
            "production_platform_preference_signal_ingest",

        "request_model":
            "PlatformPreferenceSignalRequest",

        "validator":
            "validate_signal_temporal",

        "validator_payload_parameter":
            signal_payload_param,

        "validator_as_of_parameter":
            signal_as_of_param,

        "payload_binding":
            "FULL_REQUEST_MODEL_MAPPING",

        "as_of_binding":
            "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        "as_of_must_not_bind_to":
            [
                "request.window_started_at",
                "request.window_ended_at",
            ],

        "validator_mapping_keys":
            signal_keys,

        "request_fields_cover_validator_keys":
            signal_field_coverage,

        "must_execute_before_first_mutation":
            True,

        "first_mutation_boundary":
            mutation_boundaries[
                "PREFERENCE_SIGNAL"
            ],

        "error_policy":
            "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION",
    },


    "SNAPSHOT": {
        "route":
            "/production/culture-intelligence/platform-dynamics/snapshots",

        "handler":
            "production_platform_dynamics_snapshot_build",

        "request_model":
            "PlatformDynamicsSnapshotRequest",

        "validator":
            "validate_snapshot_temporal_inputs",

        "validator_evidence_parameter":
            snapshot_evidence_param,

        "validator_signal_parameter":
            snapshot_signal_param,

        "validator_as_of_parameter":
            snapshot_as_of_param,

        "evidence_binding":
            "RESOLVED_EVIDENCE_RECORDS_FROM_REQUEST_EVIDENCE_IDS",

        "signal_binding":
            "RESOLVED_PREFERENCE_SIGNAL_RECORDS_FROM_REQUEST_PREFERENCE_SIGNAL_IDS",

        "as_of_binding":
            "request.as_of",

        "request_fields_cover_binding":
            snapshot_field_coverage,

        "resolution_policy":
            "REFERENCED_RECORDS_MUST_BE_RESOLVED_BEFORE_TEMPORAL_VALIDATION",

        "must_execute_before_first_mutation":
            True,

        "first_mutation_boundary":
            mutation_boundaries[
                "SNAPSHOT"
            ],

        "error_policy":
            "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED_NO_STATE_MUTATION",
    },
}


# ============================================================
# 10. PUBLIC API ONLY / PRIVATE PARSER PROHIBITED
# ============================================================

private_temporal_direct_call_allowed = False

public_validator_set = sorted(
    required_validators.values()
)


# ============================================================
# 11. AUTHORIZATION POLICY
# ============================================================

authorization = {
    "binding_frozen":
        True,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "provider_call_authorized":
        False,

    "model_call_authorized":
        False,

    "external_scraping_authorized":
        False,
}


# ============================================================
# 12. CONTRACT
# ============================================================

contract = {
    "contract_version":
        "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V1",

    "requirement_id":
        "A5-R04",

    "implementation_unit":
        "A5-I01",

    "implementation_name":
        "TEMPORAL_CONSUMER_ENFORCEMENT",

    "temporal_policy_version":
        "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1",

    "temporal_engine_version":
        "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1",

    "temporal_implementation_revision":
        "R2",

    "source_worker_sha256":
        sha(
            worker_path
        ),

    "source_temporal_sha256":
        sha(
            temporal_path
        ),

    "source_a1_evidence_sha256":
        sha(
            a1_evidence_path
        ),

    "source_a1_report_sha256":
        sha(
            a1_report_path
        ),

    "consumer_count":
        3,

    "public_validator_set":
        public_validator_set,

    "validator_details":
        validator_details,

    "request_model_fields":
        request_fields,

    "bindings":
        bindings,

    "global_invariants": {
        "all_three_consumers_must_validate":
            True,

        "validation_before_mutation":
            True,

        "temporal_validity_error_fail_closed":
            True,

        "no_partial_persistence_on_temporal_error":
            True,

        "public_temporal_api_only":
            True,

        "private_parse_timestamp_direct_call_allowed":
            private_temporal_direct_call_allowed,

        "ingest_as_of_authority":
            "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

        "snapshot_as_of_authority":
            "REQUEST_AS_OF",

        "temporal_module_mutation_allowed":
            False,

        "existing_route_removal_allowed":
            False,

        "existing_contract_reinterpretation_allowed":
            False,

        "provider_call_allowed":
            False,

        "model_call_allowed":
            False,

        "external_scraping_allowed":
            False,
    },

    "authorization":
        authorization,

    "next_gate":
        "09C7-B3E-A5-I01-A2-A1_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REVIEW",
}


# ============================================================
# 13. FREEZE VALIDATION
# ============================================================

freeze_checks = [
    role_discovery_pass,

    request_coverage_pass,

    len(
        public_validator_set
    )
    == 3,

    set(
        public_validator_set
    )
    == {
        "validate_evidence_temporal",
        "validate_signal_temporal",
        "validate_snapshot_temporal_inputs",
    },

    bindings[
        "EVIDENCE"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    bindings[
        "PREFERENCE_SIGNAL"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    bindings[
        "SNAPSHOT"
    ][
        "as_of_binding"
    ]
    == "request.as_of",

    bindings[
        "SNAPSHOT"
    ][
        "request_fields_cover_binding"
    ]
    is True,

    all(
        bindings[
            item
        ][
            "must_execute_before_first_mutation"
        ]
        is True
        for item in (
            "EVIDENCE",
            "PREFERENCE_SIGNAL",
            "SNAPSHOT",
        )
    ),

    authorization[
        "binding_frozen"
    ]
    is True,

    authorization[
        "implementation_authorized"
    ]
    is False,

    authorization[
        "candidate_generation_authorized"
    ]
    is False,
]


binding_contract_freeze_pass = all(
    freeze_checks
)


if not binding_contract_freeze_pass:
    raise RuntimeError(
        "TEMPORAL_BINDING_CONTRACT_FREEZE_FAILED"
    )


contract_path.write_text(
    json.dumps(
        contract,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


persisted_contract = load(
    contract_path
)


if persisted_contract != contract:
    raise RuntimeError(
        "TEMPORAL_BINDING_CONTRACT_PERSISTENCE_MISMATCH"
    )


evidence = {
    "contract_version":
        "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_FREEZE_EVIDENCE_V1",

    "source_a1_evidence_sha256":
        sha(
            a1_evidence_path
        ),

    "source_a1_report_sha256":
        sha(
            a1_report_path
        ),

    "source_worker_sha256":
        sha(
            worker_path
        ),

    "source_temporal_sha256":
        sha(
            temporal_path
        ),

    "lineage_authorized":
        lineage_authorized,

    "role_discovery_pass":
        role_discovery_pass,

    "request_coverage_pass":
        request_coverage_pass,

    "evidence_validator_parameters":
        evidence_params,

    "signal_validator_parameters":
        signal_params,

    "snapshot_validator_parameters":
        snapshot_params,

    "evidence_validator_mapping_keys":
        evidence_keys,

    "signal_validator_mapping_keys":
        signal_keys,

    "snapshot_parameter_roles": {
        "evidence":
            snapshot_evidence_param,

        "signal":
            snapshot_signal_param,

        "as_of":
            snapshot_as_of_param,
    },

    "mutation_boundaries":
        mutation_boundaries,

    "binding_contract_freeze_pass":
        binding_contract_freeze_pass,

    "binding_frozen":
        True,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "classification":
        "A5_I01_TEMPORAL_BINDING_CONTRACT_FROZEN",

    "next_gate":
        "09C7-B3E-A5-I01-A2-A1_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REVIEW",
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
    "ROLE_DISCOVERY_PASS="
    + str(
        role_discovery_pass
    )
)

print(
    "REQUEST_COVERAGE_PASS="
    + str(
        request_coverage_pass
    )
)

print(
    "EVIDENCE_VALIDATOR_PARAMETERS="
    + "|".join(
        evidence_params
    )
)

print(
    "SIGNAL_VALIDATOR_PARAMETERS="
    + "|".join(
        signal_params
    )
)

print(
    "SNAPSHOT_VALIDATOR_PARAMETERS="
    + "|".join(
        snapshot_params
    )
)

print(
    "SNAPSHOT_EVIDENCE_PARAMETER="
    + str(
        snapshot_evidence_param
    )
)

print(
    "SNAPSHOT_SIGNAL_PARAMETER="
    + str(
        snapshot_signal_param
    )
)

print(
    "SNAPSHOT_AS_OF_PARAMETER="
    + str(
        snapshot_as_of_param
    )
)

print(
    "EVIDENCE_VALIDATOR_KEYS="
    + "|".join(
        evidence_keys
    )
)

print(
    "SIGNAL_VALIDATOR_KEYS="
    + "|".join(
        signal_keys
    )
)

print(
    "EVIDENCE_AS_OF_BINDING="
    + bindings[
        "EVIDENCE"
    ][
        "as_of_binding"
    ]
)

print(
    "SIGNAL_AS_OF_BINDING="
    + bindings[
        "PREFERENCE_SIGNAL"
    ][
        "as_of_binding"
    ]
)

print(
    "SNAPSHOT_AS_OF_BINDING="
    + bindings[
        "SNAPSHOT"
    ][
        "as_of_binding"
    ]
)

print(
    "VALIDATION_BEFORE_MUTATION=True"
)

print(
    "TEMPORAL_VALIDITY_ERROR_FAIL_CLOSED=True"
)

print(
    "PRIVATE_PARSE_TIMESTAMP_DIRECT_CALL_ALLOWED=False"
)

print(
    "BINDING_FROZEN=True"
)

print(
    "IMPLEMENTATION_AUTHORIZED=False"
)

print(
    "CANDIDATE_GENERATION_AUTHORIZED=False"
)

print(
    "BINDING_CONTRACT_FREEZE_PASS="
    + str(
        binding_contract_freeze_pass
    )
)

print(
    "NEXT_GATE="
    + contract[
        "next_gate"
    ]
)