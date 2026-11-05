from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


plan_path = Path(sys.argv[1])
evidence_path = Path(sys.argv[2])
a3_report_path = Path(sys.argv[3])
h1_report_path = Path(sys.argv[4])
worker_path = Path(sys.argv[5])
temporal_path = Path(sys.argv[6])
output_path = Path(sys.argv[7])


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


def call_name(node: ast.Call) -> str | None:

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def root_name(node: ast.AST) -> str | None:

    current = node

    while isinstance(
        current,
        (
            ast.Attribute,
            ast.Subscript,
        ),
    ):

        if isinstance(
            current,
            ast.Attribute,
        ):
            current = current.value
        else:
            current = current.value

    if isinstance(current, ast.Name):
        return current.id

    return None


def expr_text(node: ast.AST | None) -> str:

    if node is None:
        return ""

    try:
        return ast.unparse(node)
    except Exception:
        return ""


plan = load(plan_path)
evidence = load(evidence_path)
a3_report = load(a3_report_path)
h1_report = load(h1_report_path)


findings: list[dict[str, Any]] = []


def finding(
    severity: str,
    code: str,
    message: str,
    scope: str = "GLOBAL",
) -> None:

    findings.append({
        "severity": severity,
        "code": code,
        "scope": scope,
        "message": message,
    })


# ============================================================
# 1. LINEAGE
# ============================================================

lineage_checks = [
    plan.get("contract_version")
    == "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_V1",

    plan.get("requirement_id")
    == "A5-R04",

    plan.get("implementation_unit")
    == "A5-I01",

    plan.get("implementation_plan_frozen")
    is True,

    plan.get("implementation_authorized")
    is False,

    plan.get("candidate_generation_authorized")
    is False,

    plan.get("candidate_execution_authorized")
    is False,

    evidence.get("plan_freeze_pass")
    is True,

    evidence.get("persistence_pass")
    is True,

    a3_report.get("a5_i01_a3_pass")
    is True,

    a3_report.get("classification")
    == "A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_FROZEN",

    h1_report.get("h1_pass")
    is True,

    h1_report.get("project_regression")
    is False,

    h1_report.get("plan_regenerated")
    is False,

    h1_report.get("evidence_regenerated")
    is False,

    h1_report.get("repaired_verifier_pass")
    is True,

    h1_report.get("next_gate")
    == "09C7-B3E-A5-I01-A3-A1_CANDIDATE_IMPLEMENTATION_PLAN_ADVERSARIAL_REVIEW",
]


lineage_authorized = all(
    lineage_checks
)


if not lineage_authorized:
    raise RuntimeError(
        "A3_A1_LINEAGE_NOT_AUTHORIZED"
    )


# ============================================================
# 2. PARSE WORKER
# ============================================================

worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_lines = worker_source.splitlines()

worker_tree = ast.parse(
    worker_source,
    filename=str(worker_path),
)


functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


module_globals: set[str] = set()


for node in worker_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        functions[node.name] = node


    elif isinstance(node, ast.Assign):

        for target in node.targets:

            if isinstance(target, ast.Name):
                module_globals.add(
                    target.id
                )


    elif isinstance(node, ast.AnnAssign):

        if isinstance(node.target, ast.Name):
            module_globals.add(
                node.target.id
            )


# ============================================================
# 3. REATTACK HANDLER ANCHORS
# ============================================================

handler_evidence = plan.get(
    "handler_evidence",
    {}
)


handler_anchor_pass = True


for consumer, item in handler_evidence.items():

    handler_name = item.get(
        "handler"
    )

    fn = functions.get(
        handler_name
    )


    if fn is None:

        handler_anchor_pass = False

        finding(
            "HIGH",
            "TARGET_HANDLER_MISSING",
            "Target handler no longer exists.",
            consumer,
        )

        continue


    start = getattr(
        fn,
        "lineno",
        None,
    )

    end = getattr(
        fn,
        "end_lineno",
        None,
    )


    source = "\n".join(
        worker_lines[
            start - 1:end
        ]
    )


    current_sha = segment_sha(
        source
    )


    if current_sha != item.get(
        "source_sha256"
    ):

        handler_anchor_pass = False

        finding(
            "HIGH",
            "HANDLER_SOURCE_ANCHOR_DRIFT",
            "Current handler hash differs from frozen implementation plan.",
            consumer,
        )


    boundary_line = item.get(
        "first_mutation_line"
    )

    boundary_sha = item.get(
        "first_mutation_line_sha256"
    )


    if not isinstance(
        boundary_line,
        int,
    ):

        handler_anchor_pass = False

        finding(
            "HIGH",
            "FIRST_MUTATION_LINE_INVALID",
            "Frozen mutation line is not an integer.",
            consumer,
        )

        continue


    current_boundary_line = (
        worker_lines[
            boundary_line - 1
        ]
        if 1 <= boundary_line <= len(worker_lines)
        else ""
    )


    if segment_sha(
        current_boundary_line
    ) != boundary_sha:

        handler_anchor_pass = False

        finding(
            "HIGH",
            "FIRST_MUTATION_FINGERPRINT_DRIFT",
            "Current first-mutation fingerprint differs from frozen plan.",
            consumer,
        )


