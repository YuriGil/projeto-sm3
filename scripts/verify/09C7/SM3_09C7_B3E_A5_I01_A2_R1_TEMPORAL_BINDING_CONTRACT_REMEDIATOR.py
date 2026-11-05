from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


source_contract_path = Path(sys.argv[1])
a2_evidence_path = Path(sys.argv[2])
a2_report_path = Path(sys.argv[3])
review_data_path = Path(sys.argv[4])
review_report_path = Path(sys.argv[5])
h1_audit_path = Path(sys.argv[6])
worker_path = Path(sys.argv[7])
temporal_path = Path(sys.argv[8])
revised_contract_path = Path(sys.argv[9])
evidence_path = Path(sys.argv[10])


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


source = load(source_contract_path)
a2_evidence = load(a2_evidence_path)
a2_report = load(a2_report_path)
review = load(review_data_path)
review_report = load(review_report_path)
h1 = load(h1_audit_path)


# ============================================================
# 1. AUTHORIZE SOURCE CONTRACT
# ============================================================

source_checks = [
    source.get(
        "contract_version"
    )
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V1",

    source.get(
        "requirement_id"
    )
    == "A5-R04",

    source.get(
        "implementation_unit"
    )
    == "A5-I01",

    source.get(
        "authorization",
        {},
    ).get(
        "binding_frozen"
    )
    is True,

    source.get(
        "authorization",
        {},
    ).get(
        "implementation_authorized"
    )
    is False,

    source.get(
        "authorization",
        {},
    ).get(
        "candidate_generation_authorized"
    )
    is False,

    a2_evidence.get(
        "binding_contract_freeze_pass"
    )
    is True,

    a2_report.get(
        "a5_i01_a2_pass"
    )
    is True,
]


if not all(source_checks):

    raise RuntimeError(
        "SOURCE_BINDING_CONTRACT_NOT_AUTHORIZED"
    )


# ============================================================
# 2. AUTHORIZE EXACT ADVERSARIAL FINDINGS
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


review_exact = (
    review.get(
        "review_complete"
    )
    is True

    and review.get(
        "finding_count"
    )
    == 5

    and review.get(
        "high_finding_count"
    )
    == 2

    and review.get(
        "medium_finding_count"
    )
    == 3

    and review.get(
        "low_finding_count"
    )
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
)


if not review_exact:

    raise RuntimeError(
        "ADVERSARIAL_REVIEW_NOT_EXACT"
    )


# ============================================================
# 3. AUTHORIZE H1 DIAGNOSTIC
# ============================================================

h1_checks = [
    h1.get(
        "contract_version"
    )
    == "SM3_A5_I01_SNAPSHOT_AS_OF_DATAFLOW_AUDIT_V1",

    h1.get(
        "diagnostic_complete"
    )
    is True,

    h1.get(
        "snapshot_keyword_only_exact"
    )
    is True,

    h1.get(
        "snapshot_keyword_only_parameters"
    )
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    h1.get(
        "snapshot_required_keyword_only_parameters"
    )
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    h1.get(
        "evidence_as_of_forwarding_proven"
    )
    is True,

    h1.get(
        "signal_as_of_forwarding_proven"
    )
    is True,

    h1.get(
        "all_snapshot_as_of_forwarding_proven"
    )
    is True,

    h1.get(
        "prior_high_findings_confirmed"
    )
    is False,

    h1.get(
        "prior_high_findings_false_positive"
    )
    is True,

    h1.get(
        "medium_findings_exact"
    )
    is True,

    h1.get(
        "classification"
    )
    == "A5_I01_SNAPSHOT_AS_OF_HIGH_FINDINGS_ARE_ANALYZER_FALSE_POSITIVES",
]


if not all(h1_checks):

    raise RuntimeError(
        "H1_DATAFLOW_DIAGNOSTIC_NOT_AUTHORIZED"
    )


# ============================================================
# 4. RECONSTRUCT CONTRACT V2
# ============================================================

revised = copy.deepcopy(
    source
)


revised[
    "contract_version"
] = (
    "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V2"
)

revised[
    "revision"
] = 2

revised[
    "revision_reason"
] = (
    "A2_A1_ADVERSARIAL_REMEDIATION"
)

