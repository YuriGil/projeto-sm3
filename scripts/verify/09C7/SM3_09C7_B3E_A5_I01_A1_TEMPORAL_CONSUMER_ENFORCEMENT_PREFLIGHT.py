from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


sequence_freeze_path = Path(sys.argv[1])
sequence_reattack_data_path = Path(sys.argv[2])
sequence_reattack_report_path = Path(sys.argv[3])
matrix_path = Path(sys.argv[4])
worker_path = Path(sys.argv[5])
temporal_path = Path(sys.argv[6])
output_path = Path(sys.argv[7])


def load_json(path: Path) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def sha(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
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


def callable_name(
    node: ast.Call,
) -> str | None:

    fn = node.func

    if isinstance(fn, ast.Name):
        return fn.id

    if isinstance(fn, ast.Attribute):
        return fn.attr

    return None


def call_names(
    node: ast.AST,
) -> set[str]:

    result: set[str] = set()

    for child in ast.walk(node):

        if not isinstance(
            child,
            ast.Call,
        ):
            continue

        name = callable_name(
            child
        )

        if name:
            result.add(name)

    return result


def root_name(
    node: ast.AST,
) -> str | None:

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

        elif isinstance(
            current,
            ast.Subscript,
        ):
            current = current.value

    if isinstance(
        current,
        ast.Name,
    ):
        return current.id

    return None


def mutation_candidate(
    statement: ast.stmt,
) -> tuple[bool, list[str]]:

    reasons: list[str] = []

    mutation_tokens = (
        "save",
        "store",
        "persist",
        "append",
        "insert",
        "update",
        "upsert",
        "write",
        "commit",
        "delete",
        "remove",
        "setdefault",
    )


    for node in ast.walk(
        statement
    ):

        if isinstance(
            node,
            ast.Call,
        ):

            name = callable_name(
                node
            )

            if name:

                lowered = name.lower()

                if any(
                    token in lowered
                    for token in mutation_tokens
                ):

                    reasons.append(
                        "CALL:"
                        + name
                    )


        if isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
            ),
        ):

            targets: list[ast.AST] = []

            if isinstance(
                node,
                ast.Assign,
            ):
                targets.extend(
                    node.targets
                )

            elif isinstance(
                node,
                ast.AnnAssign,
            ):
                targets.append(
                    node.target
                )

            else:
                targets.append(
                    node.target
                )


            for target in targets:

                root = root_name(
                    target
                )

                if root is None:
                    continue

                upper = root.upper()

                if (
                    upper == root
                    or "STORE" in upper
                    or "STATE" in upper
                    or "REGISTRY" in upper
                    or "RECORD" in upper
                ):

                    reasons.append(
                        "ASSIGN:"
                        + root
                    )


    return (
        len(reasons) > 0,
        sorted(
            set(reasons)
        ),
    )


sequence_freeze = load_json(
    sequence_freeze_path
)

sequence_reattack_data = load_json(
    sequence_reattack_data_path
)

sequence_reattack_report = load_json(
    sequence_reattack_report_path
)

matrix = load_json(
    matrix_path
)


# ============================================================
# 1. AUTHORIZE ROADMAP LINEAGE
# ============================================================

freeze_checks = [
    sequence_freeze.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_FREEZE_V2",

    sequence_freeze.get(
        "revision"
    )
    == 2,

    sequence_freeze.get(
        "artifact_encoding"
    )
    == "UTF-8",

    sequence_freeze.get(
        "implementation_authorized"
    )
    is False,

    sequence_freeze.get(
        "canonical_source_mutation_authorized"
    )
    is False,

    sequence_freeze.get(
        "production_mutation_authorized"
    )
    is False,

    sequence_freeze.get(
        "next_gate"
    )
    == "09C7-B3E-A5-A4-A1-R2_IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK",
]


