from __future__ import annotations

import ast
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


plan_path = Path(sys.argv[1])
a3_report_path = Path(sys.argv[2])
h1_closeout_path = Path(sys.argv[3])
review_data_path = Path(sys.argv[4])
review_report_path = Path(sys.argv[5])
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

        current = current.value

    if isinstance(current, ast.Name):
        return current.id

    return None


def source_of(
    source: str,
    node: ast.AST,
) -> str:

    text = ast.get_source_segment(
        source,
        node,
    )

    if text:
        return text.strip()

    try:
        return ast.unparse(node)
    except Exception:
        return ""


def annotation_text(
    node: ast.AST | None,
) -> str:

    if node is None:
        return ""

    try:
        return ast.unparse(node)
    except Exception:
        return ""


plan = load(plan_path)
a3_report = load(a3_report_path)
h1_closeout = load(h1_closeout_path)
review = load(review_data_path)
review_report = load(review_report_path)


# ============================================================
# 1. AUTHORIZE EXACT PRIOR STATE
# ============================================================

expected_findings = {
    (
        "MEDIUM",
        "IMPORT_CHANGE_POLICY_CONTRADICTS_HANDLER_ONLY_DIFF_ASSERTION",
        "GLOBAL",
    ),
    (
        "MEDIUM",
        "REQUEST_SERIALIZATION_PRIMITIVE_NOT_FROZEN",
        "EVIDENCE",
    ),
    (
        "MEDIUM",
        "REQUEST_SERIALIZATION_PRIMITIVE_NOT_FROZEN",
        "PREFERENCE_SIGNAL",
    ),
    (
        "MEDIUM",
        "SERVER_UTC_CLOCK_PRIMITIVE_NOT_FROZEN",
        "EVIDENCE",
    ),
    (
        "MEDIUM",
        "SERVER_UTC_CLOCK_PRIMITIVE_NOT_FROZEN",
        "PREFERENCE_SIGNAL",
    ),
    (
        "MEDIUM",
        "SNAPSHOT_RESOLVED_RECORD_VARIABLES_NOT_FROZEN",
        "SNAPSHOT",
    ),
    (
        "MEDIUM",
        "INGEST_CLOCK_AUTHORITY_DYNAMIC_TEST_MISSING",
        "GLOBAL",
    ),
}


actual_findings = {
    (
        item.get("severity"),
        item.get("code"),
        item.get("scope"),
    )
    for item in review.get(
        "findings",
        [],
    )
}


prior_state_authorized = all([
    plan.get(
        "contract_version"
    )
    == "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_V1",

    a3_report.get(
        "a5_i01_a3_pass"
    )
    is True,

    h1_closeout.get(
        "h1_pass"
    )
    is True,

    h1_closeout.get(
        "project_regression"
    )
    is False,

    review.get(
        "review_complete"
    )
    is True,

    review.get(
        "finding_count"
    )
    == 7,

    review.get(
        "high_finding_count"
    )
    == 0,

    review.get(
        "medium_finding_count"
    )
    == 7,

    review.get(
        "low_finding_count"
    )
    == 0,

    actual_findings
    == expected_findings,

    review.get(
        "plan_accepted_without_revision"
    )
    is False,

    review_report.get(
        "a5_i01_a3_a1_pass"
    )
    is True,

    review_report.get(
        "classification"
    )
    == "A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_ADVERSARIAL_REVIEW_COMPLETE_WITH_FINDINGS",
])


if not prior_state_authorized:

    raise RuntimeError(
        "A3_A1_H1_PRIOR_STATE_NOT_AUTHORIZED"
    )


# ============================================================
# 2. PARSE WORKER / TEMPORAL
# ============================================================

worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

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


worker_functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


temporal_functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


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
# 3. TARGET HANDLERS
# ============================================================

handler_evidence = plan.get(
    "handler_evidence",
    {}
)


