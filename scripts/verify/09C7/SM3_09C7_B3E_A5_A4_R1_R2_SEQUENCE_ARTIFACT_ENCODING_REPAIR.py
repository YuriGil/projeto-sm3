from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_path = Path(sys.argv[1])
corrupted_path = Path(sys.argv[2])
remediation_path = Path(sys.argv[3])
h2_path = Path(sys.argv[4])
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


def canonical(value: Any) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def unit_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:

    return {
        unit["unit_id"]: unit
        for unit in document["sequence"]
    }


source = load(source_path)
corrupted = load(corrupted_path)
remediation = load(remediation_path)
h2 = load(h2_path)


# ------------------------------------------------------------
# H2 must conclusively authorize encoding repair.
# ------------------------------------------------------------

h2_checks = [
    h2.get("audit_pass") is True,
    h2.get("encoding_corruption_confirmed") is True,
    h2.get("architectural_scope_changed") is False,
    h2.get("project_regression") is False,
    h2.get("i04_only_purpose_changed") is True,
    h2.get("i04_encoding_repair_matches_source") is True,
    h2.get("i06_expected_prerequisite_change") is True,
    h2.get("i06_other_fields_equal") is True,
    h2.get("root_cause")
    == "UTF8_NO_BOM_READ_THROUGH_WINDOWS_POWERSHELL_DEFAULT_CODEPAGE",
]


if not all(h2_checks):

    raise RuntimeError(
        "H2_ENCODING_REPAIR_NOT_AUTHORIZED"
    )


# ------------------------------------------------------------
# Remediation lineage.
# ------------------------------------------------------------

remediation_checks = [
    remediation.get("a5_a4_r1_pass") is True,
    remediation.get("changed_unit_count") == 1,
    remediation.get("changed_unit_ids") == ["A5-I06"],
    remediation.get("added_dependency_count") == 1,
    remediation.get("added_dependencies") == ["A5-I04->A5-I06"],
    remediation.get("numeric_order_changed") is False,
    remediation.get("requirement_classification_changed") is False,
    remediation.get("dependency_graph_pass") is True,
    remediation.get("semantic_edge_pass") is True,
    remediation.get("classifications_preserved") is True,
]


if not all(remediation_checks):

    raise RuntimeError(
        "REMEDIATION_LINEAGE_INVALID"
    )


# ------------------------------------------------------------
# Reconstruct from CLEAN V1 artifact.
#
# Do NOT repair the corrupted V2 in-place.
# ------------------------------------------------------------

repaired = copy.deepcopy(source)


repaired["contract_version"] = (
    "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_FREEZE_V2"
)

repaired["status"] = (
    "IMPLEMENTATION_SEQUENCE_FREEZE_REMEDIATED"
)

repaired["classification"] = (
    "A5_IMPLEMENTATION_SEQUENCE_REMEDIATED_FROM_ADVERSARIAL_FINDING"
)

repaired["revision"] = 2

repaired["revision_reason"] = (
    "A5_I04_TO_A5_I06_TASTE_BOUNDARY_DEPENDENCY"
)

repaired["source_sequence_freeze_sha256"] = sha(
    source_path
)

repaired[
    "source_adversarial_review_data_sha256"
] = remediation.get(
    "source_adversarial_review_data_sha256"
)

repaired[
    "source_adversarial_review_report_sha256"
] = remediation.get(
    "source_adversarial_review_report_sha256"
)

repaired["changed_unit_count"] = 1

repaired["changed_unit_ids"] = [
    "A5-I06"
]

repaired["added_dependency_count"] = 1

repaired["added_dependencies"] = [
    "A5-I04->A5-I06"
]

repaired["numeric_order_changed"] = False

repaired[
    "requirement_classification_changed"
] = False

repaired[
    "artifact_encoding"
] = "UTF-8"

repaired[
    "artifact_encoding_repair_revision"
] = 1