reattack_data_checks = [
    sequence_reattack_data.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK_V2",

    sequence_reattack_data.get(
        "review_complete"
    )
    is True,

    sequence_reattack_data.get(
        "finding_count"
    )
    == 0,

    sequence_reattack_data.get(
        "high_finding_count"
    )
    == 0,

    sequence_reattack_data.get(
        "medium_finding_count"
    )
    == 0,

    sequence_reattack_data.get(
        "sequence_accepted_without_revision"
    )
    is True,

    sequence_reattack_data.get(
        "implementation_authorized"
    )
    is False,
]


reattack_report_checks = [
    sequence_reattack_report.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK_V2",

    sequence_reattack_report.get(
        "status"
    )
    == "IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK_COMPLETE",

    sequence_reattack_report.get(
        "classification"
    )
    == "A5_REPAIRED_IMPLEMENTATION_SEQUENCE_SURVIVED_ADVERSARIAL_REATTACK",

    sequence_reattack_report.get(
        "a5_a4_a1_r2_pass"
    )
    is True,

    sequence_reattack_report.get(
        "next_gate"
    )
    == "09C7-B3E-A5-I01-A1_TEMPORAL_CONSUMER_ENFORCEMENT_PREFLIGHT",
]


matrix_checks = [
    matrix.get(
        "contract_version"
    )
    == "SM3_BLACK_BOX_DYNAMICS_V2_RUNTIME_GAP_MATRIX_V2",

    matrix.get(
        "matrix_complete"
    )
    is True,

    matrix.get(
        "implementation_authorized"
    )
    is False,

    matrix.get(
        "production_mutation_authorized"
    )
    is False,
]


sequence = list(
    sequence_freeze.get(
        "sequence",
        [],
    )
)


i01_matches = [
    item
    for item in sequence
    if item.get(
        "unit_id"
    )
    == "A5-I01"
]


i01_authorized = False


if len(i01_matches) == 1:

    i01 = i01_matches[0]

    i01_authorized = all([
        i01.get(
            "order"
        )
        == 1,

        i01.get(
            "requirement_id"
        )
        == "A5-R04",

        i01.get(
            "classification"
        )
        == "PARTIAL",

        i01.get(
            "name"
        )
        == "TEMPORAL_CONSUMER_ENFORCEMENT",

        list(
            i01.get(
                "prerequisites",
                [],
            )
            or []
        )
        == [],

        i01.get(
            "mutation_scope"
        )
        == "WORKER_CANDIDATE_ONLY",
    ])


lineage_authorized = all(
    freeze_checks
    + reattack_data_checks
    + reattack_report_checks
    + matrix_checks
    + [
        i01_authorized,
    ]
)