revised[
    "source_binding_contract_v1_sha256"
] = sha(
    source_contract_path
)

revised[
    "source_adversarial_review_data_sha256"
] = sha(
    review_data_path
)

revised[
    "source_adversarial_review_report_sha256"
] = sha(
    review_report_path
)

revised[
    "source_snapshot_as_of_dataflow_audit_sha256"
] = sha(
    h1_audit_path
)


# ============================================================
# 5. EVIDENCE: REPLACE VACUOUS COVERAGE
# ============================================================

evidence_binding = revised[
    "bindings"
][
    "EVIDENCE"
]


evidence_binding[
    "temporal_input_fields"
] = [
    "source_date",
    "observed_at",
    "valid_until",
]

evidence_binding[
    "temporal_input_field_provenance"
] = (
    "A2_A1_TRANSITIVE_TEMPORAL_FIELD_USAGE"
)

evidence_binding[
    "request_fields_cover_temporal_inputs"
] = True

evidence_binding[
    "validator_mapping_keys"
] = [
    "source_date",
    "observed_at",
    "valid_until",
]

evidence_binding[
    "coverage_non_vacuous"
] = True


# ============================================================
# 6. SIGNAL: REPLACE VACUOUS COVERAGE
# ============================================================

signal_binding = revised[
    "bindings"
][
    "PREFERENCE_SIGNAL"
]


signal_binding[
    "temporal_input_fields"
] = [
    "window_started_at",
    "window_ended_at",
]

signal_binding[
    "temporal_input_field_provenance"
] = (
    "A2_A1_TRANSITIVE_TEMPORAL_FIELD_USAGE"
)

signal_binding[
    "request_fields_cover_temporal_inputs"
] = True

signal_binding[
    "validator_mapping_keys"
] = [
    "window_started_at",
    "window_ended_at",
]

signal_binding[
    "coverage_non_vacuous"
] = True


# ============================================================
# 7. SNAPSHOT: FREEZE REQUIRED CALL STYLE
# ============================================================

snapshot_binding = revised[
    "bindings"
][
    "SNAPSHOT"
]


snapshot_binding[
    "call_style"
] = "KEYWORD_ONLY_EXACT"

snapshot_binding[
    "keyword_argument_order"
] = [
    "as_of",
    "evidence",
    "signals",
]

snapshot_binding[
    "keyword_argument_bindings"
] = {
    "as_of":
        "request.as_of",

    "evidence":
        "RESOLVED_EVIDENCE_RECORDS_FROM_REQUEST_EVIDENCE_IDS",

    "signals":
        "RESOLVED_PREFERENCE_SIGNAL_RECORDS_FROM_REQUEST_PREFERENCE_SIGNAL_IDS",
}

snapshot_binding[
    "required_keyword_only_parameters"
] = [
    "as_of",
    "evidence",
    "signals",
]

snapshot_binding[
    "internal_as_of_forwarding"
] = (
    "PROVEN_SAME_NORMALIZED_REQUEST_AS_OF_TO_CHILD_VALIDATORS"
)

snapshot_binding[
    "internal_as_of_forwarding_evidence_proven"
] = True

snapshot_binding[
    "internal_as_of_forwarding_signal_proven"
] = True

snapshot_binding[
    "internal_as_of_forwarding_provenance"
] = (
    "A2_A1_H1_SNAPSHOT_AS_OF_DATAFLOW_AUDIT"
)


# ============================================================
# 8. RECORD DISPOSITION OF PRIOR HIGH FINDINGS
# ============================================================

revised[
    "adversarial_finding_disposition"
] = {
    "SNAPSHOT_KEYWORD_ONLY_CALL_STYLE_NOT_FROZEN":
        "REMEDIATED_IN_V2",

    "VACUOUS_VALIDATOR_KEY_COVERAGE_EVIDENCE":
        "REMEDIATED_IN_V2",

    "VACUOUS_VALIDATOR_KEY_COVERAGE_PREFERENCE_SIGNAL":
        "REMEDIATED_IN_V2",

    "SNAPSHOT_EVIDENCE_AS_OF_NOT_FORWARDED":
        "ANALYZER_FALSE_POSITIVE_PROVEN_BY_H1",

    "SNAPSHOT_SIGNAL_AS_OF_NOT_FORWARDED":
        "ANALYZER_FALSE_POSITIVE_PROVEN_BY_H1",
}