repaired[
    "artifact_encoding_repair_reason"
] = (
    "WINDOWS_POWERSHELL_DEFAULT_CODEPAGE_MOJIBAKE"
)

repaired[
    "corrupted_predecessor_sha256"
] = sha(
    corrupted_path
)

repaired[
    "h2_encoding_audit_sha256"
] = sha(
    h2_path
)

repaired[
    "implementation_authorized"
] = False

repaired[
    "canonical_source_mutation_authorized"
] = False

repaired[
    "production_mutation_authorized"
] = False

repaired[
    "next_gate"
] = (
    "09C7-B3E-A5-A4-A1-R2_"
    "IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK"
)


# ------------------------------------------------------------
# Apply ONLY legitimate semantic graph change.
# ------------------------------------------------------------

units = unit_map(
    repaired
)


if "A5-I06" not in units:

    raise RuntimeError(
        "I06_MISSING"
    )


units[
    "A5-I06"
][
    "prerequisites"
] = [
    "A5-I01",
    "A5-I02",
    "A5-I03",
    "A5-I04",
]


# ------------------------------------------------------------
# Exact semantic diff V1 -> repaired.
# ------------------------------------------------------------

source_units = unit_map(
    source
)

repaired_units = unit_map(
    repaired
)


if set(source_units) != set(repaired_units):

    raise RuntimeError(
        "UNIT_SET_CHANGED"
    )


semantic_changed_ids = []


for unit_id in sorted(
    source_units
):

    before = source_units[
        unit_id
    ]

    after = repaired_units[
        unit_id
    ]

    if canonical(before) != canonical(after):

        semantic_changed_ids.append(
            unit_id
        )


if semantic_changed_ids != [
    "A5-I06"
]:

    raise RuntimeError(
        "SEMANTIC_SCOPE_INVALID:"
        + "|".join(
            semantic_changed_ids
        )
    )


# ------------------------------------------------------------
# I04 must be BYTE-SEMANTICALLY clean after parse.
# ------------------------------------------------------------

source_i04 = source_units[
    "A5-I04"
]

repaired_i04 = repaired_units[
    "A5-I04"
]


i04_exact = (
    source_i04
    == repaired_i04
)


if not i04_exact:

    raise RuntimeError(
        "I04_NOT_EXACT_AFTER_RECONSTRUCTION"
    )


i04_purpose = str(
    repaired_i04.get(
        "purpose",
        "",
    )
)


i04_molotov_correct = (
    "MOLÖTOV"
    in i04_purpose
    and "MOLÃ" not in i04_purpose
)


if not i04_molotov_correct:

    raise RuntimeError(
        "I04_UNICODE_NOT_CORRECT"
    )


# ------------------------------------------------------------
# I06 exact change.
# ------------------------------------------------------------

source_i06 = source_units[
    "A5-I06"
]

repaired_i06 = repaired_units[
    "A5-I06"
]


source_i06_prereq = source_i06.get(
    "prerequisites",
    []
)

repaired_i06_prereq = repaired_i06.get(
    "prerequisites",
    []
)


i06_prerequisite_change_exact = (
    source_i06_prereq
    == [
        "A5-I01",
        "A5-I02",
        "A5-I03",
    ]
    and repaired_i06_prereq
    == [
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I04",
    ]
)


if not i06_prerequisite_change_exact:

    raise RuntimeError(
        "I06_PREREQUISITE_CHANGE_INVALID"
    )


source_i06_without = copy.deepcopy(
    source_i06
)

repaired_i06_without = copy.deepcopy(
    repaired_i06
)

source_i06_without.pop(
    "prerequisites",
    None,
)

repaired_i06_without.pop(
    "prerequisites",
    None,
)


i06_other_fields_equal = (
    source_i06_without
    == repaired_i06_without
)


if not i06_other_fields_equal:

    raise RuntimeError(
        "I06_OTHER_FIELDS_CHANGED"
    )


# ------------------------------------------------------------
# Order must remain exact.
# ------------------------------------------------------------