if not lineage_authorized:

    raise RuntimeError(
        "I01_PREFLIGHT_LINEAGE_NOT_AUTHORIZED"
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
# 3. TEMPORAL IMPORT INVENTORY
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

            local_name = (
                alias.asname
                or alias.name
            )

            temporal_imports[
                local_name
            ] = alias.name


# ============================================================
# 4. WORKER CALL GRAPH
# ============================================================

call_graph: dict[
    str,
    set[str],
] = {}


for name, fn in functions.items():

    call_graph[name] = {
        called
        for called in call_names(
            fn
        )
        if called in functions
    }


def reachable_functions(
    start: str,
) -> set[str]:

    if start not in functions:
        return set()

    visited: set[str] = set()

    stack = [
        start
    ]


    while stack:

        current = stack.pop()

        if current in visited:
            continue

        visited.add(
            current
        )


        for child in call_graph.get(
            current,
            set(),
        ):

            if child not in visited:
                stack.append(
                    child
                )


    return visited


def transitive_calls(
    start: str,
) -> set[str]:

    result: set[str] = set()


    for fn_name in reachable_functions(
        start
    ):

        fn = functions.get(
            fn_name
        )

        if fn is None:
            continue

        result.update(
            call_names(
                fn
            )
        )


    return result


# ============================================================
# 5. ROUTE INVENTORY
# ============================================================

routes: dict[
    str,
    dict[str, Any],
] = {}


for fn_name, fn in functions.items():

    for decorator in fn.decorator_list:

        if not isinstance(
            decorator,
            ast.Call,
        ):
            continue


        if not isinstance(
            decorator.func,
            ast.Attribute,
        ):
            continue


        method = (
            decorator.func.attr.upper()
        )


        if method not in {
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            continue


        if not decorator.args:
            continue


        path_node = decorator.args[0]


        if not (
            isinstance(
                path_node,
                ast.Constant,
            )
            and isinstance(
                path_node.value,
                str,
            )
        ):
            continue


        routes[
            path_node.value
        ] = {
            "method":
                method,

            "function":
                fn_name,

            "line":
                getattr(
                    fn,
                    "lineno",
                    None,
                ),
        }


# ============================================================
# 6. REQUEST MODEL EXTRACTION
# ============================================================

def class_fields(
    class_node: ast.ClassDef,
) -> list[dict[str, Any]]:

    fields: list[
        dict[str, Any]
    ] = []


    for statement in class_node.body:

        if isinstance(
            statement,
            ast.AnnAssign,
        ):

            if isinstance(
                statement.target,
                ast.Name,
            ):

                fields.append({
                    "name":
                        statement.target.id,

                    "annotation":
                        annotation_text(
                            statement.annotation
                        ),

                    "line":
                        getattr(
                            statement,
                            "lineno",
                            None,
                        ),
                })


    return fields


def handler_request_models(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, Any]]:

    result: list[
        dict[str, Any]
    ] = []


    args = list(
        fn.args.args
    )


    for arg in args:

        annotation = (
            annotation_text(
                arg.annotation
            )
        )


        if not annotation:
            continue


        simple = annotation


        if "[" in simple:
            simple = simple.split(
                "[",
                1,
            )[0]


        if simple in classes:

            class_node = classes[
                simple
            ]

            result.append({
                "parameter":
                    arg.arg,

                "name":
                    simple,

                "line_start":
                    getattr(
                        class_node,
                        "lineno",
                        None,
                    ),

                "line_end":
                    getattr(
                        class_node,
                        "end_lineno",
                        None,
                    ),

                "fields":
                    class_fields(
                        class_node
                    ),
            })


    return result


# ============================================================
# 7. HANDLER STATEMENT MAP
# ============================================================

def statement_map(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, Any]]:

    result: list[
        dict[str, Any]
    ] = []


    for statement in fn.body:

        start = getattr(
            statement,
            "lineno",
            None,
        )

        end = getattr(
            statement,
            "end_lineno",
            start,
        )


        mutation, reasons = (
            mutation_candidate(
                statement
            )
        )


        result.append({
            "line_start":
                start,

            "line_end":
                end,

            "statement_type":
                type(
                    statement
                ).__name__,

            "calls":
                sorted(
                    call_names(
                        statement
                    )
                ),

            "mutation_candidate":
                mutation,

            "mutation_reasons":
                reasons,

            "source":
                source_segment(
                    worker_lines,
                    start,
                    end,
                ),
        })


    return result


# ============================================================
# 8. PARSE TEMPORAL MODULE
# ============================================================

temporal_source = temporal_path.read_text(
    encoding="utf-8-sig"
)

temporal_lines = (
    temporal_source.splitlines()
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(
        temporal_path
    ),
)


temporal_functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


temporal_constants: dict[
    str,
    Any,
] = {}


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


    elif isinstance(
        node,
        ast.Assign,
    ):

        if isinstance(
            node.value,
            ast.Constant,
        ):

            for target in node.targets:

                if isinstance(
                    target,
                    ast.Name,
                ):

                    temporal_constants[
                        target.id
                    ] = node.value.value


