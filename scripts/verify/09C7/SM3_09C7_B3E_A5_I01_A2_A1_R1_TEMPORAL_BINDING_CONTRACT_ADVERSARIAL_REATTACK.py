from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_contract_path = Path(sys.argv[1])
revised_contract_path = Path(sys.argv[2])
remediation_evidence_path = Path(sys.argv[3])
remediation_report_path = Path(sys.argv[4])
prior_review_path = Path(sys.argv[5])
h1_audit_path = Path(sys.argv[6])
worker_path = Path(sys.argv[7])
temporal_path = Path(sys.argv[8])
output_path = Path(sys.argv[9])


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


def call_name(node: ast.Call) -> str | None:

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def get_class_fields(
    class_node: ast.ClassDef,
) -> set[str]:

    result = set()

    for statement in class_node.body:

        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(
                statement.target,
                ast.Name,
            )
        ):
            result.add(
                statement.target.id
            )

    return result


def function_parameters(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:

    positional = [
        arg.arg
        for arg in (
            list(fn.args.posonlyargs)
            + list(fn.args.args)
        )
    ]

    keyword_only = [
        arg.arg
        for arg in fn.args.kwonlyargs
    ]

    required_keyword_only = []

    for index, arg in enumerate(
        fn.args.kwonlyargs
    ):

        if fn.args.kw_defaults[index] is None:
            required_keyword_only.append(
                arg.arg
            )

    return {
        "positional":
            positional,

        "keyword_only":
            keyword_only,

        "required_keyword_only":
            required_keyword_only,
    }


def call_names(node: ast.AST) -> set[str]:

    result = set()

    for child in ast.walk(node):

        if isinstance(child, ast.Call):

            name = call_name(child)

            if name:
                result.add(name)

    return result


def string_constants(node: ast.AST) -> set[str]:

    result = set()

    for child in ast.walk(node):

        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
        ):
            result.add(child.value)

    return result


def names_and_attrs(node: ast.AST) -> set[str]:

    result = set()

    for child in ast.walk(node):

        if isinstance(child, ast.Name):
            result.add(child.id)

        elif isinstance(child, ast.Attribute):
            result.add(child.attr)

    return result


def recursive_diff(
    left: Any,
    right: Any,
    path: str = "",
) -> list[str]:

    result = []

    if type(left) is not type(right):

        result.append(
            path or "/"
        )

        return result


    if isinstance(left, dict):

        keys = (
            set(left)
            | set(right)
        )

        for key in sorted(keys):

            child_path = (
                path
                + "/"
                + str(key)
            )

            if key not in left or key not in right:

                result.append(
                    child_path
                )

                continue

            result.extend(
                recursive_diff(
                    left[key],
                    right[key],
                    child_path,
                )
            )

        return result


    if isinstance(left, list):

        if left != right:

            result.append(
                path or "/"
            )

        return result


    if left != right:

        result.append(
            path or "/"
        )

    return result


def expression_text(
    node: ast.AST | None,
) -> str | None:

    if node is None:
        return None

    try:
        return ast.unparse(node)
    except Exception:
        return None


source = load(source_contract_path)
revised = load(revised_contract_path)
remediation_evidence = load(
    remediation_evidence_path
)
remediation_report = load(
    remediation_report_path
)
prior_review = load(prior_review_path)
h1 = load(h1_audit_path)


findings: list[dict[str, Any]] = []


def finding(
    severity: str,
    code: str,
    message: str,
    consumer: str = "GLOBAL",
) -> None:

    findings.append({
        "severity":
            severity,

        "code":
            code,

        "consumer":
            consumer,

        "message":
            message,
    })


# ============================================================
# 1. LINEAGE
# ============================================================