target_handlers = {}


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
    "SNAPSHOT",
):

    item = handler_evidence[
        consumer
    ]

    fn = worker_functions.get(
        item["handler"]
    )

    if fn is None:

        raise RuntimeError(
            "TARGET_HANDLER_MISSING:"
            + consumer
        )


    target_handlers[
        consumer
    ] = fn


# ============================================================
# 4. SERIALIZATION PRIMITIVE AUDIT
# ============================================================

serialization_methods = {
    "model_dump",
    "dict",
    "json",
    "model_dump_json",
}


serialization_candidates = {
    "EVIDENCE": [],
    "PREFERENCE_SIGNAL": [],
}


global_serialization_counter = Counter()


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

        if method in serialization_methods:

            global_serialization_counter[
                method
            ] += 1


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    fn = target_handlers[
        consumer
    ]

    request_parameter = (
        handler_evidence[
            consumer
        ][
            "request_parameter"
        ]
    )


    for node in ast.walk(fn):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue


        # req.model_dump(...), req.dict(...), req.json(...)
        if isinstance(
            node.func,
            ast.Attribute,
        ):

            method = node.func.attr

            root = root_name(
                node.func.value
            )


            if (
                root == request_parameter
                and method in serialization_methods
            ):

                serialization_candidates[
                    consumer
                ].append({
                    "line":
                        getattr(
                            node,
                            "lineno",
                            None,
                        ),

                    "kind":
                        "REQUEST_METHOD",

                    "method":
                        method,

                    "expression":
                        source_of(
                            worker_source,
                            node,
                        ),
                })


        # dict(req)
        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id == "dict"
            and len(
                node.args
            ) >= 1
            and isinstance(
                node.args[0],
                ast.Name,
            )
            and node.args[0].id
            == request_parameter
        ):

            serialization_candidates[
                consumer
            ].append({
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),

                "kind":
                    "CONVERTER_CALL",

                "method":
                    "dict",

                "expression":
                    source_of(
                        worker_source,
                        node,
                    ),
            })


# Remove duplicates.
for consumer in serialization_candidates:

    unique = []
    seen = set()

    for item in serialization_candidates[
        consumer
    ]:

        key = (
            item["line"],
            item["expression"],
        )

        if key not in seen:

            seen.add(
                key
            )

            unique.append(
                item
            )

    serialization_candidates[
        consumer
    ] = unique


serialization_exact_in_target_handlers = {
    consumer:
        (
            len(
                serialization_candidates[
                    consumer
                ]
            )
            == 1
        )
    for consumer in (
        "EVIDENCE",
        "PREFERENCE_SIGNAL",
    )
}


# ============================================================
# 5. IMPORT INVENTORY
# ============================================================

import_inventory = []


datetime_name_available = False
timezone_name_available = False
utc_name_available = False
datetime_module_available = False


for node in worker_tree.body:

    if isinstance(
        node,
        ast.ImportFrom,
    ):

        module = (
            node.module
            or ""
        )

        names = [
            alias.asname
            or alias.name
            for alias in node.names
        ]


        if module == "datetime":

            original_names = {
                alias.name:
                    (
                        alias.asname
                        or alias.name
                    )
                for alias in node.names
            }


            if (
                "datetime"
                in original_names
                and original_names[
                    "datetime"
                ]
                == "datetime"
            ):
                datetime_name_available = True


            if (
                "timezone"
                in original_names
                and original_names[
                    "timezone"
                ]
                == "timezone"
            ):
                timezone_name_available = True


            if (
                "UTC"
                in original_names
                and original_names[
                    "UTC"
                ]
                == "UTC"
            ):
                utc_name_available = True


        import_inventory.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "source":
                source_of(
                    worker_source,
                    node,
                ),
        })


    elif isinstance(
        node,
        ast.Import,
    ):

        for alias in node.names:

            if (
                alias.name == "datetime"
                and (
                    alias.asname is None
                    or alias.asname
                    == "datetime"
                )
            ):

                datetime_module_available = True


        import_inventory.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "source":
                source_of(
                    worker_source,
                    node,
                ),
        })


