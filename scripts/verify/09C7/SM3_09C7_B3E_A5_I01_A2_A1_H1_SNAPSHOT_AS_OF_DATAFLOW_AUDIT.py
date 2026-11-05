from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


contract_path = Path(sys.argv[1])
review_data_path = Path(sys.argv[2])
review_report_path = Path(sys.argv[3])
worker_path = Path(sys.argv[4])
temporal_path = Path(sys.argv[5])
output_path = Path(sys.argv[6])


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


def expr_text(
    node: ast.AST | None,
) -> str | None:

    if node is None:
        return None

    try:
        return ast.unparse(node)
    except Exception:
        return None


contract = load(contract_path)
review = load(review_data_path)
review_report = load(review_report_path)


# ============================================================
# 1. AUTHORIZE EXACT PRIOR FINDING SET
# ============================================================

expected_findings = {
    (
        "MEDIUM",
        "SNAPSHOT_KEYWORD_ONLY_CALL_STYLE_NOT_FROZEN",
        "SNAPSHOT",
    ),
    (
        "MEDIUM",
        "VACUOUS_VALIDATOR_KEY_COVERAGE",
        "EVIDENCE",
    ),
    (
        "MEDIUM",
        "VACUOUS_VALIDATOR_KEY_COVERAGE",
        "PREFERENCE_SIGNAL",
    ),
    (
        "HIGH",
        "SNAPSHOT_EVIDENCE_AS_OF_NOT_FORWARDED",
        "SNAPSHOT",
    ),
    (
        "HIGH",
        "SNAPSHOT_SIGNAL_AS_OF_NOT_FORWARDED",
        "SNAPSHOT",
    ),
}


actual_findings = {
    (
        item.get("severity"),
        item.get("code"),
        item.get("consumer"),
    )
    for item in review.get(
        "findings",
        [],
    )
}


prior_review_exact = (
    review.get("review_complete")
    is True
    and review.get("finding_count")
    == 5
    and review.get("high_finding_count")
    == 2
    and review.get("medium_finding_count")
    == 3
    and review.get("low_finding_count")
    == 0
    and actual_findings
    == expected_findings
    and review.get(
        "contract_accepted_without_revision"
    )
    is False
    and review_report.get(
        "a5_i01_a2_a1_pass"
    )
    is True
    and review_report.get(
        "classification"
    )
    == "A5_I01_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REVIEW_COMPLETE_WITH_FINDINGS"
)


if not prior_review_exact:
    raise RuntimeError(
        "PRIOR_REVIEW_NOT_EXACT"
    )


contract_authorized = (
    contract.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V1"
    and contract.get(
        "requirement_id"
    )
    == "A5-R04"
    and contract.get(
        "implementation_unit"
    )
    == "A5-I01"
    and contract.get(
        "authorization",
        {},
    ).get(
        "implementation_authorized"
    )
    is False
    and contract.get(
        "authorization",
        {},
    ).get(
        "candidate_generation_authorized"
    )
    is False
)


if not contract_authorized:
    raise RuntimeError(
        "A2_CONTRACT_NOT_AUTHORIZED"
    )


# ============================================================
# 2. PARSE TEMPORAL SOURCE
# ============================================================

source = temporal_path.read_text(
    encoding="utf-8-sig"
)

lines = source.splitlines()

tree = ast.parse(
    source,
    filename=str(
        temporal_path
    ),
)


functions: dict[
    str,
    ast.FunctionDef | ast.AsyncFunctionDef,
] = {}


for node in tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        functions[node.name] = node


snapshot_name = (
    "validate_snapshot_temporal_inputs"
)

evidence_name = (
    "validate_evidence_temporal"
)

signal_name = (
    "validate_signal_temporal"
)


snapshot_fn = functions.get(
    snapshot_name
)

evidence_fn = functions.get(
    evidence_name
)

signal_fn = functions.get(
    signal_name
)


if (
    snapshot_fn is None
    or evidence_fn is None
    or signal_fn is None
):
    raise RuntimeError(
        "REQUIRED_VALIDATOR_MISSING"
    )


# ============================================================
# 3. SNAPSHOT SIGNATURE
# ============================================================

snapshot_positional = [
    arg.arg
    for arg in (
        list(
            snapshot_fn.args.posonlyargs
        )
        + list(
            snapshot_fn.args.args
        )
    )
]

snapshot_keyword_only = [
    arg.arg
    for arg in snapshot_fn.args.kwonlyargs
]

snapshot_required_keyword_only = []