lineage_checks = [
    source.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V1",

    revised.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V2",

    revised.get(
        "revision"
    )
    == 2,

    revised.get(
        "revision_reason"
    )
    == "A2_A1_ADVERSARIAL_REMEDIATION",

    revised.get(
        "source_binding_contract_v1_sha256"
    )
    == sha(source_contract_path),

    revised.get(
        "source_adversarial_review_data_sha256"
    )
    == sha(prior_review_path),

    revised.get(
        "source_snapshot_as_of_dataflow_audit_sha256"
    )
    == sha(h1_audit_path),

    remediation_evidence.get(
        "remediation_pass"
    )
    is True,

    remediation_evidence.get(
        "preserved_semantics_pass"
    )
    is True,

    remediation_evidence.get(
        "authorization_closed"
    )
    is True,

    remediation_report.get(
        "a5_i01_a2_r1_pass"
    )
    is True,

    remediation_report.get(
        "classification"
    )
    == "A5_I01_TEMPORAL_BINDING_CONTRACT_REMEDIATED",

    remediation_report.get(
        "revised_binding_contract_sha256"
    )
    == sha(revised_contract_path),

    h1.get(
        "prior_high_findings_false_positive"
    )
    is True,

    h1.get(
        "all_snapshot_as_of_forwarding_proven"
    )
    is True,
]


lineage_authorized = all(
    lineage_checks
)


if not lineage_authorized:

    raise RuntimeError(
        "A2_A1_R1_LINEAGE_NOT_AUTHORIZED"
    )


# ============================================================
# 2. CONTRACT REVISION SCOPE
# ============================================================

diff_paths = recursive_diff(
    source,
    revised,
)


allowed_exact_paths = {
    "/contract_version",
    "/revision",
    "/revision_reason",

    "/source_binding_contract_v1_sha256",
    "/source_adversarial_review_data_sha256",
    "/source_adversarial_review_report_sha256",
    "/source_snapshot_as_of_dataflow_audit_sha256",

    "/bindings/EVIDENCE/temporal_input_fields",
    "/bindings/EVIDENCE/temporal_input_field_provenance",
    "/bindings/EVIDENCE/request_fields_cover_temporal_inputs",
    "/bindings/EVIDENCE/validator_mapping_keys",
    "/bindings/EVIDENCE/coverage_non_vacuous",

    "/bindings/PREFERENCE_SIGNAL/temporal_input_fields",
    "/bindings/PREFERENCE_SIGNAL/temporal_input_field_provenance",
    "/bindings/PREFERENCE_SIGNAL/request_fields_cover_temporal_inputs",
    "/bindings/PREFERENCE_SIGNAL/validator_mapping_keys",
    "/bindings/PREFERENCE_SIGNAL/coverage_non_vacuous",

    "/bindings/SNAPSHOT/call_style",
    "/bindings/SNAPSHOT/keyword_argument_order",
    "/bindings/SNAPSHOT/keyword_argument_bindings",
    "/bindings/SNAPSHOT/required_keyword_only_parameters",
    "/bindings/SNAPSHOT/internal_as_of_forwarding",
    "/bindings/SNAPSHOT/internal_as_of_forwarding_evidence_proven",
    "/bindings/SNAPSHOT/internal_as_of_forwarding_signal_proven",
    "/bindings/SNAPSHOT/internal_as_of_forwarding_provenance",

    "/adversarial_finding_disposition",

    "/next_gate",
}


unexpected_diff_paths = sorted(
    path
    for path in diff_paths
    if path not in allowed_exact_paths
)


revision_scope_pass = (
    len(
        unexpected_diff_paths
    )
    == 0
)


if not revision_scope_pass:

    finding(
        "HIGH",
        "REMEDIATION_SCOPE_EXPANDED",
        (
            "Unexpected V1->V2 contract differences: "
            + "|".join(
                unexpected_diff_paths
            )
        ),
    )


# ============================================================
# 3. PARSE WORKER / TEMPORAL
# ============================================================

worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_lines = worker_source.splitlines()

worker_tree = ast.parse(
    worker_source,
    filename=str(worker_path),
)


temporal_source = temporal_path.read_text(
    encoding="utf-8-sig"
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(temporal_path),
)


worker_classes = {}

worker_functions = {}

temporal_functions = {}


for node in worker_tree.body:

    if isinstance(node, ast.ClassDef):
        worker_classes[node.name] = node

    elif isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        worker_functions[node.name] = node


for node in temporal_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        temporal_functions[node.name] = node