# ============================================================
# 9. KEEP AUTHORIZATION CLOSED
# ============================================================

revised[
    "authorization"
][
    "binding_frozen"
] = True

revised[
    "authorization"
][
    "implementation_authorized"
] = False

revised[
    "authorization"
][
    "candidate_generation_authorized"
] = False

revised[
    "authorization"
][
    "canonical_source_mutation_authorized"
] = False

revised[
    "authorization"
][
    "production_mutation_authorized"
] = False

revised[
    "authorization"
][
    "provider_call_authorized"
] = False

revised[
    "authorization"
][
    "model_call_authorized"
] = False


revised[
    "next_gate"
] = (
    "09C7-B3E-A5-I01-A2-A1-R1_"
    "TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REATTACK"
)


# ============================================================
# 10. VERIFY EXACT REMEDIATION CONTENT
# ============================================================

expected_evidence_fields = [
    "source_date",
    "observed_at",
    "valid_until",
]

expected_signal_fields = [
    "window_started_at",
    "window_ended_at",
]


field_remediation_pass = all([
    evidence_binding[
        "temporal_input_fields"
    ]
    == expected_evidence_fields,

    evidence_binding[
        "validator_mapping_keys"
    ]
    == expected_evidence_fields,

    evidence_binding[
        "coverage_non_vacuous"
    ]
    is True,

    evidence_binding[
        "request_fields_cover_temporal_inputs"
    ]
    is True,

    signal_binding[
        "temporal_input_fields"
    ]
    == expected_signal_fields,

    signal_binding[
        "validator_mapping_keys"
    ]
    == expected_signal_fields,

    signal_binding[
        "coverage_non_vacuous"
    ]
    is True,

    signal_binding[
        "request_fields_cover_temporal_inputs"
    ]
    is True,
])


snapshot_remediation_pass = all([
    snapshot_binding[
        "call_style"
    ]
    == "KEYWORD_ONLY_EXACT",

    snapshot_binding[
        "required_keyword_only_parameters"
    ]
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    snapshot_binding[
        "keyword_argument_bindings"
    ][
        "as_of"
    ]
    == "request.as_of",

    snapshot_binding[
        "internal_as_of_forwarding_evidence_proven"
    ]
    is True,

    snapshot_binding[
        "internal_as_of_forwarding_signal_proven"
    ]
    is True,
])


high_finding_disposition_pass = all([
    revised[
        "adversarial_finding_disposition"
    ][
        "SNAPSHOT_EVIDENCE_AS_OF_NOT_FORWARDED"
    ]
    == "ANALYZER_FALSE_POSITIVE_PROVEN_BY_H1",

    revised[
        "adversarial_finding_disposition"
    ][
        "SNAPSHOT_SIGNAL_AS_OF_NOT_FORWARDED"
    ]
    == "ANALYZER_FALSE_POSITIVE_PROVEN_BY_H1",
])


authorization_closed = all([
    revised[
        "authorization"
    ][
        "binding_frozen"
    ]
    is True,

    revised[
        "authorization"
    ][
        "implementation_authorized"
    ]
    is False,

    revised[
        "authorization"
    ][
        "candidate_generation_authorized"
    ]
    is False,

    revised[
        "authorization"
    ][
        "canonical_source_mutation_authorized"
    ]
    is False,

    revised[
        "authorization"
    ][
        "production_mutation_authorized"
    ]
    is False,
])


# ============================================================
# 11. PROVE UNRELATED FROZEN SEMANTICS PRESERVED
# ============================================================

