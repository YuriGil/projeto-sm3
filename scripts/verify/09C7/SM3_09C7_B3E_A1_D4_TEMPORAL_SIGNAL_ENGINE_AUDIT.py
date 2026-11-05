from __future__ import annotations

import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


REPORT = Path(
    "/tmp/SM3_09C7_B3E_A1_D4_TEMPORAL_SIGNAL_ENGINE_AUDIT.json"
)


TARGET_HELPERS = [
    "_platform_signal_vector",
    "_platform_surface",
    "_platform_timestamp",
    "_platform_load",
]


TARGET_FUNCTIONS = [
    "production_platform_dynamics_evidence_ingest",
    "production_platform_preference_signal_ingest",
    "production_platform_dynamics_snapshot_build",
]


# ============================================================
# 1. HELPER SOURCES
# ============================================================

helpers = []


for name in TARGET_HELPERS:

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:

        helpers.append({
            "name": name,
            "found": False,
        })

        continue

    try:
        signature = str(
            inspect.signature(
                obj
            )
        )
    except Exception:
        signature = None

    try:
        source = inspect.getsource(
            obj
        )
    except Exception as exc:
        source = (
            "SOURCE_UNAVAILABLE:"
            + repr(
                exc
            )
        )

    helpers.append({
        "name":
            name,

        "found":
            True,

        "signature":
            signature,

        "source":
            source,
    })


# ============================================================
# 2. CONSTANTS / SURFACES
# ============================================================

constants = {}


for name in (
    "_PLATFORM_SURFACES",
    "_PLATFORM_CLAIM_FAMILIES",
    "_PLATFORM_EVIDENCE_TYPES",
    "PLATFORM_DYNAMICS_ENGINE_VERSION",
    "PLATFORM_DYNAMICS_EVIDENCE_CONTRACT_VERSION",
    "PLATFORM_PREFERENCE_SIGNAL_CONTRACT_VERSION",
    "PLATFORM_DYNAMICS_SNAPSHOT_CONTRACT_VERSION",
):

    value = getattr(
        ws,
        name,
        None,
    )

    if isinstance(
        value,
        set,
    ):
        value = sorted(
            value
        )

    elif isinstance(
        value,
        dict,
    ):

        normalized = {}

        for key,item in value.items():

            if isinstance(
                item,
                set,
            ):
                normalized[
                    key
                ] = sorted(
                    item
                )

            else:
                normalized[
                    key
                ] = item

        value = normalized

    constants[
        name
    ] = value


# ============================================================
# 3. CURRENT EVIDENCE CONTENT
# ============================================================

evidence_root = getattr(
    ws,
    "PRODUCTION_PLATFORM_DYNAMICS_EVIDENCE",
)

evidence_rows = []


now = datetime.now(
    timezone.utc
)


for path in sorted(
    evidence_root.glob(
        "PDE_*.json"
    )
):

    rec = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    valid_until = rec.get(
        "valid_until"
    )

    temporal_status = (
        "NO_EXPIRY"
    )

    if valid_until:

        try:
            expiry = datetime.fromisoformat(
                valid_until
            )

            if expiry.tzinfo is None:
                expiry = expiry.replace(
                    tzinfo=timezone.utc
                )

            temporal_status = (
                "EXPIRED"
                if expiry < now
                else "CURRENT"
            )

        except Exception:
            temporal_status = (
                "INVALID_VALID_UNTIL"
            )

    evidence_rows.append({
        "evidence_id":
            rec.get(
                "evidence_id"
            ),

        "platform":
            rec.get(
                "platform"
            ),

        "surface":
            rec.get(
                "surface"
            ),

        "evidence_type":
            rec.get(
                "evidence_type"
            ),

        "source_ref":
            rec.get(
                "source_ref"
            ),

        "source_origin":
            rec.get(
                "source_origin"
            ),

        "source_date":
            rec.get(
                "source_date"
            ),

        "observed_at":
            rec.get(
                "observed_at"
            ),

        "valid_until":
            valid_until,

        "temporal_status_now":
            temporal_status,

        "evidence_confidence":
            rec.get(
                "evidence_confidence"
            ),

        "epistemic_status":
            rec.get(
                "epistemic_status"
            ),

        "claims":
            rec.get(
                "claims"
            )
            or [],
    })


# ============================================================
# 4. SOURCE INSPECTION
# ============================================================

function_sources = {}


for name in TARGET_FUNCTIONS:

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:
        continue

    try:
        source = inspect.getsource(
            obj
        )
    except Exception:
        source = ""

    function_sources[
        name
    ] = source