required_temporal_functions = {
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
}


if not required_temporal_functions.issubset(
    set(temporal_functions)
):

    finding(
        "HIGH",
        "REQUIRED_TEMPORAL_API_MISSING",
        "At least one frozen Temporal R2 public validator is missing.",
    )


# ============================================================
# 4. REQUEST MODEL COVERAGE
# ============================================================

expected_evidence_fields = [
    "source_date",
    "observed_at",
    "valid_until",
]

expected_signal_fields = [
    "window_started_at",
    "window_ended_at",
]


evidence_request = worker_classes.get(
    "PlatformDynamicsEvidenceRequest"
)

signal_request = worker_classes.get(
    "PlatformPreferenceSignalRequest"
)

snapshot_request = worker_classes.get(
    "PlatformDynamicsSnapshotRequest"
)


if (
    evidence_request is None
    or signal_request is None
    or snapshot_request is None
):

    finding(
        "HIGH",
        "REQUEST_MODEL_MISSING",
        "Required current Worker request model is missing.",
    )


evidence_request_fields = (
    get_class_fields(
        evidence_request
    )
    if evidence_request
    else set()
)

signal_request_fields = (
    get_class_fields(
        signal_request
    )
    if signal_request
    else set()
)

snapshot_request_fields = (
    get_class_fields(
        snapshot_request
    )
    if snapshot_request
    else set()
)


request_coverage_pass = all([
    set(
        expected_evidence_fields
    ).issubset(
        evidence_request_fields
    ),

    set(
        expected_signal_fields
    ).issubset(
        signal_request_fields
    ),

    {
        "evidence_ids",
        "preference_signal_ids",
        "as_of",
    }.issubset(
        snapshot_request_fields
    ),
])


if not request_coverage_pass:

    finding(
        "HIGH",
        "REQUEST_TEMPORAL_FIELD_COVERAGE_INVALID",
        "Current Worker request models no longer cover frozen temporal inputs.",
    )


# ============================================================
# 5. CONTRACT EXPLICIT FIELD SETS
# ============================================================

bindings = revised.get(
    "bindings",
    {},
)

evidence_binding = bindings.get(
    "EVIDENCE",
    {},
)

signal_binding = bindings.get(
    "PREFERENCE_SIGNAL",
    {},
)

snapshot_binding = bindings.get(
    "SNAPSHOT",
    {},
)


evidence_explicit_fields_pass = all([
    evidence_binding.get(
        "temporal_input_fields"
    )
    == expected_evidence_fields,

    evidence_binding.get(
        "validator_mapping_keys"
    )
    == expected_evidence_fields,

    evidence_binding.get(
        "coverage_non_vacuous"
    )
    is True,

    evidence_binding.get(
        "request_fields_cover_temporal_inputs"
    )
    is True,
])


signal_explicit_fields_pass = all([
    signal_binding.get(
        "temporal_input_fields"
    )
    == expected_signal_fields,

    signal_binding.get(
        "validator_mapping_keys"
    )
    == expected_signal_fields,

    signal_binding.get(
        "coverage_non_vacuous"
    )
    is True,

    signal_binding.get(
        "request_fields_cover_temporal_inputs"
    )
    is True,
])


if not evidence_explicit_fields_pass:

    finding(
        "MEDIUM",
        "EVIDENCE_EXPLICIT_TEMPORAL_INPUT_CONTRACT_INVALID",
        "Evidence temporal input fields remain incomplete or vacuous.",
        "EVIDENCE",
    )


if not signal_explicit_fields_pass:

    finding(
        "MEDIUM",
        "SIGNAL_EXPLICIT_TEMPORAL_INPUT_CONTRACT_INVALID",
        "Preference Signal temporal input fields remain incomplete or vacuous.",
        "PREFERENCE_SIGNAL",
    )


# ============================================================
# 6. TEMPORAL CALL GRAPH / TRANSITIVE FIELD USAGE
# ============================================================

call_graph = {}


for name, fn in temporal_functions.items():

    call_graph[name] = {
        called
        for called in call_names(fn)
        if called in temporal_functions
    }


