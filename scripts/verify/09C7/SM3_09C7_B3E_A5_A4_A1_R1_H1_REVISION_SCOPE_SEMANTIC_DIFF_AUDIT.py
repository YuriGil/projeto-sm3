from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_path = Path(sys.argv[1])
revised_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])


SEMANTIC_KEYS = [
    "order",
    "unit_id",
    "requirement_id",
    "classification",
    "name",
    "purpose",
    "mutation_scope",
    "prerequisites",
]


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


def normalize_prerequisites(
    value: Any,
) -> list[str]:

    if value is None:
        return []

    if isinstance(value, list):

        return [
            str(item)
            for item in value
        ]

    return [
        str(value)
    ]


def normalize_unit(
    unit: dict[str, Any],
) -> dict[str, Any]:

    result: dict[str, Any] = {}

    for key in SEMANTIC_KEYS:

        if key == "prerequisites":

            result[key] = normalize_prerequisites(
                unit.get(key)
            )

        else:

            result[key] = unit.get(key)

    return result


def canonical(
    value: Any,
) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


source = load(source_path)

revised = load(revised_path)


source_sequence = list(
    source.get(
        "sequence",
        [],
    )
)

revised_sequence = list(
    revised.get(
        "sequence",
        [],
    )
)


source_by_id = {
    unit["unit_id"]: unit
    for unit in source_sequence
}

revised_by_id = {
    unit["unit_id"]: unit
    for unit in revised_sequence
}


source_ids = [
    unit["unit_id"]
    for unit in source_sequence
]

revised_ids = [
    unit["unit_id"]
    for unit in revised_sequence
]


unit_set_equal = (
    set(source_by_id)
    == set(revised_by_id)
)

unit_order_equal = (
    source_ids
    == revised_ids
)


semantic_changed_ids: list[str] = []

raw_parsed_changed_ids: list[str] = []

representation_only_ids: list[str] = []

details: dict[str, Any] = {}


for unit_id in sorted(
    set(source_by_id)
    | set(revised_by_id)
):

    before = source_by_id.get(
        unit_id
    )

    after = revised_by_id.get(
        unit_id
    )


    if before is None or after is None:

        semantic_changed_ids.append(
            unit_id
        )

        raw_parsed_changed_ids.append(
            unit_id
        )

        details[unit_id] = {
            "missing_side": True,
        }

        continue


    before_semantic = normalize_unit(
        before
    )

    after_semantic = normalize_unit(
        after
    )


    semantic_equal = (
        before_semantic
        == after_semantic
    )


    raw_parsed_equal = (
        before
        == after
    )


    if not semantic_equal:

        semantic_changed_ids.append(
            unit_id
        )


    if not raw_parsed_equal:

        raw_parsed_changed_ids.append(
            unit_id
        )


    representation_only = (
        (not raw_parsed_equal)
        and semantic_equal
    )


    if representation_only:

        representation_only_ids.append(
            unit_id
        )


    before_prereq = before.get(
        "prerequisites"
    )

    after_prereq = after.get(
        "prerequisites"
    )


    details[unit_id] = {
        "semantic_equal":
            semantic_equal,

        "raw_parsed_equal":
            raw_parsed_equal,

        "representation_only":
            representation_only,

        "source_prerequisites_raw":
            before_prereq,

        "revised_prerequisites_raw":
            after_prereq,

        "source_prerequisites_type":
            type(before_prereq).__name__,

        "revised_prerequisites_type":
            type(after_prereq).__name__,

        "source_prerequisites_normalized":
            normalize_prerequisites(
                before_prereq
            ),

        "revised_prerequisites_normalized":
            normalize_prerequisites(
                after_prereq
            ),

        "source_semantic":
            before_semantic,

        "revised_semantic":
            after_semantic,
    }


expected_old_i06 = [
    "A5-I01",
    "A5-I02",
    "A5-I03",
]


expected_new_i06 = [
    "A5-I01",
    "A5-I02",
    "A5-I03",
    "A5-I04",
]


i04 = details.get(
    "A5-I04",
    {},
)

i06 = details.get(
    "A5-I06",
    {},
)


i04_semantically_unchanged = (
    i04.get(
        "semantic_equal"
    )
    is True
)


i06_old_prerequisites_exact = (
    i06.get(
        "source_prerequisites_normalized"
    )
    == expected_old_i06
)


i06_new_prerequisites_exact = (
    i06.get(
        "revised_prerequisites_normalized"
    )
    == expected_new_i06
)


i06_only_prerequisite_change = False


if (
    "A5-I06" in source_by_id
    and "A5-I06" in revised_by_id
):

    before = normalize_unit(
        source_by_id[
            "A5-I06"
        ]
    )

    after = normalize_unit(
        revised_by_id[
            "A5-I06"
        ]
    )

    before_without_prereq = dict(
        before
    )

    after_without_prereq = dict(
        after
    )

    before_without_prereq.pop(
        "prerequisites",
        None,
    )

    after_without_prereq.pop(
        "prerequisites",
        None,
    )

    i06_only_prerequisite_change = (
        before_without_prereq
        == after_without_prereq
        and i06_old_prerequisites_exact
        and i06_new_prerequisites_exact
    )


semantic_scope_pass = (
    unit_set_equal
    and unit_order_equal
    and semantic_changed_ids
    == [
        "A5-I06"
    ]
    and i04_semantically_unchanged
    and i06_only_prerequisite_change
)


harness_false_positive_confirmed = (
    semantic_scope_pass
)