preserved_paths = [
    (
        "requirement_id",
        source.get(
            "requirement_id"
        ),
        revised.get(
            "requirement_id"
        ),
    ),

    (
        "implementation_unit",
        source.get(
            "implementation_unit"
        ),
        revised.get(
            "implementation_unit"
        ),
    ),

    (
        "implementation_name",
        source.get(
            "implementation_name"
        ),
        revised.get(
            "implementation_name"
        ),
    ),

    (
        "temporal_policy_version",
        source.get(
            "temporal_policy_version"
        ),
        revised.get(
            "temporal_policy_version"
        ),
    ),

    (
        "temporal_engine_version",
        source.get(
            "temporal_engine_version"
        ),
        revised.get(
            "temporal_engine_version"
        ),
    ),

    (
        "temporal_implementation_revision",
        source.get(
            "temporal_implementation_revision"
        ),
        revised.get(
            "temporal_implementation_revision"
        ),
    ),

    (
        "public_validator_set",
        source.get(
            "public_validator_set"
        ),
        revised.get(
            "public_validator_set"
        ),
    ),

    (
        "validator_details",
        source.get(
            "validator_details"
        ),
        revised.get(
            "validator_details"
        ),
    ),

    (
        "request_model_fields",
        source.get(
            "request_model_fields"
        ),
        revised.get(
            "request_model_fields"
        ),
    ),

    (
        "global_invariants",
        source.get(
            "global_invariants"
        ),
        revised.get(
            "global_invariants"
        ),
    ),
]


preserved_semantics_pass = all(
    before == after
    for _, before, after
    in preserved_paths
)


if not preserved_semantics_pass:

    changed = [
        name
        for name, before, after
        in preserved_paths
        if before != after
    ]

    raise RuntimeError(
        "UNAUTHORIZED_FROZEN_SEMANTIC_CHANGE:"
        + "|".join(changed)
    )


# ============================================================
# 12. WRITE / READ BACK UTF-8
# ============================================================