def reachable(
    start: str,
) -> set[str]:

    result = set()
    stack = [start]

    while stack:

        current = stack.pop()

        if current in result:
            continue

        result.add(current)

        for child in call_graph.get(
            current,
            set(),
        ):
            if child not in result:
                stack.append(child)

    return result


def prove_fields(
    start: str,
    expected: set[str],
) -> set[str]:

    literals = set()
    symbols = set()

    for name in reachable(start):

        fn = temporal_functions.get(name)

        if fn is None:
            continue

        literals.update(
            string_constants(fn)
        )

        symbols.update(
            names_and_attrs(fn)
        )

    return {
        field
        for field in expected
        if (
            field in literals
            or field in symbols
        )
    }


evidence_proven_fields = prove_fields(
    "validate_evidence_temporal",
    set(expected_evidence_fields),
)

signal_proven_fields = prove_fields(
    "validate_signal_temporal",
    set(expected_signal_fields),
)


evidence_field_usage_pass = (
    evidence_proven_fields
    == set(
        expected_evidence_fields
    )
)

signal_field_usage_pass = (
    signal_proven_fields
    == set(
        expected_signal_fields
    )
)


if not evidence_field_usage_pass:

    finding(
        "HIGH",
        "EVIDENCE_TEMPORAL_FIELD_USAGE_NOT_PROVEN",
        "Temporal R2 no longer proves all frozen Evidence temporal fields.",
        "EVIDENCE",
    )


if not signal_field_usage_pass:

    finding(
        "HIGH",
        "SIGNAL_TEMPORAL_FIELD_USAGE_NOT_PROVEN",
        "Temporal R2 no longer proves all frozen Signal temporal fields.",
        "PREFERENCE_SIGNAL",
    )


# ============================================================
# 7. SNAPSHOT SIGNATURE + KEYWORD-ONLY CONTRACT
# ============================================================

snapshot_validator = temporal_functions.get(
    "validate_snapshot_temporal_inputs"
)


snapshot_signature_pass = False


if snapshot_validator is not None:

    snapshot_params = function_parameters(
        snapshot_validator
    )

    snapshot_signature_pass = all([
        snapshot_params[
            "positional"
        ]
        == [],

        snapshot_params[
            "keyword_only"
        ]
        == [
            "as_of",
            "evidence",
            "signals",
        ],

        snapshot_params[
            "required_keyword_only"
        ]
        == [
            "as_of",
            "evidence",
            "signals",
        ],
    ])


if not snapshot_signature_pass:

    finding(
        "HIGH",
        "SNAPSHOT_VALIDATOR_SIGNATURE_INVALID",
        "Snapshot validator no longer has the frozen keyword-only signature.",
        "SNAPSHOT",
    )


snapshot_call_style_pass = all([
    snapshot_binding.get(
        "call_style"
    )
    == "KEYWORD_ONLY_EXACT",

    snapshot_binding.get(
        "keyword_argument_order"
    )
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    snapshot_binding.get(
        "required_keyword_only_parameters"
    )
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    snapshot_binding.get(
        "keyword_argument_bindings",
        {},
    ).get(
        "as_of"
    )
    == "request.as_of",

    snapshot_binding.get(
        "keyword_argument_bindings",
        {},
    ).get(
        "evidence"
    )
    == "RESOLVED_EVIDENCE_RECORDS_FROM_REQUEST_EVIDENCE_IDS",

    snapshot_binding.get(
        "keyword_argument_bindings",
        {},
    ).get(
        "signals"
    )
    == "RESOLVED_PREFERENCE_SIGNAL_RECORDS_FROM_REQUEST_PREFERENCE_SIGNAL_IDS",
])


if not snapshot_call_style_pass:

    finding(
        "MEDIUM",
        "SNAPSHOT_KEYWORD_ONLY_CONTRACT_INVALID",
        "Snapshot KEYWORD_ONLY_EXACT binding is incomplete.",
        "SNAPSHOT",
    )


# ============================================================
# 8. ROBUST SNAPSHOT AS_OF DATAFLOW REATTACK
# ============================================================

assignments: dict[
    str,
    list[ast.AST],
] = {}


