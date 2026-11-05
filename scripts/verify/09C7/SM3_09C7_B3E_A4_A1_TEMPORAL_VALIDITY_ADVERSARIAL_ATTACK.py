from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ENGINE_PATH = Path(sys.argv[1])
REPORT_PATH = Path(sys.argv[2])


EXPECTED_ENGINE_SHA = (
    "4a8b8c10c89bb02931aafae4c59d45ca"
    "6dfe16ba20e92e12c830deae78aa3753"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


actual_engine_sha = sha256(
    ENGINE_PATH
)


if actual_engine_sha != EXPECTED_ENGINE_SHA:
    raise SystemExit(
        "A4_A1_ENGINE_SHA_MISMATCH:"
        + actual_engine_sha
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


findings = []


def add(
    attack_id,
    severity,
    title,
    passed,
    expected=None,
    actual=None,
    classification="ENGINE_REQUIREMENT",
):
    findings.append({
        "attack_id":
            attack_id,

        "severity":
            severity,

        "title":
            title,

        "passed":
            bool(passed),

        "finding":
            "PASS" if passed else "GAP",

        "classification":
            classification,

        "expected":
            expected,

        "actual":
            actual,
    })


def call_ok(fn):
    try:
        value = fn()

        return (
            True,
            value,
            None,
        )

    except Exception as exc:

        return (
            False,
            None,
            exc,
        )


def error_code(exc):
    return getattr(
        exc,
        "code",
        None,
    )


AS_OF = "2026-09-27T20:00:00+00:00"


BASE_EVIDENCE = {
    "evidence_id":
        "PDE_attack",

    "source_date":
        "2026-09-20T00:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",

    "valid_until":
        "2026-10-27T00:00:00+00:00",
}


BASE_SIGNAL = {
    "signal_id":
        "PPS_attack",

    "window_started_at":
        "2026-09-26T20:00:00+00:00",

    "window_ended_at":
        "2026-09-27T19:00:00+00:00",
}


# ============================================================
# A. TIMEZONE / NORMALIZATION ATTACKS
# ============================================================

ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,
                "observed_at":
                    "2026-09-27T15:00:00-03:00",
            },
            AS_OF,
        )
)


add(
    "A001",
    "CRITICAL",
    "Equivalent timezone offsets normalize deterministically",
    (
        ok
        and
        value.get("observed_at")
        == "2026-09-27T18:00:00+00:00"
    ),
    expected="2026-09-27T18:00:00+00:00",
    actual=(
        value.get("observed_at")
        if value
        else repr(exc)
    ),
)


ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,
                "observed_at":
                    "2026-09-27T18:00:00Z",
            },
            AS_OF,
        )
)


add(
    "A002",
    "HIGH",
    "Z timezone form accepted and normalized",
    (
        ok
        and
        value.get("observed_at")
        == "2026-09-27T18:00:00+00:00"
    ),
    actual=(
        value.get("observed_at")
        if value
        else repr(exc)
    ),
)


ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,
                "observed_at":
                    "2026-09-27T18:00:00.123456+00:00",
            },
            AS_OF,
        )
)


add(
    "A003",
    "HIGH",
    "Microsecond precision remains valid",
    ok,
    actual=(
        value.get("observed_at")
        if value
        else repr(exc)
    ),
)


# ============================================================
# B. MALFORMED / EMPTY INPUTS
# ============================================================

ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,
                "source_date":
                    "",
            },
            AS_OF,
        )
)


add(
    "B001",
    "CRITICAL",
    "Empty source_date fails closed",
    (
        not ok
        and
        error_code(exc)
        == "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED"
    ),
    expected="PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED",
    actual=error_code(exc),
)


ok, value, exc = call_ok(
    lambda:
        module.validate_signal_temporal(
            {
                **BASE_SIGNAL,
                "window_ended_at":
                    None,
            },
            AS_OF,
        )
)


add(
    "B002",
    "CRITICAL",
    "Missing signal window end fails closed",
    (
        not ok
        and
        error_code(exc)
        == "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED"
    ),
    expected="PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED",
    actual=error_code(exc),
)


