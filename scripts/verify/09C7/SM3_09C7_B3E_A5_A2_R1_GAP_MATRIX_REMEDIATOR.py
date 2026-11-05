from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_path = Path(sys.argv[1])
review_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])


ALLOWED = {
    "IMPLEMENTED",
    "PARTIAL",
    "MISSING",
    "SUPERSEDED",
    "NOT_APPLICABLE",
}


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
review = load(review_path)


if source.get(
    "contract_version"
) != "SM3_BLACK_BOX_DYNAMICS_V2_RUNTIME_GAP_MATRIX_V1":

    raise RuntimeError(
        "SOURCE_MATRIX_CONTRACT_INVALID"
    )


if review.get(
    "contract_version"
) != "SM3_BLACK_BOX_DYNAMICS_V2_GAP_MATRIX_ADVERSARIAL_REVIEW_V1":

    raise RuntimeError(
        "REVIEW_CONTRACT_INVALID"
    )


if review.get(
    "review_complete"
) is not True:

    raise RuntimeError(
        "REVIEW_NOT_COMPLETE"
    )


findings = list(
    review.get(
        "findings",
        [],
    )
)


high_findings = [
    item
    for item in findings
    if item.get("severity") == "HIGH"
]


if len(high_findings) != 1:

    raise RuntimeError(
        "EXPECTED_EXACTLY_ONE_HIGH_FINDING"
    )


high = high_findings[0]


expected_high = {
    "requirement_id":
        "A5-R09",

    "code":
        "GENERIC_SIGNATURE_FALSE_POSITIVE",

    "matrix_classification":
        "PARTIAL",

    "suggested_classification":
        "MISSING",
}


for key, expected in expected_high.items():

    if high.get(key) != expected:

        raise RuntimeError(
            "HIGH_FINDING_MISMATCH:"
            + key
        )


if (
    len(
        review.get(
            "signature_evidence",
            {},
        ).get(
            "temporal_signature_anchors",
            [],
        )
    )
    != 0
):

    raise RuntimeError(
        "TEMPORAL_SIGNATURE_ANCHOR_NOT_ZERO"
    )


revised = copy.deepcopy(
    source
)


source_rows = {
    row["requirement_id"]: row
    for row in source["rows"]
}


revised_rows = {
    row["requirement_id"]: row
    for row in revised["rows"]
}


if set(source_rows) != set(revised_rows):

    raise RuntimeError(
        "REQUIREMENT_ID_SET_CHANGED"
    )


if set(source_rows) != {
    "A5-R01",
    "A5-R02",
    "A5-R03",
    "A5-R04",
    "A5-R05",
    "A5-R06",
    "A5-R07",
    "A5-R08",
    "A5-R09",
    "A5-R10",
    "A5-R11",
    "A5-R12",
    "A5-R13",
}:

    raise RuntimeError(
        "SOURCE_REQUIREMENT_SET_INVALID"
    )


r09_before = copy.deepcopy(
    source_rows["A5-R09"]
)

r09 = revised_rows["A5-R09"]


if r09.get(
    "classification"
) != "PARTIAL":

    raise RuntimeError(
        "R09_SOURCE_NOT_PARTIAL"
    )


r09[
    "classification"
] = "MISSING"


r09[
    "gap"
] = (
    "No explicit temporal-event signature representation "
    "is evidenced in the current runtime. Existing generic "
    "signature/hash references do not satisfy the frozen "
    "adaptive temporal-event signature requirement."
)


r09[
    "rationale"
] = (
    "Adversarial review found zero temporal-event signature "
    "anchors. Generic signature/hash identifiers are not "
    "implementation evidence for this requirement."
)


r09[
    "adversarial_remediation"
] = {
    "source_review_code":
        "GENERIC_SIGNATURE_FALSE_POSITIVE",

    "source_severity":
        "HIGH",

    "original_classification":
        "PARTIAL",

    "revised_classification":
        "MISSING",

    "temporal_signature_anchor_count":
        0,
}


# ------------------------------------------------------------
# Verify all other rows stayed semantically identical.
# ------------------------------------------------------------

changed_ids: list[str] = []

unchanged_ids: list[str] = []


for requirement_id in sorted(
    source_rows
):

    before = source_rows[
        requirement_id
    ]

    after = revised_rows[
        requirement_id
    ]

    if canonical(before) == canonical(after):

        unchanged_ids.append(
            requirement_id
        )

    else:

        changed_ids.append(
            requirement_id
        )


if changed_ids != [
    "A5-R09"
]:

    raise RuntimeError(
        "UNAUTHORIZED_ROW_CHANGE:"
        + "|".join(changed_ids)
    )


if len(unchanged_ids) != 12:

    raise RuntimeError(
        "UNCHANGED_ROW_COUNT_INVALID"
    )


# ------------------------------------------------------------
# Recompute counts and derived sets.
# ------------------------------------------------------------

counts = {
    value: sum(
        1
        for row in revised["rows"]
        if row["classification"] == value
    )
    for value in sorted(ALLOWED)
}


expected_counts = {
    "IMPLEMENTED": 0,
    "PARTIAL": 7,
    "MISSING": 5,
    "SUPERSEDED": 0,
    "NOT_APPLICABLE": 1,
}


