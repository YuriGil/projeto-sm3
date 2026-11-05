from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = (
    ROOT
    / "worker"
    / "worker_service.py"
)

CONTAINER = "deployment-media-worker-1"

RMA_ID = (
    "RMA_0072a9689863b956298a9ec34f01bd0e"
)

EXPECTED_HOST_SHA = (
    "8ca08d498d41cb732341c368d8aaa03e"
    "252a4c6eeef81a430201199a2e05f882"
)


def run_docker(*args: str) -> str:

    result = subprocess.run(
        [
            "docker",
            *args,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:

        raise SystemExit(
            "SM3_09C7_B2A_DOCKER_COMMAND_FAILED:"
            + " ".join(args)
            + ":"
            + result.stderr.strip()
        )

    return result.stdout.strip()


# ============================================================
# SOURCE
# ============================================================

raw = WORKER.read_bytes()

host_sha = hashlib.sha256(
    raw
).hexdigest()


if host_sha != EXPECTED_HOST_SHA:

    raise SystemExit(
        "SM3_09C7_B2A_SOURCE_SHA_CHANGED:"
        + host_sha
    )


text = WORKER.read_text(
    encoding="utf-8-sig"
)


tree = ast.parse(
    text,
    filename=str(WORKER),
)


lines = text.splitlines()


functions = {
    node.name: node
    for node in tree.body
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
}


def source_of(name: str) -> str:

    node = functions.get(name)

    if node is None:
        return ""

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


semantic_src = source_of(
    "production_reference_semantic_analysis"
)


provider_src = source_of(
    "_reference_semantic_provider_analyze"
)


mechanical_verify_src = source_of(
    "_verify_reference_mechanical_analysis"
)


# ============================================================
# FIND IDENTITY DICT
# ============================================================

semantic_node = functions.get(
    "production_reference_semantic_analysis"
)


identity_fields = []


if semantic_node is not None:

    for node in ast.walk(
        semantic_node
    ):

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not isinstance(
            node.value,
            ast.Dict,
        ):
            continue

        matched = False

        for target in node.targets:

            if (
                isinstance(
                    target,
                    ast.Name,
                )
                and
                target.id == "identity"
            ):
                matched = True

        if not matched:
            continue

        for key in node.value.keys:

            if isinstance(
                key,
                ast.Constant,
            ):
                identity_fields.append(
                    str(key.value)
                )


# ============================================================
# PROVIDER INPUT DEPENDENCIES
# ============================================================

provider_item_dependencies = []


for field in (
    "network",
    "item_type",
    "caption",
):

    markers = (
        f'item.get("{field}")',
        f"item.get('{field}')",
    )

    if any(
        marker in provider_src
        for marker in markers
    ):
        provider_item_dependencies.append(
            field
        )


provider_uses_mechanical = (
    "mechanical"
    in provider_src
)


# ============================================================
# PHYSICAL CANONICAL RMA
# ============================================================

find_cmd = (
    "grep -RIl "
    + "'"
    + RMA_ID
    + "' "
    + "/data/media/production_state/reference_mechanical_analyses "
    + "2>/dev/null"
)


paths_text = run_docker(
    "exec",
    CONTAINER,
    "sh",
    "-lc",
    find_cmd,
)


rma_paths = [
    row.strip()
    for row in paths_text.splitlines()
    if row.strip()
]


if len(rma_paths) != 1:

    raise SystemExit(
        "SM3_09C7_B2A_RMA_PATH_COUNT_INVALID:"
        + str(len(rma_paths))
        + ":"
        + repr(rma_paths)
    )


rma_path = rma_paths[0]


raw_rma = run_docker(
    "exec",
    CONTAINER,
    "cat",
    rma_path,
)


rma = json.loads(
    raw_rma
)


# ============================================================
# SELECT CANONICAL RMA FIELDS
# ============================================================

rma_fields = sorted(
    rma.keys()
)


selected = {}


for field in (
    "mechanical_analysis_id",
    "contract_version",
    "analyzer_version",
    "source_sha256",
    "mechanical_analysis_sha256",
    "contact_sheet_path",
    "contact_sheet_sha256",
    "media_artifact_id",
    "created_at",
):

    selected[field] = rma.get(
        field
    )


rma_has_contact_sha = bool(
    rma.get(
        "contact_sheet_sha256"
    )
)


rma_has_mechanical_hash = bool(
    rma.get(
        "mechanical_analysis_sha256"
    )
)


# The verifier hashes the entire RMA record after removing only
# mechanical_analysis_sha256. If contact_sheet_sha256 is part
# of that record, the mechanical hash transitively commits it.

verifier_removes_only_own_hash = (
    "chk=dict(rec)"
    in mechanical_verify_src
    and
    'chk.pop("mechanical_analysis_sha256",None)'
    in mechanical_verify_src.replace(
        " ",
        "",
    )
)


# Whitespace-independent confirmation.

compact_mechanical_verify = "".join(
    mechanical_verify_src.split()
)


verifier_removes_only_own_hash = (
    "chk=dict(rec)"
    in compact_mechanical_verify
    and
    'chk.pop("mechanical_analysis_sha256",None)'
    in compact_mechanical_verify
    and
    "_canonical_sha256(chk)"
    in compact_mechanical_verify
)


contact_sheet_transitively_committed = (
    rma_has_contact_sha
    and
    rma_has_mechanical_hash
    and
    verifier_removes_only_own_hash
)


# ============================================================
# IDENTITY / INPUT CONSISTENCY
# ============================================================

identity_set = set(
    identity_fields
)


mutable_item_input_not_committed = [
    field
    for field in provider_item_dependencies
    if field not in identity_set
]


semantic_identity_input_mismatch = bool(
    mutable_item_input_not_committed
)


media_centric_dedup_blocked = (
    "reference_item_id"
    in identity_set
)


contact_sheet_explicit_in_identity = (
    "contact_sheet_sha256"
    in identity_set
)


# ============================================================
# STORAGE SHAPE
# ============================================================

semantic_storage_is_item_scoped = (
    "_reference_semantic_analysis_dir"
    in semantic_src
)


semantic_dir_src = source_of(
    "_reference_semantic_analysis_dir"
)


semantic_storage_uses_item_id = (
    "item_id"
    in semantic_dir_src
)


# ============================================================
# OUTPUT
# ============================================================

print(
    "=== SM3 09C7-B2A SEMANTIC INPUT / IDENTITY AUDIT ==="
)

print()

print(
    "HOST_SHA256="
    + host_sha
)

print(
    "RMA_PATH="
    + rma_path
)

print()

print(
    "=== CURRENT RSA IDENTITY ==="
)

print(
    "RSA_IDENTITY_FIELDS="
    + ",".join(
        identity_fields
    )
)

print()

print(
    "=== PROVIDER ITEM CONTEXT INPUTS ==="
)

print(
    "PROVIDER_ITEM_DEPENDENCIES="
    + ",".join(
        provider_item_dependencies
    )
)

print(
    "PROVIDER_USES_MECHANICAL="
    + str(
        provider_uses_mechanical
    )
)

print()

print(
    "=== CANONICAL RMA ==="
)

for key,value in selected.items():

    print(
        key.upper()
        + "="
        + str(value)
    )


print(
    "RMA_TOP_LEVEL_FIELDS="
    + ",".join(
        rma_fields
    )
)

print(
    "RMA_HAS_CONTACT_SHEET_SHA="
    + str(
        rma_has_contact_sha
    )
)

print(
    "RMA_HAS_MECHANICAL_ANALYSIS_SHA="
    + str(
        rma_has_mechanical_hash
    )
)

print(
    "RMA_VERIFIER_HASHES_RECORD_MINUS_OWN_HASH="
    + str(
        verifier_removes_only_own_hash
    )
)

print(
    "CONTACT_SHEET_TRANSITIVELY_COMMITTED_BY_RMA_HASH="
    + str(
        contact_sheet_transitively_committed
    )
)

print()

print(
    "=== ARCHITECTURAL FINDINGS ==="
)

print(
    "MUTABLE_ITEM_INPUT_NOT_COMMITTED="
    + ",".join(
        mutable_item_input_not_committed
    )
)

print(
    "SEMANTIC_IDENTITY_INPUT_MISMATCH="
    + str(
        semantic_identity_input_mismatch
    )
)

print(
    "MEDIA_CENTRIC_DEDUP_BLOCKED_BY_REFERENCE_ITEM_ID="
    + str(
        media_centric_dedup_blocked
    )
)

print(
    "CONTACT_SHEET_EXPLICIT_IN_RSA_IDENTITY="
    + str(
        contact_sheet_explicit_in_identity
    )
)

print(
    "SEMANTIC_STORAGE_ITEM_SCOPED="
    + str(
        semantic_storage_is_item_scoped
        and
        semantic_storage_uses_item_id
    )
)

print()

print(
    "SOURCE_MODIFIED=False"
)

print(
    "RUNTIME_MODIFIED=False"
)

print(
    "API_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "DIAGNOSTIC_READ_ONLY=True"
)

print(
    "SM3_09C7_B2A_SEMANTIC_INPUT_IDENTITY_AUDIT_COMPLETE"
)

sys.exit(0)
