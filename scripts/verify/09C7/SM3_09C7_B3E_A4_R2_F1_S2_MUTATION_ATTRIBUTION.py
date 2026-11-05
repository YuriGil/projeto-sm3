from __future__ import annotations

import ast
import hashlib
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


STATE_A = Path(sys.argv[1])
STATE_B = Path(sys.argv[2])
S1_REPORT = Path(sys.argv[3])
RUNTIME_SOURCE = Path(sys.argv[4])
REPORT = Path(sys.argv[5])

F1_START_RAW = sys.argv[6]
F1_BASELINE_RAW = sys.argv[7]
F1_END_RAW = sys.argv[8]


def parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if parsed.tzinfo is None:
        raise ValueError(
            "TIMESTAMP_TZ_REQUIRED"
        )

    return parsed.astimezone(
        timezone.utc
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


a = load(
    STATE_A
)

b = load(
    STATE_B
)

s1 = load(
    S1_REPORT
)


# ============================================================
# F1 WINDOW
# ============================================================

f1_start = parse_ts(
    F1_START_RAW
)

f1_baseline = parse_ts(
    F1_BASELINE_RAW
)

f1_end = parse_ts(
    F1_END_RAW
)


# Small tolerance for filesystem timestamp ordering.
window_start = (
    f1_start
    - timedelta(
        seconds=15
    )
)

window_end = (
    f1_end
    + timedelta(
        seconds=15
    )
)


# ============================================================
# CLASSIFY STATE PATHS
# ============================================================

def classify_path(path: str) -> str:

    if path.startswith(
        "culture_runner_watchdog/snapshots/"
    ):
        return "WATCHDOG_IMMUTABLE_SNAPSHOT"

    if path == (
        "culture_runner_watchdog/latest.json"
    ):
        return "WATCHDOG_LATEST_POINTER"

    if path == (
        "culture_runner_control/state.json"
    ):
        return "RUNNER_CONTROL_MUTABLE_STATE"

    if path.startswith(
        "culture_runner_watchdog/"
    ):
        return "WATCHDOG_OTHER"

    if path.startswith(
        "culture_runner_control/"
    ):
        return "RUNNER_CONTROL_OTHER"

    return "OTHER_PRODUCTION_STATE"


window_records = []


for item in a.get(
    "files",
    []
):

    raw_mtime = item.get(
        "mtime_utc"
    )

    if not raw_mtime:
        continue

    mtime = parse_ts(
        raw_mtime
    )

    if (
        window_start
        <= mtime
        <= window_end
    ):

        enriched = dict(
            item
        )

        enriched[
            "classification"
        ] = classify_path(
            str(
                item.get(
                    "path"
                )
                or ""
            )
        )

        window_records.append(
            enriched
        )


window_records.sort(
    key=lambda item: (
        item.get(
            "mtime_ns",
            0,
        ),
        item.get(
            "path",
            "",
        ),
    )
)


watchdog_snapshot_records = [
    item
    for item in window_records
    if item[
        "classification"
    ]
    == "WATCHDOG_IMMUTABLE_SNAPSHOT"
]


mutable_background_records = [
    item
    for item in window_records
    if item[
        "classification"
    ]
    in {
        "WATCHDOG_LATEST_POINTER",
        "RUNNER_CONTROL_MUTABLE_STATE",
        "WATCHDOG_OTHER",
        "RUNNER_CONTROL_OTHER",
    }
]


other_records = [
    item
    for item in window_records
    if item[
        "classification"
    ]
    == "OTHER_PRODUCTION_STATE"
]


# ============================================================
# WATCHDOG PERIODICITY
# ============================================================

watchdog_all = []


for item in a.get(
    "files",
    []
):

    path = str(
        item.get(
            "path"
        )
        or ""
    )

    if not path.startswith(
        "culture_runner_watchdog/snapshots/"
    ):
        continue

    raw_mtime = item.get(
        "mtime_utc"
    )

    if not raw_mtime:
        continue

    watchdog_all.append({
        "path":
            path,

        "mtime":
            parse_ts(
                raw_mtime
            ),

        "mtime_utc":
            raw_mtime,

        "json_metadata":
            item.get(
                "json_metadata"
            ),
    })


watchdog_all.sort(
    key=lambda item:
        item[
            "mtime"
        ]
)


recent_watchdog = watchdog_all[
    -12:
]


intervals_seconds = []


for before,after in zip(
    recent_watchdog,
    recent_watchdog[
        1:
    ],
):

    intervals_seconds.append(
        (
            after[
                "mtime"
            ]
            - before[
                "mtime"
            ]
        ).total_seconds()
    )


median_interval = (
    statistics.median(
        intervals_seconds
    )
    if intervals_seconds
    else None
)


periodic_5m_pattern = (
    median_interval
    is not None
    and
    295.0
    <= median_interval
    <= 305.0
)


recent_statuses = []


for item in recent_watchdog:

    metadata = item.get(
        "json_metadata"
    )

    if isinstance(
        metadata,
        dict,
    ):

        status = metadata.get(
            "status"
        )

        if status is not None:

            recent_statuses.append(
                status
            )


all_reported_statuses_disarmed = (
    bool(
        recent_statuses
    )
    and
    all(
        status
        == "DISARMED"
        for status in recent_statuses
    )
)


# ============================================================
# S1 IDLE RESULT CONFIRMATION
# ============================================================

s1_idle_confirmed = (
    s1.get(
        "status"
    )
    == "PRODUCTION_STATE_CONCURRENT_WRITER_AUDIT_COMPLETE"
    and
    s1.get(
        "file_count_a"
    )
    == 602
    and
    s1.get(
        "file_count_b"
    )
    == 602
    and
    s1.get(
        "added_count"
    )
    == 0
    and
    s1.get(
        "removed_count"
    )
    == 0
    and
    s1.get(
        "changed_count"
    )
    == 0
    and
    s1.get(
        "idle_delta_detected"
    )
    is False
)


# ============================================================
# STATIC SOURCE ATTRIBUTION
# ============================================================

source = RUNTIME_SOURCE.read_text(
    encoding="utf-8-sig"
)

source_lower = source.lower()


tree = ast.parse(
    source,
    filename=str(
        RUNTIME_SOURCE
    ),
)


watchdog_functions = []


for node in ast.walk(
    tree
):

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        if "watchdog" in node.name.lower():

            watchdog_functions.append(
                node.name
            )


watchdog_functions = sorted(
    set(
        watchdog_functions
    )
)


watchdog_literal_present = (
    "culture_runner_watchdog"
    in source
)


watchdog_snapshot_literal_present = (
    "snapshots"
    in source_lower
    and
    "watchdog"
    in source_lower
)


watchdog_latest_literal_present = (
    "latest.json"
    in source_lower
    and
    "watchdog"
    in source_lower
)


# Collect relevant lines without dumping the whole worker.
source_lines = source.splitlines()

relevant_source_lines = []


for index,line in enumerate(
    source_lines,
    start=1,
):

    low = line.lower()

    if (
        "watchdog"
        in low
        or
        (
            "300"
            in line
            and
            (
                "interval"
                in low
                or
                "second"
                in low
                or
                "sleep"
                in low
            )
        )
    ):

        relevant_source_lines.append({
            "line":
                index,

            "text":
                line.strip(),
        })


relevant_source_lines = (
    relevant_source_lines[
        :120
    ]
)


# ============================================================
# ATTRIBUTION DECISION
# ============================================================

#
# The failed F1 gate observed a count increase of exactly +1.
#
# We attribute that increase only if:
#
# - exactly one append-only watchdog snapshot exists in F1 window
# - no OTHER production-state file exists in that window
# - watchdog shows independent periodic behavior
# - runtime source contains watchdog persistence implementation
#
# Mutable watchdog/control files may coexist because modifying
# an existing file does not explain a +1 file-count increment.
#

immutable_increment_candidate_count = len(
    watchdog_snapshot_records
)


unattributed_increment_candidate_count = len(
    other_records
)


exact_plus_one_watchdog_candidate = (
    immutable_increment_candidate_count
    == 1
)


no_other_state_in_f1_window = (
    unattributed_increment_candidate_count
    == 0
)


runtime_watchdog_implementation_present = (
    watchdog_literal_present
    and
    bool(
        watchdog_functions
    )
)


f1_count_delta_attributable_to_watchdog = (
    exact_plus_one_watchdog_candidate
    and
    no_other_state_in_f1_window
    and
    periodic_5m_pattern
    and
    runtime_watchdog_implementation_present
)


f1_candidate_exonerated_from_count_delta = (
    f1_count_delta_attributable_to_watchdog
)


#
# Safety-gate conclusion:
#
# Total production-state count is not a valid isolation invariant
# when known independent append-only background stores are active.
#
# Future gates must protect relevant scopes/hash sets and separately
# account for allowed background mutations rather than silently
# ignoring them.
#

total_file_count_equality_is_valid_global_invariant = False


scope_aware_mutation_accounting_required = True


report = {
    "phase":
        "09C7-B3E-A4-R2-F1-S2",

    "status":
        "PRODUCTION_STATE_MUTATION_ATTRIBUTION_COMPLETE",

    "runtime_source_sha256":
        sha256(
            RUNTIME_SOURCE
        ),

    "f1_window": {
        "candidate_mtime_utc":
            f1_start.isoformat(),

        "baseline_report_mtime_utc":
            f1_baseline.isoformat(),

        "focused_report_mtime_utc":
            f1_end.isoformat(),

        "analysis_window_started_at":
            window_start.isoformat(),

        "analysis_window_ended_at":
            window_end.isoformat(),
    },

    "window_record_count":
        len(
            window_records
        ),

    "window_records":
        window_records,

    "watchdog_snapshot_count_in_f1_window":
        len(
            watchdog_snapshot_records
        ),

    "mutable_background_record_count_in_f1_window":
        len(
            mutable_background_records
        ),

    "other_production_state_record_count_in_f1_window":
        len(
            other_records
        ),

    "watchdog_snapshot_records":
        watchdog_snapshot_records,

    "mutable_background_records":
        mutable_background_records,

    "other_records":
        other_records,

    "recent_watchdog_snapshot_count":
        len(
            recent_watchdog
        ),

    "watchdog_intervals_seconds":
        intervals_seconds,

    "watchdog_median_interval_seconds":
        median_interval,

    "watchdog_periodic_5m_pattern":
        periodic_5m_pattern,

    "watchdog_reported_statuses":
        recent_statuses,

    "all_reported_statuses_disarmed":
        all_reported_statuses_disarmed,

    "s1_idle_window_confirmed":
        s1_idle_confirmed,

    "watchdog_functions":
        watchdog_functions,

    "watchdog_literal_present":
        watchdog_literal_present,

    "watchdog_snapshot_literal_present":
        watchdog_snapshot_literal_present,

    "watchdog_latest_literal_present":
        watchdog_latest_literal_present,

    "runtime_watchdog_implementation_present":
        runtime_watchdog_implementation_present,

    "relevant_runtime_source_lines":
        relevant_source_lines,

    "expected_f1_file_count_delta":
        1,

    "immutable_increment_candidate_count":
        immutable_increment_candidate_count,

    "unattributed_increment_candidate_count":
        unattributed_increment_candidate_count,

    "exact_plus_one_watchdog_candidate":
        exact_plus_one_watchdog_candidate,

    "no_other_state_in_f1_window":
        no_other_state_in_f1_window,

    "f1_count_delta_attributable_to_watchdog":
        f1_count_delta_attributable_to_watchdog,

    "f1_candidate_exonerated_from_count_delta":
        f1_candidate_exonerated_from_count_delta,

    "total_file_count_equality_is_valid_global_invariant":
        total_file_count_equality_is_valid_global_invariant,

    "scope_aware_mutation_accounting_required":
        scope_aware_mutation_accounting_required,

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


print(
    "=== F1 MUTATION ATTRIBUTION ==="
)

print(
    "F1_WINDOW_START="
    + report[
        "f1_window"
    ][
        "analysis_window_started_at"
    ]
)

print(
    "F1_WINDOW_END="
    + report[
        "f1_window"
    ][
        "analysis_window_ended_at"
    ]
)

print(
    "WINDOW_RECORD_COUNT="
    + str(
        report[
            "window_record_count"
        ]
    )
)

print(
    "WATCHDOG_SNAPSHOT_COUNT_IN_F1_WINDOW="
    + str(
        report[
            "watchdog_snapshot_count_in_f1_window"
        ]
    )
)

print(
    "MUTABLE_BACKGROUND_RECORD_COUNT_IN_F1_WINDOW="
    + str(
        report[
            "mutable_background_record_count_in_f1_window"
        ]
    )
)

print(
    "OTHER_PRODUCTION_STATE_RECORD_COUNT_IN_F1_WINDOW="
    + str(
        report[
            "other_production_state_record_count_in_f1_window"
        ]
    )
)


print(
    "\n=== F1 WINDOW RECORDS ==="
)

for item in window_records:

    print(
        item[
            "mtime_utc"
        ]
        + " | "
        + item[
            "classification"
        ]
        + " | "
        + item[
            "path"
        ]
    )

    metadata = item.get(
        "json_metadata"
    )

    if metadata:

        print(
            "  META="
            + json.dumps(
                metadata,
                ensure_ascii=False,
                default=str,
            )
        )


print(
    "\n=== WATCHDOG PERIODICITY ==="
)

print(
    "RECENT_WATCHDOG_SNAPSHOT_COUNT="
    + str(
        report[
            "recent_watchdog_snapshot_count"
        ]
    )
)

print(
    "WATCHDOG_INTERVALS_SECONDS="
    + json.dumps(
        intervals_seconds
    )
)

print(
    "WATCHDOG_MEDIAN_INTERVAL_SECONDS="
    + str(
        median_interval
    )
)

print(
    "WATCHDOG_PERIODIC_5M_PATTERN="
    + str(
        periodic_5m_pattern
    )
)

print(
    "ALL_REPORTED_STATUSES_DISARMED="
    + str(
        all_reported_statuses_disarmed
    )
)


print(
    "\n=== RUNTIME SOURCE ATTRIBUTION ==="
)

print(
    "WATCHDOG_FUNCTIONS="
    + json.dumps(
        watchdog_functions
    )
)

print(
    "WATCHDOG_LITERAL_PRESENT="
    + str(
        watchdog_literal_present
    )
)

print(
    "WATCHDOG_SNAPSHOT_LITERAL_PRESENT="
    + str(
        watchdog_snapshot_literal_present
    )
)

print(
    "WATCHDOG_LATEST_LITERAL_PRESENT="
    + str(
        watchdog_latest_literal_present
    )
)

print(
    "RUNTIME_WATCHDOG_IMPLEMENTATION_PRESENT="
    + str(
        runtime_watchdog_implementation_present
    )
)


print(
    "\n=== ATTRIBUTION VERDICT ==="
)

print(
    "EXPECTED_F1_FILE_COUNT_DELTA=1"
)

print(
    "IMMUTABLE_INCREMENT_CANDIDATE_COUNT="
    + str(
        immutable_increment_candidate_count
    )
)

print(
    "UNATTRIBUTED_INCREMENT_CANDIDATE_COUNT="
    + str(
        unattributed_increment_candidate_count
    )
)

print(
    "EXACT_PLUS_ONE_WATCHDOG_CANDIDATE="
    + str(
        exact_plus_one_watchdog_candidate
    )
)

print(
    "NO_OTHER_STATE_IN_F1_WINDOW="
    + str(
        no_other_state_in_f1_window
    )
)

print(
    "F1_COUNT_DELTA_ATTRIBUTABLE_TO_WATCHDOG="
    + str(
        f1_count_delta_attributable_to_watchdog
    )
)

print(
    "F1_CANDIDATE_EXONERATED_FROM_COUNT_DELTA="
    + str(
        f1_candidate_exonerated_from_count_delta
    )
)

print(
    "TOTAL_FILE_COUNT_EQUALITY_VALID_GLOBAL_INVARIANT=False"
)

print(
    "SCOPE_AWARE_MUTATION_ACCOUNTING_REQUIRED=True"
)

print(
    "S1_IDLE_WINDOW_CONFIRMED="
    + str(
        s1_idle_confirmed
    )
)


print(
    "\nPRODUCTION_WRITE_PERFORMED=False"
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
    "SM3_09C7_B3E_A4_R2_F1_S2_MUTATION_ATTRIBUTION_COMPLETE"
)
