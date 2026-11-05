from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_path = Path(sys.argv[1])
repaired_path = Path(sys.argv[2])
repair_report_path = Path(sys.argv[3])
h2_path = Path(sys.argv[4])
matrix_path = Path(sys.argv[5])
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


def canonical(value: Any) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


source = load(source_path)
repaired = load(repaired_path)
repair_report = load(repair_report_path)
h2 = load(h2_path)
matrix = load(matrix_path)


findings: list[dict[str, Any]] = []


def finding(
    severity: str,
    code: str,
    message: str,
    unit_id: str = "GLOBAL",
) -> None:

    findings.append({
        "severity": severity,
        "code": code,
        "unit_id": unit_id,
        "message": message,
    })


# ============================================================
# 1. LINEAGE / ENCODING AUTHORITY
# ============================================================

if repaired.get(
    "contract_version"
) != "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_FREEZE_V2":

    finding(
        "HIGH",
        "REPAIRED_FREEZE_CONTRACT_INVALID",
        "Repaired sequence freeze contract version is invalid.",
    )


if repaired.get("revision") != 2:

    finding(
        "HIGH",
        "REPAIRED_FREEZE_REVISION_INVALID",
        "Repaired freeze must remain revision 2.",
    )


if repaired.get(
    "artifact_encoding"
) != "UTF-8":

    finding(
        "HIGH",
        "REPAIRED_FREEZE_ENCODING_NOT_UTF8",
        "Authoritative repaired freeze is not marked UTF-8.",
    )


if repaired.get(
    "artifact_encoding_repair_revision"
) != 1:

    finding(
        "HIGH",
        "ENCODING_REPAIR_REVISION_INVALID",
        "Encoding repair revision metadata is invalid.",
    )


if repair_report.get(
    "a5_a4_r1_r2_pass"
) is not True:

    finding(
        "HIGH",
        "ENCODING_REPAIR_GATE_NOT_PASS",
        "Encoding repair gate did not close PASS.",
    )


if repair_report.get(
    "classification"
) != "A5_SEQUENCE_ARTIFACT_ENCODING_REPAIRED_WITH_SEMANTIC_SCOPE_PRESERVED":

    finding(
        "HIGH",
        "ENCODING_REPAIR_CLASSIFICATION_INVALID",
        "Encoding repair report classification is invalid.",
    )


if repair_report.get(
    "repaired_freeze_sha256"
) != sha(repaired_path):

    finding(
        "HIGH",
        "REPAIRED_FREEZE_HASH_LINEAGE_INVALID",
        "Repair report does not authorize this repaired freeze hash.",
    )


if h2.get(
    "encoding_corruption_confirmed"
) is not True:

    finding(
        "HIGH",
        "H2_ENCODING_CORRUPTION_NOT_CONFIRMED",
        "H2 did not prove the encoding corruption.",
    )


if h2.get(
    "architectural_scope_changed"
) is not False:

    finding(
        "HIGH",
        "H2_ARCHITECTURAL_SCOPE_CHANGED",
        "H2 unexpectedly indicates architectural scope change.",
    )


if h2.get(
    "project_regression"
) is not False:

    finding(
        "HIGH",
        "H2_PROJECT_REGRESSION",
        "H2 unexpectedly indicates project regression.",
    )


# ============================================================
# 2. UNIT SET / ORDER / IDENTITY
# ============================================================

expected = [
    (
        "A5-I01",
        "A5-R04",
        "PARTIAL",
        "TEMPORAL_CONSUMER_ENFORCEMENT",
    ),
    (
        "A5-I02",
        "A5-R12",
        "PARTIAL",
        "IDENTITY_VERSIONING_FINALITY",
    ),
    (
        "A5-I03",
        "A5-R11",
        "PARTIAL",
        "EVIDENCE_UNCERTAINTY_PROVENANCE",
    ),
    (
        "A5-I04",
        "A5-R10",
        "MISSING",
        "TASTE_MODEL_SEPARATION_BOUNDARY",
    ),
    (
        "A5-I05",
        "A5-R01",
        "PARTIAL",
        "PLATFORM_DYNAMICS_EVIDENCE_V2",
    ),
    (
        "A5-I06",
        "A5-R02",
        "PARTIAL",
        "PLATFORM_PREFERENCE_SIGNAL_V2",
    ),
    (
        "A5-I07",
        "A5-R03",
        "PARTIAL",
        "PLATFORM_DYNAMICS_SNAPSHOT_V2",
    ),
    (
        "A5-I08",
        "A5-R09",
        "MISSING",
        "TEMPORAL_EVENT_SIGNATURE",
    ),
    (
        "A5-I09",
        "A5-R05",
        "MISSING",
        "HYPOTHESIS_REVISION_LIFECYCLE",
    ),
    (
        "A5-I10",
        "A5-R06",
        "MISSING",
        "PREDICTION_OUTCOME_RETENTION",
    ),
    (
        "A5-I11",
        "A5-R07",
        "MISSING",
        "DRIFT_EVIDENCE",
    ),
    (
        "A5-I12",
        "A5-R08",
        "PARTIAL",
        "EXPERIMENT_CONFOUNDER_BOUNDARIES",
    ),
]


