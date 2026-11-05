from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(sys.argv[1])
WORKER = Path(sys.argv[2])
TEMPORAL = Path(sys.argv[3])
STAGE_DIR = Path(sys.argv[4])
REPORT = Path(sys.argv[5])
MANIFEST = Path(sys.argv[6])


EXPECTED_WORKER_SHA = (
    "cf778554e324acdc30ba60897767e97c8"
    "6dfe7fa3cc497ac0545cc71796ef89f"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)


SOURCE_VERSION = "2.35.0"
STAGED_VERSION = "2.35.1"

TEMPORAL_MODULE_NAME = (
    "SM3_platform_temporal_validity_v1_r2"
)


PUBLIC_IMPORT_NAMES = [
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TemporalValidityError",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
]


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write_json(
    path: Path,
    value,
):

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


worker_sha = sha256(
    WORKER
)

temporal_sha = sha256(
    TEMPORAL
)


if worker_sha != EXPECTED_WORKER_SHA:

    raise SystemExit(
        "A4_A4_SOURCE_WORKER_SHA_MISMATCH:"
        + worker_sha
    )


if temporal_sha != EXPECTED_TEMPORAL_SHA:

    raise SystemExit(
        "A4_A4_TEMPORAL_SHA_MISMATCH:"
        + temporal_sha
    )


# ============================================================
# 1. CLEAN / CREATE STAGE
# ============================================================

if STAGE_DIR.exists():

    shutil.rmtree(
        STAGE_DIR
    )


STAGE_DIR.mkdir(
    parents=True,
    exist_ok=False,
)


stage_worker = (
    STAGE_DIR
    / "worker_service.py"
)

stage_temporal = (
    STAGE_DIR
    / (
        TEMPORAL_MODULE_NAME
        + ".py"
    )
)


# ============================================================
# 2. COPY TEMPORAL MODULE BYTE-FOR-BYTE
# ============================================================

shutil.copyfile(
    TEMPORAL,
    stage_temporal,
)


if sha256(
    stage_temporal
) != temporal_sha:

    raise SystemExit(
        "A4_A4_STAGED_TEMPORAL_SHA_MISMATCH"
    )


# ============================================================
# 3. LOAD CANONICAL WORKER
# ============================================================

source = WORKER.read_text(
    encoding="utf-8-sig"
)


source_tree = ast.parse(
    source,
    filename=str(
        WORKER
    ),
)


# ============================================================
# 4. VERIFY SOURCE VERSION EXACTLY ONCE
# ============================================================

version_pattern = re.compile(
    r'''(?m)^(
        [ \t]*
        WORKER_VERSION
        [ \t]*=[ \t]*
    )
    (["'])
    2\.35\.0
    \2
    ''',
    re.VERBOSE,
)


matches = list(
    version_pattern.finditer(
        source
    )
)


if len(
    matches
) != 1:

    raise SystemExit(
        "A4_A4_WORKER_VERSION_ASSIGNMENT_COUNT_INVALID:"
        + str(
            len(
                matches
            )
        )
    )


# ============================================================
# 5. BUMP ONLY STAGED WORKER VERSION
# ============================================================

patched_source = version_pattern.sub(
    lambda match:
        (
            match.group(
                1
            )
            + '"'
            + STAGED_VERSION
            + '"'
        ),
    source,
    count=1,
)


# ============================================================
# 6. FIND SAFE IMPORT INSERTION POINT
# ============================================================

patched_tree_before_import = ast.parse(
    patched_source,
    filename="candidate_before_temporal_import",
)


body = list(
    patched_tree_before_import.body
)


cursor = 0


if (
    body
    and
    isinstance(
        body[0],
        ast.Expr,
    )
    and
    isinstance(
        body[0].value,
        ast.Constant,
    )
    and
    isinstance(
        body[0].value.value,
        str,
    )
):

    cursor = 1


last_import_end_line = 0


