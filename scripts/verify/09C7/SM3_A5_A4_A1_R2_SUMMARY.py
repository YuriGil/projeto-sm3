import json
import sys
from pathlib import Path

d = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8-sig"
    )
)

keys = [
    "review_complete",
    "sequence_unit_count",
    "semantic_changed_unit_count",
    "i04_exact_from_source",
    "i04_unicode_correct",
    "i06_taste_boundary_edge_present",
    "missing_required_direct_edge_count",
    "unknown_dependency_count",
    "forward_dependency_count",
    "dependency_graph_pass",
    "deferred_policy_pass",
    "execution_policy_pass",
    "authorization_closed",
    "finding_count",
    "high_finding_count",
    "medium_finding_count",
    "low_finding_count",
    "previous_encoding_scope_failure_resolved",
    "sequence_accepted_without_revision",
]

for key in keys:
    print(
        key.upper()
        + "="
        + str(d[key])
    )

print(
    "SEMANTIC_CHANGED_UNIT_IDS="
    + "|".join(
        d[
            "semantic_changed_unit_ids"
        ]
    )
)

for finding in d["findings"]:

    print(
        "FINDING="
        + finding["severity"]
        + "|"
        + finding["code"]
        + "|"
        + finding["unit_id"]
    )