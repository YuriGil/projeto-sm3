from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ENGINE_PATH = Path(
    sys.argv[1]
)

REPORT_PATH = Path(
    sys.argv[2]
)


spec = importlib.util.spec_from_file_location(
    "sm3_temporal_validity",
    ENGINE_PATH,
)

module = importlib.util.module_from_spec(
    spec
)

assert spec.loader is not None

spec.loader.exec_module(
    module
)


tests = []


def record(
    name,
    passed,
    detail=None,
):
    tests.append({
        "name":
            name,

        "passed":
            bool(
                passed
            ),

        "detail":
            detail,
    })


def expect_pass(
    name,
    fn,
):
    try:
        result = fn()

    except Exception as exc:
        record(
            name,
            False,
            {
                "unexpected_exception":
                    repr(
                        exc
                    )
            },
        )

        return None

    record(
        name,
        True,
    )

    return result


def expect_error(
    name,
    expected_code,
    fn,
):
    try:
        fn()

    except module.TemporalValidityError as exc:

        record(
            name,
            exc.code
            == expected_code,
            {
                "expected":
                    expected_code,

                "actual":
                    exc.code,

                "message":
                    str(
                        exc
                    ),
            },
        )

        return

    except Exception as exc:

        record(
            name,
            False,
            {
                "expected":
                    expected_code,

                "unexpected_exception":
                    repr(
                        exc
                    ),
            },
        )

        return

    record(
        name,
        False,
        {
            "expected":
                expected_code,

            "actual":
                "NO_EXCEPTION",
        },
    )


AS_OF = (
    "2026-09-27T20:00:00+00:00"
)


BASE_EVIDENCE = {
    "evidence_id":
        "PDE_test",

    "source_date":
        "2026-09-20T00:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",

    "valid_until":
        "2026-10-27T00:00:00+00:00",
}


BASE_SIGNAL = {
    "signal_id":
        "PPS_test",

    "window_started_at":
        "2026-09-26T20:00:00+00:00",

    "window_ended_at":
        "2026-09-27T19:00:00+00:00",
}


# ============================================================
# EVIDENCE
# ============================================================

result = expect_pass(
    "EVIDENCE_CURRENT_PASS",
    lambda:
        module.validate_evidence_temporal(
            BASE_EVIDENCE,
            AS_OF,
        ),
)


record(
    "EVIDENCE_CURRENT_ELIGIBLE",
    (
        result is not None
        and
        result.get(
            "eligible"
        )
        is True
    ),
)


equal_expiry = {
    **BASE_EVIDENCE,
    "valid_until":
        AS_OF,
}


expect_pass(
    "EVIDENCE_VALID_UNTIL_EQUAL_AS_OF_PASS",
    lambda:
        module.validate_evidence_temporal(
            equal_expiry,
            AS_OF,
        ),
)


no_expiry = {
    **BASE_EVIDENCE,
    "valid_until":
        None,
}


no_expiry_result = expect_pass(
    "EVIDENCE_NO_HARD_EXPIRY_PASS",
    lambda:
        module.validate_evidence_temporal(
            no_expiry,
            AS_OF,
        ),
)


record(
    "EVIDENCE_NO_HARD_EXPIRY_REPORTED",
    (
        no_expiry_result is not None
        and
        no_expiry_result.get(
            "hard_expiry_present"
        )
        is False
    ),
)


future_source = {
    **BASE_EVIDENCE,
    "source_date":
        "2026-09-28T00:00:00+00:00",
}


expect_error(
    "EVIDENCE_FUTURE_SOURCE_FAIL",
    "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE",
    lambda:
        module.validate_evidence_temporal(
            future_source,
            AS_OF,
        ),
)


future_observed = {
    **BASE_EVIDENCE,
    "observed_at":
        "2026-09-27T21:00:00+00:00",
}


expect_error(
    "EVIDENCE_FUTURE_OBSERVED_FAIL",
    "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE",
    lambda:
        module.validate_evidence_temporal(
            future_observed,
            AS_OF,
        ),
)


expired = {
    **BASE_EVIDENCE,
    "valid_until":
        "2026-09-27T19:59:59+00:00",
}


expect_error(
    "EVIDENCE_EXPIRED_FAIL",
    "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED",
    lambda:
        module.validate_evidence_temporal(
            expired,
            AS_OF,
        ),
)


naive_source = {
    **BASE_EVIDENCE,
    "source_date":
        "2026-09-20T00:00:00",
}