sequence = list(
    repaired.get(
        "sequence",
        [],
    )
)


if len(sequence) != 12:

    finding(
        "HIGH",
        "SEQUENCE_UNIT_COUNT_INVALID",
        "Repaired sequence must contain exactly 12 units.",
    )


units: dict[str, dict[str, Any]] = {}


for index, spec in enumerate(
    expected,
    start=1,
):

    unit_id = spec[0]
    requirement_id = spec[1]
    classification = spec[2]
    name = spec[3]

    matches = [
        unit
        for unit in sequence
        if unit.get("unit_id")
        == unit_id
    ]

    if len(matches) != 1:

        finding(
            "HIGH",
            "UNIT_CARDINALITY_INVALID",
            f"{unit_id} does not occur exactly once.",
            unit_id,
        )

        continue

    unit = matches[0]

    units[unit_id] = unit

    if unit.get("order") != index:

        finding(
            "HIGH",
            "UNIT_ORDER_INVALID",
            f"{unit_id} order changed.",
            unit_id,
        )

    if unit.get(
        "requirement_id"
    ) != requirement_id:

        finding(
            "HIGH",
            "UNIT_REQUIREMENT_MAPPING_INVALID",
            f"{unit_id} requirement mapping changed.",
            unit_id,
        )

    if unit.get(
        "classification"
    ) != classification:

        finding(
            "HIGH",
            "UNIT_CLASSIFICATION_INVALID",
            f"{unit_id} classification changed.",
            unit_id,
        )

    if unit.get(
        "name"
    ) != name:

        finding(
            "HIGH",
            "UNIT_NAME_INVALID",
            f"{unit_id} name changed.",
            unit_id,
        )

    if unit.get(
        "mutation_scope"
    ) != "WORKER_CANDIDATE_ONLY":

        finding(
            "HIGH",
            "MUTATION_SCOPE_INVALID",
            f"{unit_id} is not candidate-only.",
            unit_id,
        )


# ============================================================
# 3. MATRIX ALIGNMENT
# ============================================================

matrix_rows = {
    row["requirement_id"]:
        row
    for row in matrix.get(
        "rows",
        [],
    )
}


for unit_id, unit in units.items():

    requirement_id = unit[
        "requirement_id"
    ]

    row = matrix_rows.get(
        requirement_id
    )

    if row is None:

        finding(
            "HIGH",
            "MATRIX_REQUIREMENT_MISSING",
            f"{requirement_id} missing from matrix V2.",
            unit_id,
        )

        continue

    if row.get(
        "classification"
    ) != unit.get(
        "classification"
    ):

        finding(
            "HIGH",
            "MATRIX_CLASSIFICATION_DIVERGENCE",
            f"{unit_id} diverges from matrix V2 classification.",
            unit_id,
        )


# ============================================================
# 4. SOURCE -> REPAIRED SEMANTIC CHANGE SCOPE
# ============================================================

source_units = {
    unit["unit_id"]: unit
    for unit in source.get(
        "sequence",
        [],
    )
}


if set(source_units) != set(units):

    finding(
        "HIGH",
        "SOURCE_REPAIRED_UNIT_SET_CHANGED",
        "V1 and repaired V2 unit sets differ.",
    )


semantic_changed_ids = []


for unit_id in sorted(
    set(source_units)
    & set(units)
):

    if canonical(
        source_units[unit_id]
    ) != canonical(
        units[unit_id]
    ):

        semantic_changed_ids.append(
            unit_id
        )


if semantic_changed_ids != [
    "A5-I06"
]:

    finding(
        "HIGH",
        "SEMANTIC_REVISION_SCOPE_EXPANDED",
        (
            "Only A5-I06 may differ semantically from "
            "the original sequence freeze."
        ),
    )


# ============================================================
# 5. I04 UNICODE / EXACT PRESERVATION
# ============================================================

if (
    "A5-I04" in source_units
    and "A5-I04" in units
):

    source_i04 = source_units[
        "A5-I04"
    ]

    repaired_i04 = units[
        "A5-I04"
    ]

    if source_i04 != repaired_i04:

        finding(
            "HIGH",
            "I04_NOT_EXACT_FROM_SOURCE",
            "A5-I04 differs from clean source freeze.",
            "A5-I04",
        )

    purpose = str(
        repaired_i04.get(
            "purpose",
            "",
        )
    )

    if (
        "MOLÖTOV" not in purpose
        or "MOLÃ" in purpose
    ):

        finding(
            "HIGH",
            "I04_UNICODE_CORRUPTION_PRESENT",
            "A5-I04 purpose still contains encoding corruption.",
            "A5-I04",
        )