while cursor < len(
    body
):

    node = body[
        cursor
    ]

    if not isinstance(
        node,
        (
            ast.Import,
            ast.ImportFrom,
        ),
    ):

        break

    last_import_end_line = max(
        last_import_end_line,
        getattr(
            node,
            "end_lineno",
            node.lineno,
        ),
    )

    cursor += 1


if last_import_end_line == 0:

    if (
        body
        and
        isinstance(
            body[0],
            ast.Expr,
        )
        and
        isinstance(
            body[0].value,
            ast.Constant,
        )
        and
        isinstance(
            body[0].value.value,
            str,
        )
    ):

        last_import_end_line = getattr(
            body[0],
            "end_lineno",
            body[0].lineno,
        )

    else:

        last_import_end_line = 0


import_block = (
    "\n"
    "# ============================================================\n"
    "# SM3 TEMPORAL VALIDITY — DORMANT RUNTIME CAPABILITY\n"
    "# Contract: SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1\n"
    "# Engine: SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1\n"
    "# Implementation: R2\n"
    "# Consumer binding intentionally deferred until Snapshot V2.\n"
    "# ============================================================\n"
    "from SM3_platform_temporal_validity_v1_r2 import (\n"
    "    TEMPORAL_VALIDITY_POLICY_VERSION,\n"
    "    TEMPORAL_VALIDITY_ENGINE_VERSION,\n"
    "    TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION,\n"
    "    TemporalValidityError,\n"
    "    validate_evidence_temporal,\n"
    "    validate_signal_temporal,\n"
    "    validate_snapshot_temporal_inputs,\n"
    ")\n"
    "\n"
)


lines = patched_source.splitlines(
    keepends=True
)


lines.insert(
    last_import_end_line,
    import_block,
)


staged_source = "".join(
    lines
)


stage_worker.write_text(
    staged_source,
    encoding="utf-8",
)


# ============================================================
# 7. COMPILE STAGED SOURCES
# ============================================================

compile(
    stage_worker.read_text(
        encoding="utf-8-sig"
    ),
    str(
        stage_worker
    ),
    "exec",
)


compile(
    stage_temporal.read_text(
        encoding="utf-8-sig"
    ),
    str(
        stage_temporal
    ),
    "exec",
)


# ============================================================
# 8. PARSE STAGED WORKER
# ============================================================

stage_source = stage_worker.read_text(
    encoding="utf-8-sig"
)


stage_tree = ast.parse(
    stage_source,
    filename=str(
        stage_worker
    ),
)


# ============================================================
# 9. AST HELPERS
# ============================================================

def string_literals(
    tree,
):

    values = []

    for node in ast.walk(
        tree
    ):

        if (
            isinstance(
                node,
                ast.Constant,
            )
            and
            isinstance(
                node.value,
                str,
            )
        ):

            values.append(
                node.value
            )

    return values


def route_literals(
    tree,
):

    return sorted(
        set(
            value
            for value in string_literals(
                tree
            )
            if value.startswith(
                "/production/"
            )
        )
    )


def production_state_literals(
    tree,
):

    return sorted(
        value
        for value in string_literals(
            tree
        )
        if "production_state" in value
    )


def call_name(
    node,
):

    if isinstance(
        node,
        ast.Name,
    ):

        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):

        parent = call_name(
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


def call_counter(
    tree,
):

    names = []

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Call,
        ):

            name = call_name(
                node.func
            )

            names.append(
                name
                or "<dynamic>"
            )

    return Counter(
        names
    )


def defs_counter(
    tree,
):

    return Counter(
        type(
            node
        ).__name__
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        )
    )


source_routes = route_literals(
    source_tree
)

stage_routes = route_literals(
    stage_tree
)


source_state_literals = production_state_literals(
    source_tree
)

stage_state_literals = production_state_literals(
    stage_tree
)


source_calls = call_counter(
    source_tree
)

stage_calls = call_counter(
    stage_tree
)


source_defs = defs_counter(
    source_tree
)

stage_defs = defs_counter(
    stage_tree
)


# ============================================================
# 10. VERIFY TEMPORAL IMPORT
# ============================================================

temporal_import_nodes = []


