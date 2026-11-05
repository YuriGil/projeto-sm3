from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


contract_path = Path(sys.argv[1])
a2_evidence_path = Path(sys.argv[2])
a2_report_path = Path(sys.argv[3])
a1_evidence_path = Path(sys.argv[4])
a1_report_path = Path(sys.argv[5])
worker_path = Path(sys.argv[6])
temporal_path = Path(sys.argv[7])
output_path = Path(sys.argv[8])


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


def annotation_text(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def call_name(node: ast.Call) -> str | None:

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def function_signature_detail(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:

    positional = []

    for arg in list(fn.args.posonlyargs) + list(fn.args.args):

        positional.append({
            "name": arg.arg,
            "annotation": annotation_text(arg.annotation),
        })


    keyword_only = []

    for index, arg in enumerate(fn.args.kwonlyargs):

        default_node = fn.args.kw_defaults[index]

        keyword_only.append({
            "name": arg.arg,
            "annotation": annotation_text(arg.annotation),
            "required": default_node is None,
        })


    return {
        "positional": positional,
        "keyword_only": keyword_only,
        "vararg": (
            fn.args.vararg.arg
            if fn.args.vararg
            else None
        ),
        "kwarg": (
            fn.args.kwarg.arg
            if fn.args.kwarg
            else None
        ),
    }


def parameters(detail: dict[str, Any]) -> list[str]:

    result = []

    for item in detail["positional"]:
        result.append(item["name"])

    for item in detail["keyword_only"]:
        result.append(item["name"])

    return result


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


def forwarded_as_of(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    target_name: str,
) -> bool:

    for node in ast.walk(fn):

        if not isinstance(node, ast.Call):
            continue

        if call_name(node) != target_name:
            continue

        # keyword: as_of=as_of
        for keyword in node.keywords:

            if (
                keyword.arg == "as_of"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "as_of"
            ):
                return True


        # positional fallback:
        # evidence/signal validators have payload first, as_of second.
        if len(node.args) >= 2:

            candidate = node.args[1]

            if (
                isinstance(candidate, ast.Name)
                and candidate.id == "as_of"
            ):
                return True

    return False


def raises_temporal_error(
    functions: dict[
        str,
        ast.FunctionDef | ast.AsyncFunctionDef,
    ],
    call_graph: dict[str, set[str]],
    start: str,
) -> bool:

    visited = set()
    stack = [start]

    while stack:

        current = stack.pop()

        if current in visited:
            continue

        visited.add(current)

        fn = functions.get(current)

        if fn is None:
            continue

        for node in ast.walk(fn):

            if not isinstance(node, ast.Raise):
                continue

            exc = node.exc

            if isinstance(exc, ast.Call):

                if call_name(exc) == "TemporalValidityError":
                    return True

            elif isinstance(exc, ast.Name):

                if exc.id == "TemporalValidityError":
                    return True


        for child in call_graph.get(current, set()):

            if child not in visited:
                stack.append(child)

    return False


def transitive_nodes(
    functions: dict[
        str,
        ast.FunctionDef | ast.AsyncFunctionDef,
    ],
    call_graph: dict[str, set[str]],
    start: str,
) -> list[ast.AST]:

    result: list[ast.AST] = []

    visited = set()
    stack = [start]

    while stack:

        current = stack.pop()

        if current in visited:
            continue

        visited.add(current)

        fn = functions.get(current)

        if fn is None:
            continue

        result.append(fn)

        for child in call_graph.get(current, set()):

            if child not in visited:
                stack.append(child)

    return result


contract = load(contract_path)
a2_evidence = load(a2_evidence_path)
a2_report = load(a2_report_path)
a1_evidence = load(a1_evidence_path)
a1_report = load(a1_report_path)


findings: list[dict[str, Any]] = []


def add_finding(
    severity: str,
    code: str,
    message: str,
    consumer: str = "GLOBAL",
) -> None:

    findings.append({
        "severity": severity,
        "code": code,
        "consumer": consumer,
        "message": message,
    })


# ============================================================
# 1. LINEAGE
# ============================================================

lineage_checks = [
    contract.get("contract_version")
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V1",

    contract.get("requirement_id")
    == "A5-R04",

    contract.get("implementation_unit")
    == "A5-I01",

    a2_evidence.get(
        "binding_contract_freeze_pass"
    )
    is True,

    a2_evidence.get(
        "binding_frozen"
    )
    is True,

    a2_evidence.get(
        "implementation_authorized"
    )
    is False,

    a2_evidence.get(
        "candidate_generation_authorized"
    )
    is False,

    a2_report.get(
        "a5_i01_a2_pass"
    )
    is True,

    a2_report.get(
        "classification"
    )
    == "A5_I01_TEMPORAL_BINDING_CONTRACT_FROZEN",

    a2_report.get(
        "next_gate"
    )
    == "09C7-B3E-A5-I01-A2-A1_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REVIEW",

    a1_evidence.get(
        "preflight_complete"
    )
    is True,

    a1_report.get(
        "a5_i01_a1_pass"
    )
    is True,
]


lineage_authorized = all(lineage_checks)


if not lineage_authorized:

    raise RuntimeError(
        "A2_A1_LINEAGE_NOT_AUTHORIZED"
    )


# ============================================================
# 2. PARSE TEMPORAL MODULE
# ============================================================

temporal_source = temporal_path.read_text(
    encoding="utf-8-sig"
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(temporal_path),
)


functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


for node in temporal_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        functions[node.name] = node


required_validators = {
    "EVIDENCE": "validate_evidence_temporal",
    "PREFERENCE_SIGNAL": "validate_signal_temporal",
    "SNAPSHOT": "validate_snapshot_temporal_inputs",
}


for name in required_validators.values():

    if name not in functions:

        add_finding(
            "HIGH",
            "PUBLIC_VALIDATOR_MISSING",
            "Frozen public validator no longer exists: " + name,
        )


call_graph: dict[str, set[str]] = {}


for name, fn in functions.items():

    call_graph[name] = {
        called
        for called in call_names(fn)
        if called in functions
    }


# ============================================================
# 3. SIGNATURE ATTACK
# ============================================================

signature_evidence = {}


for consumer, validator in required_validators.items():

    fn = functions.get(validator)

    if fn is None:
        continue

    detail = function_signature_detail(fn)

    signature_evidence[consumer] = detail


    frozen = (
        contract
        .get("validator_details", {})
        .get(consumer, {})
    )


    frozen_positional = [
        item.get("name")
        for item in frozen.get(
            "positional",
            []
        )
    ]

    frozen_keyword_only = [
        item.get("name")
        for item in frozen.get(
            "keyword_only",
            []
        )
    ]

    current_positional = [
        item["name"]
        for item in detail[
            "positional"
        ]
    ]

    current_keyword_only = [
        item["name"]
        for item in detail[
            "keyword_only"
        ]
    ]


    if (
        frozen_positional
        != current_positional
        or frozen_keyword_only
        != current_keyword_only
    ):

        add_finding(
            "HIGH",
            "VALIDATOR_SIGNATURE_DRIFT",
            (
                validator
                + " signature differs from frozen contract."
            ),
            consumer,
        )


# ============================================================
# 4. SNAPSHOT KEYWORD-ONLY ATTACK
# ============================================================

snapshot_detail = signature_evidence.get(
    "SNAPSHOT",
    {},
)

snapshot_required_keyword_only = [
    item["name"]
    for item in snapshot_detail.get(
        "keyword_only",
        []
    )
    if item.get("required") is True
]


snapshot_binding = (
    contract
    .get("bindings", {})
    .get("SNAPSHOT", {})
)


snapshot_call_style = (
    snapshot_binding.get(
        "call_style"
    )
)


snapshot_keyword_only_required = (
    len(
        snapshot_required_keyword_only
    )
    > 0
)


if (
    snapshot_keyword_only_required
    and snapshot_call_style
    != "KEYWORD_ONLY_EXACT"
):

    add_finding(
        "MEDIUM",
        "SNAPSHOT_KEYWORD_ONLY_CALL_STYLE_NOT_FROZEN",
        (
            "Snapshot validator has required keyword-only parameters "
            "but the binding contract does not explicitly freeze "
            "KEYWORD_ONLY_EXACT invocation."
        ),
        "SNAPSHOT",
    )


# ============================================================
# 5. TRANSITIVE TEMPORAL FIELD USAGE
# ============================================================

expected_temporal_fields = {
    "EVIDENCE": {
        "source_date",
        "observed_at",
        "valid_until",
    },

    "PREFERENCE_SIGNAL": {
        "window_started_at",
        "window_ended_at",
    },
}


field_usage = {}


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    validator = required_validators[
        consumer
    ]

    nodes = transitive_nodes(
        functions,
        call_graph,
        validator,
    )


    literals = set()
    symbol_names = set()


    for node in nodes:

        literals.update(
            string_constants(node)
        )

        symbol_names.update(
            names_and_attrs(node)
        )


    found = sorted(
        field
        for field in expected_temporal_fields[
            consumer
        ]
        if (
            field in literals
            or field in symbol_names
        )
    )


    missing = sorted(
        expected_temporal_fields[
            consumer
        ]
        - set(found)
    )


    field_usage[consumer] = {
        "expected":
            sorted(
                expected_temporal_fields[
                    consumer
                ]
            ),

        "found":
            found,

        "missing":
            missing,
    }


    if missing:

        add_finding(
            "HIGH",
            "TEMPORAL_REQUIRED_FIELD_USAGE_NOT_PROVEN",
            (
                "Could not prove validator/reachable helpers consume: "
                + "|".join(missing)
            ),
            consumer,
        )


# ============================================================
# 6. VACUOUS COVERAGE ATTACK
# ============================================================

for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    binding = (
        contract
        .get("bindings", {})
        .get(consumer, {})
    )


    frozen_keys = list(
        binding.get(
            "validator_mapping_keys",
            []
        )
        or []
    )


    if len(frozen_keys) == 0:

        add_finding(
            "MEDIUM",
            "VACUOUS_VALIDATOR_KEY_COVERAGE",
            (
                "A2 froze request-field coverage using an empty "
                "validator_mapping_keys set. Coverage is therefore "
                "vacuous and must be replaced by an explicit temporal "
                "input field set."
            ),
            consumer,
        )


# ============================================================
# 7. SNAPSHOT DELEGATION ATTACK
# ============================================================

snapshot_fn = functions.get(
    "validate_snapshot_temporal_inputs"
)


snapshot_calls_evidence = False
snapshot_calls_signal = False
snapshot_forwards_as_of_evidence = False
snapshot_forwards_as_of_signal = False


if snapshot_fn is not None:

    snapshot_call_names = call_names(
        snapshot_fn
    )


    snapshot_calls_evidence = (
        "validate_evidence_temporal"
        in snapshot_call_names
    )

    snapshot_calls_signal = (
        "validate_signal_temporal"
        in snapshot_call_names
    )


    snapshot_forwards_as_of_evidence = forwarded_as_of(
        snapshot_fn,
        "validate_evidence_temporal",
    )

    snapshot_forwards_as_of_signal = forwarded_as_of(
        snapshot_fn,
        "validate_signal_temporal",
    )


if not snapshot_calls_evidence:

    add_finding(
        "HIGH",
        "SNAPSHOT_DOES_NOT_VALIDATE_EVIDENCE",
        "Snapshot validator does not call validate_evidence_temporal.",
        "SNAPSHOT",
    )


if not snapshot_calls_signal:

    add_finding(
        "HIGH",
        "SNAPSHOT_DOES_NOT_VALIDATE_SIGNALS",
        "Snapshot validator does not call validate_signal_temporal.",
        "SNAPSHOT",
    )


if (
    snapshot_calls_evidence
    and not snapshot_forwards_as_of_evidence
):

    add_finding(
        "HIGH",
        "SNAPSHOT_EVIDENCE_AS_OF_NOT_FORWARDED",
        "Snapshot does not forward the same as_of to evidence validation.",
        "SNAPSHOT",
    )


if (
    snapshot_calls_signal
    and not snapshot_forwards_as_of_signal
):

    add_finding(
        "HIGH",
        "SNAPSHOT_SIGNAL_AS_OF_NOT_FORWARDED",
        "Snapshot does not forward the same as_of to signal validation.",
        "SNAPSHOT",
    )


# ============================================================
# 8. ERROR SEMANTICS
# ============================================================

error_semantics = {}


for consumer, validator in required_validators.items():

    raises = raises_temporal_error(
        functions,
        call_graph,
        validator,
    )


    error_semantics[
        consumer
    ] = raises


    if not raises:

        add_finding(
            "HIGH",
            "TEMPORAL_VALIDITY_ERROR_PATH_NOT_PROVEN",
            (
                validator
                + " has no direct/transitive TemporalValidityError path."
            ),
            consumer,
        )


# ============================================================
# 9. CONTRACT BINDING ATTACK
# ============================================================

bindings = contract.get(
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


if evidence_binding.get(
    "as_of_binding"
) != "SERVER_UTC_NOW_AT_HANDLER_ENTRY":

    add_finding(
        "HIGH",
        "EVIDENCE_AS_OF_AUTHORITY_INVALID",
        "Evidence as_of authority changed.",
        "EVIDENCE",
    )


if signal_binding.get(
    "as_of_binding"
) != "SERVER_UTC_NOW_AT_HANDLER_ENTRY":

    add_finding(
        "HIGH",
        "SIGNAL_AS_OF_AUTHORITY_INVALID",
        "Signal as_of authority changed.",
        "PREFERENCE_SIGNAL",
    )


if snapshot_binding.get(
    "as_of_binding"
) != "request.as_of":

    add_finding(
        "HIGH",
        "SNAPSHOT_AS_OF_AUTHORITY_INVALID",
        "Snapshot as_of authority changed.",
        "SNAPSHOT",
    )


if (
    "request.observed_at"
    not in evidence_binding.get(
        "as_of_must_not_bind_to",
        []
    )
):

    add_finding(
        "HIGH",
        "EVIDENCE_OBSERVED_AT_ANTI_BINDING_MISSING",
        "Evidence contract does not prohibit observed_at as as_of authority.",
        "EVIDENCE",
    )


if (
    "request.window_ended_at"
    not in signal_binding.get(
        "as_of_must_not_bind_to",
        []
    )
):

    add_finding(
        "HIGH",
        "SIGNAL_WINDOW_END_ANTI_BINDING_MISSING",
        "Signal contract does not prohibit window_ended_at as as_of authority.",
        "PREFERENCE_SIGNAL",
    )


# ============================================================
# 10. MUTATION BOUNDARY FINGERPRINT ATTACK
# ============================================================

worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_lines = worker_source.splitlines()


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

    expected_line_sha = boundary.get(
        "current_statement_line_sha256"
    )


    current_line = ""


    if (
        isinstance(line, int)
        and line >= 1
        and line <= len(worker_lines)
    ):

        current_line = worker_lines[
            line - 1
        ]


    current_line_sha = hashlib.sha256(
        current_line.encode(
            "utf-8"
        )
    ).hexdigest()


    matches = (
        current_line != ""
        and current_line_sha
        == expected_line_sha
    )


    mutation_boundary_results[
        consumer
    ] = {
        "line": line,
        "fingerprint_matches": matches,
    }


    if not matches:

        mutation_boundary_pass = False

        add_finding(
            "HIGH",
            "FIRST_MUTATION_BOUNDARY_FINGERPRINT_DRIFT",
            "Frozen first-mutation boundary no longer matches Worker source.",
            consumer,
        )


# ============================================================
# 11. AUTHORIZATION ATTACK
# ============================================================

authorization = contract.get(
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

    add_finding(
        "HIGH",
        "AUTHORIZATION_BOUNDARY_OPENED",
        "Binding contract unexpectedly authorizes implementation or production mutation.",
    )


# ============================================================
# 12. FINDING SUMMARY
# ============================================================

high = [
    item
    for item in findings
    if item["severity"] == "HIGH"
]

medium = [
    item
    for item in findings
    if item["severity"] == "MEDIUM"
]

low = [
    item
    for item in findings
    if item["severity"] == "LOW"
]


review_complete = (
    lineage_authorized
    and len(signature_evidence) == 3
)


contract_accepted_without_revision = (
    len(high) == 0
    and len(medium) == 0
)


if contract_accepted_without_revision:

    classification = (
        "A5_I01_TEMPORAL_BINDING_CONTRACT_SURVIVED_ADVERSARIAL_REVIEW"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A3_CANDIDATE_IMPLEMENTATION_PLAN_FREEZE"
    )

else:

    classification = (
        "A5_I01_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REVIEW_COMPLETE_WITH_FINDINGS"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A2-R1_TEMPORAL_BINDING_CONTRACT_REMEDIATION"
    )


result = {
    "contract_version":
        "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REVIEW_V1",

    "source_binding_contract_sha256":
        sha(contract_path),

    "source_a2_evidence_sha256":
        sha(a2_evidence_path),

    "source_a2_report_sha256":
        sha(a2_report_path),

    "source_a1_evidence_sha256":
        sha(a1_evidence_path),

    "source_a1_report_sha256":
        sha(a1_report_path),

    "worker_sha256":
        sha(worker_path),

    "temporal_sha256":
        sha(temporal_path),

    "lineage_authorized":
        lineage_authorized,

    "signature_evidence":
        signature_evidence,

    "snapshot_keyword_only_required":
        snapshot_keyword_only_required,

    "snapshot_required_keyword_only_parameters":
        snapshot_required_keyword_only,

    "snapshot_frozen_call_style":
        snapshot_call_style,

    "field_usage":
        field_usage,

    "snapshot_calls_evidence_validator":
        snapshot_calls_evidence,

    "snapshot_calls_signal_validator":
        snapshot_calls_signal,

    "snapshot_forwards_as_of_to_evidence":
        snapshot_forwards_as_of_evidence,

    "snapshot_forwards_as_of_to_signal":
        snapshot_forwards_as_of_signal,

    "error_semantics":
        error_semantics,

    "mutation_boundary_pass":
        mutation_boundary_pass,

    "mutation_boundary_results":
        mutation_boundary_results,

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

    "contract_accepted_without_revision":
        contract_accepted_without_revision,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "review_complete":
        review_complete,

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
    "REVIEW_COMPLETE="
    + str(
        review_complete
    )
)

print(
    "SNAPSHOT_KEYWORD_ONLY_REQUIRED="
    + str(
        snapshot_keyword_only_required
    )
)

print(
    "SNAPSHOT_REQUIRED_KEYWORD_ONLY_PARAMETERS="
    + "|".join(
        snapshot_required_keyword_only
    )
)

print(
    "SNAPSHOT_FROZEN_CALL_STYLE="
    + str(
        snapshot_call_style
    )
)


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    usage = field_usage.get(
        consumer,
        {},
    )

    print(
        consumer
        + "_EXPECTED_TEMPORAL_FIELDS="
        + "|".join(
            usage.get(
                "expected",
                [],
            )
        )
    )

    print(
        consumer
        + "_PROVEN_TEMPORAL_FIELDS="
        + "|".join(
            usage.get(
                "found",
                [],
            )
        )
    )

    print(
        consumer
        + "_MISSING_TEMPORAL_FIELDS="
        + "|".join(
            usage.get(
                "missing",
                [],
            )
        )
    )


print(
    "SNAPSHOT_CALLS_EVIDENCE_VALIDATOR="
    + str(
        snapshot_calls_evidence
    )
)

print(
    "SNAPSHOT_CALLS_SIGNAL_VALIDATOR="
    + str(
        snapshot_calls_signal
    )
)

print(
    "SNAPSHOT_FORWARDS_AS_OF_TO_EVIDENCE="
    + str(
        snapshot_forwards_as_of_evidence
    )
)

print(
    "SNAPSHOT_FORWARDS_AS_OF_TO_SIGNAL="
    + str(
        snapshot_forwards_as_of_signal
    )
)

print(
    "MUTATION_BOUNDARY_PASS="
    + str(
        mutation_boundary_pass
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
    "CONTRACT_ACCEPTED_WITHOUT_REVISION="
    + str(
        contract_accepted_without_revision
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