# ============================================================
# 6. I06 EXACT AUTHORIZED CHANGE
# ============================================================

if (
    "A5-I06" in source_units
    and "A5-I06" in units
):

    before = copy.deepcopy(
        source_units["A5-I06"]
    )

    after = copy.deepcopy(
        units["A5-I06"]
    )

    before_prereq = before.pop(
        "prerequisites",
        [],
    )

    after_prereq = after.pop(
        "prerequisites",
        [],
    )

    if before != after:

        finding(
            "HIGH",
            "I06_NON_PREREQUISITE_FIELD_CHANGED",
            "A5-I06 changed outside prerequisites.",
            "A5-I06",
        )

    if before_prereq != [
        "A5-I01",
        "A5-I02",
        "A5-I03",
    ]:

        finding(
            "HIGH",
            "I06_SOURCE_PREREQUISITES_INVALID",
            "Original I06 prerequisites are not expected.",
            "A5-I06",
        )

    if after_prereq != [
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I04",
    ]:

        finding(
            "HIGH",
            "I06_REPAIRED_PREREQUISITES_INVALID",
            "Repaired I06 prerequisites are not exact.",
            "A5-I06",
        )


# ============================================================
# 7. REQUIRED DIRECT EDGES
# ============================================================

required_edges = {
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


order_by_unit = {
    unit_id: int(
        unit["order"]
    )
    for unit_id, unit in units.items()
}


missing_required_edges = []
unknown_dependencies = []
forward_dependencies = []


for unit_id, unit in units.items():

    actual = list(
        unit.get(
            "prerequisites",
            [],
        )
        or []
    )

    for dep in actual:

        if dep not in units:

            unknown_dependencies.append(
                dep
                + "->"
                + unit_id
            )

            continue

        if (
            order_by_unit[dep]
            >= order_by_unit[unit_id]
        ):

            forward_dependencies.append(
                dep
                + "->"
                + unit_id
            )


for unit_id, required in required_edges.items():

    unit = units.get(
        unit_id
    )

    if unit is None:

        missing_required_edges.append(
            "MISSING_UNIT->"
            + unit_id
        )

        continue

    actual = set(
        unit.get(
            "prerequisites",
            [],
        )
        or []
    )

    for dep in sorted(
        required - actual
    ):

        missing_required_edges.append(
            dep
            + "->"
            + unit_id
        )


if missing_required_edges:

    finding(
        "MEDIUM",
        "REQUIRED_SEMANTIC_EDGE_MISSING",
        "Required semantic dependency edge is missing.",
    )


if unknown_dependencies:

    finding(
        "HIGH",
        "UNKNOWN_DEPENDENCY_PRESENT",
        "Dependency graph contains unknown units.",
    )


if forward_dependencies:

    finding(
        "HIGH",
        "FORWARD_DEPENDENCY_PRESENT",
        "Dependency graph contains forward prerequisites.",
    )


# ============================================================
# 8. DEFERRED POLICY
# ============================================================

deferred = list(
    repaired.get(
        "deferred_requirements",
        [],
    )
)


deferred_pass = (
    len(deferred) == 1
    and deferred[0].get(
        "requirement_id"
    ) == "A5-R13"
    and deferred[0].get(
        "classification"
    ) == "NOT_APPLICABLE"
    and deferred[0].get(
        "status"
    ) == "DEFERRED_BY_FROZEN_POLICY"
)


if not deferred_pass:

    finding(
        "HIGH",
        "CONFIDENCE_DECAY_DEFERMENT_REGRESSION",
        "A5-R13 deferred policy changed.",
    )


# ============================================================
# 9. EXECUTION POLICY
# ============================================================

policy = repaired.get(
    "execution_policy",
    {},
)


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

    "preserve_existing_routes":
        True,

    "preserve_existing_contracts_unless_explicitly_versioned":
        True,

    "fail_closed":
        True,

    "provider_calls_during_implementation_unit":
        False,

    "model_calls_during_implementation_unit":
        False,
}


execution_policy_pass = all(
    policy.get(key) == expected_value
    for key, expected_value
    in policy_expectations.items()
)


if not execution_policy_pass:

    finding(
        "HIGH",
        "EXECUTION_POLICY_REGRESSION",
        "Candidate-first fail-closed policy changed.",
    )


# ============================================================
# 10. AUTHORIZATION MUST REMAIN CLOSED
# ============================================================

authorization_closed = (
    repaired.get(
        "implementation_authorized"
    )
    is False
    and repaired.get(
        "canonical_source_mutation_authorized"
    )
    is False
    and repaired.get(
        "production_mutation_authorized"
    )
    is False
)