for node in stage_tree.body:

    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and
        node.module
        == TEMPORAL_MODULE_NAME
    ):

        temporal_import_nodes.append(
            node
        )


imported_temporal_names = []


for node in temporal_import_nodes:

    for alias in node.names:

        imported_temporal_names.append(
            alias.asname
            or
            alias.name
        )


imported_temporal_names = sorted(
    imported_temporal_names
)


expected_imported_names = sorted(
    PUBLIC_IMPORT_NAMES
)


# ============================================================
# 11. VERIFY DORMANCY
# ============================================================

consumer_function_names = {
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
}


usage_counts = {
    name:
        0
    for name in sorted(
        consumer_function_names
    )
}


for node in ast.walk(
    stage_tree
):

    if isinstance(
        node,
        ast.Name,
    ):

        if node.id in usage_counts:

            usage_counts[
                node.id
            ] += 1


#
# Imported aliases do not appear as ast.Name nodes inside
# ImportFrom itself. Therefore usage count zero means no
# consumer binding exists elsewhere in worker_service.
#

consumer_binding_present = any(
    count > 0
    for count in usage_counts.values()
)


# ============================================================
# 12. VERIFY WORKER VERSION
# ============================================================

def worker_version_from_tree(
    tree,
):

    found = []

    for node in tree.body:

        if isinstance(
            node,
            ast.Assign,
        ):

            for target in node.targets:

                if (
                    isinstance(
                        target,
                        ast.Name,
                    )
                    and
                    target.id
                    == "WORKER_VERSION"
                ):

                    if (
                        isinstance(
                            node.value,
                            ast.Constant,
                        )
                        and
                        isinstance(
                            node.value.value,
                            str,
                        )
                    ):

                        found.append(
                            node.value.value
                        )

    return found


source_versions = worker_version_from_tree(
    source_tree
)

stage_versions = worker_version_from_tree(
    stage_tree
)


# ============================================================
# 13. TEMPORAL MODULE SMOKE TEST
# ============================================================

spec = importlib.util.spec_from_file_location(
    TEMPORAL_MODULE_NAME,
    stage_temporal,
)


module = importlib.util.module_from_spec(
    spec
)


assert spec.loader is not None


spec.loader.exec_module(
    module
)


smoke_valid = module.validate_evidence_temporal(
    {
        "evidence_id":
            "PDE_A4_A4_SMOKE",

        "source_date":
            "2026-09-27T17:00:00+00:00",

        "observed_at":
            "2026-09-27T18:00:00+00:00",

        "valid_until":
            "2026-10-27T00:00:00+00:00",
    },
    "2026-09-27T20:00:00+00:00",
)


smoke_causal_code = None


try:

    module.validate_evidence_temporal(
        {
            "evidence_id":
                "PDE_A4_A4_CAUSAL",

            "source_date":
                "2026-09-27T19:00:00+00:00",

            "observed_at":
                "2026-09-27T18:00:00+00:00",

            "valid_until":
                "2026-10-27T00:00:00+00:00",
        },
        "2026-09-27T20:00:00+00:00",
    )


except module.TemporalValidityError as exc:

    smoke_causal_code = exc.code


# ============================================================
# 14. MATERIALIZATION CHECKS
# ============================================================