expect_error(
    "EVIDENCE_NAIVE_TIMESTAMP_FAIL",
    "PLATFORM_TEMPORAL_TIMESTAMP_TZ_REQUIRED",
    lambda:
        module.validate_evidence_temporal(
            naive_source,
            AS_OF,
        ),
)


bad_timestamp = {
    **BASE_EVIDENCE,
    "observed_at":
        "not-a-timestamp",
}


expect_error(
    "EVIDENCE_INVALID_TIMESTAMP_FAIL",
    "PLATFORM_TEMPORAL_TIMESTAMP_INVALID",
    lambda:
        module.validate_evidence_temporal(
            bad_timestamp,
            AS_OF,
        ),
)


# ============================================================
# SIGNAL
# ============================================================

signal_result = expect_pass(
    "SIGNAL_CURRENT_PASS",
    lambda:
        module.validate_signal_temporal(
            BASE_SIGNAL,
            AS_OF,
        ),
)


record(
    "SIGNAL_CURRENT_ELIGIBLE",
    (
        signal_result is not None
        and
        signal_result.get(
            "eligible"
        )
        is True
    ),
)


signal_equal_asof = {
    **BASE_SIGNAL,
    "window_ended_at":
        AS_OF,
}


expect_pass(
    "SIGNAL_END_EQUAL_AS_OF_PASS",
    lambda:
        module.validate_signal_temporal(
            signal_equal_asof,
            AS_OF,
        ),
)


invalid_window = {
    **BASE_SIGNAL,
    "window_started_at":
        "2026-09-27T19:00:00+00:00",

    "window_ended_at":
        "2026-09-27T19:00:00+00:00",
}


expect_error(
    "SIGNAL_ZERO_WINDOW_FAIL",
    "PLATFORM_TEMPORAL_SIGNAL_WINDOW_INVALID",
    lambda:
        module.validate_signal_temporal(
            invalid_window,
            AS_OF,
        ),
)


reversed_window = {
    **BASE_SIGNAL,
    "window_started_at":
        "2026-09-27T19:30:00+00:00",

    "window_ended_at":
        "2026-09-27T19:00:00+00:00",
}


expect_error(
    "SIGNAL_REVERSED_WINDOW_FAIL",
    "PLATFORM_TEMPORAL_SIGNAL_WINDOW_INVALID",
    lambda:
        module.validate_signal_temporal(
            reversed_window,
            AS_OF,
        ),
)


future_signal = {
    **BASE_SIGNAL,
    "window_ended_at":
        "2026-09-27T20:00:01+00:00",
}


expect_error(
    "SIGNAL_FUTURE_WINDOW_FAIL",
    "PLATFORM_TEMPORAL_SIGNAL_WINDOW_FUTURE",
    lambda:
        module.validate_signal_temporal(
            future_signal,
            AS_OF,
        ),
)


# ============================================================
# AS_OF VALIDATION
# ============================================================

expect_error(
    "AS_OF_NAIVE_FAIL",
    "PLATFORM_TEMPORAL_TIMESTAMP_TZ_REQUIRED",
    lambda:
        module.validate_evidence_temporal(
            BASE_EVIDENCE,
            "2026-09-27T20:00:00",
        ),
)


expect_error(
    "AS_OF_INVALID_FAIL",
    "PLATFORM_TEMPORAL_TIMESTAMP_INVALID",
    lambda:
        module.validate_evidence_temporal(
            BASE_EVIDENCE,
            "invalid",
        ),
)


# ============================================================
# BATCH / DETERMINISM / IMMUTABILITY
# ============================================================

evidence_a = {
    **BASE_EVIDENCE,
    "evidence_id":
        "PDE_b",
}


evidence_b = {
    **BASE_EVIDENCE,
    "evidence_id":
        "PDE_a",
}


signal_a = {
    **BASE_SIGNAL,
    "signal_id":
        "PPS_b",
}


signal_b = {
    **BASE_SIGNAL,
    "signal_id":
        "PPS_a",
}


original_evidence = copy.deepcopy(
    [
        evidence_a,
        evidence_b,
    ]
)

original_signals = copy.deepcopy(
    [
        signal_a,
        signal_b,
    ]
)


batch_1 = expect_pass(
    "BATCH_VALID_PASS",
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,
            evidence=[
                evidence_a,
                evidence_b,
            ],
            signals=[
                signal_a,
                signal_b,
            ],
        ),
)


batch_2 = expect_pass(
    "BATCH_DETERMINISTIC_SECOND_PASS",
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,
            evidence=[
                evidence_b,
                evidence_a,
            ],
            signals=[
                signal_b,
                signal_a,
            ],
        ),
)