direct_aware_utc_expression_possible_without_import = (
    (
        datetime_name_available
        and (
            timezone_name_available
            or utc_name_available
        )
    )
    or datetime_module_available
)


# ============================================================
# 6. UTC CLOCK PRIMITIVE INVENTORY
# ============================================================

aware_utc_calls = []


for node in ast.walk(
    worker_tree
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    text = source_of(
        worker_source,
        node,
    )

    compact = (
        text
        .replace(" ", "")
        .replace("\n", "")
        .lower()
    )


    recognized = False


    if (
        "datetime.now(timezone.utc)"
        in compact
    ):
        recognized = True


    if (
        "datetime.now(utc)"
        in compact
    ):
        recognized = True


    if (
        "datetime.datetime.now(datetime.timezone.utc)"
        in compact
    ):
        recognized = True


    if (
        "datetime.now(tz=timezone.utc)"
        in compact
    ):
        recognized = True


    if recognized:

        aware_utc_calls.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "expression":
                text,
        })


# De-duplicate.
aware_unique = []

seen_clock = set()


for item in aware_utc_calls:

    key = (
        item["line"],
        item["expression"],
    )

    if key not in seen_clock:

        seen_clock.add(
            key
        )

        aware_unique.append(
            item
        )


aware_utc_calls = aware_unique


clock_expression_counter = Counter(
    item[
        "expression"
    ]
    for item in aware_utc_calls
)


dominant_clock_expression = None
dominant_clock_count = 0


if clock_expression_counter:

    ranked = (
        clock_expression_counter
        .most_common()
    )

    dominant_clock_expression = (
        ranked[0][0]
    )

    dominant_clock_count = (
        ranked[0][1]
    )


clock_expression_unique_winner = False


if clock_expression_counter:

    counts = sorted(
        clock_expression_counter.values(),
        reverse=True,
    )

    if len(counts) == 1:

        clock_expression_unique_winner = True

    elif counts[0] > counts[1]:

        clock_expression_unique_winner = True


# ============================================================
# 7. UTC HELPER INVENTORY
# ============================================================

utc_helpers = []


for name, fn in worker_functions.items():

    local_clock_calls = []


    for node in ast.walk(fn):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue


        text = source_of(
            worker_source,
            node,
        )

        compact = (
            text
            .replace(" ", "")
            .replace("\n", "")
            .lower()
        )


        if (
            "datetime.now(timezone.utc)"
            in compact
            or "datetime.now(utc)"
            in compact
            or "datetime.datetime.now(datetime.timezone.utc)"
            in compact
            or "datetime.now(tz=timezone.utc)"
            in compact
        ):

            local_clock_calls.append(
                text
            )


    if local_clock_calls:

        utc_helpers.append({
            "name":
                name,

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

            "clock_expressions":
                sorted(
                    set(
                        local_clock_calls
                    )
                ),
        })


# ============================================================
# 8. TARGET HANDLER EXISTING CLOCK CALLS
# ============================================================

target_clock_candidates = {
    "EVIDENCE": [],
    "PREFERENCE_SIGNAL": [],
}


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    fn = target_handlers[
        consumer
    ]


    for node in ast.walk(fn):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue


        text = source_of(
            worker_source,
            node,
        )

        compact = (
            text
            .replace(" ", "")
            .replace("\n", "")
            .lower()
        )


        if (
            "datetime.now(timezone.utc)"
            in compact
            or "datetime.now(utc)"
            in compact
            or "datetime.datetime.now(datetime.timezone.utc)"
            in compact
            or "datetime.now(tz=timezone.utc)"
            in compact
        ):

            target_clock_candidates[
                consumer
            ].append({
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),

                "expression":
                    text,
            })


