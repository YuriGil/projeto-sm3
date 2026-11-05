from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ENGINE = Path(sys.argv[1])
REPORT = Path(sys.argv[2])


EXPECTED_ENGINE_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


actual_sha = sha256(
    ENGINE
)


if actual_sha != EXPECTED_ENGINE_SHA:
    raise SystemExit(
        "A4_A2_ENGINE_SHA_MISMATCH:"
        + actual_sha
    )


spec = importlib.util.spec_from_file_location(
    "sm3_temporal_validity_r2",
    ENGINE,
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
    attack_id,
    severity,
    title,
    passed,
    detail=None,
):

    tests.append({
        "attack_id":
            attack_id,

        "severity":
            severity,

        "title":
            title,

        "passed":
            bool(
                passed
            ),

        "finding":
            (
                "PASS"
                if passed
                else "GAP"
            ),

        "detail":
            detail,
    })


def evidence_call(
    evidence,
    as_of,
):

    try:

        value = module.validate_evidence_temporal(
            evidence,
            as_of,
        )

        return {
            "ok":
                True,

            "code":
                None,

            "message":
                None,

            "value":
                value,
        }

    except module.TemporalValidityError as exc:

        return {
            "ok":
                False,

            "code":
                exc.code,

            "message":
                str(
                    exc
                ),

            "value":
                None,
        }

    except Exception as exc:

        return {
            "ok":
                False,

            "code":
                "UNEXPECTED_EXCEPTION",

            "message":
                repr(
                    exc
                ),

            "value":
                None,
        }


def signal_call(
    signal,
    as_of,
):

    try:

        value = module.validate_signal_temporal(
            signal,
            as_of,
        )

        return {
            "ok":
                True,

            "code":
                None,

            "message":
                None,

            "value":
                value,
        }

    except module.TemporalValidityError as exc:

        return {
            "ok":
                False,

            "code":
                exc.code,

            "message":
                str(
                    exc
                ),

            "value":
                None,
        }

    except Exception as exc:

        return {
            "ok":
                False,

            "code":
                "UNEXPECTED_EXCEPTION",

            "message":
                repr(
                    exc
                ),

            "value":
                None,
        }


def batch_call(
    *,
    as_of,
    evidence,
    signals,
):

    try:

        value = module.validate_snapshot_temporal_inputs(
            as_of=as_of,
            evidence=evidence,
            signals=signals,
        )

        return {
            "ok":
                True,

            "code":
                None,

            "message":
                None,

            "value":
                value,
        }

    except module.TemporalValidityError as exc:

        return {
            "ok":
                False,

            "code":
                exc.code,

            "message":
                str(
                    exc
                ),

            "value":
                None,
        }

    except Exception as exc:

        return {
            "ok":
                False,

            "code":
                "UNEXPECTED_EXCEPTION",

            "message":
                repr(
                    exc
                ),

            "value":
                None,
        }


AS_OF = (
    "2026-09-27T20:00:00+00:00"
)


BASE_EVIDENCE = {
    "evidence_id":
        "PDE_A4_A2",

    "source_date":
        "2026-09-27T17:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",

    "valid_until":
        "2026-10-27T00:00:00+00:00",
}


BASE_SIGNAL = {
    "signal_id":
        "PPS_A4_A2",

    "window_started_at":
        "2026-09-26T20:00:00+00:00",

    "window_ended_at":
        "2026-09-27T19:00:00+00:00",
}


# ============================================================
# A — TIMESTAMP NORMALIZATION
# ============================================================

result = evidence_call(
    {
        **BASE_EVIDENCE,

        "observed_at":
            "2026-09-27T15:00:00-03:00",
    },
    AS_OF,
)


record(
    "A001",
    "CRITICAL",
    "Equivalent timezone offsets normalize to UTC",
    (
        result["ok"]
        and
        result["value"]["observed_at"]
        == "2026-09-27T18:00:00+00:00"
    ),
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "observed_at":
            "2026-09-27T18:00:00Z",
    },
    AS_OF,
)


record(
    "A002",
    "HIGH",
    "Z suffix accepted and normalized",
    (
        result["ok"]
        and
        result["value"]["observed_at"]
        == "2026-09-27T18:00:00+00:00"
    ),
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "observed_at":
            "2026-09-27T18:00:00.123456+00:00",
    },
    AS_OF,
)


record(
    "A003",
    "HIGH",
    "Microsecond timestamp precision remains valid",
    (
        result["ok"]
        and
        result["value"]["observed_at"]
        == "2026-09-27T18:00:00.123456+00:00"
    ),
    result,
)


# ============================================================
# B — MALFORMED / REQUIRED TIMESTAMPS
# ============================================================

