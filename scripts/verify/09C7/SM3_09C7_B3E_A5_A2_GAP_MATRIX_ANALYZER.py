from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


a2_path = Path(sys.argv[1])
a3_path = Path(sys.argv[2])
a1_path = Path(sys.argv[3])
worker_path = Path(sys.argv[4])
temporal_path = Path(sys.argv[5])
output_path = Path(sys.argv[6])


ALLOWED = {
    "IMPLEMENTED",
    "PARTIAL",
    "MISSING",
    "SUPERSEDED",
    "NOT_APPLICABLE",
}


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


def get_call_name(node: ast.Call) -> str | None:

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def names_in_function(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:

    names: set[str] = set()

    for node in ast.walk(fn):

        if isinstance(node, ast.Name):
            names.add(node.id)

        if isinstance(node, ast.Call):

            call_name = get_call_name(node)

            if call_name:
                names.add(call_name)

    return names


def strings_in_tree(
    tree: ast.AST,
) -> set[str]:

    result: set[str] = set()

    for node in ast.walk(tree):

        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ):
            result.add(node.value)

    return result


def count_name_token(
    names: set[str],
    token: str,
) -> int:

    lowered = token.lower()

    return sum(
        1
        for name in names
        if lowered in name.lower()
    )


def count_string_token(
    values: set[str],
    token: str,
) -> int:

    lowered = token.lower()

    return sum(
        1
        for value in values
        if lowered in value.lower()
    )


a2 = load(a2_path)
a3 = load(a3_path)
a1 = load(a1_path)


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


worker_strings = strings_in_tree(
    worker_tree
)

worker_names = {
    node.id
    for node in ast.walk(worker_tree)
    if isinstance(node, ast.Name)
}


functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


routes: dict[str, dict[str, Any]] = {}


for node in worker_tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        functions[node.name] = node


        for decorator in node.decorator_list:

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
                "function": node.name,
            }


temporal_imports: set[str] = set()


for node in worker_tree.body:

    if (
        isinstance(node, ast.ImportFrom)
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):

        for alias in node.names:
            temporal_imports.add(alias.name)


temporal_usage = {
    name: 0
    for name in temporal_imports
}


for node in ast.walk(worker_tree):

    if (
        isinstance(node, ast.Name)
        and node.id in temporal_usage
    ):
        temporal_usage[node.id] += 1


def route_present(path: str) -> bool:
    return path in routes


def route_function(path: str) -> str | None:

    entry = routes.get(path)

    if entry is None:
        return None

    return entry["function"]


def route_function_names(
    path: str,
) -> set[str]:

    fn_name = route_function(path)

    if fn_name is None:
        return set()

    fn = functions.get(fn_name)

    if fn is None:
        return set()

    return names_in_function(fn)


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

SUMMARY_ROUTE = (
    "/production/culture-intelligence/"
    "platform-dynamics/summary"
)

EXP_PLAN_POST = (
    "/production/culture-intelligence/"
    "platform-dynamics/experiments/plans"
)

EXP_PLAN_GET = (
    "/production/culture-intelligence/"
    "platform-dynamics/experiments/plans/"
    "{experiment_plan_id}"
)

EXP_EVALUATE = (
    "/production/culture-intelligence/"
    "platform-dynamics/experiments/evaluations"
)

EXP_SUMMARY = (
    "/production/culture-intelligence/"
    "platform-dynamics/experiments/summary"
)


evidence_names = route_function_names(
    EVIDENCE_ROUTE
)

signal_names = route_function_names(
    SIGNAL_ROUTE
)

snapshot_names = route_function_names(
    SNAPSHOT_ROUTE
)


temporal_constants: dict[str, Any] = {}


for node in temporal_tree.body:

    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(node.value, ast.Constant):
        continue

    for target in node.targets:

        if isinstance(target, ast.Name):
            temporal_constants[target.id] = (
                node.value.value
            )


temporal_exact = (
    temporal_constants.get(
        "TEMPORAL_VALIDITY_POLICY_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    and temporal_constants.get(
        "TEMPORAL_VALIDITY_ENGINE_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    and temporal_constants.get(
        "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
    )
    == "R2"
)


evidence_temporal_call = (
    "validate_evidence_temporal"
    in evidence_names
)

signal_temporal_call = (
    "validate_signal_temporal"
    in signal_names
)

snapshot_temporal_call = (
    "validate_snapshot_temporal_inputs"
    in snapshot_names
)


all_three_temporal_consumers = (
    evidence_temporal_call
    and signal_temporal_call
    and snapshot_temporal_call
)