for index, arg in enumerate(
    snapshot_fn.args.kwonlyargs
):

    default = (
        snapshot_fn.args.kw_defaults[
            index
        ]
    )

    if default is None:
        snapshot_required_keyword_only.append(
            arg.arg
        )


snapshot_keyword_only_exact = (
    snapshot_positional == []
    and snapshot_keyword_only
    == [
        "as_of",
        "evidence",
        "signals",
    ]
    and snapshot_required_keyword_only
    == [
        "as_of",
        "evidence",
        "signals",
    ]
)


# ============================================================
# 4. BUILD SIMPLE LOCAL DATAFLOW GRAPH
# ============================================================

assignments: dict[
    str,
    list[ast.AST],
] = {}


def add_assignment(
    name: str,
    expression: ast.AST | None,
) -> None:

    if expression is None:
        return

    assignments.setdefault(
        name,
        [],
    ).append(
        expression
    )


for node in ast.walk(
    snapshot_fn
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
                add_assignment(
                    target.id,
                    node.value,
                )


    elif isinstance(
        node,
        ast.AnnAssign,
    ):

        if isinstance(
            node.target,
            ast.Name,
        ):
            add_assignment(
                node.target.id,
                node.value,
            )


    elif isinstance(
        node,
        ast.NamedExpr,
    ):

        if isinstance(
            node.target,
            ast.Name,
        ):
            add_assignment(
                node.target.id,
                node.value,
            )


def expression_depends_on_snapshot_as_of(
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


        next_seen = set(
            seen
        )

        next_seen.add(
            node.id
        )


        for expression in assignments.get(
            node.id,
            [],
        ):

            if expression_depends_on_snapshot_as_of(
                expression,
                next_seen,
            ):
                return True


        return False


    for child in ast.iter_child_nodes(
        node
    ):

        if expression_depends_on_snapshot_as_of(
            child,
            seen,
        ):
            return True


    return False


# ============================================================
# 5. BIND CALL ARGUMENT TO TARGET "as_of"
# ============================================================

def target_as_of_position(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int | None:

    positional = (
        list(
            fn.args.posonlyargs
        )
        + list(
            fn.args.args
        )
    )


    for index, arg in enumerate(
        positional
    ):

        if arg.arg == "as_of":
            return index


    return None


evidence_as_of_position = (
    target_as_of_position(
        evidence_fn
    )
)

signal_as_of_position = (
    target_as_of_position(
        signal_fn
    )
)


def bound_as_of_expression(
    call: ast.Call,
    target_fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[
    ast.AST | None,
    str,
]:

    for keyword in call.keywords:

        if keyword.arg == "as_of":

            return (
                keyword.value,
                "KEYWORD",
            )


    position = target_as_of_position(
        target_fn
    )


    if (
        position is not None
        and position < len(
            call.args
        )
    ):

        return (
            call.args[position],
            "POSITIONAL",
        )


    return (
        None,
        "UNBOUND_OR_DYNAMIC",
    )


# ============================================================
# 6. INSPECT ALL SNAPSHOT -> CHILD VALIDATOR CALLS
# ============================================================

call_records = []


for node in ast.walk(
    snapshot_fn
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    name = call_name(
        node
    )


    if name not in {
        evidence_name,
        signal_name,
    }:
        continue


    target_fn = (
        evidence_fn
        if name == evidence_name
        else signal_fn
    )


    as_of_expression, binding_style = (
        bound_as_of_expression(
            node,
            target_fn,
        )
    )


    depends_on_snapshot_as_of = (
        expression_depends_on_snapshot_as_of(
            as_of_expression
        )
    )


    call_records.append({
        "target":
            name,

        "line":
            getattr(
                node,
                "lineno",
                None,
            ),

        "call_source":
            expr_text(
                node
            ),

        "as_of_binding_style":
            binding_style,

        "as_of_expression":
            expr_text(
                as_of_expression
            ),

        "as_of_depends_on_snapshot_input":
            depends_on_snapshot_as_of,
    })


evidence_calls = [
    item
    for item in call_records
    if item["target"]
    == evidence_name
]

signal_calls = [
    item
    for item in call_records
    if item["target"]
    == signal_name
]


evidence_forwarding_proven = (
    len(
        evidence_calls
    )
    > 0
    and all(
        item[
            "as_of_depends_on_snapshot_input"
        ]
        is True
        for item in evidence_calls
    )
)


signal_forwarding_proven = (
    len(
        signal_calls
    )
    > 0
    and all(
        item[
            "as_of_depends_on_snapshot_input"
        ]
        is True
        for item in signal_calls
    )
)


all_snapshot_as_of_forwarding_proven = (
    evidence_forwarding_proven
    and signal_forwarding_proven
)


# ============================================================
# 7. SHOW ALIASES DERIVED FROM SNAPSHOT as_of
# ============================================================

as_of_derived_aliases = []


for name, expressions in sorted(
    assignments.items()
):

    if any(
        expression_depends_on_snapshot_as_of(
            expression
        )
        for expression in expressions
    ):

        as_of_derived_aliases.append({
            "name":
                name,

            "expressions":
                [
                    expr_text(
                        expression
                    )
                    for expression
                    in expressions
                ],
        })


# ============================================================
# 8. CLASSIFY THE TWO HIGH FINDINGS
# ============================================================

if all_snapshot_as_of_forwarding_proven:

    prior_high_findings_confirmed = False

    prior_high_findings_false_positive = True

    high_root_cause = (
        "A2_A1_FORWARDING_CHECK_REQUIRED_LITERAL_VARIABLE_NAME_AS_OF"
    )

else:

    prior_high_findings_confirmed = True

    prior_high_findings_false_positive = False

    high_root_cause = (
        "SNAPSHOT_CHILD_VALIDATORS_NOT_PROVEN_TO_RECEIVE_REQUEST_AS_OF_DERIVATION"
    )


# ============================================================
# 9. MEDIUM FINDINGS ARE INDEPENDENTLY CONFIRMED
# ============================================================

medium_codes = {
    (
        item.get(
            "code"
        ),
        item.get(
            "consumer"
        ),
    )
    for item in review.get(
        "findings",
        [],
    )
    if item.get(
        "severity"
    )
    == "MEDIUM"
}


expected_medium_codes = {
    (
        "SNAPSHOT_KEYWORD_ONLY_CALL_STYLE_NOT_FROZEN",
        "SNAPSHOT",
    ),
    (
        "VACUOUS_VALIDATOR_KEY_COVERAGE",
        "EVIDENCE",
    ),
    (
        "VACUOUS_VALIDATOR_KEY_COVERAGE",
        "PREFERENCE_SIGNAL",
    ),
}


medium_findings_exact = (
    medium_codes
    == expected_medium_codes
)


# ============================================================
# 10. FINAL DIAGNOSTIC CLASSIFICATION
# ============================================================

diagnostic_complete = all([
    prior_review_exact,
    contract_authorized,
    snapshot_keyword_only_exact,
    len(
        evidence_calls
    )
    > 0,
    len(
        signal_calls
    )
    > 0,
    medium_findings_exact,
])


if not diagnostic_complete:

    classification = (
        "A5_I01_SNAPSHOT_AS_OF_DATAFLOW_AUDIT_INCOMPLETE"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A2-A1-H1_REMEDIATION_REQUIRED"
    )

elif prior_high_findings_false_positive:

    classification = (
        "A5_I01_SNAPSHOT_AS_OF_HIGH_FINDINGS_ARE_ANALYZER_FALSE_POSITIVES"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A2-R1_TEMPORAL_BINDING_CONTRACT_REMEDIATION"
    )

else:

    classification = (
        "A5_I01_SNAPSHOT_AS_OF_FORWARDING_BLOCKER_CONFIRMED"
    )

    next_gate = (
        "09C7-B3E-A5-I01-A2-A1-H2_SNAPSHOT_TEMPORAL_BEHAVIOR_DECISION"
    )


result = {
    "contract_version":
        "SM3_A5_I01_SNAPSHOT_AS_OF_DATAFLOW_AUDIT_V1",

    "source_binding_contract_sha256":
        sha(
            contract_path
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

    "prior_review_exact":
        prior_review_exact,

    "contract_authorized":
        contract_authorized,

    "snapshot_positional_parameters":
        snapshot_positional,

    "snapshot_keyword_only_parameters":
        snapshot_keyword_only,

    "snapshot_required_keyword_only_parameters":
        snapshot_required_keyword_only,

    "snapshot_keyword_only_exact":
        snapshot_keyword_only_exact,

    "snapshot_source_lines": {
        "start":
            getattr(
                snapshot_fn,
                "lineno",
                None,
            ),

        "end":
            getattr(
                snapshot_fn,
                "end_lineno",
                None,
            ),
    },

    "snapshot_source":
        "\n".join(
            lines[
                snapshot_fn.lineno - 1:
                snapshot_fn.end_lineno
            ]
        ),

    "as_of_derived_aliases":
        as_of_derived_aliases,

    "child_validator_calls":
        call_records,

    "evidence_child_call_count":
        len(
            evidence_calls
        ),

    "signal_child_call_count":
        len(
            signal_calls
        ),

    "evidence_as_of_forwarding_proven":
        evidence_forwarding_proven,

    "signal_as_of_forwarding_proven":
        signal_forwarding_proven,

    "all_snapshot_as_of_forwarding_proven":
        all_snapshot_as_of_forwarding_proven,

    "prior_high_findings_confirmed":
        prior_high_findings_confirmed,

    "prior_high_findings_false_positive":
        prior_high_findings_false_positive,

    "high_finding_root_cause":
        high_root_cause,

    "medium_findings_exact":
        medium_findings_exact,

    "confirmed_contract_remediation_requirements": [
        "FREEZE_SNAPSHOT_CALL_STYLE_AS_KEYWORD_ONLY_EXACT",
        "REPLACE_EVIDENCE_VACUOUS_KEYS_WITH_EXPLICIT_TEMPORAL_INPUT_FIELDS",
        "REPLACE_SIGNAL_VACUOUS_KEYS_WITH_EXPLICIT_TEMPORAL_INPUT_FIELDS",
    ],

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "diagnostic_complete":
        diagnostic_complete,

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
    "PRIOR_REVIEW_EXACT="
    + str(
        prior_review_exact
    )
)

print(
    "CONTRACT_AUTHORIZED="
    + str(
        contract_authorized
    )
)

print(
    "SNAPSHOT_POSITIONAL_PARAMETERS="
    + "|".join(
        snapshot_positional
    )
)

print(
    "SNAPSHOT_KEYWORD_ONLY_PARAMETERS="
    + "|".join(
        snapshot_keyword_only
    )
)

print(
    "SNAPSHOT_REQUIRED_KEYWORD_ONLY_PARAMETERS="
    + "|".join(
        snapshot_required_keyword_only
    )
)

print(
    "SNAPSHOT_KEYWORD_ONLY_EXACT="
    + str(
        snapshot_keyword_only_exact
    )
)


print(
    "AS_OF_DERIVED_ALIAS_COUNT="
    + str(
        len(
            as_of_derived_aliases
        )
    )
)


for item in as_of_derived_aliases:

    print(
        "AS_OF_DERIVED_ALIAS="
        + item["name"]
        + "|"
        + "|".join(
            str(value)
            for value
            in item["expressions"]
        )
    )


for item in call_records:

    print("")

    print(
        "CHILD_VALIDATOR="
        + item["target"]
    )

    print(
        "CHILD_CALL_LINE="
        + str(
            item["line"]
        )
    )

    print(
        "CHILD_CALL_SOURCE="
        + str(
            item["call_source"]
        )
    )

    print(
        "CHILD_AS_OF_BINDING_STYLE="
        + item[
            "as_of_binding_style"
        ]
    )

    print(
        "CHILD_AS_OF_EXPRESSION="
        + str(
            item[
                "as_of_expression"
            ]
        )
    )

    print(
        "CHILD_AS_OF_DEPENDS_ON_SNAPSHOT_INPUT="
        + str(
            item[
                "as_of_depends_on_snapshot_input"
            ]
        )
    )


print("")

print(
    "EVIDENCE_CHILD_CALL_COUNT="
    + str(
        len(
            evidence_calls
        )
    )
)

print(
    "SIGNAL_CHILD_CALL_COUNT="
    + str(
        len(
            signal_calls
        )
    )
)

print(
    "EVIDENCE_AS_OF_FORWARDING_PROVEN="
    + str(
        evidence_forwarding_proven
    )
)

print(
    "SIGNAL_AS_OF_FORWARDING_PROVEN="
    + str(
        signal_forwarding_proven
    )
)

print(
    "ALL_SNAPSHOT_AS_OF_FORWARDING_PROVEN="
    + str(
        all_snapshot_as_of_forwarding_proven
    )
)

print(
    "PRIOR_HIGH_FINDINGS_CONFIRMED="
    + str(
        prior_high_findings_confirmed
    )
)

print(
    "PRIOR_HIGH_FINDINGS_FALSE_POSITIVE="
    + str(
        prior_high_findings_false_positive
    )
)

print(
    "HIGH_FINDING_ROOT_CAUSE="
    + high_root_cause
)

print(
    "MEDIUM_FINDINGS_EXACT="
    + str(
        medium_findings_exact
    )
)

print(
    "DIAGNOSTIC_COMPLETE="
    + str(
        diagnostic_complete
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


if not diagnostic_complete:
    raise SystemExit(1)