source_order = [
    unit["unit_id"]
    for unit in source["sequence"]
]

repaired_order = [
    unit["unit_id"]
    for unit in repaired["sequence"]
]


unit_order_equal = (
    source_order
    == repaired_order
)


if not unit_order_equal:

    raise RuntimeError(
        "UNIT_ORDER_CHANGED"
    )


# ------------------------------------------------------------
# Execution policy remains closed.
# ------------------------------------------------------------

policy = repaired.get(
    "execution_policy",
    {},
)


policy_closed = (
    policy.get(
        "implementation_mode"
    )
    == "ONE_UNIT_AT_A_TIME"
    and policy.get(
        "canonical_source_mutation_allowed"
    )
    is False
    and policy.get(
        "production_mutation_allowed"
    )
    is False
    and policy.get(
        "direct_production_edit_allowed"
    )
    is False
    and policy.get(
        "candidate_first_required"
    )
    is True
    and policy.get(
        "fail_closed"
    )
    is True
)


if not policy_closed:

    raise RuntimeError(
        "EXECUTION_POLICY_NOT_CLOSED"
    )


# ------------------------------------------------------------
# Write UTF-8 explicitly.
# ------------------------------------------------------------

output_path.write_text(
    json.dumps(
        repaired,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


# ------------------------------------------------------------
# Read back from disk to prove persistence.
# ------------------------------------------------------------

persisted = load(
    output_path
)

persisted_units = unit_map(
    persisted
)


persisted_i04_exact = (
    persisted_units[
        "A5-I04"
    ]
    == source_i04
)


persisted_i04_unicode_ok = (
    "MOLÖTOV"
    in persisted_units[
        "A5-I04"
    ].get(
        "purpose",
        "",
    )
    and "MOLÃ"
    not in persisted_units[
        "A5-I04"
    ].get(
        "purpose",
        "",
    )
)


persisted_i06_exact = (
    persisted_units[
        "A5-I06"
    ][
        "prerequisites"
    ]
    == [
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I04",
    ]
)


repair_pass = all([
    semantic_changed_ids
    == ["A5-I06"],

    i04_exact,

    i04_molotov_correct,

    i06_prerequisite_change_exact,

    i06_other_fields_equal,

    unit_order_equal,

    policy_closed,

    persisted_i04_exact,

    persisted_i04_unicode_ok,

    persisted_i06_exact,
])


if not repair_pass:

    raise RuntimeError(
        "ENCODING_REPAIR_FINAL_VERIFY_FAILED"
    )


print(
    "SOURCE_FREEZE_SHA256="
    + sha(source_path)
)

print(
    "CORRUPTED_FREEZE_SHA256="
    + sha(corrupted_path)
)

print(
    "REPAIRED_FREEZE_SHA256="
    + sha(output_path)
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
        i04_exact
    )
)

print(
    "I04_UNICODE_CORRECT="
    + str(
        i04_molotov_correct
    )
)

print(
    "I04_PURPOSE="
    + i04_purpose
)

print(
    "I06_PREREQUISITE_CHANGE_EXACT="
    + str(
        i06_prerequisite_change_exact
    )
)

print(
    "I06_OTHER_FIELDS_EQUAL="
    + str(
        i06_other_fields_equal
    )
)

print(
    "UNIT_ORDER_EQUAL="
    + str(
        unit_order_equal
    )
)

print(
    "EXECUTION_POLICY_CLOSED="
    + str(
        policy_closed
    )
)

print(
    "PERSISTED_I04_EXACT="
    + str(
        persisted_i04_exact
    )
)

print(
    "PERSISTED_I04_UNICODE_OK="
    + str(
        persisted_i04_unicode_ok
    )
)

print(
    "PERSISTED_I06_EXACT="
    + str(
        persisted_i06_exact
    )
)

print(
    "ENCODING_REPAIR_PASS="
    + str(
        repair_pass
    )
)