snapshot_source = function_sources.get(
    "production_platform_dynamics_snapshot_build",
    "",
)


# ============================================================
# 5. TEMPORAL REFERENCES IN SNAPSHOT BUILDER
# ============================================================

temporal_references = {

    "references_as_of":
        "as_of" in snapshot_source,

    "references_valid_until":
        "valid_until" in snapshot_source,

    "references_source_date":
        "source_date" in snapshot_source,

    "references_observed_at":
        "observed_at" in snapshot_source,

    "references_window_started_at":
        "window_started_at" in snapshot_source,

    "references_window_ended_at":
        "window_ended_at" in snapshot_source,

    "references_evidence_confidence":
        "evidence_confidence" in snapshot_source,

    "references_signal_vector":
        "signal_vector" in snapshot_source,

    "uses_statistics_fmean":
        "statistics.fmean" in snapshot_source,

    "references_weight":
        "weight" in snapshot_source.lower(),

    "references_decay":
        "decay" in snapshot_source.lower(),

    "references_drift":
        "drift" in snapshot_source.lower(),

    "references_stale":
        "stale" in snapshot_source.lower(),

    "references_expired":
        "expired" in snapshot_source.lower(),
}


# ============================================================
# 6. SNAPSHOT VECTOR SEMANTICS
# ============================================================

signal_vector_helper = next(
    (
        row
        for row in helpers
        if row[
            "name"
        ]
        == "_platform_signal_vector"
    ),
    None,
)


signal_vector_source = (
    signal_vector_helper.get(
        "source"
    )
    if signal_vector_helper
    else ""
)


vector_semantics = {

    "mentions_retention_strength":
        "retention_strength"
        in signal_vector_source,

    "mentions_active_engagement_strength":
        "active_engagement_strength"
        in signal_vector_source,

    "mentions_conversion_strength":
        "conversion_strength"
        in signal_vector_source,

    "mentions_negative_feedback_strength":
        "negative_feedback_strength"
        in signal_vector_source,

    "mentions_average_watch_seconds":
        "average_watch_seconds"
        in signal_vector_source,

    "mentions_hold_rate_2s":
        "hold_rate_2s"
        in signal_vector_source,

    "mentions_hold_rate_3s":
        "hold_rate_3s"
        in signal_vector_source,

    "mentions_completion_rate":
        "completion_rate"
        in signal_vector_source,

    "mentions_replay_rate":
        "replay_rate"
        in signal_vector_source,

    "mentions_skip_rate":
        "skip_rate"
        in signal_vector_source,

    "mentions_share_rate":
        "share_rate"
        in signal_vector_source,

    "mentions_save_rate":
        "save_rate"
        in signal_vector_source,

    "mentions_profile_visit_rate":
        "profile_visit_rate"
        in signal_vector_source,

    "mentions_follow_rate":
        "follow_rate"
        in signal_vector_source,

    "mentions_conversion_rate":
        "conversion_rate"
        in signal_vector_source,

    "explicit_metric_weights":
        "weight"
        in signal_vector_source.lower(),
}


# ============================================================
# 7. CURRENT STORAGE COUNTS
# ============================================================

signal_root = getattr(
    ws,
    "PRODUCTION_PLATFORM_PREFERENCE_SIGNALS",
)

snapshot_root = getattr(
    ws,
    "PRODUCTION_PLATFORM_DYNAMICS_SNAPSHOTS",
)


signal_count = (
    len(
        list(
            signal_root.glob(
                "PPS_*.json"
            )
        )
    )
    if signal_root.exists()
    else 0
)


snapshot_count = (
    len(
        list(
            snapshot_root.glob(
                "PDS_*.json"
            )
        )
    )
    if snapshot_root.exists()
    else 0
)


# ============================================================
# 8. TEMPORAL RISK FLAGS
# These are observations about the current source,
# not mutations or simulated production calls.
# ============================================================

temporal_risk_flags = []


if (
    temporal_references[
        "references_as_of"
    ]
    and
    not temporal_references[
        "references_valid_until"
    ]
):
    temporal_risk_flags.append(
        "SNAPSHOT_AS_OF_WITHOUT_VISIBLE_VALID_UNTIL_CHECK"
    )


if not temporal_references[
    "references_observed_at"
]:
    temporal_risk_flags.append(
        "SNAPSHOT_NO_VISIBLE_OBSERVED_AT_CHECK"
    )