# ============================================================
# 4. INDEPENDENT PRE-BOUNDARY MUTATION ATTACK
# ============================================================

mutator_methods = {
    "append",
    "extend",
    "update",
    "setdefault",
    "pop",
    "popitem",
    "remove",
    "discard",
    "clear",
    "insert",
    "__setitem__",
}


pre_boundary_mutation_candidates: dict[
    str,
    list[dict[str, Any]],
] = {}


for consumer, item in handler_evidence.items():

    fn = functions.get(
        item.get(
            "handler"
        )
    )


    if fn is None:
        continue


    boundary_line = item[
        "first_mutation_line"
    ]


    candidates = []


    for node in ast.walk(fn):

        line = getattr(
            node,
            "lineno",
            None,
        )


        if (
            line is None
            or line >= boundary_line
        ):
            continue


        # Global/object collection mutator.
        if isinstance(node, ast.Call):

            if isinstance(
                node.func,
                ast.Attribute,
            ):

                method = node.func.attr

                root = root_name(
                    node.func.value
                )


                if (
                    method in mutator_methods
                    and root in module_globals
                ):

                    candidates.append({
                        "line": line,
                        "type": "GLOBAL_MUTATOR_CALL",
                        "root": root,
                        "operation": method,
                        "source": expr_text(node),
                    })


        # Assignment directly into global subscript/attribute.
        if isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
            ),
        ):

            targets = []


            if isinstance(node, ast.Assign):
                targets.extend(
                    node.targets
                )

            elif isinstance(node, ast.AnnAssign):
                targets.append(
                    node.target
                )

            else:
                targets.append(
                    node.target
                )


            for target in targets:

                if not isinstance(
                    target,
                    (
                        ast.Subscript,
                        ast.Attribute,
                    ),
                ):
                    continue


                root = root_name(
                    target
                )


                if root in module_globals:

                    candidates.append({
                        "line": line,
                        "type": "GLOBAL_TARGET_ASSIGNMENT",
                        "root": root,
                        "operation": type(node).__name__,
                        "source": expr_text(target),
                    })


    # De-duplicate.
    unique = []

    seen = set()


    for candidate in candidates:

        key = (
            candidate[
                "line"
            ],
            candidate[
                "type"
            ],
            candidate[
                "root"
            ],
            candidate[
                "operation"
            ],
            candidate[
                "source"
            ],
        )

        if key not in seen:

            seen.add(key)

            unique.append(
                candidate
            )


    pre_boundary_mutation_candidates[
        consumer
    ] = unique


    if unique:

        finding(
            "HIGH",
            "PRE_BOUNDARY_STATE_MUTATION_CANDIDATE",
            (
                "Independent mutation scan found possible state "
                "mutation before the frozen boundary."
            ),
            consumer,
        )


mutation_boundary_reattack_pass = all(
    len(items) == 0
    for items in pre_boundary_mutation_candidates.values()
)


# ============================================================
# 5. EXACT ALLOWED HANDLER SET
# ============================================================

diff_budget = plan.get(
    "diff_budget",
    {}
)


expected_handler_set = {
    "production_platform_dynamics_evidence_ingest",
    "production_platform_preference_signal_ingest",
    "production_platform_dynamics_snapshot_build",
}


actual_handler_set = set(
    diff_budget.get(
        "allowed_handler_body_changes",
        [],
    )
)


allowed_handler_set_pass = (
    actual_handler_set
    == expected_handler_set
)


if not allowed_handler_set_pass:

    finding(
        "HIGH",
        "ALLOWED_HANDLER_SET_INVALID",
        "Diff budget does not restrict body changes to the exact three handlers.",
    )