temporal_contract_exact = all([
    temporal_constants.get(
        "TEMPORAL_VALIDITY_POLICY_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1",

    temporal_constants.get(
        "TEMPORAL_VALIDITY_ENGINE_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1",

    temporal_constants.get(
        "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
    )
    == "R2",
])


def function_signature(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:

    parts: list[str] = []


    for arg in fn.args.args:

        value = arg.arg

        annotation = annotation_text(
            arg.annotation
        )

        if annotation:
            value += (
                ":"
                + annotation
            )

        parts.append(
            value
        )


    return_annotation = (
        annotation_text(
            fn.returns
        )
    )


    result = (
        fn.name
        + "("
        + ", ".join(
            parts
        )
        + ")"
    )


    if return_annotation:

        result += (
            " -> "
            + return_annotation
        )


    return result


temporal_api = []


for name, fn in sorted(
    temporal_functions.items()
):

    source = source_segment(
        temporal_lines,
        getattr(
            fn,
            "lineno",
            None,
        ),
        getattr(
            fn,
            "end_lineno",
            None,
        ),
    )


    lowered = (
        name
        + "\n"
        + source
    ).lower()


    relevant = any(
        token in lowered
        for token in (
            "temporal",
            "valid",
            "expiry",
            "expire",
            "observed_at",
            "source_date",
            "as_of",
            "future",
            "age",
        )
    )


    if relevant:

        temporal_api.append({
            "name":
                name,

            "signature":
                function_signature(
                    fn
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

            "source":
                source,
        })


# ============================================================
# 9. TARGET CONSUMERS
# ============================================================

targets = [
    {
        "consumer_id":
            "EVIDENCE",

        "route":
            "/production/culture-intelligence/platform-dynamics/evidence",

        "method":
            "POST",

        "expected_handler":
            "production_platform_dynamics_evidence_ingest",

        "keywords":
            [
                "evidence",
                "observation",
                "source",
            ],
    },

    {
        "consumer_id":
            "PREFERENCE_SIGNAL",

        "route":
            "/production/culture-intelligence/platform-preference-signals",

        "method":
            "POST",

        "expected_handler":
            "production_platform_preference_signal_ingest",

        "keywords":
            [
                "signal",
                "preference",
            ],
    },

    {
        "consumer_id":
            "SNAPSHOT",

        "route":
            "/production/culture-intelligence/platform-dynamics/snapshots",

        "method":
            "POST",

        "expected_handler":
            "production_platform_dynamics_snapshot_build",

        "keywords":
            [
                "snapshot",
                "summary",
            ],
    },
]


consumer_results = []

route_map_pass = True

source_map_complete = True


for target in targets:

    route_info = routes.get(
        target["route"]
    )


    route_exact = (
        route_info is not None
        and route_info.get(
            "method"
        )
        == target["method"]
        and route_info.get(
            "function"
        )
        == target[
            "expected_handler"
        ]
    )


    if not route_exact:
        route_map_pass = False


    handler_name = (
        route_info.get(
            "function"
        )
        if route_info
        else None
    )


    handler = (
        functions.get(
            handler_name
        )
        if handler_name
        else None
    )


    if handler is None:

        source_map_complete = False

        consumer_results.append({
            "consumer_id":
                target[
                    "consumer_id"
                ],

            "route":
                target[
                    "route"
                ],

            "route_exact":
                False,

            "handler":
                handler_name,

            "error":
                "HANDLER_NOT_FOUND",
        })

        continue


    direct_calls = call_names(
        handler
    )

    transitive = transitive_calls(
        handler_name
    )


    direct_temporal = []

    transitive_temporal = []


    for local_name, original_name in sorted(
        temporal_imports.items()
    ):

        if local_name in direct_calls:

            direct_temporal.append({
                "local_name":
                    local_name,

                "original_name":
                    original_name,
            })


        if local_name in transitive:

            transitive_temporal.append({
                "local_name":
                    local_name,

                "original_name":
                    original_name,
            })


    statements = statement_map(
        handler
    )


    mutation_lines = [
        item["line_start"]
        for item in statements
        if item[
            "mutation_candidate"
        ]
        and item[
            "line_start"
        ]
        is not None
    ]


    first_mutation_line = (
        min(
            mutation_lines
        )
        if mutation_lines
        else None
    )


    request_models = (
        handler_request_models(
            handler
        )
    )


    # --------------------------------------------------------
    # Candidate temporal APIs are DISCOVERY ONLY.
    # This preflight does not bind a validator.
    # --------------------------------------------------------

    api_candidates = []


    for api in temporal_api:

        haystack = (
            api["name"]
            + "\n"
            + api["source"]
        ).lower()


        score = 0


        if (
            "temporal"
            in haystack
            or "valid"
            in haystack
        ):
            score += 2


        if "validate" in haystack:
            score += 1


        for keyword in target[
            "keywords"
        ]:

            if keyword in haystack:
                score += 3


        if score > 0:

            api_candidates.append({
                "name":
                    api["name"],

                "signature":
                    api[
                        "signature"
                    ],

                "line_start":
                    api[
                        "line_start"
                    ],

                "line_end":
                    api[
                        "line_end"
                    ],

                "score":
                    score,
            })


    api_candidates.sort(
        key=lambda item: (
            -item["score"],
            item["name"],
        )
    )


    handler_line_start = getattr(
        handler,
        "lineno",
        None,
    )

    handler_line_end = getattr(
        handler,
        "end_lineno",
        None,
    )


    if (
        handler_line_start is None
        or handler_line_end is None
    ):

        source_map_complete = False


    consumer_results.append({
        "consumer_id":
            target[
                "consumer_id"
            ],

        "route":
            target[
                "route"
            ],

        "method":
            target[
                "method"
            ],

        "route_exact":
            route_exact,

        "handler":
            handler_name,

        "handler_line_start":
            handler_line_start,

        "handler_line_end":
            handler_line_end,

        "handler_source":
            source_segment(
                worker_lines,
                handler_line_start,
                handler_line_end,
            ),

        "request_models":
            request_models,

        "direct_calls":
            sorted(
                direct_calls
            ),

        "reachable_functions":
            sorted(
                reachable_functions(
                    handler_name
                )
            ),

        "direct_temporal_calls":
            direct_temporal,

        "transitive_temporal_calls":
            transitive_temporal,

        "statement_map":
            statements,

        "mutation_candidate_lines":
            sorted(
                mutation_lines
            ),

        "first_mutation_candidate_line":
            first_mutation_line,

        "temporal_api_candidates":
            api_candidates[:12],

        "binding_frozen":
            False,
    })


# ============================================================
# 10. GLOBAL TEMPORAL IMPORT/API STATE
# ============================================================

all_current_temporal_call_free = all(
    len(
        item.get(
            "direct_temporal_calls",
            [],
        )
    )
    == 0
    and len(
        item.get(
            "transitive_temporal_calls",
            [],
        )
    )
    == 0
    for item in consumer_results
    if "error" not in item
)


preflight_complete = all([
    lineage_authorized,
    route_map_pass,
    source_map_complete,
    temporal_contract_exact,
    len(
        consumer_results
    )
    == 3,
    len(
        temporal_imports
    )
    > 0,
    len(
        temporal_api
    )
    > 0,
])


if preflight_complete:

    classification = (
        "A5_I01_TEMPORAL_CONSUMER_ENFORCEMENT_PREFLIGHT_COMPLETE"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A2_TEMPORAL_BINDING_CONTRACT_FREEZE"
    )

else:

    classification = (
        "A5_I01_TEMPORAL_CONSUMER_ENFORCEMENT_PREFLIGHT_BLOCKED"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A1_REMEDIATION_REQUIRED"
    )


result = {
    "contract_version":
        "SM3_A5_I01_TEMPORAL_CONSUMER_ENFORCEMENT_PREFLIGHT_V1",

    "source_sequence_freeze_sha256":
        sha(
            sequence_freeze_path
        ),

    "source_sequence_reattack_data_sha256":
        sha(
            sequence_reattack_data_path
        ),

    "source_sequence_reattack_report_sha256":
        sha(
            sequence_reattack_report_path
        ),

    "source_matrix_v2_sha256":
        sha(
            matrix_path
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

    "i01_authorized":
        i01_authorized,

    "consumer_count":
        len(
            consumer_results
        ),

    "route_map_pass":
        route_map_pass,

    "source_map_complete":
        source_map_complete,

    "temporal_contract_exact":
        temporal_contract_exact,

    "temporal_policy_version":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_POLICY_VERSION"
        ),

    "temporal_engine_version":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_ENGINE_VERSION"
        ),

    "temporal_revision":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
        ),

    "worker_temporal_import_count":
        len(
            temporal_imports
        ),

    "worker_temporal_imports":
        temporal_imports,

    "temporal_public_function_count":
        len(
            temporal_api
        ),

    "temporal_public_functions":
        temporal_api,

    "all_current_temporal_call_free":
        all_current_temporal_call_free,

    "consumers":
        consumer_results,

    "binding_frozen":
        False,

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

    "preflight_complete":
        preflight_complete,

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
    "I01_AUTHORIZED="
    + str(
        i01_authorized
    )
)

print(
    "CONSUMER_COUNT="
    + str(
        len(
            consumer_results
        )
    )
)

print(
    "ROUTE_MAP_PASS="
    + str(
        route_map_pass
    )
)

print(
    "SOURCE_MAP_COMPLETE="
    + str(
        source_map_complete
    )
)

print(
    "TEMPORAL_CONTRACT_EXACT="
    + str(
        temporal_contract_exact
    )
)

print(
    "WORKER_TEMPORAL_IMPORT_COUNT="
    + str(
        len(
            temporal_imports
        )
    )
)

print(
    "TEMPORAL_PUBLIC_FUNCTION_COUNT="
    + str(
        len(
            temporal_api
        )
    )
)

print(
    "ALL_CURRENT_TEMPORAL_CALL_FREE="
    + str(
        all_current_temporal_call_free
    )
)


for consumer in consumer_results:

    print("")

    print(
        "CONSUMER="
        + str(
            consumer.get(
                "consumer_id"
            )
        )
    )

    print(
        "ROUTE="
        + str(
            consumer.get(
                "route"
            )
        )
    )

    print(
        "HANDLER="
        + str(
            consumer.get(
                "handler"
            )
        )
    )

    print(
        "HANDLER_LINES="
        + str(
            consumer.get(
                "handler_line_start"
            )
        )
        + "-"
        + str(
            consumer.get(
                "handler_line_end"
            )
        )
    )


    model_names = [
        item["name"]
        for item in consumer.get(
            "request_models",
            [],
        )
    ]


    print(
        "REQUEST_MODELS="
        + "|".join(
            model_names
        )
    )


    direct_names = [
        item["original_name"]
        for item in consumer.get(
            "direct_temporal_calls",
            [],
        )
    ]


    transitive_names = [
        item["original_name"]
        for item in consumer.get(
            "transitive_temporal_calls",
            [],
        )
    ]


    print(
        "DIRECT_TEMPORAL_CALLS="
        + "|".join(
            direct_names
        )
    )

    print(
        "TRANSITIVE_TEMPORAL_CALLS="
        + "|".join(
            transitive_names
        )
    )

    print(
        "FIRST_MUTATION_CANDIDATE_LINE="
        + str(
            consumer.get(
                "first_mutation_candidate_line"
            )
        )
    )


    candidate_text = [
        item["name"]
        + "@"
        + str(
            item["line_start"]
        )
        for item in consumer.get(
            "temporal_api_candidates",
            [],
        )
    ]


    print(
        "TEMPORAL_API_CANDIDATES="
        + "|".join(
            candidate_text
        )
    )


print("")

print(
    "PREFLIGHT_COMPLETE="
    + str(
        preflight_complete
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


if not preflight_complete:
    raise SystemExit(1)