result = evidence_call(
    {
        **BASE_EVIDENCE,

        "source_date":
            "",
    },
    AS_OF,
)


record(
    "B001",
    "CRITICAL",
    "Empty source_date fails closed",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED"
    ),
    result,
)


result = signal_call(
    {
        **BASE_SIGNAL,

        "window_ended_at":
            None,
    },
    AS_OF,
)


record(
    "B002",
    "CRITICAL",
    "Missing signal window end fails closed",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED"
    ),
    result,
)


result = batch_call(
    as_of="",
    evidence=[],
    signals=[],
)


record(
    "B003",
    "CRITICAL",
    "Missing as_of fails closed even for empty batch",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED"
    ),
    result,
)


# ============================================================
# C — CAUSAL ORDER
# ============================================================

causal_invalid = {
    **BASE_EVIDENCE,

    "source_date":
        "2026-09-27T19:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",
}


result = evidence_call(
    causal_invalid,
    AS_OF,
)


record(
    "C001",
    "CRITICAL",
    "Source after observation fails with frozen causal error",
    (
        not result["ok"]
        and
        result["code"]
        == (
            "PLATFORM_TEMPORAL_EVIDENCE_"
            "SOURCE_AFTER_OBSERVATION"
        )
    ),
    result,
)


boundary_equal = {
    **BASE_EVIDENCE,

    "source_date":
        AS_OF,

    "observed_at":
        AS_OF,
}


result = evidence_call(
    boundary_equal,
    AS_OF,
)


record(
    "C002",
    "HIGH",
    "Source and observation exactly at as_of are valid",
    result["ok"],
    result,
)


subsecond_signal = {
    **BASE_SIGNAL,

    "window_started_at":
        "2026-09-27T19:59:59.999999+00:00",

    "window_ended_at":
        AS_OF,
}


result = signal_call(
    subsecond_signal,
    AS_OF,
)


record(
    "C003",
    "HIGH",
    "Positive subsecond signal window remains temporally valid",
    (
        result["ok"]
        and
        result["value"]["window_ended_at"]
        == "2026-09-27T20:00:00+00:00"
    ),
    result,
)


# ============================================================
# D — BATCH FAIL-CLOSED
# ============================================================

future_observation = {
    **BASE_EVIDENCE,

    "evidence_id":
        "PDE_bad",

    "observed_at":
        "2026-09-28T00:00:00+00:00",
}


result = batch_call(
    as_of=AS_OF,

    evidence=[
        BASE_EVIDENCE,
        future_observation,
    ],

    signals=[
        BASE_SIGNAL,
    ],
)


record(
    "D001",
    "CRITICAL",
    "One invalid evidence fails entire batch",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE"
    ),
    result,
)


future_signal = {
    **BASE_SIGNAL,

    "signal_id":
        "PPS_bad",

    "window_ended_at":
        "2026-09-28T00:00:00+00:00",
}


result = batch_call(
    as_of=AS_OF,

    evidence=[
        BASE_EVIDENCE,
    ],

    signals=[
        BASE_SIGNAL,
        future_signal,
    ],
)


record(
    "D002",
    "CRITICAL",
    "One invalid signal fails entire batch",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_SIGNAL_WINDOW_FUTURE"
    ),
    result,
)


# ============================================================
# E — INPUT IMMUTABILITY
# ============================================================

evidence_input = [
    copy.deepcopy(
        BASE_EVIDENCE
    ),
    copy.deepcopy(
        future_observation
    ),
]

evidence_before = copy.deepcopy(
    evidence_input
)


batch_call(
    as_of=AS_OF,
    evidence=evidence_input,
    signals=[],
)


record(
    "E001",
    "CRITICAL",
    "Failed evidence batch does not mutate caller input",
    evidence_input
    == evidence_before,
)


signal_input = [
    copy.deepcopy(
        BASE_SIGNAL
    ),
    copy.deepcopy(
        future_signal
    ),
]

signal_before = copy.deepcopy(
    signal_input
)


batch_call(
    as_of=AS_OF,
    evidence=[],
    signals=signal_input,
)


record(
    "E002",
    "CRITICAL",
    "Failed signal batch does not mutate caller input",
    signal_input
    == signal_before,
)


# ============================================================
# F — ERROR DETERMINISM
# ============================================================

first = evidence_call(
    causal_invalid,
    AS_OF,
)

second = evidence_call(
    causal_invalid,
    AS_OF,
)


record(
    "F001",
    "CRITICAL",
    "Repeated causal violation produces deterministic error",
    (
        first["code"]
        == second["code"]
        and
        first["message"]
        == second["message"]
    ),
    {
        "first":
            first,

        "second":
            second,
    },
)