# ============================================================
# 6. PATCH-SCOPE CONTRADICTION ATTACK
# ============================================================

static_assertions = set(
    plan.get(
        "static_assertions",
        [],
    )
)


only_three_handler_assertion = (
    "ONLY_THREE_TARGET_HANDLER_BODIES_MAY_CHANGE"
    in static_assertions
)


optional_import_policy = diff_budget.get(
    "optional_standard_library_import_change"
)


import_scope_ambiguous = (
    only_three_handler_assertion
    and optional_import_policy
    not in (
        None,
        False,
        "FORBIDDEN",
        "NONE",
    )
)


if import_scope_ambiguous:

    finding(
        "MEDIUM",
        "IMPORT_CHANGE_POLICY_CONTRADICTS_HANDLER_ONLY_DIFF_ASSERTION",
        (
            "Plan freezes ONLY_THREE_TARGET_HANDLER_BODIES_MAY_CHANGE "
            "but separately permits an optional module-level standard "
            "library import. Candidate diff scope is therefore ambiguous."
        ),
    )


# ============================================================
# 7. PYDANTIC SERIALIZATION INVENTORY
# ============================================================

serialization_methods: set[str] = set()


for node in ast.walk(
    worker_tree
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    if isinstance(
        node.func,
        ast.Attribute,
    ):

        method = node.func.attr


        if method in {
            "model_dump",
            "dict",
            "model_dump_json",
            "json",
        }:

            serialization_methods.add(
                method
            )


serialization_methods_sorted = sorted(
    serialization_methods
)


operations = {
    item.get(
        "consumer"
    ):
        item
    for item in plan.get(
        "operations",
        [],
    )
}


serialization_freeze_pass = True


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    operation = operations.get(
        consumer,
        {}
    )


    exact_api = (
        operation.get(
            "payload_serialization_api"
        )
        or operation.get(
            "payload_serialization_expression"
        )
        or operation.get(
            "payload_serialization_helper"
        )
    )


    if not exact_api:

        serialization_freeze_pass = False

        finding(
            "MEDIUM",
            "REQUEST_SERIALIZATION_PRIMITIVE_NOT_FROZEN",
            (
                "Plan freezes semantic full-model mapping but not the "
                "exact Pydantic serialization primitive/expression."
            ),
            consumer,
        )


# ============================================================
# 8. UTC CLOCK INVENTORY / EXACTNESS
# ============================================================

utc_function_candidates = []


for name, fn in functions.items():

    lowered = name.lower()


    if (
        "utc" in lowered
        and (
            "now" in lowered
            or "time" in lowered
        )
    ):

        utc_function_candidates.append(
            name
        )


utc_expression_candidates = []


for node in ast.walk(
    worker_tree
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    text = expr_text(
        node
    )


    lowered = text.lower()


    if (
        "datetime.now" in lowered
        or "datetime.utcnow" in lowered
        or "timezone.utc" in lowered
    ):

        utc_expression_candidates.append(
            text
        )


utc_function_candidates = sorted(
    set(
        utc_function_candidates
    )
)

utc_expression_candidates = sorted(
    set(
        utc_expression_candidates
    )
)


clock_freeze_pass = True


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    operation = operations.get(
        consumer,
        {}
    )


    exact_clock = (
        operation.get(
            "server_clock_helper"
        )
        or operation.get(
            "server_clock_expression"
        )
        or operation.get(
            "server_clock_primitive"
        )
    )


    if not exact_clock:

        clock_freeze_pass = False

        finding(
            "MEDIUM",
            "SERVER_UTC_CLOCK_PRIMITIVE_NOT_FROZEN",
            (
                "UTC semantics are frozen, but the candidate plan does "
                "not freeze the exact existing helper or expression used "
                "to obtain that clock."
            ),
            consumer,
        )


# ============================================================
# 9. SNAPSHOT RESOLUTION VARIABLE INVENTORY
# ============================================================

snapshot_item = handler_evidence.get(
    "SNAPSHOT",
    {}
)

snapshot_fn = functions.get(
    snapshot_item.get(
        "handler"
    )
)


snapshot_resolution_candidates = {
    "evidence": [],
    "signals": [],
}


if snapshot_fn is not None:

    boundary_line = snapshot_item[
        "first_mutation_line"
    ]


    for statement in snapshot_fn.body:

        line = getattr(
            statement,
            "lineno",
            None,
        )


        if (
            line is None
            or line >= boundary_line
        ):
            continue


        targets = []


        if isinstance(
            statement,
            ast.Assign,
        ):

            for target in statement.targets:

                if isinstance(
                    target,
                    ast.Name,
                ):
                    targets.append(
                        target.id
                    )


        elif isinstance(
            statement,
            ast.AnnAssign,
        ):

            if isinstance(
                statement.target,
                ast.Name,
            ):
                targets.append(
                    statement.target.id
                )


        if not targets:
            continue


        text = expr_text(
            statement
        )

        lowered = text.lower()


        for target in targets:

            if "evidence" in lowered:

                snapshot_resolution_candidates[
                    "evidence"
                ].append({
                    "variable": target,
                    "line": line,
                    "source": text,
                })


            if (
                "signal" in lowered
                or "preference" in lowered
            ):

                snapshot_resolution_candidates[
                    "signals"
                ].append({
                    "variable": target,
                    "line": line,
                    "source": text,
                })


snapshot_operation = operations.get(
    "SNAPSHOT",
    {}
)


snapshot_exact_variable_bindings = (
    snapshot_operation.get(
        "resolved_evidence_variable"
    ),
    snapshot_operation.get(
        "resolved_signals_variable"
    ),
)


snapshot_variable_binding_pass = all(
    isinstance(value, str)
    and value.strip() != ""
    for value in snapshot_exact_variable_bindings
)


if not snapshot_variable_binding_pass:

    finding(
        "MEDIUM",
        "SNAPSHOT_RESOLVED_RECORD_VARIABLES_NOT_FROZEN",
        (
            "Snapshot plan defines semantic record bindings but not "
            "the exact current local variables that must be passed to "
            "validate_snapshot_temporal_inputs."
        ),
        "SNAPSHOT",
    )


# ============================================================
# 10. DYNAMIC CLOCK-AUTHORITY COVERAGE
# ============================================================

dynamic_tests = plan.get(
    "dynamic_test_matrix",
    []
)


dynamic_text = " ".join(
    (
        str(item.get("scenario", ""))
        + " "
        + str(item.get("expected", ""))
    ).upper()
    for item in dynamic_tests
)


clock_authority_dynamic_test_present = any(
    token in dynamic_text
    for token in (
        "SERVER_CLOCK",
        "UTC_CLOCK",
        "REQUEST_CONTROLLED_CLOCK",
        "CLOCK_AUTHORITY",
        "EXACTLY_ONCE",
    )
)


if not clock_authority_dynamic_test_present:

    finding(
        "MEDIUM",
        "INGEST_CLOCK_AUTHORITY_DYNAMIC_TEST_MISSING",
        (
            "Dynamic matrix does not explicitly prove that Evidence/"
            "Signal temporal as_of comes from one server UTC capture "
            "rather than request-controlled timestamps."
        ),
    )


# ============================================================
# 11. TEMPORAL FAILURE COVERAGE
# ============================================================

expected_dynamic_ids = {
    "A5-I01-D01",
    "A5-I01-D02",
    "A5-I01-D03",
    "A5-I01-D04",
    "A5-I01-D05",
    "A5-I01-D06",
    "A5-I01-D07",
    "A5-I01-D08",
}


dynamic_matrix_baseline_pass = (
    len(
        dynamic_tests
    )
    == 8
    and {
        item.get(
            "test_id"
        )
        for item in dynamic_tests
    }
    == expected_dynamic_ids
)


if not dynamic_matrix_baseline_pass:

    finding(
        "HIGH",
        "DYNAMIC_TEST_MATRIX_BASELINE_DRIFT",
        "Frozen eight-test dynamic matrix changed unexpectedly.",
    )


invalid_temporal_test_count = sum(
    1
    for item in dynamic_tests
    if item.get(
        "expected"
    )
    == "TEMPORAL_VALIDITY_ERROR_AND_ZERO_STATE_MUTATION"
)


temporal_failure_coverage_pass = (
    invalid_temporal_test_count
    >= 4
)


if not temporal_failure_coverage_pass:

    finding(
        "HIGH",
        "TEMPORAL_FAILURE_DYNAMIC_COVERAGE_INSUFFICIENT",
        "Dynamic matrix no longer has sufficient fail-closed scenarios.",
    )


# ============================================================
# 12. AUTHORIZATION / SAFETY REATTACK
# ============================================================

candidate_policy = plan.get(
    "candidate_policy",
    {}
)

global_safety = plan.get(
    "global_safety",
    {}
)


authorization_closed = all([
    plan.get(
        "implementation_authorized"
    )
    is False,

    plan.get(
        "candidate_generation_authorized"
    )
    is False,

    plan.get(
        "candidate_execution_authorized"
    )
    is False,

    plan.get(
        "canonical_source_mutation_authorized"
    )
    is False,

    plan.get(
        "production_mutation_authorized"
    )
    is False,

    candidate_policy.get(
        "candidate_generation_authorized"
    )
    is False,

    candidate_policy.get(
        "candidate_execution_authorized"
    )
    is False,

    candidate_policy.get(
        "candidate_container_authorized"
    )
    is False,

    candidate_policy.get(
        "canonical_materialization_authorized"
    )
    is False,

    candidate_policy.get(
        "production_deployment_authorized"
    )
    is False,

    global_safety.get(
        "canonical_worker_read_only"
    )
    is True,

    global_safety.get(
        "temporal_module_read_only"
    )
    is True,

    global_safety.get(
        "production_read_only"
    )
    is True,

    global_safety.get(
        "no_provider_call"
    )
    is True,

    global_safety.get(
        "no_model_call"
    )
    is True,
])


if not authorization_closed:

    finding(
        "HIGH",
        "PLAN_AUTHORIZATION_BOUNDARY_OPENED",
        "Plan unexpectedly authorizes candidate execution or production mutation.",
    )


semantic_model_safety_fence_pass = (
    global_safety.get(
        "semantic_priority_decision_cache_hit_audit_still_required_before_any_real_semantic_model_call"
    )
    is True
)


if not semantic_model_safety_fence_pass:

    finding(
        "HIGH",
        "SEMANTIC_PRIORITY_CACHE_AUDIT_FENCE_LOST",
        "Global pre-model semantic priority_decision_id safety fence was lost.",
    )


# ============================================================
# 13. FINDING SUMMARY
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
    handler_anchor_pass,
    allowed_handler_set_pass,
    dynamic_matrix_baseline_pass,
    authorization_closed,
    semantic_model_safety_fence_pass,
])