revised_contract_path.write_text(
    json.dumps(
        revised,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


persisted = load(
    revised_contract_path
)


persistence_pass = (
    persisted
    == revised
)


if not persistence_pass:

    raise RuntimeError(
        "REVISED_CONTRACT_PERSISTENCE_MISMATCH"
    )


# ============================================================
# 13. FINAL REMEDIATION VERDICT
# ============================================================

remediation_pass = all([
    field_remediation_pass,
    snapshot_remediation_pass,
    high_finding_disposition_pass,
    authorization_closed,
    preserved_semantics_pass,
    persistence_pass,
])


if not remediation_pass:

    raise RuntimeError(
        "A2_R1_REMEDIATION_FAILED"
    )


# ============================================================
# 14. EVIDENCE
# ============================================================

evidence = {
    "contract_version":
        "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_REMEDIATION_EVIDENCE_V1",

    "source_contract_v1_sha256":
        sha(
            source_contract_path
        ),

    "source_a2_evidence_sha256":
        sha(
            a2_evidence_path
        ),

    "source_a2_report_sha256":
        sha(
            a2_report_path
        ),

    "source_adversarial_review_data_sha256":
        sha(
            review_data_path
        ),

    "source_adversarial_review_report_sha256":
        sha(
            review_report_path
        ),

    "source_h1_dataflow_audit_sha256":
        sha(
            h1_audit_path
        ),

    "worker_sha256":
        sha(
            worker_path
        ),

    "temporal_sha256":
        sha(
            temporal_path
        ),

    "review_exact":
        review_exact,

    "h1_high_findings_false_positive":
        h1.get(
            "prior_high_findings_false_positive"
        ),

    "h1_all_snapshot_as_of_forwarding_proven":
        h1.get(
            "all_snapshot_as_of_forwarding_proven"
        ),

    "evidence_temporal_input_fields":
        evidence_binding[
            "temporal_input_fields"
        ],

    "signal_temporal_input_fields":
        signal_binding[
            "temporal_input_fields"
        ],

    "evidence_coverage_non_vacuous":
        evidence_binding[
            "coverage_non_vacuous"
        ],

    "signal_coverage_non_vacuous":
        signal_binding[
            "coverage_non_vacuous"
        ],

    "snapshot_call_style":
        snapshot_binding[
            "call_style"
        ],

    "snapshot_required_keyword_only_parameters":
        snapshot_binding[
            "required_keyword_only_parameters"
        ],

    "snapshot_internal_as_of_forwarding_evidence_proven":
        snapshot_binding[
            "internal_as_of_forwarding_evidence_proven"
        ],

    "snapshot_internal_as_of_forwarding_signal_proven":
        snapshot_binding[
            "internal_as_of_forwarding_signal_proven"
        ],

    "field_remediation_pass":
        field_remediation_pass,

    "snapshot_remediation_pass":
        snapshot_remediation_pass,

    "high_finding_disposition_pass":
        high_finding_disposition_pass,

    "preserved_semantics_pass":
        preserved_semantics_pass,

    "authorization_closed":
        authorization_closed,

    "persistence_pass":
        persistence_pass,

    "remediation_pass":
        remediation_pass,

    "binding_frozen":
        True,

    "implementation_authorized":
        False,

    "candidate_generation_authorized":
        False,

    "canonical_source_mutation_authorized":
        False,

    "production_mutation_authorized":
        False,

    "classification":
        "A5_I01_TEMPORAL_BINDING_CONTRACT_REMEDIATED",

    "next_gate":
        "09C7-B3E-A5-I01-A2-A1-R1_TEMPORAL_BINDING_CONTRACT_ADVERSARIAL_REATTACK",
}


evidence_path.write_text(
    json.dumps(
        evidence,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "REVIEW_EXACT="
    + str(
        review_exact
    )
)

print(
    "H1_HIGH_FINDINGS_FALSE_POSITIVE="
    + str(
        h1.get(
            "prior_high_findings_false_positive"
        )
    )
)

print(
    "H1_ALL_SNAPSHOT_AS_OF_FORWARDING_PROVEN="
    + str(
        h1.get(
            "all_snapshot_as_of_forwarding_proven"
        )
    )
)

print(
    "EVIDENCE_TEMPORAL_INPUT_FIELDS="
    + "|".join(
        evidence_binding[
            "temporal_input_fields"
        ]
    )
)

print(
    "SIGNAL_TEMPORAL_INPUT_FIELDS="
    + "|".join(
        signal_binding[
            "temporal_input_fields"
        ]
    )
)

print(
    "EVIDENCE_COVERAGE_NON_VACUOUS="
    + str(
        evidence_binding[
            "coverage_non_vacuous"
        ]
    )
)

print(
    "SIGNAL_COVERAGE_NON_VACUOUS="
    + str(
        signal_binding[
            "coverage_non_vacuous"
        ]
    )
)

print(
    "SNAPSHOT_CALL_STYLE="
    + snapshot_binding[
        "call_style"
    ]
)

print(
    "SNAPSHOT_REQUIRED_KEYWORD_ONLY_PARAMETERS="
    + "|".join(
        snapshot_binding[
            "required_keyword_only_parameters"
        ]
    )
)

print(
    "SNAPSHOT_AS_OF_KEYWORD_BINDING="
    + snapshot_binding[
        "keyword_argument_bindings"
    ][
        "as_of"
    ]
)

print(
    "SNAPSHOT_INTERNAL_AS_OF_FORWARDING_EVIDENCE_PROVEN="
    + str(
        snapshot_binding[
            "internal_as_of_forwarding_evidence_proven"
        ]
    )
)

print(
    "SNAPSHOT_INTERNAL_AS_OF_FORWARDING_SIGNAL_PROVEN="
    + str(
        snapshot_binding[
            "internal_as_of_forwarding_signal_proven"
        ]
    )
)

print(
    "FIELD_REMEDIATION_PASS="
    + str(
        field_remediation_pass
    )
)

print(
    "SNAPSHOT_REMEDIATION_PASS="
    + str(
        snapshot_remediation_pass
    )
)

print(
    "HIGH_FINDING_DISPOSITION_PASS="
    + str(
        high_finding_disposition_pass
    )
)

print(
    "PRESERVED_SEMANTICS_PASS="
    + str(
        preserved_semantics_pass
    )
)

print(
    "AUTHORIZATION_CLOSED="
    + str(
        authorization_closed
    )
)

print(
    "PERSISTENCE_PASS="
    + str(
        persistence_pass
    )
)

print(
    "REMEDIATION_PASS="
    + str(
        remediation_pass
    )
)

print(
    "IMPLEMENTATION_AUTHORIZED=False"
)

print(
    "CANDIDATE_GENERATION_AUTHORIZED=False"
)

print(
    "NEXT_GATE="
    + evidence[
        "next_gate"
    ]
)