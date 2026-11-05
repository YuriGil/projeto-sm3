from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any


source_path = Path(sys.argv[1])
revised_path = Path(sys.argv[2])
h1_path = Path(sys.argv[3])
output_path = Path(sys.argv[4])


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


def unit_by_id(
    document: dict[str, Any],
    unit_id: str,
) -> dict[str, Any]:

    matches = [
        unit
        for unit in document.get(
            "sequence",
            [],
        )
        if unit.get("unit_id") == unit_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "UNIT_CARDINALITY_INVALID:"
            + unit_id
        )

    return matches[0]


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


def semantic_value(
    unit: dict[str, Any],
    key: str,
) -> Any:

    if key == "prerequisites":
        return normalize_prerequisites(
            unit.get(key)
        )

    return unit.get(key)


def codepoints(
    value: Any,
) -> list[dict[str, Any]]:

    if not isinstance(value, str):
        return []

    return [
        {
            "index": index,
            "char": char,
            "codepoint":
                "U+%04X" % ord(char),
            "name":
                unicodedata.name(
                    char,
                    "UNKNOWN",
                ),
        }
        for index, char in enumerate(value)
    ]


def first_string_difference(
    left: str,
    right: str,
) -> dict[str, Any]:

    limit = min(
        len(left),
        len(right),
    )

    for index in range(limit):

        if left[index] != right[index]:

            return {
                "index": index,

                "source_char":
                    left[index],

                "source_codepoint":
                    "U+%04X"
                    % ord(left[index]),

                "source_name":
                    unicodedata.name(
                        left[index],
                        "UNKNOWN",
                    ),

                "revised_char":
                    right[index],

                "revised_codepoint":
                    "U+%04X"
                    % ord(right[index]),

                "revised_name":
                    unicodedata.name(
                        right[index],
                        "UNKNOWN",
                    ),
            }

    if len(left) != len(right):

        return {
            "index": limit,
            "source_char": None,
            "source_codepoint": None,
            "source_name": None,
            "revised_char": None,
            "revised_codepoint": None,
            "revised_name": None,
            "length_only_difference": True,
        }

    return {}


def cp1252_to_utf8_repair(
    value: Any,
) -> tuple[bool, str | None]:

    if not isinstance(value, str):
        return False, None

    try:

        repaired = (
            value
            .encode("cp1252")
            .decode("utf-8")
        )

        return True, repaired

    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
    ):

        return False, None


source = load(
    source_path
)

revised = load(
    revised_path
)

h1 = load(
    h1_path
)


source_i04 = unit_by_id(
    source,
    "A5-I04",
)

revised_i04 = unit_by_id(
    revised,
    "A5-I04",
)

source_i06 = unit_by_id(
    source,
    "A5-I06",
)

revised_i06 = unit_by_id(
    revised,
    "A5-I06",
)


i04_diffs: list[dict[str, Any]] = []


for key in SEMANTIC_KEYS:

    before = semantic_value(
        source_i04,
        key,
    )

    after = semantic_value(
        revised_i04,
        key,
    )


    if before == after:
        continue


    item: dict[str, Any] = {
        "field": key,
        "source_value": before,
        "revised_value": after,
        "source_type":
            type(before).__name__,
        "revised_type":
            type(after).__name__,
    }


    if (
        isinstance(before, str)
        and isinstance(after, str)
    ):

        item[
            "first_string_difference"
        ] = first_string_difference(
            before,
            after,
        )

        item[
            "source_codepoints"
        ] = codepoints(
            before
        )

        item[
            "revised_codepoints"
        ] = codepoints(
            after
        )


        repair_possible, repaired = (
            cp1252_to_utf8_repair(
                after
            )
        )


        item[
            "cp1252_utf8_repair_possible"
        ] = repair_possible

        item[
            "cp1252_utf8_repaired_value"
        ] = repaired

        item[
            "cp1252_utf8_repair_matches_source"
        ] = (
            repair_possible
            and repaired == before
        )


    i04_diffs.append(
        item
    )


i04_diff_keys = [
    item["field"]
    for item in i04_diffs
]


i04_only_purpose_changed = (
    i04_diff_keys == [
        "purpose"
    ]
)


i04_purpose_diff = (
    i04_diffs[0]
    if i04_only_purpose_changed
    else {}
)


i04_encoding_repair_matches = (
    i04_only_purpose_changed
    and i04_purpose_diff.get(
        "cp1252_utf8_repair_matches_source"
    )
    is True
)


source_i06_prereq = (
    normalize_prerequisites(
        source_i06.get(
            "prerequisites"
        )
    )
)

revised_i06_prereq = (
    normalize_prerequisites(
        revised_i06.get(
            "prerequisites"
        )
    )
)


i06_expected_change = (
    source_i06_prereq
    == [
        "A5-I01",
        "A5-I02",
        "A5-I03",
    ]
    and
    revised_i06_prereq
    == [
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I04",
    ]
)


i06_other_fields_equal = all(
    semantic_value(
        source_i06,
        key,
    )
    ==
    semantic_value(
        revised_i06,
        key,
    )
    for key in SEMANTIC_KEYS
    if key != "prerequisites"
)