plan_accepted_without_revision = (
    review_complete
    and len(high) == 0
    and len(medium) == 0
)


if plan_accepted_without_revision:

    classification = (
        "A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_SURVIVED_ADVERSARIAL_REVIEW"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A4_CANDIDATE_MATERIALIZATION"
    )

else:

    classification = (
        "A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_ADVERSARIAL_REVIEW_COMPLETE_WITH_FINDINGS"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A3-R1_CANDIDATE_IMPLEMENTATION_PLAN_REMEDIATION"
    )


result = {
    "contract_version":
        "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_ADVERSARIAL_REVIEW_V1",

    "source_plan_sha256":
        sha(plan_path),

    "source_evidence_sha256":
        sha(evidence_path),

    "source_a3_report_sha256":
        sha(a3_report_path),

    "source_h1_report_sha256":
        sha(h1_report_path),

    "worker_sha256":
        sha(worker_path),

    "temporal_sha256":
        sha(temporal_path),

    "lineage_authorized":
        lineage_authorized,

    "handler_anchor_pass":
        handler_anchor_pass,

    "allowed_handler_set_pass":
        allowed_handler_set_pass,

    "pre_boundary_mutation_candidates":
        pre_boundary_mutation_candidates,

    "mutation_boundary_reattack_pass":
        mutation_boundary_reattack_pass,

    "optional_import_policy":
        optional_import_policy,

    "only_three_handler_assertion":
        only_three_handler_assertion,

    "import_scope_ambiguous":
        import_scope_ambiguous,

    "worker_serialization_method_inventory":
        serialization_methods_sorted,

    "serialization_freeze_pass":
        serialization_freeze_pass,

    "utc_function_candidates":
        utc_function_candidates,

    "utc_expression_candidates":
        utc_expression_candidates,

    "clock_freeze_pass":
        clock_freeze_pass,

    "snapshot_resolution_candidates":
        snapshot_resolution_candidates,

    "snapshot_variable_binding_pass":
        snapshot_variable_binding_pass,

    "clock_authority_dynamic_test_present":
        clock_authority_dynamic_test_present,

    "dynamic_matrix_baseline_pass":
        dynamic_matrix_baseline_pass,

    "temporal_failure_dynamic_test_count":
        invalid_temporal_test_count,

    "temporal_failure_coverage_pass":
        temporal_failure_coverage_pass,

    "authorization_closed":
        authorization_closed,

    "semantic_model_safety_fence_pass":
        semantic_model_safety_fence_pass,

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

    "plan_accepted_without_revision":
        plan_accepted_without_revision,

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
    "HANDLER_ANCHOR_PASS="
    + str(
        handler_anchor_pass
    )
)