ok, value, exc = call_ok(
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of="",
            evidence=[],
            signals=[],
        )
)


add(
    "B003",
    "CRITICAL",
    "Missing as_of fails closed even for empty batch",
    (
        not ok
        and
        error_code(exc)
        == "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED"
    ),
    expected="PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED",
    actual=error_code(exc),
)


# ============================================================
# C. TEMPORAL ORDERING / CAUSALITY
# ============================================================

source_after_observation = {
    **BASE_EVIDENCE,

    "source_date":
        "2026-09-27T19:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",
}


ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            source_after_observation,
            AS_OF,
        )
)


# This is deliberately an architectural probe.
# If current engine accepts it, this becomes a contract gap,
# not an execution failure.
source_observation_order_enforced = (
    not ok
)


add(
    "C001",
    "HIGH",
    "Evidence cannot be observed before its source date",
    source_observation_order_enforced,
    expected="source_date <= observed_at",
    actual=(
        error_code(exc)
        if not ok
        else "ACCEPTED"
    ),
    classification="CONTRACT_PROBE",
)


ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,

                "source_date":
                    AS_OF,

                "observed_at":
                    AS_OF,
            },
            AS_OF,
        )
)


add(
    "C002",
    "HIGH",
    "Evidence exactly at as_of boundary is accepted",
    ok,
    actual=(
        "ACCEPTED"
        if ok
        else error_code(exc)
    ),
)


ok, value, exc = call_ok(
    lambda:
        module.validate_signal_temporal(
            {
                **BASE_SIGNAL,

                "window_started_at":
                    "2026-09-27T19:59:59.999999+00:00",

                "window_ended_at":
                    AS_OF,
            },
            AS_OF,
        )
)


add(
    "C003",
    "HIGH",
    "Positive subsecond signal window accepted",
    ok,
    actual=(
        value.get("window_duration_seconds")
        if value
        else error_code(exc)
    ),
)


# ============================================================
# D. BATCH FAIL-CLOSED
# ============================================================

invalid_evidence = {
    **BASE_EVIDENCE,

    "evidence_id":
        "PDE_bad",

    "observed_at":
        "2026-09-28T00:00:00+00:00",
}


ok, value, exc = call_ok(
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,

            evidence=[
                BASE_EVIDENCE,
                invalid_evidence,
            ],

            signals=[
                BASE_SIGNAL,
            ],
        )
)


add(
    "D001",
    "CRITICAL",
    "One invalid evidence fails entire batch",
    (
        not ok
        and
        error_code(exc)
        == "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE"
    ),
    expected=(
        "PLATFORM_TEMPORAL_EVIDENCE_"
        "OBSERVED_AT_FUTURE"
    ),
    actual=error_code(exc),
)


invalid_signal = {
    **BASE_SIGNAL,

    "signal_id":
        "PPS_bad",

    "window_ended_at":
        "2026-09-28T00:00:00+00:00",
}


ok, value, exc = call_ok(
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,

            evidence=[
                BASE_EVIDENCE,
            ],

            signals=[
                BASE_SIGNAL,
                invalid_signal,
            ],
        )
)


add(
    "D002",
    "CRITICAL",
    "One invalid signal fails entire batch",
    (
        not ok
        and
        error_code(exc)
        == "PLATFORM_TEMPORAL_SIGNAL_WINDOW_FUTURE"
    ),
    expected="PLATFORM_TEMPORAL_SIGNAL_WINDOW_FUTURE",
    actual=error_code(exc),
)


# ============================================================
# E. INPUT IMMUTABILITY UNDER FAILURE
# ============================================================

bad_list = [
    copy.deepcopy(
        BASE_EVIDENCE
    ),
    copy.deepcopy(
        invalid_evidence
    ),
]

before = copy.deepcopy(
    bad_list
)


call_ok(
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,
            evidence=bad_list,
            signals=[],
        )
)


add(
    "E001",
    "CRITICAL",
    "Failed batch does not mutate evidence input",
    bad_list == before,
)