if snapshot_validator is not None:

    for node in ast.walk(
        snapshot_validator
    ):

        if isinstance(
            node,
            ast.Assign,
        ):

            for target in node.targets:

                if isinstance(
                    target,
                    ast.Name,
                ):

                    assignments.setdefault(
                        target.id,
                        [],
                    ).append(
                        node.value
                    )


        elif isinstance(
            node,
            ast.AnnAssign,
        ):

            if (
                isinstance(
                    node.target,
                    ast.Name,
                )
                and node.value
                is not None
            ):

                assignments.setdefault(
                    node.target.id,
                    [],
                ).append(
                    node.value
                )


def depends_on_snapshot_as_of(
    node: ast.AST | None,
    seen: set[str] | None = None,
) -> bool:

    if node is None:
        return False

    if seen is None:
        seen = set()


    if isinstance(
        node,
        ast.Name,
    ):

        if node.id == "as_of":
            return True


        if node.id in seen:
            return False


        next_seen = set(seen)
        next_seen.add(node.id)


        for expression in assignments.get(
            node.id,
            [],
        ):

            if depends_on_snapshot_as_of(
                expression,
                next_seen,
            ):
                return True


        return False


    for child in ast.iter_child_nodes(
        node
    ):

        if depends_on_snapshot_as_of(
            child,
            seen,
        ):
            return True


    return False