record(
    "BATCH_SORTED_EVIDENCE_IDS",
    (
        batch_1 is not None
        and
        [
            row.get(
                "evidence_id"
            )
            for row in batch_1[
                "evidence"
            ]
        ]
        == [
            "PDE_a",
            "PDE_b",
        ]
    ),
)


record(
    "BATCH_SORTED_SIGNAL_IDS",
    (
        batch_1 is not None
        and
        [
            row.get(
                "signal_id"
            )
            for row in batch_1[
                "signals"
            ]
        ]
        == [
            "PPS_a",
            "PPS_b",
        ]
    ),
)


record(
    "BATCH_ORDER_INDEPENDENT",
    batch_1
    == batch_2,
)


record(
    "INPUT_EVIDENCE_NOT_MUTATED",
    [
        evidence_a,
        evidence_b,
    ]
    == original_evidence,
)


record(
    "INPUT_SIGNALS_NOT_MUTATED",
    [
        signal_a,
        signal_b,
    ]
    == original_signals,
)


record(
    "CONFIDENCE_DECAY_NOT_APPLIED",
    (
        batch_1 is not None
        and
        batch_1.get(
            "confidence_decay_applied"
        )
        is False
        and
        batch_1.get(
            "confidence_decay_reason"
        )
        == "NUMERIC_POLICY_DEFERRED"
    ),
)


record(
    "POLICY_VERSION_EXACT",
    (
        module.TEMPORAL_VALIDITY_POLICY_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    ),
)


record(
    "ENGINE_VERSION_EXACT",
    (
        module.TEMPORAL_VALIDITY_ENGINE_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    ),
)


# ============================================================
# RESULT
# ============================================================

failures = [
    row
    for row in tests
    if not row[
        "passed"
    ]
]


engine_sha = hashlib.sha256(
    ENGINE_PATH.read_bytes()
).hexdigest()


report = {
    "phase":
        "09C7-B3E-A4",

    "status":
        "TEMPORAL_VALIDITY_ENGINE_BEHAVIOR_TEST_COMPLETE",

    "policy_version":
        module.TEMPORAL_VALIDITY_POLICY_VERSION,

    "engine_version":
        module.TEMPORAL_VALIDITY_ENGINE_VERSION,

    "engine_sha256":
        engine_sha,

    "test_count":
        len(
            tests
        ),

    "pass_count":
        len(
            tests
        )
        - len(
            failures
        ),

    "failure_count":
        len(
            failures
        ),

    "behavior_pass":
        not failures,

    "confidence_decay_applied":
        False,

    "confidence_decay_numeric_policy_deferred":
        True,

    "tests":
        tests,

    "production_source_modified":
        False,

    "production_state_modified":
        False,

    "production_restart_executed":
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


REPORT_PATH.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== TEMPORAL VALIDITY BEHAVIOR TEST ==="
)

print(
    "POLICY_VERSION="
    + report[
        "policy_version"
    ]
)

print(
    "ENGINE_VERSION="
    + report[
        "engine_version"
    ]
)

print(
    "ENGINE_SHA256="
    + report[
        "engine_sha256"
    ]
)

print(
    "TEST_COUNT="
    + str(
        report[
            "test_count"
        ]
    )
)

print(
    "PASS_COUNT="
    + str(
        report[
            "pass_count"
        ]
    )
)

print(
    "FAILURE_COUNT="
    + str(
        report[
            "failure_count"
        ]
    )
)

print(
    "BEHAVIOR_PASS="
    + str(
        report[
            "behavior_pass"
        ]
    )
)

print(
    "CONFIDENCE_DECAY_APPLIED=False"
)

print(
    "CONFIDENCE_DECAY_NUMERIC_POLICY_DEFERRED=True"
)


print(
    "\n=== TESTS ==="
)

for row in tests:

    print(
        row[
            "name"
        ]
        + "="
        + (
            "PASS"
            if row[
                "passed"
            ]
            else "FAIL"
        )
    )

    if not row[
        "passed"
    ]:
        print(
            "  DETAIL="
            + json.dumps(
                row.get(
                    "detail"
                ),
                ensure_ascii=False,
            )
        )


print(
    "\nPRODUCTION_SOURCE_MODIFIED=False"
)

print(
    "PRODUCTION_STATE_MODIFIED=False"
)

print(
    "PRODUCTION_RESTART_EXECUTED=False"
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
        REPORT_PATH
    )
)

print(
    "SM3_09C7_B3E_A4_TEMPORAL_VALIDITY_BEHAVIOR_TEST_COMPLETE"
)


if failures:
    raise SystemExit(
        1
    )