if not temporal_references[
    "references_source_date"
]:
    temporal_risk_flags.append(
        "SNAPSHOT_NO_VISIBLE_SOURCE_DATE_CHECK"
    )


if not temporal_references[
    "references_window_ended_at"
]:
    temporal_risk_flags.append(
        "SNAPSHOT_NO_VISIBLE_SIGNAL_WINDOW_END_CHECK"
    )


if not temporal_references[
    "references_decay"
]:
    temporal_risk_flags.append(
        "NO_VISIBLE_CONFIDENCE_DECAY"
    )


if not temporal_references[
    "references_drift"
]:
    temporal_risk_flags.append(
        "NO_VISIBLE_DRIFT_LOGIC"
    )


# ============================================================
# 9. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3E-A1-D4",

    "status":
        "TEMPORAL_SEMANTICS_AND_SIGNAL_ENGINE_AUDIT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "constants":
        constants,

    "helpers":
        helpers,

    "evidence":
        evidence_rows,

    "signal_count":
        signal_count,

    "snapshot_count":
        snapshot_count,

    "snapshot_temporal_references":
        temporal_references,

    "signal_vector_semantics":
        vector_semantics,

    "temporal_risk_flags":
        temporal_risk_flags,

    "production_write_performed":
        False,

    "route_called":
        False,

    "network_request_performed":
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
# 10. OUTPUT
# ============================================================

print(
    "=== PLATFORM SURFACES ==="
)

print(
    json.dumps(
        constants.get(
            "_PLATFORM_SURFACES"
        ),
        indent=2,
        ensure_ascii=False,
        default=str,
    )
)


print(
    "\n=== CLAIM FAMILIES ==="
)

print(
    json.dumps(
        constants.get(
            "_PLATFORM_CLAIM_FAMILIES"
        ),
        ensure_ascii=False,
        default=str,
    )
)


print(
    "\n=== CURRENT EVIDENCE ==="
)

for row in evidence_rows:

    print("")
    print(
        "EVIDENCE_ID="
        + str(
            row[
                "evidence_id"
            ]
        )
    )

    print(
        "SCOPE="
        + str(
            row[
                "platform"
            ]
        )
        + "/"
        + str(
            row[
                "surface"
            ]
        )
    )

    print(
        "TYPE="
        + str(
            row[
                "evidence_type"
            ]
        )
    )

    print(
        "SOURCE_ORIGIN="
        + str(
            row[
                "source_origin"
            ]
        )
    )

    print(
        "SOURCE_DATE="
        + str(
            row[
                "source_date"
            ]
        )
    )

    print(
        "OBSERVED_AT="
        + str(
            row[
                "observed_at"
            ]
        )
    )

    print(
        "VALID_UNTIL="
        + str(
            row[
                "valid_until"
            ]
        )
    )

    print(
        "TEMPORAL_STATUS_NOW="
        + str(
            row[
                "temporal_status_now"
            ]
        )
    )

    print(
        "CONFIDENCE="
        + str(
            row[
                "evidence_confidence"
            ]
        )
    )

    print(
        "CLAIMS="
        + json.dumps(
            row[
                "claims"
            ],
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== SNAPSHOT TEMPORAL REFERENCES ==="
)

for name,value in temporal_references.items():

    print(
        name.upper()
        + "="
        + str(
            value
        )
    )


print(
    "\n=== SIGNAL VECTOR SEMANTICS ==="
)

for name,value in vector_semantics.items():

    print(
        name.upper()
        + "="
        + str(
            value
        )
    )


print(
    "\n=== TEMPORAL RISK FLAGS ==="
)

if temporal_risk_flags:

    for flag in temporal_risk_flags:

        print(
            "RISK="
            + flag
        )

else:

    print(
        "RISK=NONE"
    )


print(
    "\nSIGNAL_COUNT="
    + str(
        signal_count
    )
)

print(
    "SNAPSHOT_COUNT="
    + str(
        snapshot_count
    )
)


print(
    "\n=== HELPER SOURCES ==="
)

for row in helpers:

    print(
        "\n--- "
        + row[
            "name"
        ]
        + " ---"
    )

    print(
        row.get(
            "source"
        )
    )


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
)

print(
    "ROUTE_CALLED=False"
)

print(
    "NETWORK_REQUEST_PERFORMED=False"
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
    "SM3_09C7_B3E_A1_D4_TEMPORAL_SEMANTICS_AND_SIGNAL_ENGINE_AUDIT_COMPLETE"
)