# ============================================================
# G — HARD EXPIRY BOUNDARIES
# ============================================================

result = evidence_call(
    {
        **BASE_EVIDENCE,

        "valid_until":
            "2026-09-27T20:00:00.000001+00:00",
    },
    AS_OF,
)


record(
    "G001",
    "HIGH",
    "Expiry one microsecond after as_of remains valid",
    result["ok"],
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "valid_until":
            "2026-09-27T19:59:59.999999+00:00",
    },
    AS_OF,
)


record(
    "G002",
    "CRITICAL",
    "Expiry one microsecond before as_of fails closed",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED"
    ),
    result,
)


# ============================================================
# H — DECAY BOUNDARY
# ============================================================

result = batch_call(
    as_of=AS_OF,

    evidence=[
        BASE_EVIDENCE,
    ],

    signals=[
        BASE_SIGNAL,
    ],
)


record(
    "H001",
    "CRITICAL",
    "Temporal engine does not silently apply confidence decay",
    (
        result["ok"]
        and
        result["value"]["confidence_decay_applied"]
        is False
        and
        result["value"]["confidence_decay_reason"]
        == "NUMERIC_POLICY_DEFERRED"
    ),
    result,
)


# ============================================================
# I — AST SIDE-EFFECT AUDIT
# ============================================================

source = ENGINE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    source,
    filename=str(
        ENGINE
    ),
)


imports = set()
calls = []


def dotted_name(node):

    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):

        parent = dotted_name(
            node.value
        )

        if parent:

            return (
                parent
                + "."
                + node.attr
            )

        return node.attr

    return None


for node in ast.walk(
    tree
):

    if isinstance(
        node,
        ast.Import,
    ):

        for alias in node.names:

            imports.add(
                alias.name
            )

    elif isinstance(
        node,
        ast.ImportFrom,
    ):

        if node.module:

            imports.add(
                node.module
            )

    elif isinstance(
        node,
        ast.Call,
    ):

        name = dotted_name(
            node.func
        )

        if name:

            calls.append(
                name
            )


forbidden_import_roots = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
}


forbidden_imports = sorted(
    item
    for item in imports
    if item.split(
        "."
    )[0]
    in forbidden_import_roots
)


dangerous_exact_calls = {
    "open",
    "os.remove",
    "os.unlink",
    "os.rename",
    "os.replace",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
    "requests.get",
    "requests.post",
    "httpx.get",
    "httpx.post",
}


dangerous_suffixes = {
    ".write_text",
    ".write_bytes",
    ".unlink",
    ".rename",
}


dangerous_calls = sorted(
    set(
        name
        for name in calls
        if (
            name in dangerous_exact_calls
            or
            any(
                name.endswith(
                    suffix
                )
                for suffix in dangerous_suffixes
            )
        )
    )
)


replace_calls = sorted(
    set(
        name
        for name in calls
        if name.endswith(
            ".replace"
        )
    )
)


record(
    "I001",
    "CRITICAL",
    "No forbidden network/process imports",
    forbidden_imports == [],
    forbidden_imports,
)


record(
    "I002",
    "CRITICAL",
    "No file-write/process/network calls",
    dangerous_calls == [],
    dangerous_calls,
)


record(
    "I003",
    "HIGH",
    "Only expected string replacement exists",
    replace_calls
    == [
        "raw.replace"
    ],
    replace_calls,
)


# ============================================================
# J — ARTIFACT / VERSION IDENTITY
# ============================================================

record(
    "J001",
    "CRITICAL",
    "Candidate SHA remains exact",
    sha256(
        ENGINE
    )
    == EXPECTED_ENGINE_SHA,
    sha256(
        ENGINE
    ),
)


record(
    "J002",
    "CRITICAL",
    "Policy version exact",
    (
        module.TEMPORAL_VALIDITY_POLICY_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    ),
)


record(
    "J003",
    "CRITICAL",
    "Engine version exact",
    (
        module.TEMPORAL_VALIDITY_ENGINE_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    ),
)


record(
    "J004",
    "CRITICAL",
    "Implementation revision exact R2",
    (
        module.TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION
        == "R2"
    ),
)


# ============================================================
# K — FROZEN ERROR PRECEDENCE
# ============================================================

result = evidence_call(
    {
        **BASE_EVIDENCE,

        "source_date":
            "2026-09-28T00:00:00+00:00",

        "observed_at":
            "2026-09-27T18:00:00+00:00",
    },
    AS_OF,
)


record(
    "K001",
    "CRITICAL",
    "Source future precedes causal-order error",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE"
    ),
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "source_date":
            "2026-09-29T00:00:00+00:00",

        "observed_at":
            "2026-09-28T00:00:00+00:00",
    },
    AS_OF,
)