bad_signal_list = [
    copy.deepcopy(
        BASE_SIGNAL
    ),
    copy.deepcopy(
        invalid_signal
    ),
]

before_signal = copy.deepcopy(
    bad_signal_list
)


call_ok(
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,
            evidence=[],
            signals=bad_signal_list,
        )
)


add(
    "E002",
    "CRITICAL",
    "Failed batch does not mutate signal input",
    bad_signal_list == before_signal,
)


# ============================================================
# F. ERROR DETERMINISM
# ============================================================

def capture_code():
    try:
        module.validate_evidence_temporal(
            invalid_evidence,
            AS_OF,
        )

    except module.TemporalValidityError as exc:
        return (
            exc.code,
            str(exc),
        )

    return (
        None,
        None,
    )


first_error = capture_code()
second_error = capture_code()


add(
    "F001",
    "CRITICAL",
    "Repeated invalid evidence produces deterministic error",
    first_error == second_error,
    actual=[
        first_error,
        second_error,
    ],
)


# ============================================================
# G. VALID_UNTIL EDGE CASES
# ============================================================

ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,

                "valid_until":
                    "2026-09-27T20:00:00.000001+00:00",
            },
            AS_OF,
        )
)


add(
    "G001",
    "HIGH",
    "Expiry one microsecond after as_of remains valid",
    ok,
    actual=(
        "ACCEPTED"
        if ok
        else error_code(exc)
    ),
)


ok, value, exc = call_ok(
    lambda:
        module.validate_evidence_temporal(
            {
                **BASE_EVIDENCE,

                "valid_until":
                    "2026-09-27T19:59:59.999999+00:00",
            },
            AS_OF,
        )
)


add(
    "G002",
    "CRITICAL",
    "Expiry one microsecond before as_of fails closed",
    (
        not ok
        and
        error_code(exc)
        == "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED"
    ),
    expected="PLATFORM_TEMPORAL_EVIDENCE_EXPIRED",
    actual=error_code(exc),
)


# ============================================================
# H. DECAY BOUNDARY
# ============================================================

ok, value, exc = call_ok(
    lambda:
        module.validate_snapshot_temporal_inputs(
            as_of=AS_OF,
            evidence=[
                BASE_EVIDENCE,
            ],
            signals=[
                BASE_SIGNAL,
            ],
        )
)


add(
    "H001",
    "CRITICAL",
    "Temporal engine does not silently apply confidence decay",
    (
        ok
        and
        value.get(
            "confidence_decay_applied"
        )
        is False
        and
        value.get(
            "confidence_decay_reason"
        )
        == "NUMERIC_POLICY_DEFERRED"
    ),
    actual=(
        {
            "applied":
                value.get(
                    "confidence_decay_applied"
                ),

            "reason":
                value.get(
                    "confidence_decay_reason"
                ),
        }
        if value
        else repr(exc)
    ),
)


# ============================================================
# I. PURITY / SIDE-EFFECT STATIC ATTACK
# ============================================================

source = ENGINE_PATH.read_text(
    encoding="utf-8-sig"
).lower()


forbidden_fragments = [
    "requests.",
    "httpx.",
    "urllib.",
    "socket.",
    "subprocess.",
    "open(",
    "write_text(",
    "write_bytes(",
    "unlink(",
    "remove(",
    "rename(",
    "replace(",
]


present_forbidden = [
    item
    for item in forbidden_fragments
    if item in source
]


add(
    "I001",
    "CRITICAL",
    "Temporal engine contains no obvious network/process/file-write side effects",
    not present_forbidden,
    expected=[],
    actual=present_forbidden,
)


# ============================================================
# J. ENGINE IDENTITY
# ============================================================

add(
    "J001",
    "CRITICAL",
    "Engine SHA remains canonical A4 artifact",
    sha256(
        ENGINE_PATH
    )
    == EXPECTED_ENGINE_SHA,
    expected=EXPECTED_ENGINE_SHA,
    actual=sha256(
        ENGINE_PATH
    ),
)