print(
    "ALLOWED_HANDLER_SET_PASS="
    + str(
        allowed_handler_set_pass
    )
)

print(
    "MUTATION_BOUNDARY_REATTACK_PASS="
    + str(
        mutation_boundary_reattack_pass
    )
)


for consumer, items in sorted(
    pre_boundary_mutation_candidates.items()
):

    print(
        "PRE_BOUNDARY_MUTATION_CANDIDATE_COUNT_"
        + consumer
        + "="
        + str(
            len(items)
        )
    )


    for item in items:

        print(
            "PRE_BOUNDARY_MUTATION_CANDIDATE="
            + consumer
            + "|LINE="
            + str(
                item["line"]
            )
            + "|TYPE="
            + item["type"]
            + "|ROOT="
            + str(
                item["root"]
            )
            + "|OP="
            + str(
                item["operation"]
            )
        )


print(
    "IMPORT_SCOPE_AMBIGUOUS="
    + str(
        import_scope_ambiguous
    )
)

print(
    "WORKER_SERIALIZATION_METHOD_INVENTORY="
    + "|".join(
        serialization_methods_sorted
    )
)

print(
    "SERIALIZATION_FREEZE_PASS="
    + str(
        serialization_freeze_pass
    )
)

print(
    "UTC_FUNCTION_CANDIDATES="
    + "|".join(
        utc_function_candidates
    )
)