# ============================================================
# 9. TEMPORAL as_of SIGNATURE / USAGE
# ============================================================

temporal_as_of = {}


for validator_name in (
    "validate_evidence_temporal",
    "validate_signal_temporal",
):

    fn = temporal_functions.get(
        validator_name
    )


    if fn is None:

        raise RuntimeError(
            "TEMPORAL_VALIDATOR_MISSING:"
            + validator_name
        )


    positional = (
        list(
            fn.args.posonlyargs
        )
        + list(
            fn.args.args
        )
    )


    as_of_arg = None


    for arg in positional:

        if arg.arg == "as_of":

            as_of_arg = arg
            break


    as_of_annotation = (
        annotation_text(
            as_of_arg.annotation
        )
        if as_of_arg
        else ""
    )


    parser_calls = []


    for node in ast.walk(fn):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue


        name = call_name(
            node
        )


        if name == "_parse_timestamp":

            parser_calls.append(
                source_of(
                    temporal_source,
                    node,
                )
            )


    temporal_as_of[
        validator_name
    ] = {
        "annotation":
            as_of_annotation,

        "parse_timestamp_calls":
            parser_calls,
    }


# ============================================================
# 10. SNAPSHOT EXACT LOCAL VARIABLE AUDIT
# ============================================================

snapshot_fn = target_handlers[
    "SNAPSHOT"
]

snapshot_boundary = (
    handler_evidence[
        "SNAPSHOT"
    ][
        "first_mutation_line"
    ]
)


snapshot_assignments = {
    "evidence": [],
    "signals": [],
}