experiment_routes = {
    "plan_post": route_present(EXP_PLAN_POST),
    "plan_get": route_present(EXP_PLAN_GET),
    "evaluate": route_present(EXP_EVALUATE),
    "summary": route_present(EXP_SUMMARY),
}


experiment_route_count = sum(
    1
    for value in experiment_routes.values()
    if value
)


def runtime_token(token: str) -> dict[str, int]:

    return {
        "name_hits":
            count_name_token(
                worker_names,
                token,
            ),

        "string_hits":
            count_string_token(
                worker_strings,
                token,
            ),
    }


tokens = {
    name: runtime_token(name)
    for name in [
        "provenance",
        "uncertainty",
        "hypothesis",
        "revision",
        "prediction",
        "outcome",
        "drift",
        "experiment",
        "confound",
        "signature",
        "taste",
        "confidence",
        "decay",
        "identity",
        "version",
        "causal",
    ]
}


def explicit_runtime_symbol(
    token: str,
) -> bool:

    return (
        tokens[token]["name_hits"] > 0
    )


def any_runtime_reference(
    token: str,
) -> bool:

    return (
        tokens[token]["name_hits"] > 0
        or tokens[token]["string_hits"] > 0
    )


rows: list[dict[str, Any]] = []


def add_row(
    requirement_id: str,
    requirement: str,
    classification: str,
    evidence: dict[str, Any],
    gap: str | None,
    rationale: str,
) -> None:

    if classification not in ALLOWED:
        raise ValueError(
            "invalid classification: "
            + classification
        )

    rows.append({
        "requirement_id":
            requirement_id,

        "requirement":
            requirement,

        "classification":
            classification,

        "evidence":
            evidence,

        "gap":
            gap,

        "rationale":
            rationale,
    })


# ------------------------------------------------------------
# 1. Platform Dynamics evidence semantics
#
# Existing V1 ingestion is real runtime evidence, but by itself
# does not prove the whole frozen V2 semantics.
# ------------------------------------------------------------

evidence_surface = route_present(
    EVIDENCE_ROUTE
)

evidence_provenance = (
    explicit_runtime_symbol(
        "provenance"
    )
    or any_runtime_reference(
        "provenance"
    )
)


if (
    evidence_surface
    and evidence_provenance
):

    evidence_class = "PARTIAL"

    evidence_gap = (
        "Existing ingestion/provenance surface does not by "
        "itself establish the complete frozen V2 evidence "
        "semantics and uncertainty lifecycle."
    )

else:

    evidence_class = "MISSING"

    evidence_gap = (
        "Required evidence ingestion/provenance surface is "
        "not materially present."
    )


add_row(
    "A5-R01",
    "Platform Dynamics evidence semantics",
    evidence_class,
    {
        "route_present":
            evidence_surface,

        "route_function":
            route_function(
                EVIDENCE_ROUTE
            ),

        "provenance":
            tokens["provenance"],

        "uncertainty":
            tokens["uncertainty"],

        "temporal_validator_in_route":
            evidence_temporal_call,
    },
    evidence_gap,
    (
        "Classification is conservative: a V1 runtime "
        "surface is not treated as proof of full V2 semantics."
    ),
)


# ------------------------------------------------------------
# 2. Preference signal semantics
# ------------------------------------------------------------

signal_surface = route_present(
    SIGNAL_ROUTE
)


if signal_surface:

    signal_class = "PARTIAL"

    signal_gap = (
        "Preference-signal ingestion exists, but the frozen "
        "V2 identity/versioning and uncertainty semantics are "
        "not proven complete by route presence."
    )

else:

    signal_class = "MISSING"

    signal_gap = (
        "Preference-signal ingestion surface is absent."
    )


add_row(
    "A5-R02",
    "Platform preference signal semantics",
    signal_class,
    {
        "route_present":
            signal_surface,

        "route_function":
            route_function(
                SIGNAL_ROUTE
            ),

        "temporal_validator_in_route":
            signal_temporal_call,
    },
    signal_gap,
    (
        "Existing runtime functionality is credited without "
        "promoting it to full V2 compliance."
    ),
)


# ------------------------------------------------------------
# 3. Snapshot semantics
# ------------------------------------------------------------

snapshot_surface = (
    route_present(SNAPSHOT_ROUTE)
    and route_present(SUMMARY_ROUTE)
)


if snapshot_surface:

    snapshot_class = "PARTIAL"

    snapshot_gap = (
        "Snapshot/summary surfaces exist, while frozen V2 "
        "drift, uncertainty, decay and revision semantics are "
        "not yet demonstrated as complete."
    )