add(
    "J002",
    "CRITICAL",
    "Temporal policy version remains exact",
    (
        module.TEMPORAL_VALIDITY_POLICY_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    ),
)


add(
    "J003",
    "CRITICAL",
    "Temporal engine version remains exact",
    (
        module.TEMPORAL_VALIDITY_ENGINE_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    ),
)


# ============================================================
# CLASSIFICATION
# ============================================================

critical_gaps = [
    item
    for item in findings
    if (
        not item["passed"]
        and
        item["severity"]
        == "CRITICAL"
    )
]


high_engine_gaps = [
    item
    for item in findings
    if (
        not item["passed"]
        and
        item["severity"]
        == "HIGH"
        and
        item["classification"]
        == "ENGINE_REQUIREMENT"
    )
]


contract_probes = [
    item
    for item in findings
    if (
        not item["passed"]
        and
        item["classification"]
        == "CONTRACT_PROBE"
    )
]


engine_attack_pass = (
    len(
        critical_gaps
    )
    == 0
    and
    len(
        high_engine_gaps
    )
    == 0
)


integration_ready = (
    engine_attack_pass
    and
    len(
        contract_probes
    )
    == 0
)


next_gate = (
    "09C7-B3E-A4-A2_INTEGRATION_PREFLIGHT"
    if integration_ready
    else
    (
        "09C7-B3E-A4-R1_TEMPORAL_CONTRACT_AMENDMENT"
        if contract_probes
        else
        "09C7-B3E-A4_ENGINE_REMEDIATION"
    )
)


report = {
    "phase":
        "09C7-B3E-A4-A1",

    "status":
        "TEMPORAL_VALIDITY_ADVERSARIAL_ATTACK_COMPLETE",

    "engine_sha256":
        actual_engine_sha,

    "attack_count":
        len(
            findings
        ),

    "pass_count":
        sum(
            1
            for item in findings
            if item[
                "passed"
            ]
        ),

    "critical_gap_count":
        len(
            critical_gaps
        ),

    "high_engine_gap_count":
        len(
            high_engine_gaps
        ),

    "contract_probe_gap_count":
        len(
            contract_probes
        ),

    "engine_attack_pass":
        engine_attack_pass,

    "integration_ready":
        integration_ready,

    "next_gate":
        next_gate,

    "findings":
        findings,

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
    "=== TEMPORAL VALIDITY ADVERSARIAL ATTACK ==="
)

print(
    "ATTACK_COUNT="
    + str(
        report[
            "attack_count"
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
    "CRITICAL_GAP_COUNT="
    + str(
        report[
            "critical_gap_count"
        ]
    )
)

print(
    "HIGH_ENGINE_GAP_COUNT="
    + str(
        report[
            "high_engine_gap_count"
        ]
    )
)

print(
    "CONTRACT_PROBE_GAP_COUNT="
    + str(
        report[
            "contract_probe_gap_count"
        ]
    )
)

print(
    "ENGINE_ATTACK_PASS="
    + str(
        report[
            "engine_attack_pass"
        ]
    )
)

print(
    "INTEGRATION_READY="
    + str(
        report[
            "integration_ready"
        ]
    )
)

print(
    "NEXT_GATE="
    + report[
        "next_gate"
    ]
)


print(
    "\n=== FINDINGS ==="
)

for item in findings:

    print(
        item[
            "attack_id"
        ]
        + " "
        + item[
            "severity"
        ]
        + " "
        + item[
            "finding"
        ]
        + " "
        + item[
            "classification"
        ]
        + " :: "
        + item[
            "title"
        ]
    )

    if not item[
        "passed"
    ]:
        print(
            "  EXPECTED="
            + str(
                item.get(
                    "expected"
                )
            )
        )

        print(
            "  ACTUAL="
            + str(
                item.get(
                    "actual"
                )
            )
        )


print("")
print(
    "PRODUCTION_SOURCE_MODIFIED=False"
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
    "SM3_09C7_B3E_A4_A1_TEMPORAL_VALIDITY_ADVERSARIAL_ATTACK_COMPLETE"
)