for statement in snapshot_fn.body:

    line = getattr(
        statement,
        "lineno",
        None,
    )


    if (
        line is None
        or line >= snapshot_boundary
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


    for target in targets:

        if target in {
            "evidence",
            "signals",
        }:

            snapshot_assignments[
                target
            ].append({
                "line":
                    line,

                "source":
                    source_of(
                        worker_source,
                        statement,
                    ),
            })


snapshot_evidence_exact = (
    len(
        snapshot_assignments[
            "evidence"
        ]
    )
    == 1
)

snapshot_signals_exact = (
    len(
        snapshot_assignments[
            "signals"
        ]
    )
    == 1
)

snapshot_variable_resolution_exact = (
    snapshot_evidence_exact
    and snapshot_signals_exact
)


# ============================================================
# 11. IMPORT-SCOPE RESOLUTION
# ============================================================

existing_clock_primitive_available = (
    len(
        aware_utc_calls
    )
    > 0
)


handler_only_diff_possible_without_import = (
    direct_aware_utc_expression_possible_without_import
    or len(
        utc_helpers
    )
    > 0
)


recommended_import_policy = (
    "FORBID_NEW_IMPORTS_KEEP_THREE_HANDLER_BODY_DIFF"
    if handler_only_diff_possible_without_import
    else
    "EXPLICIT_CLOCK_IMPORT_DECISION_REQUIRED"
)


# ============================================================
# 12. SERIALIZATION REMEDIATION READINESS
# ============================================================

target_serialization_all_exact = all(
    serialization_exact_in_target_handlers.values()
)


global_serialization_inventory = {
    name:
        global_serialization_counter[name]
    for name in sorted(
        global_serialization_counter
    )
}


# ============================================================
# 13. CLOCK REMEDIATION READINESS
# ============================================================

clock_primitive_source_resolved = (
    (
        dominant_clock_expression
        is not None
        and clock_expression_unique_winner
    )
    or len(
        utc_helpers
    )
    == 1
)


# ============================================================
# 14. REQUIRED DYNAMIC TEST REMEDIATION
# ============================================================

required_dynamic_test = {
    "test_id":
        "A5-I01-D09",

    "consumer":
        "EVIDENCE|PREFERENCE_SIGNAL",

    "scenario":
        "INGEST_SERVER_UTC_CLOCK_AUTHORITY_SINGLE_CAPTURE",

    "expected":
        (
            "VALIDATOR_AS_OF_COMES_FROM_SERVER_UTC_"
            "NOT_REQUEST_TIMESTAMPS_AND_IS_CAPTURED_ONCE_PER_HANDLER"
        ),
}


# ============================================================
# 15. DIAGNOSTIC VERDICT
# ============================================================

audit_complete = all([
    prior_state_authorized,

    snapshot_variable_resolution_exact,

    len(
        aware_utc_calls
    )
    > 0,

    len(
        temporal_as_of
    )
    == 2,
])


remediation_primitive_resolution = {
    "serialization_exact_in_target_handlers":
        target_serialization_all_exact,

    "snapshot_variables_exact":
        snapshot_variable_resolution_exact,

    "clock_existing_primitive_found":
        existing_clock_primitive_available,

    "clock_primitive_source_resolved":
        clock_primitive_source_resolved,

    "handler_only_diff_possible_without_import":
        handler_only_diff_possible_without_import,
}


all_implementation_primitives_resolved = all([
    target_serialization_all_exact,
    snapshot_variable_resolution_exact,
    existing_clock_primitive_available,
    clock_primitive_source_resolved,
    handler_only_diff_possible_without_import,
])


if (
    audit_complete
    and all_implementation_primitives_resolved
):

    classification = (
        "A5_I01_IMPLEMENTATION_PRIMITIVES_RESOLVED_FOR_PLAN_REMEDIATION"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A3-R1_CANDIDATE_IMPLEMENTATION_PLAN_REMEDIATION"
    )

elif audit_complete:

    classification = (
        "A5_I01_IMPLEMENTATION_PRIMITIVE_AUDIT_COMPLETE_WITH_UNRESOLVED_SELECTIONS"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A3-A1-H2_IMPLEMENTATION_PRIMITIVE_SELECTION_FREEZE"
    )

else:

    classification = (
        "A5_I01_IMPLEMENTATION_PRIMITIVE_AUDIT_INCOMPLETE"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A3-A1-H1_REMEDIATION_REQUIRED"
    )


result = {
    "contract_version":
        "SM3_A5_I01_IMPLEMENTATION_PRIMITIVE_AUDIT_V1",

    "source_plan_sha256":
        sha(
            plan_path
        ),

    "source_a3_report_sha256":
        sha(
            a3_report_path
        ),

    "source_h1_closeout_sha256":
        sha(
            h1_closeout_path
        ),

    "source_adversarial_review_data_sha256":
        sha(
            review_data_path
        ),

    "source_adversarial_review_report_sha256":
        sha(
            review_report_path
        ),

    "worker_sha256":
        sha(
            worker_path
        ),

    "temporal_sha256":
        sha(
            temporal_path
        ),

    "prior_state_authorized":
        prior_state_authorized,

    "serialization_candidates":
        serialization_candidates,

    "serialization_exact_in_target_handlers":
        serialization_exact_in_target_handlers,

    "global_serialization_inventory":
        global_serialization_inventory,

    "datetime_import_state": {
        "datetime_name_available":
            datetime_name_available,

        "timezone_name_available":
            timezone_name_available,

        "utc_name_available":
            utc_name_available,

        "datetime_module_available":
            datetime_module_available,

        "direct_aware_utc_expression_possible_without_import":
            direct_aware_utc_expression_possible_without_import,
    },

    "aware_utc_expression_count":
        len(
            aware_utc_calls
        ),

    "aware_utc_expressions":
        aware_utc_calls,

    "clock_expression_frequency":
        dict(
            clock_expression_counter
        ),

    "dominant_clock_expression":
        dominant_clock_expression,

    "dominant_clock_expression_count":
        dominant_clock_count,

    "clock_expression_unique_winner":
        clock_expression_unique_winner,

    "utc_helpers":
        utc_helpers,

    "target_clock_candidates":
        target_clock_candidates,

    "temporal_as_of":
        temporal_as_of,

    "snapshot_assignments":
        snapshot_assignments,

    "snapshot_evidence_exact":
        snapshot_evidence_exact,

    "snapshot_signals_exact":
        snapshot_signals_exact,

    "snapshot_variable_resolution_exact":
        snapshot_variable_resolution_exact,

    "existing_clock_primitive_available":
        existing_clock_primitive_available,

    "handler_only_diff_possible_without_import":
        handler_only_diff_possible_without_import,

    "recommended_import_policy":
        recommended_import_policy,

    "target_serialization_all_exact":
        target_serialization_all_exact,

    "clock_primitive_source_resolved":
        clock_primitive_source_resolved,

    "required_dynamic_test":
        required_dynamic_test,

    "remediation_primitive_resolution":
        remediation_primitive_resolution,

    "all_implementation_primitives_resolved":
        all_implementation_primitives_resolved,

    "audit_complete":
        audit_complete,

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
    "PRIOR_STATE_AUTHORIZED="
    + str(
        prior_state_authorized
    )
)


print("")
print("=== SERIALIZATION AUDIT ===")


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    items = serialization_candidates[
        consumer
    ]

    print(
        "SERIALIZATION_CANDIDATE_COUNT_"
        + consumer
        + "="
        + str(
            len(items)
        )
    )


    for item in items:

        print(
            "SERIALIZATION_CANDIDATE="
            + consumer
            + "|LINE="
            + str(
                item["line"]
            )
            + "|METHOD="
            + item["method"]
            + "|EXPR="
            + item["expression"]
        )


    print(
        "SERIALIZATION_EXACT_"
        + consumer
        + "="
        + str(
            serialization_exact_in_target_handlers[
                consumer
            ]
        )
    )


print(
    "GLOBAL_SERIALIZATION_INVENTORY="
    + "|".join(
        name
        + ":"
        + str(
            global_serialization_inventory[
                name
            ]
        )
        for name
        in sorted(
            global_serialization_inventory
        )
    )
)


print("")
print("=== CLOCK IMPORT AUDIT ===")

print(
    "DATETIME_NAME_AVAILABLE="
    + str(
        datetime_name_available
    )
)

print(
    "TIMEZONE_NAME_AVAILABLE="
    + str(
        timezone_name_available
    )
)

print(
    "UTC_NAME_AVAILABLE="
    + str(
        utc_name_available
    )
)

print(
    "DATETIME_MODULE_AVAILABLE="
    + str(
        datetime_module_available
    )
)

print(
    "DIRECT_AWARE_UTC_EXPRESSION_POSSIBLE_WITHOUT_IMPORT="
    + str(
        direct_aware_utc_expression_possible_without_import
    )
)


print("")
print("=== CLOCK PRIMITIVE AUDIT ===")

print(
    "AWARE_UTC_EXPRESSION_COUNT="
    + str(
        len(
            aware_utc_calls
        )
    )
)

print(
    "CLOCK_EXPRESSION_UNIQUE_FORM_COUNT="
    + str(
        len(
            clock_expression_counter
        )
    )
)

print(
    "DOMINANT_CLOCK_EXPRESSION="
    + str(
        dominant_clock_expression
    )
)

print(
    "DOMINANT_CLOCK_EXPRESSION_COUNT="
    + str(
        dominant_clock_count
    )
)

print(
    "CLOCK_EXPRESSION_UNIQUE_WINNER="
    + str(
        clock_expression_unique_winner
    )
)


for expression, count in (
    clock_expression_counter
    .most_common()
):

    print(
        "CLOCK_EXPRESSION_FORM="
        + str(
            count
        )
        + "|"
        + expression
    )


print(
    "UTC_HELPER_COUNT="
    + str(
        len(
            utc_helpers
        )
    )
)


for helper in utc_helpers:

    print(
        "UTC_HELPER="
        + helper[
            "name"
        ]
        + "|LINES="
        + str(
            helper[
                "line_start"
            ]
        )
        + "-"
        + str(
            helper[
                "line_end"
            ]
        )
        + "|CLOCK="
        + "|".join(
            helper[
                "clock_expressions"
            ]
        )
    )


for consumer in (
    "EVIDENCE",
    "PREFERENCE_SIGNAL",
):

    print(
        "TARGET_CLOCK_CANDIDATE_COUNT_"
        + consumer
        + "="
        + str(
            len(
                target_clock_candidates[
                    consumer
                ]
            )
        )
    )


    for item in target_clock_candidates[
        consumer
    ]:

        print(
            "TARGET_CLOCK_CANDIDATE="
            + consumer
            + "|LINE="
            + str(
                item[
                    "line"
                ]
            )
            + "|EXPR="
            + item[
                "expression"
            ]
        )


print("")
print("=== TEMPORAL AS_OF AUDIT ===")


for validator_name in (
    "validate_evidence_temporal",
    "validate_signal_temporal",
):

    item = temporal_as_of[
        validator_name
    ]

    print(
        "TEMPORAL_AS_OF_VALIDATOR="
        + validator_name
    )

    print(
        "TEMPORAL_AS_OF_ANNOTATION="
        + item[
            "annotation"
        ]
    )

    print(
        "TEMPORAL_AS_OF_PARSE_CALLS="
        + "|".join(
            item[
                "parse_timestamp_calls"
            ]
        )
    )


print("")
print("=== SNAPSHOT VARIABLE AUDIT ===")


for role in (
    "evidence",
    "signals",
):

    items = snapshot_assignments[
        role
    ]

    print(
        "SNAPSHOT_"
        + role.upper()
        + "_ASSIGNMENT_COUNT="
        + str(
            len(items)
        )
    )


    for item in items:

        print(
            "SNAPSHOT_"
            + role.upper()
            + "_ASSIGNMENT="
            + role
            + "|LINE="
            + str(
                item[
                    "line"
                ]
            )
            + "|SOURCE="
            + item[
                "source"
            ]
        )


print(
    "SNAPSHOT_VARIABLE_RESOLUTION_EXACT="
    + str(
        snapshot_variable_resolution_exact
    )
)


print("")
print("=== IMPORT-SCOPE VERDICT ===")

print(
    "EXISTING_CLOCK_PRIMITIVE_AVAILABLE="
    + str(
        existing_clock_primitive_available
    )
)

print(
    "HANDLER_ONLY_DIFF_POSSIBLE_WITHOUT_IMPORT="
    + str(
        handler_only_diff_possible_without_import
    )
)

print(
    "RECOMMENDED_IMPORT_POLICY="
    + recommended_import_policy
)


print("")
print("=== REMEDIATION READINESS ===")

print(
    "TARGET_SERIALIZATION_ALL_EXACT="
    + str(
        target_serialization_all_exact
    )
)

print(
    "CLOCK_PRIMITIVE_SOURCE_RESOLVED="
    + str(
        clock_primitive_source_resolved
    )
)

print(
    "SNAPSHOT_VARIABLES_EXACT="
    + str(
        snapshot_variable_resolution_exact
    )
)

print(
    "ALL_IMPLEMENTATION_PRIMITIVES_RESOLVED="
    + str(
        all_implementation_primitives_resolved
    )
)

print(
    "REQUIRED_DYNAMIC_TEST_ID="
    + required_dynamic_test[
        "test_id"
    ]
)

print(
    "REQUIRED_DYNAMIC_TEST_SCENARIO="
    + required_dynamic_test[
        "scenario"
    ]
)

print(
    "AUDIT_COMPLETE="
    + str(
        audit_complete
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


if not audit_complete:
    raise SystemExit(1)