checks = {
    "SOURCE_WORKER_SHA_CANONICAL":
        worker_sha
        == EXPECTED_WORKER_SHA,

    "TEMPORAL_MODULE_SHA_CANONICAL":
        temporal_sha
        == EXPECTED_TEMPORAL_SHA,

    "STAGED_TEMPORAL_BYTE_IDENTICAL":
        sha256(
            stage_temporal
        )
        == temporal_sha,

    "SOURCE_WORKER_VERSION_EXACT":
        source_versions
        == [
            SOURCE_VERSION
        ],

    "STAGED_WORKER_VERSION_EXACT":
        stage_versions
        == [
            STAGED_VERSION
        ],

    "TEMPORAL_IMPORT_NODE_EXACTLY_ONE":
        len(
            temporal_import_nodes
        )
        == 1,

    "TEMPORAL_IMPORTED_SYMBOLS_EXACT":
        imported_temporal_names
        == expected_imported_names,

    "PUBLIC_ROUTES_IDENTICAL":
        source_routes
        == stage_routes,

    "PRODUCTION_STATE_LITERALS_IDENTICAL":
        source_state_literals
        == stage_state_literals,

    "CALL_GRAPH_COUNTS_IDENTICAL":
        source_calls
        == stage_calls,

    "TOP_LEVEL_FUNCTION_CLASS_COUNTS_IDENTICAL":
        source_defs
        == stage_defs,

    "TEMPORAL_CONSUMER_BINDING_ABSENT":
        consumer_binding_present
        is False,

    "TEMPORAL_POLICY_VERSION_EXACT":
        module.TEMPORAL_VALIDITY_POLICY_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1",

    "TEMPORAL_ENGINE_VERSION_EXACT":
        module.TEMPORAL_VALIDITY_ENGINE_VERSION
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1",

    "TEMPORAL_IMPLEMENTATION_REVISION_R2":
        module.TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION
        == "R2",

    "SMOKE_VALID_EVIDENCE_PASS":
        smoke_valid.get(
            "eligible"
        )
        is True,

    "SMOKE_CAUSAL_ERROR_PASS":
        smoke_causal_code
        == (
            "PLATFORM_TEMPORAL_EVIDENCE_"
            "SOURCE_AFTER_OBSERVATION"
        ),
}


materialization_pass = all(
    checks.values()
)


# ============================================================
# 15. STAGE MANIFEST
# ============================================================

stage_worker_sha = sha256(
    stage_worker
)


stage_temporal_sha = sha256(
    stage_temporal
)


manifest = {
    "contract_version":
        "SM3_TEMPORAL_VALIDITY_RUNTIME_STAGE_V1",

    "phase":
        "09C7-B3E-A4-A4",

    "status":
        (
            "MATERIALIZED"
            if materialization_pass
            else
            "BLOCKED"
        ),

    "source_worker_version":
        SOURCE_VERSION,

    "staged_worker_version":
        STAGED_VERSION,

    "source_worker_sha256":
        worker_sha,

    "staged_worker_sha256":
        stage_worker_sha,

    "source_temporal_sha256":
        temporal_sha,

    "staged_temporal_sha256":
        stage_temporal_sha,

    "stage_directory":
        str(
            STAGE_DIR
        ),

    "stage_worker_file":
        str(
            stage_worker
        ),

    "stage_temporal_file":
        str(
            stage_temporal
        ),

    "temporal_module_name":
        TEMPORAL_MODULE_NAME,

    "imported_temporal_symbols":
        imported_temporal_names,

    "consumer_binding_present":
        consumer_binding_present,

    "consumer_usage_counts":
        usage_counts,

    "public_routes_before":
        source_routes,

    "public_routes_after":
        stage_routes,

    "production_state_store_added":
        False,

    "public_route_added":
        False,

    "network_call_added":
        False,

    "provider_call_added":
        False,

    "model_call_added":
        False,

    "confidence_decay_enabled":
        False,

    "runtime_deployment_performed":
        False,

    "canonical_worker_modified":
        False,

    "consumer_binding_deferred_until_snapshot_v2":
        True,
}


write_json(
    MANIFEST,
    manifest,
)


manifest_sha = sha256(
    MANIFEST
)