print(
    "UTC_EXPRESSION_CANDIDATE_COUNT="
    + str(
        len(
            utc_expression_candidates
        )
    )
)

print(
    "CLOCK_FREEZE_PASS="
    + str(
        clock_freeze_pass
    )
)


for role in (
    "evidence",
    "signals",
):

    items = snapshot_resolution_candidates[
        role
    ]

    print(
        "SNAPSHOT_"
        + role.upper()
        + "_RESOLUTION_CANDIDATE_COUNT="
        + str(
            len(items)
        )
    )


    for item in items:

        print(
            "SNAPSHOT_RESOLUTION_CANDIDATE="
            + role.upper()
            + "|"
            + item[
                "variable"
            ]
            + "|LINE="
            + str(
                item[
                    "line"
                ]
            )
        )


print(
    "SNAPSHOT_VARIABLE_BINDING_PASS="
    + str(
        snapshot_variable_binding_pass
    )
)

print(
    "CLOCK_AUTHORITY_DYNAMIC_TEST_PRESENT="
    + str(
        clock_authority_dynamic_test_present
    )
)

print(
    "DYNAMIC_MATRIX_BASELINE_PASS="
    + str(
        dynamic_matrix_baseline_pass
    )
)

print(
    "TEMPORAL_FAILURE_DYNAMIC_TEST_COUNT="
    + str(
        invalid_temporal_test_count
    )
)

print(
    "TEMPORAL_FAILURE_COVERAGE_PASS="
    + str(
        temporal_failure_coverage_pass
    )
)

print(
    "AUTHORIZATION_CLOSED="
    + str(
        authorization_closed
    )
)

print(
    "SEMANTIC_MODEL_SAFETY_FENCE_PASS="
    + str(
        semantic_model_safety_fence_pass
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
        + item[
            "severity"
        ]
        + "|"
        + item[
            "code"
        ]
        + "|"
        + item[
            "scope"
        ]
    )


print(
    "REVIEW_COMPLETE="
    + str(
        review_complete
    )
)

print(
    "PLAN_ACCEPTED_WITHOUT_REVISION="
    + str(
        plan_accepted_without_revision
    )
)

print(
    "IMPLEMENTATION_AUTHORIZED=False"
)

print(
    "CANDIDATE_GENERATION_AUTHORIZED=False"
)

print(
    "CANDIDATE_EXECUTION_AUTHORIZED=False"
)

print(
    "CLASSIFICATION="
    + classification
)

print(
    "NEXT_GATE="
    + next_gate
)