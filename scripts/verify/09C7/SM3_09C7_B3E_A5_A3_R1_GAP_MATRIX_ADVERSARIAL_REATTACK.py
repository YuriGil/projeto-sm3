from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_matrix_path = Path(sys.argv[1])
matrix_path = Path(sys.argv[2])
worker_path = Path(sys.argv[3])
temporal_path = Path(sys.argv[4])
output_path = Path(sys.argv[5])


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


source_matrix = load(
    source_matrix_path
)

matrix = load(
    matrix_path
)


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


# ============================================================
# FUNCTION / CLASS / CONSTANT INVENTORY
# ============================================================

functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}

classes: set[str] = set()

top_assignments: set[str] = set()


for node in worker_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        functions[node.name] = node

    elif isinstance(node, ast.ClassDef):
        classes.add(node.name)

    elif isinstance(node, ast.Assign):

        for target in node.targets:

            if isinstance(target, ast.Name):
                top_assignments.add(
                    target.id
                )

    elif isinstance(node, ast.AnnAssign):

        if isinstance(node.target, ast.Name):
            top_assignments.add(
                node.target.id
            )


definition_names = (
    set(functions)
    | classes
    | top_assignments
)


all_names = {
    node.id
    for node in ast.walk(worker_tree)
    if isinstance(node, ast.Name)
}


all_strings = {
    node.value
    for node in ast.walk(worker_tree)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
    )
}


def names_containing(
    token: str,
    source: set[str],
) -> list[str]:

    token = token.lower()

    return sorted(
        item
        for item in source
        if token in item.lower()
    )


def strings_containing(
    token: str,
) -> list[str]:

    token = token.lower()

    return sorted(
        item
        for item in all_strings
        if token in item.lower()
    )


def explicit_definition(
    token: str,
) -> bool:

    return bool(
        names_containing(
            token,
            definition_names,
        )
    )


# ============================================================
# CALL GRAPH
# ============================================================

def call_names(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:

    names: set[str] = set()

    for node in ast.walk(fn):

        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            names.add(node.func.id)

        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)

    return names


call_graph: dict[str, set[str]] = {}


for name, fn in functions.items():

    call_graph[name] = {
        called
        for called in call_names(fn)
        if called in functions
    }


def reachable_functions(
    start: str | None,
) -> set[str]:

    if start is None:
        return set()

    if start not in functions:
        return set()

    visited: set[str] = set()
    stack = [start]

    while stack:

        current = stack.pop()

        if current in visited:
            continue

        visited.add(current)

        for child in call_graph.get(
            current,
            set(),
        ):
            if child not in visited:
                stack.append(child)

    return visited


def transitive_calls(
    start: str | None,
) -> set[str]:

    result: set[str] = set()

    for function_name in reachable_functions(
        start
    ):

        fn = functions.get(
            function_name
        )

        if fn is None:
            continue

        result.update(
            call_names(fn)
        )

    return result


# ============================================================
# ROUTES
# ============================================================

routes: dict[str, dict[str, str]] = {}


for name, fn in functions.items():

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

        first = decorator.args[0]

        if not (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
        ):
            continue

        routes[first.value] = {
            "method": method,
            "function": name,
        }


def route_function(
    path: str,
) -> str | None:

    item = routes.get(path)

    if item is None:
        return None

    return item["function"]


EVIDENCE_ROUTE = (
    "/production/culture-intelligence/"
    "platform-dynamics/evidence"
)

SIGNAL_ROUTE = (
    "/production/culture-intelligence/"
    "platform-preference-signals"
)

SNAPSHOT_ROUTE = (
    "/production/culture-intelligence/"
    "platform-dynamics/snapshots"
)


consumer_specs = {
    "evidence": (
        EVIDENCE_ROUTE,
        "validate_evidence_temporal",
    ),

    "signal": (
        SIGNAL_ROUTE,
        "validate_signal_temporal",
    ),

    "snapshot": (
        SNAPSHOT_ROUTE,
        "validate_snapshot_temporal_inputs",
    ),
}


consumer_evidence: dict[str, Any] = {}


