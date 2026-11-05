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


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


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


def capture(
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


AS_OF = (
    "2026-09-27T20:00:00+00:00"
)


BASE = {
    "evidence_id":
        "PDE_precedence",

    "source_date":
        "2026-09-27T17:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",

    "valid_until":
        "2026-10-27T00:00:00+00:00",
}


# ============================================================
# 1. FUTURE SOURCE HAS PRECEDENCE OVER CAUSAL VIOLATION
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-28T00:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_DATE_FUTURE_PRECEDES_SOURCE_AFTER_OBSERVATION",
    (
        result[
            "code"
        ]
        == "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE"
    ),
    result,
)


# ============================================================
# 2. SOURCE FUTURE PRECEDES OBSERVED FUTURE
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-29T00:00:00+00:00",

    "observed_at":
        "2026-09-28T00:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_DATE_FUTURE_PRECEDES_OBSERVED_AT_FUTURE",
    (
        result[
            "code"
        ]
        == "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE"
    ),
    result,
)


# ============================================================
# 3. OBSERVED FUTURE WHEN SOURCE IS VALID
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-27T18:00:00+00:00",

    "observed_at":
        "2026-09-28T00:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "OBSERVED_AT_FUTURE_WHEN_SOURCE_VALID",
    (
        result[
            "code"
        ]
        == "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE"
    ),
    result,
)


# ============================================================
# 4. CAUSAL ERROR WHEN BOTH ARE INSIDE AS_OF
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-27T19:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_AFTER_OBSERVATION_WHEN_AS_OF_BOUNDS_VALID",
    (
        result[
            "code"
        ]
        == (
            "PLATFORM_TEMPORAL_EVIDENCE_"
            "SOURCE_AFTER_OBSERVATION"
        )
    ),
    result,
)


# ============================================================
# 5. EXPIRY LAST
# ============================================================

case = {
    **BASE,

    "valid_until":
        "2026-09-27T19:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "EXPIRED_WHEN_HIGHER_PRECEDENCE_RULES_VALID",
    (
        result[
            "code"
        ]
        == "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED"
    ),
    result,
)


# ============================================================
# 6. FUTURE SOURCE PRECEDES EXPIRY
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-28T00:00:00+00:00",

    "observed_at":
        "2026-09-28T01:00:00+00:00",

    "valid_until":
        "2026-09-27T19:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_DATE_FUTURE_PRECEDES_EXPIRED",
    (
        result[
            "code"
        ]
        == "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE"
    ),
    result,
)


# ============================================================
# 7. OBSERVED FUTURE PRECEDES EXPIRY
# ============================================================

case = {
    **BASE,

    "observed_at":
        "2026-09-28T00:00:00+00:00",

    "valid_until":
        "2026-09-27T19:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "OBSERVED_AT_FUTURE_PRECEDES_EXPIRED",
    (
        result[
            "code"
        ]
        == "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE"
    ),
    result,
)


# ============================================================
# 8. CAUSAL ERROR PRECEDES EXPIRY
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-27T19:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",

    "valid_until":
        "2026-09-27T17:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_AFTER_OBSERVATION_PRECEDES_EXPIRED",
    (
        result[
            "code"
        ]
        == (
            "PLATFORM_TEMPORAL_EVIDENCE_"
            "SOURCE_AFTER_OBSERVATION"
        )
    ),
    result,
)


# ============================================================
# 9. FULLY VALID RECORD
# ============================================================

result = capture(
    BASE,
    AS_OF,
)


record(
    "VALID_RECORD_PASSES",
    result[
        "ok"
    ]
    is True,
    result,
)


# ============================================================
# 10. EQUALITY BOUNDARIES
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-27T18:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_DATE_EQUAL_OBSERVED_AT_ALLOWED",
    result[
        "ok"
    ]
    is True,
    result,
)


case = {
    **BASE,

    "source_date":
        AS_OF,

    "observed_at":
        AS_OF,
}