else:

    snapshot_class = "MISSING"

    snapshot_gap = (
        "Snapshot and summary runtime surface is incomplete."
    )


add_row(
    "A5-R03",
    "Platform Dynamics snapshot semantics",
    snapshot_class,
    {
        "snapshot_route_present":
            route_present(
                SNAPSHOT_ROUTE
            ),

        "summary_route_present":
            route_present(
                SUMMARY_ROUTE
            ),

        "snapshot_temporal_validator":
            snapshot_temporal_call,

        "drift":
            tokens["drift"],

        "decay":
            tokens["decay"],
    },
    snapshot_gap,
    (
        "The current snapshot implementation predates the "
        "full Black Box Dynamics V2 contract."
    ),
)


# ------------------------------------------------------------
# 4. Temporal as-of validity / expiry
# ------------------------------------------------------------

if (
    temporal_exact
    and all_three_temporal_consumers
):

    temporal_class = "IMPLEMENTED"

    temporal_gap = None

elif temporal_exact:

    temporal_class = "PARTIAL"

    temporal_gap = (
        "Temporal Validity R2 is present and exact, but all "
        "three principal Platform Dynamics consumers are not "
        "proven to call it."
    )

else:

    temporal_class = "MISSING"

    temporal_gap = (
        "Canonical Temporal Validity R2 contract is not "
        "present."
    )


add_row(
    "A5-R04",
    "Temporal as-of validity and expiry behavior",
    temporal_class,
    {
        "temporal_contract_exact":
            temporal_exact,

        "evidence_validator":
            evidence_temporal_call,

        "signal_validator":
            signal_temporal_call,

        "snapshot_validator":
            snapshot_temporal_call,

        "all_three_consumers":
            all_three_temporal_consumers,

        "temporal_import_usage":
            temporal_usage,
    },
    temporal_gap,
    (
        "A4 Temporal Validity R2 is the canonical temporal "
        "authority."
    ),
)


# ------------------------------------------------------------
# 5. Hypothesis lifecycle and revision model
# ------------------------------------------------------------

hypothesis_symbols = (
    explicit_runtime_symbol(
        "hypothesis"
    )
)

revision_symbols = (
    explicit_runtime_symbol(
        "revision"
    )
)


if (
    hypothesis_symbols
    and revision_symbols
):

    hypothesis_class = "PARTIAL"

    hypothesis_gap = (
        "Runtime symbols exist, but complete hypothesis "
        "revision lifecycle persistence is not proven."
    )

else:

    hypothesis_class = "MISSING"

    hypothesis_gap = (
        "No explicit runtime hypothesis lifecycle plus "
        "revision model is present."
    )


add_row(
    "A5-R05",
    "Hypothesis lifecycle and revision model",
    hypothesis_class,
    {
        "hypothesis":
            tokens["hypothesis"],

        "revision":
            tokens["revision"],
    },
    hypothesis_gap,
    (
        "Incidental strings are not treated as lifecycle "
        "implementation."
    ),
)


# ------------------------------------------------------------
# 6. Prediction / outcome retention
# ------------------------------------------------------------

prediction_symbols = (
    explicit_runtime_symbol(
        "prediction"
    )
)

outcome_symbols = (
    explicit_runtime_symbol(
        "outcome"
    )
)


if (
    prediction_symbols
    and outcome_symbols
):

    prediction_class = "PARTIAL"

    prediction_gap = (
        "Prediction and outcome symbols exist, but durable "
        "retention/linkage is not proven."
    )

else:

    prediction_class = "MISSING"

    prediction_gap = (
        "Explicit prediction/outcome retention surface is "
        "absent."
    )


add_row(
    "A5-R06",
    "Prediction and outcome retention",
    prediction_class,
    {
        "prediction":
            tokens["prediction"],

        "outcome":
            tokens["outcome"],
    },
    prediction_gap,
    (
        "Text mentions alone do not prove retained prediction "
        "and outcome records."
    ),
)


# ------------------------------------------------------------
# 7. Drift evidence
# ------------------------------------------------------------

if explicit_runtime_symbol(
    "drift"
):

    drift_class = "PARTIAL"

    drift_gap = (
        "Drift runtime symbols exist, but multi-sample drift "
        "evidence semantics are not proven complete."
    )

else:

    drift_class = "MISSING"

    drift_gap = (
        "No explicit runtime drift evidence implementation "
        "is present."
    )


add_row(
    "A5-R07",
    "Drift evidence semantics",
    drift_class,
    {
        "drift":
            tokens["drift"],
    },
    drift_gap,
    (
        "Drift evidence must not be equated with proof of a "
        "platform rule change."
    ),
)


