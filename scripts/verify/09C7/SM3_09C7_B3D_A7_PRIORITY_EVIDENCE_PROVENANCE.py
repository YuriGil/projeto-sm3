from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


ITEM_ID = "RI_500f8618a5796dc9b1fbded2f3bfff2e"
RMA_ID = "RMA_0072a9689863b956298a9ec34f01bd0e"
SOURCE_SHA = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

STATE = Path("/data/media/production_state")

REPORT = Path(
    "/tmp/SM3_09C7_B3D_A7_PRIORITY_EVIDENCE_PROVENANCE.json"
)


def src(name):

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:
        return None

    try:
        return inspect.getsource(
            obj
        )
    except Exception as exc:
        return "SOURCE_UNAVAILABLE:" + repr(exc)


# ============================================================
# 1. CURRENT ITEM / MECHANICAL
# ============================================================

item = ws._require_reference_item_active(
    ITEM_ID
)

mechanical_path = (
    ws._reference_mechanical_analysis_path(
        SOURCE_SHA,
        RMA_ID,
    )
)

mechanical = (
    ws._verify_reference_mechanical_analysis(
        json.loads(
            mechanical_path.read_text(
                encoding="utf-8"
            )
        )
    )
)


# ============================================================
# 2. CURRENT EVIDENCE
# ============================================================

evidence = (
    ws._reference_priority_current_evidence(
        item,
        mechanical,
    )
)

score, weights = (
    ws._reference_priority_score(
        evidence
    )
)


# ============================================================
# 3. PRIORITY-RELATED HELPER SOURCE
# ============================================================

helper_names = [
    "_reference_priority_current_evidence",
    "_reference_priority_score",
]

# Discover other runtime helpers rather than assuming names.
for name in sorted(dir(ws)):

    lower = name.lower()

    if (
        "priority" in lower
        and (
            "metric" in lower
            or
            "human" in lower
            or
            "evidence" in lower
            or
            "score" in lower
        )
    ):
        if name not in helper_names:
            helper_names.append(
                name
            )


helper_sources = {}

for name in helper_names:
    helper_sources[name] = src(
        name
    )


# ============================================================
# 4. ALL JSON RECORDS RELEVANT TO PROFILE / ITEM / SOURCE
# ============================================================

profile_id = item.get(
    "reference_profile_id"
)

relevant_records = []

contract_counts = {}

metric_like_records = []

for path in STATE.rglob("*.json"):

    try:
        rec = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        continue

    if not isinstance(rec, dict):
        continue

    contract = str(
        rec.get(
            "contract_version"
        )
        or ""
    )

    if contract:
        contract_counts[contract] = (
            contract_counts.get(
                contract,
                0
            )
            + 1
        )

    haystack = json.dumps(
        rec,
        ensure_ascii=False,
        default=str,
    ).lower()

    metric_like = (
        "metric" in contract.lower()
        or
        "engagement" in haystack
        or
        "views" in haystack
        or
        "likes" in haystack
        or
        "comments" in haystack
        or
        "shares" in haystack
        or
        "saves" in haystack
        or
        "followers" in haystack
    )

    if metric_like:

        metric_like_records.append({
            "path":
                str(path),

            "contract_version":
                contract,

            "reference_item_id":
                rec.get(
                    "reference_item_id"
                ),

            "reference_profile_id":
                rec.get(
                    "reference_profile_id"
                ),

            "source_sha256":
                rec.get(
                    "source_sha256"
                ),

            "fields":
                sorted(
                    rec.keys()
                ),

            "record":
                rec,
        })

    related = (
        rec.get(
            "reference_item_id"
        )
        == ITEM_ID

        or

        rec.get(
            "reference_profile_id"
        )
        == profile_id

        or

        str(
            rec.get(
                "source_sha256"
            )
            or ""
        ).lower()
        == SOURCE_SHA
    )

    if related:

        relevant_records.append({
            "path":
                str(path),

            "contract_version":
                contract,

            "record":
                rec,
        })


# ============================================================
# 5. ITEM FIELDS THAT MAY DRIVE HUMAN PRIORITY
# ============================================================

human_candidate_fields = {}

for key,value in item.items():

    lower = str(key).lower()

    if any(
        token in lower
        for token in (
            "priority",
            "human",
            "score",
            "rank",
            "weight",
            "importance",
        )
    ):
        human_candidate_fields[
            key
        ] = value


# ============================================================
# 6. DECISION
# ============================================================

metric = evidence[
    "metric_signal"
]

human = evidence[
    "human_priority"
]

mechanical_quality = evidence[
    "mechanical_evidence_quality"
]

if (
    score
    >= ws.REFERENCE_PRIORITY_SEMANTIC_THRESHOLD
):
    decision = "SEMANTIC_ANALYSIS"