record(
    "K002",
    "CRITICAL",
    "Source future precedes observed future",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE"
    ),
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "observed_at":
            "2026-09-28T00:00:00+00:00",

        "valid_until":
            "2026-09-27T19:00:00+00:00",
    },
    AS_OF,
)


record(
    "K003",
    "CRITICAL",
    "Observed future precedes expiry error",
    (
        not result["ok"]
        and
        result["code"]
        == "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE"
    ),
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "source_date":
            "2026-09-27T19:00:00+00:00",

        "observed_at":
            "2026-09-27T18:00:00+00:00",

        "valid_until":
            "2026-09-27T17:00:00+00:00",
    },
    AS_OF,
)


record(
    "K004",
    "CRITICAL",
    "Causal-order error precedes expiry",
    (
        not result["ok"]
        and
        result["code"]
        == (
            "PLATFORM_TEMPORAL_EVIDENCE_"
            "SOURCE_AFTER_OBSERVATION"
        )
    ),
    result,
)


# ============================================================
# L — ADDITIONAL EDGE CONDITIONS
# ============================================================

result = batch_call(
    as_of=AS_OF,
    evidence=[],
    signals=[],
)


record(
    "L001",
    "HIGH",
    "Valid as_of with empty batch remains valid",
    (
        result["ok"]
        and
        result["value"]["evidence_count"]
        == 0
        and
        result["value"]["signal_count"]
        == 0
    ),
    result,
)


result = evidence_call(
    BASE_EVIDENCE,
    AS_OF,
)


record(
    "L002",
    "CRITICAL",
    "Valid evidence produces non-negative causally ordered ages",
    (
        result["ok"]
        and
        result["value"]["source_age_seconds"]
        >= result["value"]["observation_age_seconds"]
        >= 0
    ),
    result,
)


result = evidence_call(
    {
        **BASE_EVIDENCE,

        "valid_until":
            "   ",
    },
    AS_OF,
)


record(
    "L003",
    "HIGH",
    "Whitespace-only valid_until behaves as absent hard expiry",
    (
        result["ok"]
        and
        result["value"]["hard_expiry_present"]
        is False
        and
        result["value"]["valid_until"]
        is None
    ),
    result,
)


# ============================================================
# FINAL CLASSIFICATION
# ============================================================

if len(
    tests
) != 31:

    raise SystemExit(
        "A4_A2_INTERNAL_ATTACK_COUNT_INVALID:"
        + str(
            len(
                tests
            )
        )
    )


failures = [
    row
    for row in tests
    if not row[
        "passed"
    ]
]


critical_gaps = [
    row
    for row in failures
    if row[
        "severity"
    ]
    == "CRITICAL"
]


high_gaps = [
    row
    for row in failures
    if row[
        "severity"
    ]
    == "HIGH"
]


attack_pass = (
    len(
        failures
    )
    == 0
)


report = {
    "phase":
        "09C7-B3E-A4-A2",

    "status":
        "TEMPORAL_VALIDITY_ADVERSARIAL_REATTACK_COMPLETE",

    "engine_sha256":
        actual_sha,

    "policy_version":
        module.TEMPORAL_VALIDITY_POLICY_VERSION,

    "engine_version":
        module.TEMPORAL_VALIDITY_ENGINE_VERSION,

    "implementation_revision":
        module.TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION,

    "attack_count":
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

    "critical_gap_count":
        len(
            critical_gaps
        ),

    "high_gap_count":
        len(
            high_gaps
        ),

    "attack_pass":
        attack_pass,

    "confidence_decay_applied":
        False,

    "runtime_integrated":
        False,

    "tests":
        tests,

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
    "=== TEMPORAL ADVERSARIAL REATTACK ==="
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
    "FAILURE_COUNT="
    + str(
        report[
            "failure_count"
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
    "HIGH_GAP_COUNT="
    + str(
        report[
            "high_gap_count"
        ]
    )
)

print(
    "ATTACK_PASS="
    + str(
        report[
            "attack_pass"
        ]
    )
)


print(
    "\n=== FINDINGS ==="
)

for row in tests:

    print(
        row[
            "attack_id"
        ]
        + " "
        + row[
            "severity"
        ]
        + " "
        + row[
            "finding"
        ]
        + " :: "
        + row[
            "title"
        ]
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
                default=str,
            )
        )


print("")
print(
    "CONFIDENCE_DECAY_APPLIED=False"
)

print(
    "RUNTIME_INTEGRATED=False"
)

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


if failures:

    raise SystemExit(
        1
    )