for name, spec in consumer_specs.items():

    route_path = spec[0]
    validator = spec[1]

    fn_name = route_function(
        route_path
    )

    direct = set()

    if fn_name in functions:
        direct = call_names(
            functions[fn_name]
        )

    transitive = transitive_calls(
        fn_name
    )

    consumer_evidence[name] = {
        "route_function":
            fn_name,

        "validator":
            validator,

        "validator_direct":
            validator in direct,

        "validator_transitive":
            validator in transitive,

        "reachable_functions":
            sorted(
                reachable_functions(
                    fn_name
                )
            ),
    }


all_temporal_transitive = all(
    item[
        "validator_transitive"
    ]
    for item in consumer_evidence.values()
)


# ============================================================
# TEMPORAL CONTRACT
# ============================================================

temporal_constants: dict[str, Any] = {}


for node in temporal_tree.body:

    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(
        node.value,
        ast.Constant,
    ):
        continue

    for target in node.targets:

        if isinstance(target, ast.Name):
            temporal_constants[
                target.id
            ] = node.value.value


temporal_contract_exact = (
    temporal_constants.get(
        "TEMPORAL_VALIDITY_POLICY_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    and
    temporal_constants.get(
        "TEMPORAL_VALIDITY_ENGINE_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    and
    temporal_constants.get(
        "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
    )
    == "R2"
)


# ============================================================
# SIGNATURE ATTACK
# ============================================================

signature_definitions = names_containing(
    "signature",
    definition_names,
)

signature_names = names_containing(
    "signature",
    all_names,
)

signature_strings = strings_containing(
    "signature"
)


temporal_signature_anchors: list[str] = []


for value in (
    signature_definitions
    + signature_names
    + signature_strings
):

    lowered = value.lower()

    if (
        "signature" in lowered
        and any(
            token in lowered
            for token in [
                "temporal",
                "event",
                "timestamp",
                "millisecond",
                "scene",
                "timeline",
                "time_signature",
            ]
        )
    ):
        temporal_signature_anchors.append(
            value
        )


temporal_signature_anchors = sorted(
    set(
        temporal_signature_anchors
    )
)


# ============================================================
# IDENTITY / VERSION ATTACK
# ============================================================

identity_definitions = names_containing(
    "identity",
    definition_names,
)

version_definitions = names_containing(
    "version",
    definition_names,
)


platform_identity_anchors: list[str] = []


for value in (
    identity_definitions
    + version_definitions
):

    lowered = value.lower()

    if any(
        token in lowered
        for token in [
            "platform",
            "dynamics",
            "evidence",
            "signal",
            "snapshot",
            "experiment",
            "hypothesis",
        ]
    ):
        platform_identity_anchors.append(
            value
        )


platform_identity_anchors = sorted(
    set(
        platform_identity_anchors
    )
)


# ============================================================
# EXPERIMENT / CONFOUNDER ATTACK
# ============================================================

experiment_routes = [
    path
    for path in routes
    if "/platform-dynamics/experiments/" in path
]


experiment_functions: set[str] = set()


for path in experiment_routes:

    fn_name = route_function(
        path
    )

    experiment_functions.update(
        reachable_functions(
            fn_name
        )
    )


experiment_names: set[str] = set()
experiment_strings: set[str] = set()


for function_name in experiment_functions:

    fn = functions.get(
        function_name
    )

    if fn is None:
        continue

    for node in ast.walk(fn):

        if isinstance(node, ast.Name):
            experiment_names.add(
                node.id
            )

        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ):
            experiment_strings.add(
                node.value
            )


control_terms = [
    "confound",
    "single_variable",
    "same_source",
    "same_duration",
    "same_audio",
    "same_caption",
    "posting_time",
    "no_paid",
    "paid_distribution",
    "variant",
    "control",
]


control_hits: dict[str, list[str]] = {}


for term in control_terms:

    values = []

    for value in (
        experiment_names
        | experiment_strings
    ):

        if term in value.lower():
            values.append(value)

    control_hits[term] = sorted(
        set(values)
    )


implicit_control_term_count = sum(
    1
    for values in control_hits.values()
    if values
)


# ============================================================
# STRUCTURAL CONCEPTS
# ============================================================

concepts = {}


for concept in [
    "hypothesis",
    "revision",
    "prediction",
    "outcome",
    "drift",
    "taste",
    "uncertainty",
    "provenance",
]:

    concepts[concept] = {
        "definition_hits":
            names_containing(
                concept,
                definition_names,
            ),

        "name_hits":
            names_containing(
                concept,
                all_names,
            ),

        "string_hits":
            strings_containing(
                concept,
            ),
    }


# ============================================================
# MATRIX INDEX
# ============================================================

rows = {
    row["requirement_id"]:
        row
    for row in matrix["rows"]
}


source_rows = {
    row["requirement_id"]:
        row
    for row in source_matrix["rows"]
}


findings: list[dict[str, Any]] = []


def add_finding(
    requirement_id: str,
    severity: str,
    code: str,
    message: str,
) -> None:

    findings.append({
        "requirement_id":
            requirement_id,

        "severity":
            severity,

        "code":
            code,

        "classification":
            rows[
                requirement_id
            ][
                "classification"
            ],

        "message":
            message,
    })


# ============================================================
# ATTACK: R04 TEMPORAL
# ============================================================

if not temporal_contract_exact:

    add_finding(
        "A5-R04",
        "HIGH",
        "TEMPORAL_R2_CONTRACT_NOT_EXACT",
        "Canonical Temporal Validity R2 contract changed.",
    )


if all_temporal_transitive:

    if rows[
        "A5-R04"
    ][
        "classification"
    ] != "IMPLEMENTED":

        add_finding(
            "A5-R04",
            "HIGH",
            "TEMPORAL_CLASSIFICATION_UNDERSTATED",
            "All consumers reach validators but matrix is not IMPLEMENTED.",
        )

else:

    if rows[
        "A5-R04"
    ][
        "classification"
    ] != "PARTIAL":

        add_finding(
            "A5-R04",
            "HIGH",
            "TEMPORAL_CLASSIFICATION_INVALID",
            "Not all consumers reach validators; classification must remain PARTIAL.",
        )


# ============================================================
# ATTACK: R05
# ============================================================

if (
    explicit_definition("hypothesis")
    and explicit_definition("revision")
    and rows["A5-R05"]["classification"] == "MISSING"
):

    add_finding(
        "A5-R05",
        "MEDIUM",
        "HYPOTHESIS_REVISION_STRUCTURAL_IMPLEMENTATION_FOUND",
        "Explicit hypothesis and revision definitions require reclassification review.",
    )


# ============================================================
# ATTACK: R06
# ============================================================

if (
    explicit_definition("prediction")
    and explicit_definition("outcome")
    and rows["A5-R06"]["classification"] == "MISSING"
):

    add_finding(
        "A5-R06",
        "MEDIUM",
        "PREDICTION_OUTCOME_STRUCTURAL_IMPLEMENTATION_FOUND",
        "Explicit prediction and outcome definitions require reclassification review.",
    )


# ============================================================
# ATTACK: R07
# ============================================================

if (
    explicit_definition("drift")
    and rows["A5-R07"]["classification"] == "MISSING"
):

    add_finding(
        "A5-R07",
        "MEDIUM",
        "DRIFT_STRUCTURAL_IMPLEMENTATION_FOUND",
        "Explicit drift definition requires reclassification review.",
    )


# ============================================================
# ATTACK: R08
#
# Existing implicit controls are informational and do not
# promote PARTIAL to IMPLEMENTED.
# ============================================================

if rows[
    "A5-R08"
][
    "classification"
] != "PARTIAL":

    add_finding(
        "A5-R08",
        "HIGH",
        "EXPERIMENT_CLASSIFICATION_CHANGED",
        "Experiment requirement must remain PARTIAL under current evidence.",
    )


if implicit_control_term_count >= 2:

    add_finding(
        "A5-R08",
        "LOW",
        "IMPLICIT_CONFOUNDER_CONTROLS_PRESENT",
        "Existing experiment controls are present but do not prove the full frozen confounder contract.",
    )


# ============================================================
# ATTACK: R09
#
# This is the previously failing HIGH finding.
# Zero temporal anchors now REQUIRE MISSING.
# ============================================================

r09_class = rows[
    "A5-R09"
][
    "classification"
]


if len(
    temporal_signature_anchors
) == 0:

    if r09_class != "MISSING":

        add_finding(
            "A5-R09",
            "HIGH",
            "GENERIC_SIGNATURE_FALSE_POSITIVE_NOT_REMEDIATED",
            "Zero temporal-event signature anchors require A5-R09=MISSING.",
        )

else:

    if r09_class == "MISSING":

        add_finding(
            "A5-R09",
            "HIGH",
            "TEMPORAL_SIGNATURE_EVIDENCE_NOW_PRESENT",
            "Temporal-event signature anchors exist while matrix still says MISSING.",
        )


# ============================================================
# ATTACK: R10
# ============================================================

if (
    explicit_definition("taste")
    and rows["A5-R10"]["classification"] == "MISSING"
):

    add_finding(
        "A5-R10",
        "MEDIUM",
        "TASTE_STRUCTURAL_IMPLEMENTATION_FOUND",
        "Explicit taste definition requires separation-boundary reclassification review.",
    )


# ============================================================
# ATTACK: R11
# ============================================================

if rows[
    "A5-R11"
][
    "classification"
] != "PARTIAL":

    add_finding(
        "A5-R11",
        "HIGH",
        "UNCERTAINTY_PROVENANCE_CLASSIFICATION_CHANGED",
        "Current evidence supports PARTIAL, not another classification.",
    )


if not explicit_definition(
    "uncertainty"
):

    add_finding(
        "A5-R11",
        "LOW",
        "UNCERTAINTY_EXPLICIT_MODEL_ABSENT",
        "Provenance exists but explicit uncertainty model remains absent.",
    )


# ============================================================
# ATTACK: R12
# ============================================================

if (
    len(platform_identity_anchors) == 0
    and rows[
        "A5-R12"
    ][
        "classification"
    ] == "PARTIAL"
):

    add_finding(
        "A5-R12",
        "HIGH",
        "GENERIC_IDENTITY_VERSION_FALSE_POSITIVE",
        "No Platform Dynamics identity/version anchors exist.",
    )


# ============================================================
# ATTACK: R13
# ============================================================

if rows[
    "A5-R13"
][
    "classification"
] != "NOT_APPLICABLE":

    add_finding(
        "A5-R13",
        "HIGH",
        "DEFERRED_CONFIDENCE_DECAY_POLICY_VIOLATION",
        "Numeric confidence-decay policy must remain NOT_APPLICABLE while deferred.",
    )


# ============================================================
# VERIFY ONLY R09 CHANGED FROM V1
# ============================================================

changed_ids = []


for requirement_id in sorted(
    source_rows
):

    source_class = source_rows[
        requirement_id
    ][
        "classification"
    ]

    current_class = rows[
        requirement_id
    ][
        "classification"
    ]

    if source_class != current_class:
        changed_ids.append(
            requirement_id
        )


if changed_ids != [
    "A5-R09"
]:

    add_finding(
        "A5-R09",
        "HIGH",
        "CLASSIFICATION_DELTA_SCOPE_INVALID",
        "Classification delta from V1 is not restricted to A5-R09.",
    )


# ============================================================
# EXPECTED LOW FINDINGS
# ============================================================

severity_counts = {
    "HIGH": 0,
    "MEDIUM": 0,
    "LOW": 0,
}


for finding in findings:

    severity = finding[
        "severity"
    ]

    if severity in severity_counts:
        severity_counts[
            severity
        ] += 1


low_codes = sorted(
    finding["code"]
    for finding in findings
    if finding["severity"] == "LOW"
)


expected_low_codes = sorted([
    "IMPLICIT_CONFOUNDER_CONTROLS_PRESENT",
    "UNCERTAINTY_EXPLICIT_MODEL_ABSENT",
])


informational_findings_exact = (
    low_codes
    == expected_low_codes
)


high_clean = (
    severity_counts["HIGH"] == 0
)

medium_clean = (
    severity_counts["MEDIUM"] == 0
)


matrix_accepted_without_revision = (
    high_clean
    and medium_clean
    and informational_findings_exact
)


review_complete = (
    len(rows) == 13
    and changed_ids == ["A5-R09"]
)


result = {
    "contract_version":
        "SM3_BLACK_BOX_DYNAMICS_V2_GAP_MATRIX_ADVERSARIAL_REATTACK_V1",

    "source_matrix_sha256":
        sha(source_matrix_path),

    "revised_matrix_sha256":
        sha(matrix_path),

    "worker_sha256":
        sha(worker_path),

    "temporal_sha256":
        sha(temporal_path),

    "review_method":
        "TRANSITIVE_CALL_GRAPH_PLUS_STRUCTURAL_SEMANTIC_REATTACK_V1",

    "requirement_count":
        len(rows),

    "changed_classification_ids_from_v1":
        changed_ids,

    "consumer_evidence":
        consumer_evidence,

    "temporal_contract_exact":
        temporal_contract_exact,

    "all_temporal_consumers_transitively_validated":
        all_temporal_transitive,

    "signature_evidence": {
        "signature_definition_count":
            len(
                signature_definitions
            ),

        "signature_name_hit_count":
            len(
                signature_names
            ),

        "signature_string_hit_count":
            len(
                signature_strings
            ),

        "temporal_signature_anchors":
            temporal_signature_anchors,
    },

    "identity_version_evidence": {
        "platform_identity_anchors":
            platform_identity_anchors,
    },

    "experiment_evidence": {
        "route_count":
            len(
                experiment_routes
            ),

        "implicit_control_term_count":
            implicit_control_term_count,

        "control_hits":
            control_hits,
    },

    "structural_concepts":
        concepts,

    "finding_count":
        len(
            findings
        ),

    "severity_counts":
        severity_counts,

    "low_finding_codes":
        low_codes,

    "informational_findings_exact":
        informational_findings_exact,

    "findings":
        findings,

    "previous_r09_high_finding_resolved":
        (
            len(
                temporal_signature_anchors
            ) == 0
            and r09_class == "MISSING"
        ),

    "matrix_accepted_without_revision":
        matrix_accepted_without_revision,

    "implementation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "review_complete":
        review_complete,
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
    "REVIEW_COMPLETE="
    + str(
        review_complete
    )
)

print(
    "CHANGED_CLASSIFICATION_IDS="
    + "|".join(
        changed_ids
    )
)

print(
    "HIGH_FINDING_COUNT="
    + str(
        severity_counts["HIGH"]
    )
)

print(
    "MEDIUM_FINDING_COUNT="
    + str(
        severity_counts["MEDIUM"]
    )
)

print(
    "LOW_FINDING_COUNT="
    + str(
        severity_counts["LOW"]
    )
)

print(
    "TEMPORAL_CONTRACT_EXACT="
    + str(
        temporal_contract_exact
    )
)

print(
    "ALL_TEMPORAL_CONSUMERS_TRANSITIVE="
    + str(
        all_temporal_transitive
    )
)

print(
    "TEMPORAL_SIGNATURE_ANCHOR_COUNT="
    + str(
        len(
            temporal_signature_anchors
        )
    )
)

print(
    "PLATFORM_IDENTITY_ANCHOR_COUNT="
    + str(
        len(
            platform_identity_anchors
        )
    )
)

print(
    "IMPLICIT_CONFOUNDER_CONTROL_TERM_COUNT="
    + str(
        implicit_control_term_count
    )
)

print(
    "INFORMATIONAL_FINDINGS_EXACT="
    + str(
        informational_findings_exact
    )
)

print(
    "PREVIOUS_R09_HIGH_FINDING_RESOLVED="
    + str(
        result[
            "previous_r09_high_finding_resolved"
        ]
    )
)

print(
    "MATRIX_ACCEPTED_WITHOUT_REVISION="
    + str(
        matrix_accepted_without_revision
    )
)


if not review_complete:
    raise SystemExit(1)

if not matrix_accepted_without_revision:
    raise SystemExit(2)