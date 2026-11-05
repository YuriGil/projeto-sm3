import json
import sys
from pathlib import Path

d = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8-sig"
    )
)

checks = [
    d["contract_version"]
    == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_ADVERSARIAL_REATTACK_V2",

    d["review_complete"] is True,

    d["sequence_unit_count"] == 12,

    d["semantic_changed_unit_count"] == 1,

    d["semantic_changed_unit_ids"] == [
        "A5-I06"
    ],

    d["i04_exact_from_source"] is True,

    d["i04_unicode_correct"] is True,

    d["i06_taste_boundary_edge_present"] is True,

    d["missing_required_direct_edge_count"] == 0,

    d["unknown_dependency_count"] == 0,

    d["forward_dependency_count"] == 0,

    d["dependency_graph_pass"] is True,

    d["deferred_policy_pass"] is True,

    d["execution_policy_pass"] is True,

    d["authorization_closed"] is True,

    d["finding_count"] == 0,

    d["high_finding_count"] == 0,

    d["medium_finding_count"] == 0,

    d["low_finding_count"] == 0,

    d["previous_encoding_scope_failure_resolved"] is True,

    d["sequence_accepted_without_revision"] is True,

    d["implementation_authorized"] is False,

    d["canonical_source_mutation_authorized"] is False,

    d["production_mutation_authorized"] is False,
]

print(
    "REATTACK_VERIFY_PASS="
    + str(
        all(checks)
    )
)

raise SystemExit(
    0 if all(checks) else 1
)