def target_as_of_position(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int | None:

    args = (
        list(fn.args.posonlyargs)
        + list(fn.args.args)
    )

    for index, arg in enumerate(args):

        if arg.arg == "as_of":
            return index

    return None


def bound_as_of_expression(
    call: ast.Call,
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> ast.AST | None:

    for keyword in call.keywords:

        if keyword.arg == "as_of":
            return keyword.value


    position = target_as_of_position(
        fn
    )

    if (
        position is not None
        and position < len(
            call.args
        )
    ):
        return call.args[
            position
        ]


    return None


child_calls = []


if snapshot_validator is not None:

    for node in ast.walk(
        snapshot_validator
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue


        name = call_name(node)


        if name not in {
            "validate_evidence_temporal",
            "validate_signal_temporal",
        }:
            continue


        target_fn = temporal_functions[
            name
        ]

        bound_expression = (
            bound_as_of_expression(
                node,
                target_fn,
            )
        )


        child_calls.append({
            "target":
                name,

            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "as_of_expression":
                expression_text(
                    bound_expression
                ),

            "depends_on_snapshot_as_of":
                depends_on_snapshot_as_of(
                    bound_expression
                ),
        })


evidence_child_calls = [
    item
    for item in child_calls
    if item["target"]
    == "validate_evidence_temporal"
]

signal_child_calls = [
    item
    for item in child_calls
    if item["target"]
    == "validate_signal_temporal"
]


evidence_forwarding_pass = (
    len(
        evidence_child_calls
    )
    > 0
    and all(
        item[
            "depends_on_snapshot_as_of"
        ]
        is True
        for item in evidence_child_calls
    )
)


signal_forwarding_pass = (
    len(
        signal_child_calls
    )
    > 0
    and all(
        item[
            "depends_on_snapshot_as_of"
        ]
        is True
        for item in signal_child_calls
    )
)


snapshot_forwarding_pass = (
    evidence_forwarding_pass
    and signal_forwarding_pass
)


if not evidence_forwarding_pass:

    finding(
        "HIGH",
        "SNAPSHOT_EVIDENCE_AS_OF_DATAFLOW_INVALID",
        "Snapshot Evidence child validation is not proven to derive as_of from request as_of.",
        "SNAPSHOT",
    )


if not signal_forwarding_pass:

    finding(
        "HIGH",
        "SNAPSHOT_SIGNAL_AS_OF_DATAFLOW_INVALID",
        "Snapshot Signal child validation is not proven to derive as_of from request as_of.",
        "SNAPSHOT",
    )


contract_forwarding_metadata_pass = all([
    snapshot_binding.get(
        "internal_as_of_forwarding_evidence_proven"
    )
    is True,

    snapshot_binding.get(
        "internal_as_of_forwarding_signal_proven"
    )
    is True,

    snapshot_binding.get(
        "internal_as_of_forwarding"
    )
    == "PROVEN_SAME_NORMALIZED_REQUEST_AS_OF_TO_CHILD_VALIDATORS",

    snapshot_binding.get(
        "internal_as_of_forwarding_provenance"
    )
    == "A2_A1_H1_SNAPSHOT_AS_OF_DATAFLOW_AUDIT",
])


if not contract_forwarding_metadata_pass:

    finding(
        "MEDIUM",
        "SNAPSHOT_FORWARDING_PROVENANCE_NOT_FROZEN",
        "V2 contract does not preserve H1 forwarding proof metadata.",
        "SNAPSHOT",
    )


# ============================================================
# 9. PRIOR HIGH FINDING DISPOSITION
# ============================================================

disposition = revised.get(
    "adversarial_finding_disposition",
    {},
)


high_disposition_pass = all([
    disposition.get(
        "SNAPSHOT_EVIDENCE_AS_OF_NOT_FORWARDED"
    )
    == "ANALYZER_FALSE_POSITIVE_PROVEN_BY_H1",

    disposition.get(
        "SNAPSHOT_SIGNAL_AS_OF_NOT_FORWARDED"
    )
    == "ANALYZER_FALSE_POSITIVE_PROVEN_BY_H1",

    h1.get(
        "prior_high_findings_false_positive"
    )
    is True,

    h1.get(
        "all_snapshot_as_of_forwarding_proven"
    )
    is True,
])


if not high_disposition_pass:

    finding(
        "HIGH",
        "PRIOR_HIGH_FINDING_DISPOSITION_INVALID",
        "The two prior false-positive HIGH findings are not dispositioned correctly.",
    )


# ============================================================
# 10. MUTATION BOUNDARY FINGERPRINTS
# ============================================================

mutation_boundary_pass = True

mutation_boundary_results = {}


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
    "SNAPSHOT",
):

    binding = bindings.get(
        consumer,
        {},
    )

    boundary = binding.get(
        "first_mutation_boundary",
        {},
    )

    line = boundary.get(
        "current_line"
    )

    expected_sha = boundary.get(
        "current_statement_line_sha256"
    )


    current_line = ""


    if (
        isinstance(line, int)
        and 1 <= line <= len(worker_lines)
    ):

        current_line = worker_lines[
            line - 1
        ]


    current_sha = hashlib.sha256(
        current_line.encode(
            "utf-8"
        )
    ).hexdigest()


    match = (
        current_line != ""
        and current_sha
        == expected_sha
    )


    mutation_boundary_results[
        consumer
    ] = {
        "line":
            line,

        "fingerprint_matches":
            match,
    }


    if not match:

        mutation_boundary_pass = False

        finding(
            "HIGH",
            "FIRST_MUTATION_BOUNDARY_FINGERPRINT_DRIFT",
            "Frozen first mutation boundary no longer matches Worker source.",
            consumer,
        )


# ============================================================
# 11. GLOBAL INVARIANTS / AUTHORIZATION
# ============================================================

global_invariants = revised.get(
    "global_invariants",
    {},
)


global_invariants_pass = all([
    global_invariants.get(
        "all_three_consumers_must_validate"
    )
    is True,

    global_invariants.get(
        "validation_before_mutation"
    )
    is True,

    global_invariants.get(
        "temporal_validity_error_fail_closed"
    )
    is True,

    global_invariants.get(
        "no_partial_persistence_on_temporal_error"
    )
    is True,

    global_invariants.get(
        "public_temporal_api_only"
    )
    is True,

    global_invariants.get(
        "private_parse_timestamp_direct_call_allowed"
    )
    is False,

    global_invariants.get(
        "temporal_module_mutation_allowed"
    )
    is False,

    global_invariants.get(
        "provider_call_allowed"
    )
    is False,

    global_invariants.get(
        "model_call_allowed"
    )
    is False,
])


if not global_invariants_pass:

    finding(
        "HIGH",
        "GLOBAL_TEMPORAL_INVARIANT_REGRESSION",
        "At least one frozen A5-I01 global invariant changed.",
    )


authorization = revised.get(
    "authorization",
    {},
)


authorization_closed = all([
    authorization.get(
        "binding_frozen"
    )
    is True,

    authorization.get(
        "implementation_authorized"
    )
    is False,

    authorization.get(
        "candidate_generation_authorized"
    )
    is False,

    authorization.get(
        "canonical_source_mutation_authorized"
    )
    is False,

    authorization.get(
        "production_mutation_authorized"
    )
    is False,

    authorization.get(
        "provider_call_authorized"
    )
    is False,

    authorization.get(
        "model_call_authorized"
    )
    is False,
])


if not authorization_closed:

    finding(
        "HIGH",
        "AUTHORIZATION_BOUNDARY_OPENED",
        "The remediated contract opened an implementation or production authorization.",
    )


# ============================================================
# 12. FINDINGS / FINAL ACCEPTANCE
# ============================================================

high = [
    item
    for item in findings
    if item[
        "severity"
    ]
    == "HIGH"
]

medium = [
    item
    for item in findings
    if item[
        "severity"
    ]
    == "MEDIUM"
]

low = [
    item
    for item in findings
    if item[
        "severity"
    ]
    == "LOW"
]


review_complete = all([
    lineage_authorized,
    request_coverage_pass,
    snapshot_signature_pass,
])


contract_accepted = (
    review_complete
    and len(high) == 0
    and len(medium) == 0
)


if contract_accepted:

    classification = (
        "A5_I01_REMEDIATED_TEMPORAL_BINDING_CONTRACT_SURVIVED_ADVERSARIAL_REATTACK"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A3_CANDIDATE_IMPLEMENTATION_PLAN_FREEZE"
    )

else:

    classification = (
        "A5_I01_REMEDIATED_TEMPORAL_BINDING_CONTRACT_REATTACK_WITH_FINDINGS"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A2-R2_TEMPORAL_BINDING_CONTRACT_REMEDIATION_REQUIRED"
    )


result = {
    "contract_version":
        "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REATTACK_V1",

    "source_contract_v1_sha256":
        sha(
            source_contract_path
        ),

    "revised_contract_v2_sha256":
        sha(
            revised_contract_path
        ),

    "source_remediation_evidence_sha256":
        sha(
            remediation_evidence_path
        ),

    "source_remediation_report_sha256":
        sha(
            remediation_report_path
        ),

    "source_h1_audit_sha256":
        sha(
            h1_audit_path
        ),

    "worker_sha256":
        sha(
            worker_path
        ),

    "temporal_sha256":
        sha(
            temporal_path
        ),

    "lineage_authorized":
        lineage_authorized,

    "revision_diff_paths":
        diff_paths,

    "unexpected_revision_diff_paths":
        unexpected_diff_paths,

    "revision_scope_pass":
        revision_scope_pass,

    "request_coverage_pass":
        request_coverage_pass,

    "evidence_explicit_fields_pass":
        evidence_explicit_fields_pass,

    "signal_explicit_fields_pass":
        signal_explicit_fields_pass,

    "evidence_proven_temporal_fields":
        sorted(
            evidence_proven_fields
        ),

    "signal_proven_temporal_fields":
        sorted(
            signal_proven_fields
        ),

    "evidence_field_usage_pass":
        evidence_field_usage_pass,

    "signal_field_usage_pass":
        signal_field_usage_pass,

    "snapshot_signature_pass":
        snapshot_signature_pass,

    "snapshot_call_style_pass":
        snapshot_call_style_pass,

    "evidence_as_of_forwarding_pass":
        evidence_forwarding_pass,

    "signal_as_of_forwarding_pass":
        signal_forwarding_pass,

    "snapshot_as_of_forwarding_pass":
        snapshot_forwarding_pass,

    "snapshot_child_validator_calls":
        child_calls,

    "contract_forwarding_metadata_pass":
        contract_forwarding_metadata_pass,

    "high_disposition_pass":
        high_disposition_pass,

    "mutation_boundary_pass":
        mutation_boundary_pass,

    "mutation_boundary_results":
        mutation_boundary_results,

    "global_invariants_pass":
        global_invariants_pass,

    "authorization_closed":
        authorization_closed,

    "finding_count":
        len(findings),

    "high_finding_count":
        len(high),

    "medium_finding_count":
        len(medium),

    "low_finding_count":
        len(low),

    "findings":
        findings,

    "review_complete":
        review_complete,

    "contract_accepted_without_revision":
        contract_accepted,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "classification":
        classification,

    "next_gate":
        next_gate,
}


output_path.write_text(
    json.dumps(
        result,
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
    "REVISION_SCOPE_PASS="
    + str(
        revision_scope_pass
    )
)

print(
    "UNEXPECTED_REVISION_DIFF_COUNT="
    + str(
        len(
            unexpected_diff_paths
        )
    )
)

for path in unexpected_diff_paths:

    print(
        "UNEXPECTED_REVISION_DIFF="
        + path
    )


print(
    "REQUEST_COVERAGE_PASS="
    + str(
        request_coverage_pass
    )
)

print(
    "EVIDENCE_EXPLICIT_FIELDS_PASS="
    + str(
        evidence_explicit_fields_pass
    )
)

print(
    "SIGNAL_EXPLICIT_FIELDS_PASS="
    + str(
        signal_explicit_fields_pass
    )
)

print(
    "EVIDENCE_PROVEN_TEMPORAL_FIELDS="
    + "|".join(
        sorted(
            evidence_proven_fields
        )
    )
)

print(
    "SIGNAL_PROVEN_TEMPORAL_FIELDS="
    + "|".join(
        sorted(
            signal_proven_fields
        )
    )
)

print(
    "EVIDENCE_FIELD_USAGE_PASS="
    + str(
        evidence_field_usage_pass
    )
)

print(
    "SIGNAL_FIELD_USAGE_PASS="
    + str(
        signal_field_usage_pass
    )
)

print(
    "SNAPSHOT_SIGNATURE_PASS="
    + str(
        snapshot_signature_pass
    )
)

print(
    "SNAPSHOT_CALL_STYLE_PASS="
    + str(
        snapshot_call_style_pass
    )
)

print(
    "EVIDENCE_AS_OF_FORWARDING_PASS="
    + str(
        evidence_forwarding_pass
    )
)

print(
    "SIGNAL_AS_OF_FORWARDING_PASS="
    + str(
        signal_forwarding_pass
    )
)

print(
    "SNAPSHOT_AS_OF_FORWARDING_PASS="
    + str(
        snapshot_forwarding_pass
    )
)

print(
    "CONTRACT_FORWARDING_METADATA_PASS="
    + str(
        contract_forwarding_metadata_pass
    )
)

print(
    "HIGH_DISPOSITION_PASS="
    + str(
        high_disposition_pass
    )
)

print(
    "MUTATION_BOUNDARY_PASS="
    + str(
        mutation_boundary_pass
    )
)

print(
    "GLOBAL_INVARIANTS_PASS="
    + str(
        global_invariants_pass
    )
)

print(
    "AUTHORIZATION_CLOSED="
    + str(
        authorization_closed
    )
)

print(
    "FINDING_COUNT="
    + str(
        len(findings)
    )
)

print(
    "HIGH_FINDING_COUNT="
    + str(
        len(high)
    )
)

print(
    "MEDIUM_FINDING_COUNT="
    + str(
        len(medium)
    )
)

print(
    "LOW_FINDING_COUNT="
    + str(
        len(low)
    )
)


for item in findings:

    print(
        "FINDING="
        + item["severity"]
        + "|"
        + item["code"]
        + "|"
        + item["consumer"]
    )


print(
    "REVIEW_COMPLETE="
    + str(
        review_complete
    )
)

print(
    "CONTRACT_ACCEPTED_WITHOUT_REVISION="
    + str(
        contract_accepted
    )
)

print(
    "IMPLEMENTATION_AUTHORIZED=False"
)

print(
    "CANDIDATE_GENERATION_AUTHORIZED=False"
)

print(
    "CLASSIFICATION="
    + classification
)

print(
    "NEXT_GATE="
    + next_gate
)