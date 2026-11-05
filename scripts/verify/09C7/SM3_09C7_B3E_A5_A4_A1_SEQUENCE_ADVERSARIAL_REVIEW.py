from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


freeze_path = Path(sys.argv[1])
matrix_path = Path(sys.argv[2])
reattack_path = Path(sys.argv[3])
output_path = Path(sys.argv[4])


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


freeze = load(freeze_path)
matrix = load(matrix_path)
reattack = load(reattack_path)

sequence = freeze["sequence"]

units = {
    unit["unit_id"]: unit
    for unit in sequence
}

order = {
    unit["unit_id"]: int(unit["order"])
    for unit in sequence
}

prerequisites = {
    unit["unit_id"]: set(unit.get("prerequisites", []))
    for unit in sequence
}


findings: list[dict[str, Any]] = []


def finding(
    severity: str,
    code: str,
    unit_id: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> None:

    findings.append({
        "severity": severity,
        "code": code,
        "unit_id": unit_id,
        "message": message,
        "evidence": evidence or {},
    })


# ============================================================
# BASIC GRAPH ATTACK
# ============================================================

expected_units = {
    "A5-I01",
    "A5-I02",
    "A5-I03",
    "A5-I04",
    "A5-I05",
    "A5-I06",
    "A5-I07",
    "A5-I08",
    "A5-I09",
    "A5-I10",
    "A5-I11",
    "A5-I12",
}


if set(units) != expected_units:
    finding(
        "HIGH",
        "UNIT_SET_CHANGED",
        "GLOBAL",
        "Frozen implementation unit set is not the expected 12-unit set.",
    )


if sorted(order.values()) != list(range(1, 13)):
    finding(
        "HIGH",
        "ORDER_SEQUENCE_INVALID",
        "GLOBAL",
        "Implementation orders are not exactly 1 through 12.",
    )


for unit_id, deps in prerequisites.items():

    for dep in deps:

        if dep not in units:
            finding(
                "HIGH",
                "UNKNOWN_PREREQUISITE",
                unit_id,
                f"Unknown prerequisite {dep}.",
            )

            continue

        if order[dep] >= order[unit_id]:
            finding(
                "HIGH",
                "NON_CAUSAL_FORWARD_PREREQUISITE",
                unit_id,
                f"Prerequisite {dep} does not precede {unit_id}.",
            )


# ============================================================
# DIRECT SEMANTIC DEPENDENCY CONTRACT
#
# These edges are requirements of the frozen architecture,
# not merely consequences of current numeric order.
# ============================================================

required_direct_edges = {
    "A5-I03": {
        "A5-I02",
    },

    "A5-I05": {
        "A5-I01",
        "A5-I02",
        "A5-I03",
    },

    "A5-I06": {
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I04",
    },

    "A5-I07": {
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I05",
        "A5-I06",
    },

    "A5-I08": {
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I05",
    },

    "A5-I09": {
        "A5-I04",
        "A5-I05",
        "A5-I06",
        "A5-I07",
        "A5-I08",
    },

    "A5-I10": {
        "A5-I09",
    },

    "A5-I11": {
        "A5-I07",
        "A5-I09",
        "A5-I10",
    },

    "A5-I12": {
        "A5-I03",
        "A5-I04",
        "A5-I09",
        "A5-I10",
        "A5-I11",
    },
}


missing_direct_edges: list[str] = []


for unit_id, required in required_direct_edges.items():

    actual = prerequisites.get(
        unit_id,
        set(),
    )

    missing = sorted(
        required - actual
    )

    for dep in missing:

        edge = dep + "->" + unit_id

        missing_direct_edges.append(edge)

        severity = "MEDIUM"

        code = "REQUIRED_SEMANTIC_PREREQUISITE_MISSING"

        message = (
            f"{unit_id} is ordered after {dep}, but the semantic "
            f"dependency is not encoded directly in prerequisites."
        )

        if (
            dep == "A5-I04"
            and unit_id == "A5-I06"
        ):

            code = "TASTE_BOUNDARY_NOT_ENCODED_FOR_PREFERENCE_SIGNAL"

            message = (
                "A5-I06 promises platform-preference semantics without "
                "conflating network evidence with taste, but the explicit "
                "Taste Model separation boundary A5-I04 is not declared "
                "as a prerequisite."
            )

        finding(
            severity,
            code,
            unit_id,
            message,
            {
                "missing_edge": edge,
                "current_unit_order": order[unit_id],
                "dependency_order": order[dep],
            },
        )


# ============================================================
# REQUIREMENT / UNIT IDENTITY ATTACK
# ============================================================

expected_mapping = {
    "A5-I01": ("A5-R04", "TEMPORAL_CONSUMER_ENFORCEMENT"),
    "A5-I02": ("A5-R12", "IDENTITY_VERSIONING_FINALITY"),
    "A5-I03": ("A5-R11", "EVIDENCE_UNCERTAINTY_PROVENANCE"),
    "A5-I04": ("A5-R10", "TASTE_MODEL_SEPARATION_BOUNDARY"),
    "A5-I05": ("A5-R01", "PLATFORM_DYNAMICS_EVIDENCE_V2"),
    "A5-I06": ("A5-R02", "PLATFORM_PREFERENCE_SIGNAL_V2"),
    "A5-I07": ("A5-R03", "PLATFORM_DYNAMICS_SNAPSHOT_V2"),
    "A5-I08": ("A5-R09", "TEMPORAL_EVENT_SIGNATURE"),
    "A5-I09": ("A5-R05", "HYPOTHESIS_REVISION_LIFECYCLE"),
    "A5-I10": ("A5-R06", "PREDICTION_OUTCOME_RETENTION"),
    "A5-I11": ("A5-R07", "DRIFT_EVIDENCE"),
    "A5-I12": ("A5-R08", "EXPERIMENT_CONFOUNDER_BOUNDARIES"),
}


for unit_id, expected in expected_mapping.items():

    unit = units.get(unit_id)

    if unit is None:
        continue

    if unit["requirement_id"] != expected[0]:
        finding(
            "HIGH",
            "UNIT_REQUIREMENT_MAPPING_CHANGED",
            unit_id,
            "Unit-to-requirement mapping differs from the validated matrix.",
        )

    if unit["name"] != expected[1]:
        finding(
            "HIGH",
            "UNIT_NAME_CHANGED",
            unit_id,
            "Frozen implementation unit name differs from the expected architecture.",
        )

    if unit.get("mutation_scope") != "WORKER_CANDIDATE_ONLY":
        finding(
            "HIGH",
            "UNIT_MUTATION_SCOPE_NOT_CANDIDATE_ONLY",
            unit_id,
            "Every implementation unit must remain candidate-only before promotion.",
        )


# ============================================================
# DEFERRED POLICY ATTACK
# ============================================================

deferred = freeze.get(
    "deferred_requirements",
    [],
)


if len(deferred) != 1:
    finding(
        "HIGH",
        "DEFERRED_SET_INVALID",
        "GLOBAL",
        "Exactly one deferred requirement is expected.",
    )
else:

    item = deferred[0]

    if (
        item.get("requirement_id") != "A5-R13"
        or item.get("classification") != "NOT_APPLICABLE"
        or item.get("status") != "DEFERRED_BY_FROZEN_POLICY"
    ):
        finding(
            "HIGH",
            "CONFIDENCE_DECAY_DEFERMENT_CHANGED",
            "A5-R13",
            "Numeric confidence-decay must remain deferred.",
        )


# ============================================================
# EXECUTION POLICY ATTACK
# ============================================================

policy = freeze["execution_policy"]


policy_expectations = {
    "implementation_mode":
        "ONE_UNIT_AT_A_TIME",

    "canonical_source_mutation_allowed":
        False,

    "production_mutation_allowed":
        False,

    "direct_production_edit_allowed":
        False,

    "candidate_first_required":
        True,

    "static_attack_required":
        True,

    "adversarial_review_required":
        True,

    "isolated_dynamic_test_required":
        True,

    "canonical_materialization_requires_separate_gate":
        True,

    "production_deployment_requires_separate_gate":
        True,

    "rollback_evidence_required":
        True,

    "fail_closed":
        True,
}


for key, expected in policy_expectations.items():

    if policy.get(key) != expected:
        finding(
            "HIGH",
            "EXECUTION_POLICY_REGRESSION",
            "GLOBAL",
            f"Execution policy field {key} changed.",
            {
                "expected": expected,
                "actual": policy.get(key),
            },
        )


# ============================================================
# MATRIX ALIGNMENT ATTACK
# ============================================================

matrix_rows = {
    row["requirement_id"]: row
    for row in matrix["rows"]
}


for unit in sequence:

    requirement_id = unit["requirement_id"]

    row = matrix_rows.get(
        requirement_id
    )

    if row is None:
        finding(
            "HIGH",
            "MATRIX_REQUIREMENT_MISSING",
            unit["unit_id"],
            f"{requirement_id} is absent from matrix V2.",
        )
        continue

    if row["classification"] != unit["classification"]:
        finding(
            "HIGH",
            "SEQUENCE_CLASSIFICATION_DIVERGENCE",
            unit["unit_id"],
            "Sequence classification differs from adversarially validated matrix V2.",
            {
                "matrix": row["classification"],
                "sequence": unit["classification"],
            },
        )


# ============================================================
# ARCHITECTURAL ORDER ATTACK
# ============================================================

order_rules = [
    ("A5-I01", "A5-I05", "TEMPORAL_BEFORE_EVIDENCE_V2"),
    ("A5-I01", "A5-I06", "TEMPORAL_BEFORE_SIGNAL_V2"),
    ("A5-I01", "A5-I07", "TEMPORAL_BEFORE_SNAPSHOT_V2"),
    ("A5-I02", "A5-I03", "IDENTITY_BEFORE_PROVENANCE"),
    ("A5-I03", "A5-I05", "PROVENANCE_BEFORE_EVIDENCE_V2"),
    ("A5-I03", "A5-I06", "PROVENANCE_BEFORE_SIGNAL_V2"),
    ("A5-I04", "A5-I06", "TASTE_BOUNDARY_BEFORE_PREFERENCE_SIGNAL"),
    ("A5-I04", "A5-I09", "TASTE_BOUNDARY_BEFORE_HYPOTHESIS"),
    ("A5-I05", "A5-I07", "EVIDENCE_BEFORE_SNAPSHOT"),
    ("A5-I06", "A5-I07", "SIGNAL_BEFORE_SNAPSHOT"),
    ("A5-I07", "A5-I09", "SNAPSHOT_BEFORE_HYPOTHESIS"),
    ("A5-I08", "A5-I09", "TEMPORAL_SIGNATURE_BEFORE_HYPOTHESIS"),
    ("A5-I09", "A5-I10", "HYPOTHESIS_BEFORE_PREDICTION"),
    ("A5-I10", "A5-I11", "PREDICTION_BEFORE_DRIFT"),
    ("A5-I11", "A5-I12", "DRIFT_BEFORE_EXPERIMENT_CLOSEOUT"),
]


for before, after, code in order_rules:

    if (
        before not in order
        or after not in order
        or order[before] >= order[after]
    ):
        finding(
            "HIGH",
            code + "_ORDER_VIOLATION",
            after,
            f"{before} must precede {after}.",
        )


# ============================================================
# REVIEW RESULT
# ============================================================

severity_counts = {
    "HIGH": 0,
    "MEDIUM": 0,
    "LOW": 0,
}


for item in findings:

    if item["severity"] in severity_counts:
        severity_counts[item["severity"]] += 1


high_clean = (
    severity_counts["HIGH"] == 0
)

medium_clean = (
    severity_counts["MEDIUM"] == 0
)


sequence_accepted_without_revision = (
    high_clean
    and medium_clean
)


review_complete = (
    len(sequence) == 12
    and len(matrix_rows) == 13
)


result = {
    "contract_version":
        "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REVIEW_V1",

    "source_freeze_sha256":
        sha(freeze_path),

    "source_matrix_v2_sha256":
        sha(matrix_path),

    "source_reattack_sha256":
        sha(reattack_path),

    "review_method":
        "DEPENDENCY_GRAPH_PLUS_ARCHITECTURAL_SEMANTIC_ATTACK_V1",

    "sequence_unit_count":
        len(sequence),

    "required_direct_edge_count":
        sum(
            len(value)
            for value
            in required_direct_edges.values()
        ),

    "missing_required_direct_edge_count":
        len(missing_direct_edges),

    "missing_required_direct_edges":
        sorted(missing_direct_edges),

    "finding_count":
        len(findings),

    "severity_counts":
        severity_counts,

    "findings":
        findings,

    "sequence_accepted_without_revision":
        sequence_accepted_without_revision,

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
    "MISSING_REQUIRED_DIRECT_EDGE_COUNT="
    + str(
        len(missing_direct_edges)
    )
)

for edge in sorted(
    missing_direct_edges
):
    print(
        "MISSING_REQUIRED_EDGE="
        + edge
    )

print(
    "SEQUENCE_ACCEPTED_WITHOUT_REVISION="
    + str(
        sequence_accepted_without_revision
    )
)


if not review_complete:
    raise SystemExit(1)