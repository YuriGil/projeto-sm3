from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


matrix_path = Path(sys.argv[1])
worker_path = Path(sys.argv[2])
temporal_path = Path(sys.argv[3])
output_path = Path(sys.argv[4])


def sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load(path: Path) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


matrix = load(matrix_path)

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
# TOP-LEVEL FUNCTIONS / CALL GRAPH
# ============================================================

functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


classes: set[str] = set()

top_level_assignments: set[str] = set()


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
                top_level_assignments.add(
                    target.id
                )

    elif isinstance(node, ast.AnnAssign):

        if isinstance(node.target, ast.Name):
            top_level_assignments.add(
                node.target.id
            )


def call_names(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:

    result: set[str] = set()

    for node in ast.walk(fn):

        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            result.add(node.func.id)

        elif isinstance(node.func, ast.Attribute):
            result.add(node.func.attr)

    return result


call_graph: dict[str, set[str]] = {}


for name, fn in functions.items():

    calls = call_names(fn)

    call_graph[name] = {
        called
        for called in calls
        if called in functions
    }


def reachable_functions(
    start: str,
) -> set[str]:

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


# ============================================================
# ROUTE MAP
# ============================================================

routes: dict[str, dict[str, str]] = {}


for name, fn in functions.items():

    for decorator in fn.decorator_list:

        if not isinstance(decorator, ast.Call):
            continue

        if not isinstance(
            decorator.func,
            ast.Attribute,
        ):
            continue

        method = decorator.func.attr.upper()

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


def route_function(path: str) -> str | None:

    item = routes.get(path)

    if item is None:
        return None

    return item["function"]


# ============================================================
# TEMPORAL IMPORTS + TRANSITIVE REACHABILITY
# ============================================================

temporal_imports: set[str] = set()


for node in worker_tree.body:

    if (
        isinstance(node, ast.ImportFrom)
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):

        for alias in node.names:
            temporal_imports.add(alias.name)


def names_called_by_function(
    function_name: str,
) -> set[str]:

    fn = functions.get(function_name)

    if fn is None:
        return set()

    return call_names(fn)


def transitive_external_calls(
    start: str,
) -> set[str]:

    reachable = reachable_functions(start)

    external: set[str] = set()

    for fn_name in reachable:

        calls = names_called_by_function(
            fn_name
        )

        external.update(
            calls
        )

    return external


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
    "evidence":
        (
            EVIDENCE_ROUTE,
            "validate_evidence_temporal",
        ),

    "signal":
        (
            SIGNAL_ROUTE,
            "validate_signal_temporal",
        ),

    "snapshot":
        (
            SNAPSHOT_ROUTE,
            "validate_snapshot_temporal_inputs",
        ),
}


consumer_evidence: dict[str, Any] = {}


for consumer, spec in consumer_specs.items():

    route_path = spec[0]
    validator = spec[1]

    fn_name = route_function(
        route_path
    )

    reachable = (
        reachable_functions(fn_name)
        if fn_name
        else set()
    )

    external_calls = (
        transitive_external_calls(fn_name)
        if fn_name
        else set()
    )

    direct_calls = (
        names_called_by_function(fn_name)
        if fn_name
        else set()
    )

    consumer_evidence[consumer] = {
        "route":
            route_path,

        "route_function":
            fn_name,

        "reachable_function_count":
            len(reachable),

        "reachable_functions":
            sorted(reachable),

        "validator":
            validator,

        "validator_direct":
            validator in direct_calls,

        "validator_transitive":
            validator in external_calls,
    }


all_temporal_transitive = all(
    consumer_evidence[name][
        "validator_transitive"
    ]
    for name in consumer_evidence
)


# ============================================================
# STRUCTURAL SYMBOL EVIDENCE
# ============================================================

definition_names = set(functions)
definition_names.update(classes)
definition_names.update(top_level_assignments)


all_name_nodes = {
    node.id
    for node in ast.walk(worker_tree)
    if isinstance(node, ast.Name)
}


all_string_literals = {
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
        name
        for name in source
        if token in name.lower()
    )


def strings_containing(
    token: str,
) -> list[str]:

    token = token.lower()

    return sorted(
        value
        for value in all_string_literals
        if token in value.lower()
    )


def explicit_definition(
    token: str,
) -> bool:

    return len(
        names_containing(
            token,
            definition_names,
        )
    ) > 0


# ============================================================
# TEMPORAL EVENT SIGNATURE SEMANTICS
# ============================================================

signature_names = names_containing(
    "signature",
    all_name_nodes,
)