elif (
    score
    >= ws.REFERENCE_PRIORITY_DEFER_THRESHOLD
):
    decision = "DEFER"

else:
    decision = "SKIP"


# ============================================================
# 7. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3D-A7",

    "status":
        "PRIORITY_EVIDENCE_PROVENANCE_AUDIT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "reference_item_id":
        ITEM_ID,

    "reference_profile_id":
        profile_id,

    "source_sha256":
        SOURCE_SHA,

    "mechanical_analysis_id":
        RMA_ID,

    "item":
        item,

    "human_candidate_item_fields":
        human_candidate_fields,

    "current_evidence":
        evidence,

    "effective_weights":
        weights,

    "priority_score":
        score,

    "decision":
        decision,

    "helper_sources":
        helper_sources,

    "contract_counts":
        contract_counts,

    "relevant_records":
        relevant_records,

    "metric_like_records":
        metric_like_records,

    "metric_available":
        metric.get(
            "available"
        ),

    "metric_peer_count":
        metric.get(
            "peer_count"
        ),

    "metric_snapshot_id":
        metric.get(
            "snapshot_id"
        ),

    "metric_population_fingerprint":
        metric.get(
            "population_fingerprint"
        ),

    "human_priority_score":
        human.get(
            "score"
        ),

    "mechanical_quality_score":
        mechanical_quality.get(
            "score"
        ),

    "production_write_performed":
        False,

    "priority_api_called":
        False,

    "semantic_api_called":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
        default=str,
    ),
    encoding="utf-8",
)


# ============================================================
# 8. CONSOLE
# ============================================================

print(
    "=== SM3 09C7-B3D-A7 PRIORITY EVIDENCE PROVENANCE ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)

print(
    "ITEM_ID="
    + ITEM_ID
)

print(
    "PROFILE_ID="
    + str(
        profile_id
    )
)


print(
    "\n=== ITEM HUMAN-PRIORITY CANDIDATE FIELDS ==="
)

print(
    json.dumps(
        human_candidate_fields,
        indent=2,
        ensure_ascii=False,
    )
)


print(
    "\n=== CURRENT EVIDENCE ==="
)

print(
    json.dumps(
        evidence,
        indent=2,
        ensure_ascii=False,
    )
)


print(
    "\n=== EFFECTIVE WEIGHTS ==="
)

print(
    json.dumps(
        weights,
        indent=2,
        ensure_ascii=False,
    )
)


print(
    "\nPRIORITY_SCORE="
    + str(
        score
    )
)

print(
    "DECISION="
    + decision
)

print(
    "METRIC_AVAILABLE="
    + str(
        metric.get(
            "available"
        )
    )
)

print(
    "METRIC_PEER_COUNT="
    + str(
        metric.get(
            "peer_count"
        )
    )
)

print(
    "METRIC_SNAPSHOT_ID="
    + str(
        metric.get(
            "snapshot_id"
        )
    )
)

print(
    "METRIC_POPULATION_FINGERPRINT="
    + str(
        metric.get(
            "population_fingerprint"
        )
    )
)

print(
    "HUMAN_PRIORITY_SCORE="
    + str(
        human.get(
            "score"
        )
    )
)

print(
    "MECHANICAL_QUALITY_SCORE="
    + str(
        mechanical_quality.get(
            "score"
        )
    )
)


print(
    "\n=== CONTRACT COUNTS ==="
)

for name in sorted(
    contract_counts
):

    print(
        name
        + "="
        + str(
            contract_counts[
                name
            ]
        )
    )


print(
    "\nMETRIC_LIKE_RECORD_COUNT="
    + str(
        len(
            metric_like_records
        )
    )
)


print(
    "\n=== METRIC-LIKE RECORDS ==="
)

for row in metric_like_records:

    print(
        json.dumps(
            {
                "path":
                    row[
                        "path"
                    ],

                "contract_version":
                    row[
                        "contract_version"
                    ],

                "reference_item_id":
                    row[
                        "reference_item_id"
                    ],

                "reference_profile_id":
                    row[
                        "reference_profile_id"
                    ],

                "source_sha256":
                    row[
                        "source_sha256"
                    ],

                "fields":
                    row[
                        "fields"
                    ],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== PRIORITY EVIDENCE HELPER SOURCES ==="
)

for name in helper_names:

    print(
        "\n--- "
        + name
        + " ---"
    )

    print(
        helper_sources[
            name
        ]
    )


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
)

print(
    "PRIORITY_API_CALLED=False"
)

print(
    "SEMANTIC_API_CALLED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)

print(
    "SM3_09C7_B3D_A7_PRIORITY_EVIDENCE_PROVENANCE_AUDIT_COMPLETE"
)