# ------------------------------------------------------------
# 8. Experiment / confounder boundaries
# ------------------------------------------------------------

confound_explicit = (
    explicit_runtime_symbol(
        "confound"
    )
    or any_runtime_reference(
        "confound"
    )
)


if (
    experiment_route_count >= 3
    and confound_explicit
):

    experiment_class = "PARTIAL"

    experiment_gap = (
        "Experiment runtime is substantial, but the frozen "
        "V2 causal/confounder contract still requires full "
        "requirement-level verification."
    )

elif experiment_route_count >= 3:

    experiment_class = "PARTIAL"

    experiment_gap = (
        "Experiment planning/evaluation runtime exists, but "
        "an explicit confounder boundary is not evidenced."
    )

else:

    experiment_class = "MISSING"

    experiment_gap = (
        "Experiment runtime surface is materially incomplete."
    )


add_row(
    "A5-R08",
    "Experiment evidence and confounder boundaries",
    experiment_class,
    {
        "experiment_routes":
            experiment_routes,

        "experiment_route_count":
            experiment_route_count,

        "experiment":
            tokens["experiment"],

        "confound":
            tokens["confound"],

        "causal":
            tokens["causal"],
    },
    experiment_gap,
    (
        "The presence of experiment APIs does not authorize "
        "automatic causal winner claims."
    ),
)


# ------------------------------------------------------------
# 9. Temporal event signature
# ------------------------------------------------------------

if explicit_runtime_symbol(
    "signature"
):

    signature_class = "PARTIAL"

    signature_gap = (
        "Signature symbols exist, but adaptive millisecond "
        "temporal-event representation is not proven."
    )

else:

    signature_class = "MISSING"

    signature_gap = (
        "No explicit runtime temporal event signature model "
        "is present."
    )


add_row(
    "A5-R09",
    "Temporal event signature representation",
    signature_class,
    {
        "signature":
            tokens["signature"],
    },
    signature_gap,
    (
        "Generic hashes/signatures are not automatically "
        "treated as temporal-event signatures."
    ),
)


# ------------------------------------------------------------
# 10. Taste-model separation
# ------------------------------------------------------------

if explicit_runtime_symbol(
    "taste"
):

    taste_class = "PARTIAL"

    taste_gap = (
        "Taste-related symbols exist, but explicit isolation "
        "from network-performance learning is not proven."
    )

else:

    taste_class = "MISSING"

    taste_gap = (
        "No explicit runtime MOLÖTOV Taste Model separation "
        "boundary is present."
    )


add_row(
    "A5-R10",
    "Taste-model separation boundary",
    taste_class,
    {
        "taste":
            tokens["taste"],
    },
    taste_gap,
    (
        "Performance evidence may not override brand/taste "
        "constraints."
    ),
)


# ------------------------------------------------------------
# 11. Evidence uncertainty / provenance
# ------------------------------------------------------------

provenance_explicit = (
    explicit_runtime_symbol(
        "provenance"
    )
)

uncertainty_explicit = (
    explicit_runtime_symbol(
        "uncertainty"
    )
)


if (
    provenance_explicit
    and uncertainty_explicit
):

    uncertainty_class = "PARTIAL"

    uncertainty_gap = (
        "Both concepts exist, but the complete frozen V2 "
        "uncertainty lifecycle is not proven."
    )

elif (
    provenance_explicit
    or any_runtime_reference(
        "provenance"
    )
):

    uncertainty_class = "PARTIAL"

    uncertainty_gap = (
        "Provenance is materially represented while explicit "
        "uncertainty semantics remain incomplete."
    )

else:

    uncertainty_class = "MISSING"

    uncertainty_gap = (
        "Evidence provenance and uncertainty semantics are "
        "not materially represented."
    )


add_row(
    "A5-R11",
    "Evidence uncertainty and provenance",
    uncertainty_class,
    {
        "provenance":
            tokens["provenance"],

        "uncertainty":
            tokens["uncertainty"],
    },
    uncertainty_gap,
    (
        "Evidence classes must remain epistemically distinct."
    ),
)


# ------------------------------------------------------------
# 12. Identity / versioning
# ------------------------------------------------------------

identity_reference = (
    any_runtime_reference(
        "identity"
    )
)

version_reference = (
    any_runtime_reference(
        "version"
    )
)


if (
    identity_reference
    and version_reference
):

    identity_class = "PARTIAL"

    identity_gap = (
        "Identity/versioning exists in the runtime, but the "
        "frozen V2 identity-finality issues are not proven "
        "fully resolved."
    )