signature_definitions = names_containing(
    "signature",
    definition_names,
)

signature_strings = strings_containing(
    "signature"
)


temporal_signature_anchors: list[str] = []


for value in (
    signature_names
    + signature_definitions
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
                "time_signature",
                "timeline",
            ]
        )
    ):

        temporal_signature_anchors.append(
            value
        )


temporal_signature_anchors = sorted(
    set(temporal_signature_anchors)
)


# ============================================================
# IDENTITY / VERSIONING SEMANTICS
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
    set(platform_identity_anchors)
)


# ============================================================
# EXPERIMENT / CONFOUNDER EVIDENCE
# ============================================================

experiment_route_paths = [
    path
    for path in routes
    if "/platform-dynamics/experiments/" in path
]


experiment_functions: set[str] = set()


for path in experiment_route_paths:

    fn_name = route_function(path)

    if fn_name:

        experiment_functions.update(
            reachable_functions(
                fn_name
            )
        )


experiment_corpus_names: set[str] = set()

experiment_corpus_strings: set[str] = set()


for fn_name in experiment_functions:

    fn = functions.get(fn_name)

    if fn is None:
        continue

    for node in ast.walk(fn):

        if isinstance(node, ast.Name):
            experiment_corpus_names.add(
                node.id
            )

        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ):
            experiment_corpus_strings.add(
                node.value
            )