if harness_false_positive_confirmed:

    if (
        "A5-I04"
        in representation_only_ids
    ):

        root_cause = (
            "EMPTY_PREREQUISITES_JSON_REPRESENTATION_NORMALIZATION"
        )

    elif (
        "A5-I04"
        not in raw_parsed_changed_ids
    ):

        root_cause = (
            "POWERSHELL_CONVERTTOJSON_TEXTUAL_COMPARISON_FALSE_POSITIVE"
        )

    else:

        root_cause = (
            "NON_SEMANTIC_SERIALIZATION_DIFFERENCE"
        )

    classification = (
        "REATTACK_SCOPE_FAILURE_IS_HARNESS_FALSE_POSITIVE"
    )

    next_gate = (
        "09C7-B3E-A5-A4-A1-R1-R1_REATTACK_HARNESS_REPAIR"
    )

else:

    root_cause = (
        "ACTUAL_SEMANTIC_SCOPE_EXPANSION_OR_UNRESOLVED_DIFF"
    )

    classification = (
        "REATTACK_SCOPE_FAILURE_REQUIRES_PROJECT_REMEDIATION"
    )

    next_gate = (
        "09C7-B3E-A5-A4-R1-R2_SEQUENCE_REMEDIATION_REQUIRED"
    )


result = {
    "contract_version":
        "SM3_IMPLEMENTATION_SEQUENCE_REVISION_SCOPE_SEMANTIC_DIFF_AUDIT_V1",

    "source_freeze_sha256":
        sha(source_path),

    "revised_freeze_sha256":
        sha(revised_path),

    "unit_set_equal":
        unit_set_equal,

    "unit_order_equal":
        unit_order_equal,

    "source_unit_ids":
        source_ids,

    "revised_unit_ids":
        revised_ids,

    "raw_parsed_changed_unit_ids":
        raw_parsed_changed_ids,

    "semantic_changed_unit_ids":
        semantic_changed_ids,

    "representation_only_unit_ids":
        representation_only_ids,

    "semantic_changed_unit_count":
        len(
            semantic_changed_ids
        ),

    "i04_semantically_unchanged":
        i04_semantically_unchanged,

    "i04_source_prerequisites_raw":
        i04.get(
            "source_prerequisites_raw"
        ),

    "i04_revised_prerequisites_raw":
        i04.get(
            "revised_prerequisites_raw"
        ),

    "i04_source_prerequisites_type":
        i04.get(
            "source_prerequisites_type"
        ),

    "i04_revised_prerequisites_type":
        i04.get(
            "revised_prerequisites_type"
        ),

    "i04_source_prerequisites_normalized":
        i04.get(
            "source_prerequisites_normalized"
        ),

    "i04_revised_prerequisites_normalized":
        i04.get(
            "revised_prerequisites_normalized"
        ),

    "i06_old_prerequisites_exact":
        i06_old_prerequisites_exact,

    "i06_new_prerequisites_exact":
        i06_new_prerequisites_exact,

    "i06_only_prerequisite_change":
        i06_only_prerequisite_change,

    "i06_source_prerequisites":
        i06.get(
            "source_prerequisites_normalized"
        ),

    "i06_revised_prerequisites":
        i06.get(
            "revised_prerequisites_normalized"
        ),

    "semantic_scope_pass":
        semantic_scope_pass,

    "harness_false_positive_confirmed":
        harness_false_positive_confirmed,

    "root_cause":
        root_cause,

    "classification":
        classification,

    "project_regression":
        not harness_false_positive_confirmed,

    "graph_regression":
        not semantic_scope_pass,

    "production_mutation_required":
        False,

    "details":
        details,

    "audit_pass":
        True,

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
    "UNIT_SET_EQUAL="
    + str(
        unit_set_equal
    )
)

print(
    "UNIT_ORDER_EQUAL="
    + str(
        unit_order_equal
    )
)

print(
    "RAW_PARSED_CHANGED_UNIT_IDS="
    + "|".join(
        raw_parsed_changed_ids
    )
)

print(
    "SEMANTIC_CHANGED_UNIT_IDS="
    + "|".join(
        semantic_changed_ids
    )
)

print(
    "REPRESENTATION_ONLY_UNIT_IDS="
    + "|".join(
        representation_only_ids
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
    "I04_SEMANTICALLY_UNCHANGED="
    + str(
        i04_semantically_unchanged
    )
)

print(
    "I04_SOURCE_PREREQUISITES_TYPE="
    + str(
        i04.get(
            "source_prerequisites_type"
        )
    )
)

print(
    "I04_REVISED_PREREQUISITES_TYPE="
    + str(
        i04.get(
            "revised_prerequisites_type"
        )
    )
)

print(
    "I04_SOURCE_PREREQUISITES_NORMALIZED="
    + "|".join(
        i04.get(
            "source_prerequisites_normalized",
            [],
        )
    )
)

print(
    "I04_REVISED_PREREQUISITES_NORMALIZED="
    + "|".join(
        i04.get(
            "revised_prerequisites_normalized",
            [],
        )
    )
)

print(
    "I06_OLD_PREREQUISITES_EXACT="
    + str(
        i06_old_prerequisites_exact
    )
)

print(
    "I06_NEW_PREREQUISITES_EXACT="
    + str(
        i06_new_prerequisites_exact
    )
)

print(
    "I06_ONLY_PREREQUISITE_CHANGE="
    + str(
        i06_only_prerequisite_change
    )
)

print(
    "SEMANTIC_SCOPE_PASS="
    + str(
        semantic_scope_pass
    )
)

print(
    "HARNESS_FALSE_POSITIVE_CONFIRMED="
    + str(
        harness_false_positive_confirmed
    )
)

print(
    "ROOT_CAUSE="
    + root_cause
)

print(
    "CLASSIFICATION="
    + classification
)

print(
    "NEXT_GATE="
    + next_gate
)