if not authorization_closed:

    finding(
        "HIGH",
        "IMPLEMENTATION_AUTHORIZATION_OPENED",
        "Implementation or production mutation became authorized.",
    )


# ============================================================
# 11. FINDING SUMMARY
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


sequence_accepted = (
    len(high) == 0
    and len(medium) == 0
)


review_complete = (
    len(sequence) == 12
    and len(matrix_rows) == 13
)


result = {
    "contract_version":
        "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK_V2",

    "source_sequence_freeze_sha256":
        sha(source_path),

    "repaired_sequence_freeze_sha256":
        sha(repaired_path),

    "source_encoding_repair_report_sha256":
        sha(repair_report_path),

    "source_h2_audit_sha256":
        sha(h2_path),

    "source_matrix_v2_sha256":
        sha(matrix_path),

    "sequence_unit_count":
        len(sequence),

    "semantic_changed_unit_count":
        len(
            semantic_changed_ids
        ),

    "semantic_changed_unit_ids":
        semantic_changed_ids,

    "i04_exact_from_source":
        (
            source_units.get("A5-I04")
            == units.get("A5-I04")
        ),

    "i04_unicode_correct":
        (
            "A5-I04" in units
            and "MOLÖTOV"
            in str(
                units[
                    "A5-I04"
                ].get(
                    "purpose",
                    "",
                )
            )
            and "MOLÃ"
            not in str(
                units[
                    "A5-I04"
                ].get(
                    "purpose",
                    "",
                )
            )
        ),

    "i06_taste_boundary_edge_present":
        (
            "A5-I06" in units
            and "A5-I04"
            in (
                units[
                    "A5-I06"
                ].get(
                    "prerequisites",
                    [],
                )
                or []
            )
        ),

    "missing_required_direct_edge_count":
        len(
            missing_required_edges
        ),

    "missing_required_direct_edges":
        missing_required_edges,

    "unknown_dependency_count":
        len(
            unknown_dependencies
        ),

    "unknown_dependencies":
        unknown_dependencies,

    "forward_dependency_count":
        len(
            forward_dependencies
        ),

    "forward_dependencies":
        forward_dependencies,

    "dependency_graph_pass":
        (
            len(
                missing_required_edges
            ) == 0
            and len(
                unknown_dependencies
            ) == 0
            and len(
                forward_dependencies
            ) == 0
        ),

    "deferred_policy_pass":
        deferred_pass,

    "execution_policy_pass":
        execution_policy_pass,

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

    "previous_encoding_scope_failure_resolved":
        (
            semantic_changed_ids
            == ["A5-I06"]
        ),

    "sequence_accepted_without_revision":
        sequence_accepted,

    "implementation_authorized":
        False,

    "canonical_source_mutation_authorized":
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
    "SEQUENCE_UNIT_COUNT="
    + str(
        len(sequence)
    )
)

print(
    "SEMANTIC_CHANGED_UNIT_COUNT="
    + str(
        len(
            semantic_changed_ids
        )
    )
)

print(
    "SEMANTIC_CHANGED_UNIT_IDS="
    + "|".join(
        semantic_changed_ids
    )
)

print(
    "I04_EXACT_FROM_SOURCE="
    + str(
        result[
            "i04_exact_from_source"
        ]
    )
)

print(
    "I04_UNICODE_CORRECT="
    + str(
        result[
            "i04_unicode_correct"
        ]
    )
)

print(
    "I06_TASTE_BOUNDARY_EDGE_PRESENT="
    + str(
        result[
            "i06_taste_boundary_edge_present"
        ]
    )
)

print(
    "MISSING_REQUIRED_DIRECT_EDGE_COUNT="
    + str(
        len(
            missing_required_edges
        )
    )
)

print(
    "UNKNOWN_DEPENDENCY_COUNT="
    + str(
        len(
            unknown_dependencies
        )
    )
)

print(
    "FORWARD_DEPENDENCY_COUNT="
    + str(
        len(
            forward_dependencies
        )
    )
)

print(
    "DEPENDENCY_GRAPH_PASS="
    + str(
        result[
            "dependency_graph_pass"
        ]
    )
)

print(
    "DEFERRED_POLICY_PASS="
    + str(
        deferred_pass
    )
)

print(
    "EXECUTION_POLICY_PASS="
    + str(
        execution_policy_pass
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

print(
    "PREVIOUS_ENCODING_SCOPE_FAILURE_RESOLVED="
    + str(
        result[
            "previous_encoding_scope_failure_resolved"
        ]
    )
)

print(
    "SEQUENCE_ACCEPTED_WITHOUT_REVISION="
    + str(
        sequence_accepted
    )
)


if not review_complete:
    raise SystemExit(1)

if not sequence_accepted:
    raise SystemExit(2)