confound_control_terms = [
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


confound_control_hits: dict[str, list[str]] = {}


for term in confound_control_terms:

    hits: list[str] = []

    for value in (
        experiment_corpus_names
        | experiment_corpus_strings
    ):

        if term in value.lower():
            hits.append(value)

    confound_control_hits[term] = sorted(
        set(hits)
    )


implicit_confound_control_term_count = sum(
    1
    for term, hits in confound_control_hits.items()
    if hits
)


# ============================================================
# HYPOTHESIS / PREDICTION / DRIFT / TASTE
# ============================================================

structural_concepts = {}


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

    structural_concepts[concept] = {
        "definition_hits":
            names_containing(
                concept,
                definition_names,
            ),

        "all_name_hits":
            names_containing(
                concept,
                all_name_nodes,
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
    row["requirement_id"]: row
    for row in matrix["rows"]
}


findings: list[dict[str, Any]] = []


def finding(
    requirement_id: str,
    severity: str,
    code: str,
    matrix_classification: str,
    suggested_classification: str | None,
    evidence: dict[str, Any],
    message: str,
) -> None:

    findings.append({
        "requirement_id":
            requirement_id,

        "severity":
            severity,

        "code":
            code,

        "matrix_classification":
            matrix_classification,

        "suggested_classification":
            suggested_classification,

        "evidence":
            evidence,

        "message":
            message,
    })


# ============================================================
# ATTACK R04 — DIRECT CALL FALSE NEGATIVE
# ============================================================

r04 = rows["A5-R04"]


if all_temporal_transitive:

    if r04["classification"] != "IMPLEMENTED":

        finding(
            "A5-R04",
            "HIGH",
            "TRANSITIVE_TEMPORAL_VALIDATION_FALSE_NEGATIVE",
            r04["classification"],
            "IMPLEMENTED",
            consumer_evidence,
            (
                "All three Platform Dynamics consumers "
                "transitively reach their canonical Temporal "
                "Validity R2 validators. Direct-handler-only "
                "analysis understated the implementation."
            ),
        )

else:

    missing_consumers = [
        name
        for name, value in consumer_evidence.items()
        if not value["validator_transitive"]
    ]

    if (
        r04["classification"]
        == "IMPLEMENTED"
    ):

        finding(
            "A5-R04",
            "HIGH",
            "TEMPORAL_IMPLEMENTATION_OVERSTATED",
            r04["classification"],
            "PARTIAL",
            {
                "missing_consumers":
                    missing_consumers,

                "consumer_evidence":
                    consumer_evidence,
            },
            (
                "At least one principal consumer does not "
                "transitively reach its canonical temporal "
                "validator."
            ),
        )


# ============================================================
# ATTACK R05 — HYPOTHESIS + REVISION
# ============================================================

r05 = rows["A5-R05"]

hypothesis_explicit = explicit_definition(
    "hypothesis"
)

revision_explicit = explicit_definition(
    "revision"
)


if (
    r05["classification"] == "MISSING"
    and hypothesis_explicit
    and revision_explicit
):

    finding(
        "A5-R05",
        "MEDIUM",
        "EXPLICIT_HYPOTHESIS_REVISION_DEFINITIONS_FOUND",
        r05["classification"],
        "PARTIAL",
        {
            "hypothesis":
                structural_concepts[
                    "hypothesis"
                ][
                    "definition_hits"
                ],

            "revision":
                structural_concepts[
                    "revision"
                ][
                    "definition_hits"
                ],
        },
        (
            "Explicit structural definitions contradict a "
            "pure MISSING classification; lifecycle semantics "
            "still require deeper verification."
        ),
    )


# ============================================================
# ATTACK R06 — PREDICTION / OUTCOME
# ============================================================

r06 = rows["A5-R06"]


if (
    r06["classification"] == "MISSING"
    and explicit_definition("prediction")
    and explicit_definition("outcome")
):

    finding(
        "A5-R06",
        "MEDIUM",
        "EXPLICIT_PREDICTION_OUTCOME_DEFINITIONS_FOUND",
        r06["classification"],
        "PARTIAL",
        {
            "prediction":
                structural_concepts[
                    "prediction"
                ][
                    "definition_hits"
                ],

            "outcome":
                structural_concepts[
                    "outcome"
                ][
                    "definition_hits"
                ],
        },
        (
            "Structural prediction/outcome definitions exist "
            "and require deeper retention/linkage analysis."
        ),
    )


# ============================================================
# ATTACK R07 — DRIFT
# ============================================================

r07 = rows["A5-R07"]


if (
    r07["classification"] == "MISSING"
    and explicit_definition("drift")
):

    finding(
        "A5-R07",
        "MEDIUM",
        "EXPLICIT_DRIFT_DEFINITION_FOUND",
        r07["classification"],
        "PARTIAL",
        {
            "drift":
                structural_concepts[
                    "drift"
                ][
                    "definition_hits"
                ],
        },
        (
            "An explicit drift definition exists; whether it "
            "satisfies multi-sample V2 semantics remains "
            "unproven."
        ),
    )


# ============================================================
# ATTACK R08 — IMPLICIT CONFOUNDER CONTROLS
# ============================================================

r08 = rows["A5-R08"]


if (
    r08["classification"] == "PARTIAL"
    and implicit_confound_control_term_count >= 2
):

    finding(
        "A5-R08",
        "LOW",
        "IMPLICIT_CONFOUNDER_CONTROLS_PRESENT",
        r08["classification"],
        "PARTIAL",
        {
            "experiment_route_count":
                len(
                    experiment_route_paths
                ),

            "control_term_count":
                implicit_confound_control_term_count,

            "control_hits":
                confound_control_hits,
        },
        (
            "The PARTIAL classification remains conservative, "
            "but CONFOUND_EXPLICIT=False alone understates "
            "existing experiment controls."
        ),
    )


# ============================================================
# ATTACK R09 — GENERIC SIGNATURE FALSE POSITIVE
# ============================================================

r09 = rows["A5-R09"]


if (
    r09["classification"] == "PARTIAL"
    and len(temporal_signature_anchors) == 0
):

    finding(
        "A5-R09",
        "HIGH",
        "GENERIC_SIGNATURE_FALSE_POSITIVE",
        r09["classification"],
        "MISSING",
        {
            "signature_definition_hits":
                signature_definitions,

            "signature_name_hits":
                signature_names,

            "signature_string_hit_count":
                len(signature_strings),

            "temporal_signature_anchors":
                temporal_signature_anchors,
        },
        (
            "Generic signature/hash identifiers are not "
            "evidence of the frozen temporal-event signature "
            "representation."
        ),
    )


# ============================================================
# ATTACK R10 — TASTE MODEL
# ============================================================

r10 = rows["A5-R10"]


if (
    r10["classification"] == "MISSING"
    and explicit_definition("taste")
):

    finding(
        "A5-R10",
        "MEDIUM",
        "EXPLICIT_TASTE_DEFINITION_FOUND",
        r10["classification"],
        "PARTIAL",
        {
            "taste":
                structural_concepts[
                    "taste"
                ][
                    "definition_hits"
                ],
        },
        (
            "Taste-related structural definitions exist; "
            "separation from performance learning still "
            "requires verification."
        ),
    )


# ============================================================
# ATTACK R11 — UNCERTAINTY / PROVENANCE
# ============================================================

r11 = rows["A5-R11"]


if (
    r11["classification"] == "PARTIAL"
    and not explicit_definition(
        "uncertainty"
    )
):

    finding(
        "A5-R11",
        "LOW",
        "UNCERTAINTY_EXPLICIT_MODEL_ABSENT",
        r11["classification"],
        "PARTIAL",
        {
            "provenance_definitions":
                structural_concepts[
                    "provenance"
                ][
                    "definition_hits"
                ],

            "uncertainty_definitions":
                structural_concepts[
                    "uncertainty"
                ][
                    "definition_hits"
                ],
        },
        (
            "PARTIAL remains defensible because provenance is "
            "present, but explicit uncertainty modeling is "
            "still absent."
        ),
    )


# ============================================================
# ATTACK R12 — GENERIC IDENTITY/VERSION FALSE POSITIVE
# ============================================================

r12 = rows["A5-R12"]


if (
    r12["classification"] == "PARTIAL"
    and len(platform_identity_anchors) == 0
):

    finding(
        "A5-R12",
        "HIGH",
        "GENERIC_IDENTITY_VERSION_FALSE_POSITIVE",
        r12["classification"],
        "MISSING",
        {
            "identity_definitions":
                identity_definitions,

            "version_definitions":
                version_definitions,

            "platform_identity_anchors":
                platform_identity_anchors,
        },
        (
            "Generic identity/version references do not prove "
            "the frozen Platform Dynamics V2 identity and "
            "finality semantics."
        ),
    )


# ============================================================
# R13 DEFERRED POLICY MUST STAY N/A
# ============================================================

r13 = rows["A5-R13"]


if r13["classification"] != "NOT_APPLICABLE":

    finding(
        "A5-R13",
        "HIGH",
        "DEFERRED_POLICY_CLASSIFICATION_VIOLATION",
        r13["classification"],
        "NOT_APPLICABLE",
        {},
        (
            "Numeric confidence-decay remains explicitly "
            "deferred by the post-A4 freeze."
        ),
    )


# ============================================================
# REVIEW SUMMARY
# ============================================================

severity_counts = {
    "HIGH": 0,
    "MEDIUM": 0,
    "LOW": 0,
}


for item in findings:

    severity = item["severity"]

    if severity in severity_counts:
        severity_counts[severity] += 1


high_findings = [
    item
    for item in findings
    if item["severity"] == "HIGH"
]


matrix_accepted_without_revision = (
    len(high_findings) == 0
)


review_complete = (
    len(rows) == 13
    and len(consumer_evidence) == 3
)


result = {
    "contract_version":
        "SM3_BLACK_BOX_DYNAMICS_V2_GAP_MATRIX_ADVERSARIAL_REVIEW_V1",

    "matrix_sha256":
        sha(matrix_path),

    "worker_sha256":
        sha(worker_path),

    "temporal_sha256":
        sha(temporal_path),

    "review_method":
        "TRANSITIVE_CALL_GRAPH_PLUS_STRUCTURAL_SEMANTIC_ATTACK_V1",

    "requirement_count":
        len(rows),

    "consumer_evidence":
        consumer_evidence,

    "all_temporal_consumers_transitively_validated":
        all_temporal_transitive,

    "signature_evidence": {
        "signature_definitions":
            signature_definitions,

        "signature_name_hits":
            signature_names,

        "signature_string_hit_count":
            len(signature_strings),

        "temporal_signature_anchors":
            temporal_signature_anchors,
    },

    "identity_version_evidence": {
        "identity_definitions":
            identity_definitions,

        "version_definitions":
            version_definitions,

        "platform_identity_anchors":
            platform_identity_anchors,
    },

    "experiment_confounder_evidence": {
        "experiment_route_count":
            len(experiment_route_paths),

        "experiment_routes":
            sorted(
                experiment_route_paths
            ),

        "implicit_control_term_count":
            implicit_confound_control_term_count,

        "control_hits":
            confound_control_hits,
    },

    "structural_concepts":
        structural_concepts,

    "finding_count":
        len(findings),

    "severity_counts":
        severity_counts,

    "findings":
        findings,

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
    + str(review_complete)
)

print(
    "FINDING_COUNT="
    + str(len(findings))
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
    "ALL_TEMPORAL_CONSUMERS_TRANSITIVE="
    + str(
        all_temporal_transitive
    )
)

for consumer in [
    "evidence",
    "signal",
    "snapshot",
]:

    item = consumer_evidence[
        consumer
    ]

    print(
        consumer.upper()
        + "_TEMPORAL_DIRECT="
        + str(
            item[
                "validator_direct"
            ]
        )
    )

    print(
        consumer.upper()
        + "_TEMPORAL_TRANSITIVE="
        + str(
            item[
                "validator_transitive"
            ]
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
        implicit_confound_control_term_count
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