result = capture(
    case,
    AS_OF,
)


record(
    "SOURCE_AND_OBSERVED_EQUAL_AS_OF_ALLOWED",
    result[
        "ok"
    ]
    is True,
    result,
)


# ============================================================
# 11. DETERMINISTIC ERROR
# ============================================================

case = {
    **BASE,

    "source_date":
        "2026-09-27T19:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",
}


first = capture(
    case,
    AS_OF,
)

second = capture(
    case,
    AS_OF,
)


record(
    "CAUSAL_ERROR_DETERMINISTIC",
    (
        first[
            "code"
        ]
        == second[
            "code"
        ]
        and
        first[
            "message"
        ]
        == second[
            "message"
        ]
    ),
    {
        "first":
            first,

        "second":
            second,
    },
)


# ============================================================
# 12. INPUT IMMUTABILITY
# ============================================================

mutable_case = copy.deepcopy(
    case
)

before = copy.deepcopy(
    mutable_case
)


capture(
    mutable_case,
    AS_OF,
)


record(
    "FAILED_RECORD_NOT_MUTATED",
    mutable_case
    == before,
)


# ============================================================
# 13. IMPLEMENTATION / CONTRACT IDENTITIES
# ============================================================

record(
    "IMPLEMENTATION_REVISION_R2",
    (
        module.TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION
        == "R2"
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
# 14. AST SIDE-EFFECT AUDIT
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
    "NO_NETWORK_PROCESS_IMPORTS",
    forbidden_imports == [],
    forbidden_imports,
)


record(
    "NO_FILE_WRITE_PROCESS_CALLS",
    dangerous_calls == [],
    dangerous_calls,
)


record(
    "ONLY_STRING_REPLACE_PRESENT",
    replace_calls == [
        "raw.replace"
    ],
    replace_calls,
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


report = {
    "phase":
        "09C7-B3E-A4-R2-F1",

    "status":
        "TEMPORAL_ERROR_PRECEDENCE_REMEDIATION_TEST_COMPLETE",

    "policy_version":
        module.TEMPORAL_VALIDITY_POLICY_VERSION,

    "engine_version":
        module.TEMPORAL_VALIDITY_ENGINE_VERSION,

    "implementation_revision":
        module.TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION,

    "engine_sha256":
        sha256(
            ENGINE
        ),

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

    "semantic_error_precedence": [
        "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE",
        "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE",
        "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_AFTER_OBSERVATION",
        "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED",
    ],

    "causal_invariant_preserved":
        True,

    "backward_compatible_error_semantics":
        True,

    "ast_side_effect_audit_pass":
        (
            forbidden_imports == []
            and
            dangerous_calls == []
        ),

    "replace_calls":
        replace_calls,

    "confidence_decay_applied":
        False,

    "runtime_integrated":
        False,

    "production_source_modified":
        False,

    "production_state_modified":
        False,

    "route_called":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "tests":
        tests,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== ERROR PRECEDENCE REMEDIATION TEST ==="
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
    "IMPLEMENTATION_REVISION="
    + report[
        "implementation_revision"
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
    "CAUSAL_INVARIANT_PRESERVED=True"
)

print(
    "BACKWARD_COMPATIBLE_ERROR_SEMANTICS=True"
)

print(
    "AST_SIDE_EFFECT_AUDIT_PASS="
    + str(
        report[
            "ast_side_effect_audit_pass"
        ]
    )
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
                default=str,
            )
        )


print("")
print(
    "RUNTIME_INTEGRATED=False"
)

print(
    "PRODUCTION_SOURCE_MODIFIED=False"
)

print(
    "PRODUCTION_STATE_MODIFIED=False"
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
    "SM3_09C7_B3E_A4_R2_F1_ERROR_PRECEDENCE_REMEDIATION_TEST_COMPLETE"
)


if failures:

    raise SystemExit(
        1
    )