if counts != expected_counts:

    raise RuntimeError(
        "REVISED_CLASSIFICATION_COUNTS_INVALID"
    )


implementation_candidates = [
    row["requirement_id"]
    for row in revised["rows"]
    if row["classification"]
    in {
        "PARTIAL",
        "MISSING",
    }
]


already_satisfied = [
    row["requirement_id"]
    for row in revised["rows"]
    if row["classification"]
    == "IMPLEMENTED"
]


deferred = [
    row["requirement_id"]
    for row in revised["rows"]
    if row["classification"]
    == "NOT_APPLICABLE"
]


if implementation_candidates != [
    "A5-R01",
    "A5-R02",
    "A5-R03",
    "A5-R04",
    "A5-R05",
    "A5-R06",
    "A5-R07",
    "A5-R08",
    "A5-R09",
    "A5-R10",
    "A5-R11",
    "A5-R12",
]:

    raise RuntimeError(
        "IMPLEMENTATION_CANDIDATE_SET_INVALID"
    )


if already_satisfied != []:

    raise RuntimeError(
        "ALREADY_SATISFIED_SET_INVALID"
    )


if deferred != [
    "A5-R13"
]:

    raise RuntimeError(
        "DEFERRED_SET_INVALID"
    )


low_findings = [
    item
    for item in findings
    if item.get("severity") == "LOW"
]


low_codes = sorted(
    item.get("code")
    for item in low_findings
)


expected_low_codes = sorted([
    "IMPLICIT_CONFOUNDER_CONTROLS_PRESENT",
    "UNCERTAINTY_EXPLICIT_MODEL_ABSENT",
])


if low_codes != expected_low_codes:

    raise RuntimeError(
        "LOW_FINDING_SET_INVALID"
    )


# ------------------------------------------------------------
# Matrix revision metadata.
# ------------------------------------------------------------

revised[
    "contract_version"
] = "SM3_BLACK_BOX_DYNAMICS_V2_RUNTIME_GAP_MATRIX_V2"


revised[
    "classification_policy"
] = "CONSERVATIVE_STATIC_EVIDENCE_V2_ADVERSARIAL_REMEDIATED"


revised[
    "source_matrix_sha256"
] = sha(source_path)


revised[
    "source_adversarial_review_sha256"
] = sha(review_path)


revised[
    "revision"
] = 2


revised[
    "revision_reason"
] = "A5_R09_GENERIC_SIGNATURE_FALSE_POSITIVE"


revised[
    "changed_requirement_ids"
] = changed_ids


revised[
    "unchanged_requirement_ids"
] = unchanged_ids


revised[
    "classification_counts"
] = counts


revised[
    "implementation_candidate_requirement_ids"
] = implementation_candidates


revised[
    "already_satisfied_requirement_ids"
] = already_satisfied


revised[
    "deferred_requirement_ids"
] = deferred


revised[
    "adversarial_review_notes"
] = {
    "high_findings_applied": [
        "A5-R09:GENERIC_SIGNATURE_FALSE_POSITIVE"
    ],

    "low_findings_preserved_without_class_change": [
        "A5-R08:IMPLICIT_CONFOUNDER_CONTROLS_PRESENT",
        "A5-R11:UNCERTAINTY_EXPLICIT_MODEL_ABSENT",
    ],

    "temporal_r04_status":
        "PARTIAL_PRESERVED_NO_DIRECT_OR_TRANSITIVE_VALIDATOR_REACHABILITY",

    "implementation_authorized":
        False,
}


revised[
    "implementation_authorized"
] = False


revised[
    "production_mutation_authorized"
] = False


revised[
    "matrix_complete"
] = (
    len(revised["rows"]) == 13
    and sum(counts.values()) == 13
    and changed_ids == ["A5-R09"]
)


if revised[
    "matrix_complete"
] is not True:

    raise RuntimeError(
        "REVISED_MATRIX_NOT_COMPLETE"
    )


output_path.write_text(
    json.dumps(
        revised,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "SOURCE_R09_CLASSIFICATION="
    + r09_before["classification"]
)

print(
    "REVISED_R09_CLASSIFICATION="
    + r09["classification"]
)

print(
    "CHANGED_REQUIREMENT_COUNT="
    + str(len(changed_ids))
)

print(
    "CHANGED_REQUIREMENT_IDS="
    + "|".join(changed_ids)
)

print(
    "UNCHANGED_REQUIREMENT_COUNT="
    + str(len(unchanged_ids))
)

print(
    "IMPLEMENTED_COUNT="
    + str(counts["IMPLEMENTED"])
)

print(
    "PARTIAL_COUNT="
    + str(counts["PARTIAL"])
)

print(
    "MISSING_COUNT="
    + str(counts["MISSING"])
)

print(
    "SUPERSEDED_COUNT="
    + str(counts["SUPERSEDED"])
)

print(
    "NOT_APPLICABLE_COUNT="
    + str(counts["NOT_APPLICABLE"])
)

print(
    "LOW_FINDING_COUNT_PRESERVED="
    + str(len(low_findings))
)

print(
    "REVISED_MATRIX_COMPLETE="
    + str(
        revised[
            "matrix_complete"
        ]
    )
)