else:

    identity_class = "MISSING"

    identity_gap = (
        "Explicit identity/versioning behavior required by "
        "the V2 contract is incomplete."
    )


add_row(
    "A5-R12",
    "Current identity and versioning behavior",
    identity_class,
    {
        "identity":
            tokens["identity"],

        "version":
            tokens["version"],
    },
    identity_gap,
    (
        "Existing V1 identities are not automatically treated "
        "as final V2 identity semantics."
    ),
)


# ------------------------------------------------------------
# 13. Numeric confidence decay
#
# R2 freeze explicitly defers this policy. This is not a
# runtime implementation failure in this stage.
# ------------------------------------------------------------

add_row(
    "A5-R13",
    "Numeric confidence-decay policy",
    "NOT_APPLICABLE",
    {
        "confidence":
            tokens["confidence"],

        "decay":
            tokens["decay"],

        "policy_status":
            "DEFERRED_BY_A5_FREEZE",
    },
    None,
    (
        "The post-A4 freeze explicitly defers numeric "
        "confidence-decay policy; A5 must not invent one."
    ),
)


counts = {
    value: sum(
        1
        for row in rows
        if row["classification"] == value
    )
    for value in sorted(ALLOWED)
}


implementation_candidates = [
    row["requirement_id"]
    for row in rows
    if row["classification"]
    in {
        "MISSING",
        "PARTIAL",
    }
]


already_satisfied = [
    row["requirement_id"]
    for row in rows
    if row["classification"]
    == "IMPLEMENTED"
]


deferred = [
    row["requirement_id"]
    for row in rows
    if row["classification"]
    == "NOT_APPLICABLE"
]


matrix_complete = (
    len(rows) == 13
    and all(
        row["classification"] in ALLOWED
        for row in rows
    )
    and sum(counts.values()) == len(rows)
)


result = {
    "contract_version":
        "SM3_BLACK_BOX_DYNAMICS_V2_RUNTIME_GAP_MATRIX_V1",

    "source_a2_sha256":
        sha(a2_path),

    "source_a3_sha256":
        sha(a3_path),

    "source_a1_evidence_sha256":
        sha(a1_path),

    "worker_sha256":
        sha(worker_path),

    "temporal_sha256":
        sha(temporal_path),

    "classification_policy":
        "CONSERVATIVE_STATIC_EVIDENCE_V1",

    "allowed_classifications":
        sorted(ALLOWED),

    "requirement_count":
        len(rows),

    "rows":
        rows,

    "classification_counts":
        counts,

    "implementation_candidate_requirement_ids":
        implementation_candidates,

    "already_satisfied_requirement_ids":
        already_satisfied,

    "deferred_requirement_ids":
        deferred,

    "temporal_runtime_evidence": {
        "temporal_contract_exact":
            temporal_exact,

        "evidence_temporal_call":
            evidence_temporal_call,

        "signal_temporal_call":
            signal_temporal_call,

        "snapshot_temporal_call":
            snapshot_temporal_call,

        "all_three_temporal_consumers":
            all_three_temporal_consumers,

        "temporal_import_usage":
            temporal_usage,
    },

    "experiment_runtime_evidence": {
        "routes":
            experiment_routes,

        "route_count":
            experiment_route_count,

        "confound_explicit":
            confound_explicit,
    },

    "implementation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "matrix_complete":
        matrix_complete,
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
    "REQUIREMENT_COUNT="
    + str(result["requirement_count"])
)


for classification in [
    "IMPLEMENTED",
    "PARTIAL",
    "MISSING",
    "SUPERSEDED",
    "NOT_APPLICABLE",
]:

    print(
        classification
        + "_COUNT="
        + str(
            counts.get(
                classification,
                0,
            )
        )
    )


print(
    "TEMPORAL_CONTRACT_EXACT="
    + str(temporal_exact)
)

print(
    "EVIDENCE_TEMPORAL_CALL="
    + str(evidence_temporal_call)
)

print(
    "SIGNAL_TEMPORAL_CALL="
    + str(signal_temporal_call)
)

print(
    "SNAPSHOT_TEMPORAL_CALL="
    + str(snapshot_temporal_call)
)

print(
    "EXPERIMENT_ROUTE_COUNT="
    + str(experiment_route_count)
)

print(
    "CONFOUND_EXPLICIT="
    + str(confound_explicit)
)

print(
    "MATRIX_COMPLETE="
    + str(matrix_complete)
)


if not matrix_complete:
    raise SystemExit(1)