# ============================================================
# 16. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3E-A4-A4",

    "status":
        "DORMANT_RUNTIME_INTEGRATION_MATERIALIZATION_COMPLETE",

    "check_count":
        len(
            checks
        ),

    "pass_count":
        sum(
            1
            for value in checks.values()
            if value
        ),

    "failure_count":
        sum(
            1
            for value in checks.values()
            if not value
        ),

    "checks":
        checks,

    "materialization_pass":
        materialization_pass,

    "source_worker_version":
        SOURCE_VERSION,

    "staged_worker_version":
        STAGED_VERSION,

    "source_worker_sha256":
        worker_sha,

    "staged_worker_sha256":
        stage_worker_sha,

    "temporal_source_sha256":
        temporal_sha,

    "temporal_staged_sha256":
        stage_temporal_sha,

    "source_route_count":
        len(
            source_routes
        ),

    "staged_route_count":
        len(
            stage_routes
        ),

    "route_delta_count":
        len(
            set(
                source_routes
            )
            ^ set(
                stage_routes
            )
        ),

    "source_call_count":
        sum(
            source_calls.values()
        ),

    "staged_call_count":
        sum(
            stage_calls.values()
        ),

    "consumer_binding_present":
        consumer_binding_present,

    "consumer_usage_counts":
        usage_counts,

    "smoke_causal_error_code":
        smoke_causal_code,

    "stage_manifest_sha256":
        manifest_sha,

    "canonical_worker_modified":
        False,

    "runtime_integration_performed":
        False,

    "production_restart_executed":
        False,

    "route_added":
        False,

    "production_state_store_added":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "next_gate":
        (
            "09C7-B3E-A4-A5_DORMANT_RUNTIME_STATIC_ATTACK"
            if materialization_pass
            else
            "09C7-B3E-A4-A4_REMEDIATION_REQUIRED"
        ),
}


write_json(
    REPORT,
    report,
)


print(
    "=== DORMANT RUNTIME MATERIALIZATION ==="
)


for name,value in checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print(
    "\nCHECK_COUNT="
    + str(
        report[
            "check_count"
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
    "MATERIALIZATION_PASS="
    + str(
        materialization_pass
    )
)


print(
    "\n=== VERSION ==="
)

print(
    "SOURCE_WORKER_VERSION="
    + SOURCE_VERSION
)

print(
    "STAGED_WORKER_VERSION="
    + STAGED_VERSION
)


print(
    "\n=== HASHES ==="
)

print(
    "SOURCE_WORKER_SHA256="
    + worker_sha
)

print(
    "STAGED_WORKER_SHA256="
    + stage_worker_sha
)

print(
    "SOURCE_TEMPORAL_SHA256="
    + temporal_sha
)

print(
    "STAGED_TEMPORAL_SHA256="
    + stage_temporal_sha
)


print(
    "\n=== STRUCTURAL DELTA ==="
)

print(
    "SOURCE_ROUTE_COUNT="
    + str(
        report[
            "source_route_count"
        ]
    )
)

print(
    "STAGED_ROUTE_COUNT="
    + str(
        report[
            "staged_route_count"
        ]
    )
)

print(
    "ROUTE_DELTA_COUNT="
    + str(
        report[
            "route_delta_count"
        ]
    )
)

print(
    "SOURCE_CALL_COUNT="
    + str(
        report[
            "source_call_count"
        ]
    )
)

print(
    "STAGED_CALL_COUNT="
    + str(
        report[
            "staged_call_count"
        ]
    )
)

print(
    "CONSUMER_BINDING_PRESENT="
    + str(
        consumer_binding_present
    )
)

print(
    "CONSUMER_USAGE_COUNTS="
    + json.dumps(
        usage_counts,
        sort_keys=True,
    )
)


print(
    "\n=== STAGE ==="
)

print(
    "STAGE_DIRECTORY="
    + str(
        STAGE_DIR
    )
)

print(
    "STAGE_WORKER="
    + str(
        stage_worker
    )
)

print(
    "STAGE_TEMPORAL="
    + str(
        stage_temporal
    )
)

print(
    "STAGE_MANIFEST_SHA256="
    + manifest_sha
)


print(
    "\nCANONICAL_WORKER_MODIFIED=False"
)

print(
    "RUNTIME_INTEGRATION_PERFORMED=False"
)

print(
    "PRODUCTION_RESTART_EXECUTED=False"
)

print(
    "ROUTE_ADDED=False"
)

print(
    "PRODUCTION_STATE_STORE_ADDED=False"
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
    "NEXT_GATE="
    + report[
        "next_gate"
    ]
)


if not materialization_pass:

    raise SystemExit(
        1
    )