h1_consistent = (
    h1.get(
        "semantic_changed_unit_ids"
    )
    == [
        "A5-I04",
        "A5-I06",
    ]
    and h1.get(
        "i04_semantically_unchanged"
    )
    is False
    and h1.get(
        "i06_only_prerequisite_change"
    )
    is True
)


encoding_corruption_confirmed = (
    h1_consistent
    and i04_only_purpose_changed
    and i04_encoding_repair_matches
    and i06_expected_change
    and i06_other_fields_equal
)


architectural_scope_changed = (
    not encoding_corruption_confirmed
)


if encoding_corruption_confirmed:

    root_cause = (
        "UTF8_NO_BOM_READ_THROUGH_WINDOWS_POWERSHELL_DEFAULT_CODEPAGE"
    )

    classification = (
        "I04_CHANGE_IS_HARNESS_ARTIFACT_ENCODING_CORRUPTION"
    )

    next_gate = (
        "09C7-B3E-A5-A4-R1-R2_SEQUENCE_ARTIFACT_ENCODING_REPAIR"
    )

else:

    root_cause = (
        "I04_ACTUAL_SEMANTIC_CHANGE_NOT_EXPLAINED_BY_ENCODING"
    )

    classification = (
        "I04_ACTUAL_SEMANTIC_SCOPE_EXPANSION_CONFIRMED"
    )

    next_gate = (
        "09C7-B3E-A5-A4-R1-R2_SEQUENCE_REMEDIATION_REQUIRED"
    )


result = {
    "contract_version":
        "SM3_I04_EXACT_UNICODE_FIELD_DIFF_AUDIT_V1",

    "source_freeze_sha256":
        sha(source_path),

    "revised_freeze_sha256":
        sha(revised_path),

    "h1_audit_sha256":
        sha(h1_path),

    "h1_consistent":
        h1_consistent,

    "i04_diff_count":
        len(i04_diffs),

    "i04_diff_keys":
        i04_diff_keys,

    "i04_diffs":
        i04_diffs,

    "i04_only_purpose_changed":
        i04_only_purpose_changed,

    "i04_encoding_repair_matches_source":
        i04_encoding_repair_matches,

    "i06_expected_prerequisite_change":
        i06_expected_change,

    "i06_other_fields_equal":
        i06_other_fields_equal,

    "encoding_corruption_confirmed":
        encoding_corruption_confirmed,

    "architectural_scope_changed":
        architectural_scope_changed,

    "project_regression":
        False
        if encoding_corruption_confirmed
        else True,

    "root_cause":
        root_cause,

    "classification":
        classification,

    "production_mutation_required":
        False,

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
    "H1_CONSISTENT="
    + str(
        h1_consistent
    )
)

print(
    "I04_DIFF_COUNT="
    + str(
        len(i04_diffs)
    )
)

print(
    "I04_DIFF_KEYS="
    + "|".join(
        i04_diff_keys
    )
)


for item in i04_diffs:

    print(
        "I04_DIFF_FIELD="
        + item["field"]
    )

    print(
        "I04_SOURCE_VALUE="
        + repr(
            item["source_value"]
        )
    )

    print(
        "I04_REVISED_VALUE="
        + repr(
            item["revised_value"]
        )
    )


    first_diff = item.get(
        "first_string_difference",
        {},
    )


    if first_diff:

        print(
            "I04_FIRST_DIFF_INDEX="
            + str(
                first_diff.get(
                    "index"
                )
            )
        )

        print(
            "I04_SOURCE_CHAR_CODEPOINT="
            + str(
                first_diff.get(
                    "source_codepoint"
                )
            )
        )

        print(
            "I04_SOURCE_CHAR_NAME="
            + str(
                first_diff.get(
                    "source_name"
                )
            )
        )

        print(
            "I04_REVISED_CHAR_CODEPOINT="
            + str(
                first_diff.get(
                    "revised_codepoint"
                )
            )
        )

        print(
            "I04_REVISED_CHAR_NAME="
            + str(
                first_diff.get(
                    "revised_name"
                )
            )
        )


    print(
        "I04_CP1252_UTF8_REPAIR_MATCHES_SOURCE="
        + str(
            item.get(
                "cp1252_utf8_repair_matches_source",
                False,
            )
        )
    )


print(
    "I04_ONLY_PURPOSE_CHANGED="
    + str(
        i04_only_purpose_changed
    )
)

print(
    "I04_ENCODING_REPAIR_MATCHES_SOURCE="
    + str(
        i04_encoding_repair_matches
    )
)

print(
    "I06_EXPECTED_PREREQUISITE_CHANGE="
    + str(
        i06_expected_change
    )
)

print(
    "I06_OTHER_FIELDS_EQUAL="
    + str(
        i06_other_fields_equal
    )
)

print(
    "ENCODING_CORRUPTION_CONFIRMED="
    + str(
        encoding_corruption_confirmed
    )
)

print(
    "ARCHITECTURAL_SCOPE_CHANGED="
    + str(
        architectural_scope_changed
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