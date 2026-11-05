from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


BASE_INSPECT = Path(sys.argv[1])
TARGET_INSPECT = Path(sys.argv[2])

BUILT_WORKER = Path(sys.argv[3])
BUILT_TEMPORAL = Path(sys.argv[4])

REPORT = Path(sys.argv[5])

EXPECTED_BASE_ID = sys.argv[6]
EXPECTED_TARGET_ID = sys.argv[7]
EXPECTED_TARGET_TAG = sys.argv[8]


EXPECTED_WORKER_SHA = (
    "550664623791a9f8a021c165b47ea511"
    "3226287cab63f0732767c47c1663a77e"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)


EXPECTED_TEMPORAL_SYMBOLS = sorted([
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TemporalValidityError",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
])


def sha256(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path: Path):

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def write_json(path: Path, value):

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


base_array = load_json(
    BASE_INSPECT
)

target_array = load_json(
    TARGET_INSPECT
)


if not isinstance(base_array, list) or len(base_array) != 1:

    raise SystemExit(
        "A4_A7_R3_BASE_INSPECT_INVALID"
    )


if not isinstance(target_array, list) or len(target_array) != 1:

    raise SystemExit(
        "A4_A7_R3_TARGET_INSPECT_INVALID"
    )


base = base_array[0]
target = target_array[0]


worker_sha = sha256(
    BUILT_WORKER
)

temporal_sha = sha256(
    BUILT_TEMPORAL
)


worker_source = BUILT_WORKER.read_text(
    encoding="utf-8-sig"
)

temporal_source = BUILT_TEMPORAL.read_text(
    encoding="utf-8-sig"
)


worker_tree = ast.parse(
    worker_source,
    filename=str(BUILT_WORKER),
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(BUILT_TEMPORAL),
)


# ============================================================
# WORKER VERSION
# ============================================================

worker_versions = []


for node in worker_tree.body:

    if not isinstance(node, ast.Assign):
        continue

    for target_node in node.targets:

        if (
            isinstance(target_node, ast.Name)
            and target_node.id == "WORKER_VERSION"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            worker_versions.append(
                node.value.value
            )


# ============================================================
# TEMPORAL IMPORT
# ============================================================

temporal_imports = []


for node in worker_tree.body:

    if (
        isinstance(node, ast.ImportFrom)
        and node.module == "SM3_platform_temporal_validity_v1_r2"
    ):
        temporal_imports.append(node)


imported_symbols = []


if len(temporal_imports) == 1:

    imported_symbols = sorted(
        alias.name
        for alias in temporal_imports[0].names
    )


# ============================================================
# TEMPORAL CONSTANTS
# ============================================================

temporal_constants = {}


for node in temporal_tree.body:

    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(node.value, ast.Constant):
        continue

    for target_node in node.targets:

        if isinstance(target_node, ast.Name):

            temporal_constants[
                target_node.id
            ] = node.value.value


# ============================================================
# IMAGE METADATA
# ============================================================

base_id = base.get("Id")
target_id = target.get("Id")

target_tags = (
    target.get("RepoTags")
    or []
)


base_arch = base.get("Architecture")
target_arch = target.get("Architecture")

base_os = base.get("Os")
target_os = target.get("Os")


base_config = (
    base.get("Config")
    or {}
)

target_config = (
    target.get("Config")
    or {}
)


config_exact_match = (
    base_config
    ==
    target_config
)


base_layers = (
    base.get(
        "RootFS",
        {},
    ).get(
        "Layers",
        [],
    )
    or []
)


target_layers = (
    target.get(
        "RootFS",
        {},
    ).get(
        "Layers",
        [],
    )
    or []
)


base_layers_are_target_prefix = (
    len(target_layers) >= len(base_layers)
    and
    target_layers[:len(base_layers)] == base_layers
)


additional_layer_count = (
    len(target_layers)
    - len(base_layers)
)


# ============================================================
# CHECKS
# ============================================================

checks = {
    "BASE_ID_EXACT":
        base_id
        == EXPECTED_BASE_ID,

    "TARGET_ID_EXACT":
        target_id
        == EXPECTED_TARGET_ID,

    "TARGET_DIFFERS_FROM_BASE":
        target_id
        != base_id,

    "TARGET_TAG_PRESENT":
        EXPECTED_TARGET_TAG
        in target_tags,

    "WORKER_BYTES_EXACT":
        worker_sha
        == EXPECTED_WORKER_SHA,

    "TEMPORAL_BYTES_EXACT":
        temporal_sha
        == EXPECTED_TEMPORAL_SHA,

    "WORKER_VERSION_EXACT":
        worker_versions
        == ["2.35.1"],

    "TEMPORAL_IMPORT_COUNT_EXACT":
        len(temporal_imports)
        == 1,

    "TEMPORAL_IMPORT_SYMBOLS_EXACT":
        imported_symbols
        == EXPECTED_TEMPORAL_SYMBOLS,

    "TEMPORAL_POLICY_EXACT":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_POLICY_VERSION"
        )
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1",

    "TEMPORAL_ENGINE_EXACT":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_ENGINE_VERSION"
        )
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1",

    "TEMPORAL_REVISION_EXACT":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
        )
        == "R2",

    "ARCHITECTURE_INHERITED":
        target_arch
        == base_arch,

    "OS_INHERITED":
        target_os
        == base_os,

    "CONFIG_EXACTLY_INHERITED":
        config_exact_match,

    "BASE_ROOTFS_IS_TARGET_PREFIX":
        base_layers_are_target_prefix,

    "TARGET_HAS_ADDITIONAL_LAYER":
        additional_layer_count
        > 0,
}


verification_pass = all(
    checks.values()
)


report = {
    "phase":
        "09C7-B3E-A4-A7-R3",

    "status":
        "IMAGE_CONTENT_AND_LINEAGE_VERIFIED",

    "base_image_id":
        base_id,

    "target_image_id":
        target_id,

    "target_image_tag":
        EXPECTED_TARGET_TAG,

    "worker_sha256":
        worker_sha,

    "temporal_sha256":
        temporal_sha,

    "worker_versions":
        worker_versions,

    "temporal_import_count":
        len(temporal_imports),

    "temporal_imported_symbols":
        imported_symbols,

    "temporal_policy_version":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_POLICY_VERSION"
        ),

    "temporal_engine_version":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_ENGINE_VERSION"
        ),

    "temporal_implementation_revision":
        temporal_constants.get(
            "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
        ),

    "base_architecture":
        base_arch,

    "target_architecture":
        target_arch,

    "base_os":
        base_os,

    "target_os":
        target_os,

    "config_exact_match":
        config_exact_match,

    "base_rootfs_layer_count":
        len(base_layers),

    "target_rootfs_layer_count":
        len(target_layers),

    "additional_layer_count":
        additional_layer_count,

    "base_layers_are_target_prefix":
        base_layers_are_target_prefix,

    "checks":
        checks,

    "check_count":
        len(checks),

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

    "verification_pass":
        verification_pass,

    "image_started":
        False,

    "app_route_called":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "production_deployment_allowed":
        False,

    "production_deployment_blocker":
        "PRODUCTION_DOCKERFILE_DOES_NOT_PACKAGE_TEMPORAL_MODULE",

    "next_gate":
        (
            "09C7-B3E-A4-A8_ISOLATED_RUNTIME_DYNAMIC_BOOT_TEST"
            if verification_pass
            else
            "09C7-B3E-A4-A7-R3_REMEDIATION_REQUIRED"
        ),
}


write_json(
    REPORT,
    report,
)


print(
    "=== IMAGE CONTENT AND LINEAGE VERIFICATION ==="
)


for name,value in checks.items():

    print(
        name
        + "="
        + str(value)
    )


print(
    "\nCHECK_COUNT="
    + str(report["check_count"])
)

print(
    "PASS_COUNT="
    + str(report["pass_count"])
)

print(
    "FAILURE_COUNT="
    + str(report["failure_count"])
)

print(
    "VERIFICATION_PASS="
    + str(verification_pass)
)


print(
    "\n=== BUILT CONTENT ==="
)

print(
    "WORKER_SHA256="
    + worker_sha
)

print(
    "TEMPORAL_SHA256="
    + temporal_sha
)

print(
    "WORKER_VERSION="
    + (
        worker_versions[0]
        if len(worker_versions) == 1
        else "INVALID"
    )
)

print(
    "TEMPORAL_IMPORT_COUNT="
    + str(len(temporal_imports))
)

print(
    "TEMPORAL_IMPORT_SYMBOLS="
    + json.dumps(imported_symbols)
)

print(
    "TEMPORAL_POLICY_VERSION="
    + str(report["temporal_policy_version"])
)

print(
    "TEMPORAL_ENGINE_VERSION="
    + str(report["temporal_engine_version"])
)

print(
    "TEMPORAL_IMPLEMENTATION_REVISION="
    + str(report["temporal_implementation_revision"])
)


print(
    "\n=== IMAGE LINEAGE ==="
)

print(
    "BASE_IMAGE_ID="
    + str(base_id)
)

print(
    "TARGET_IMAGE_ID="
    + str(target_id)
)

print(
    "CONFIG_EXACT_MATCH="
    + str(config_exact_match)
)

print(
    "BASE_ROOTFS_LAYER_COUNT="
    + str(len(base_layers))
)

print(
    "TARGET_ROOTFS_LAYER_COUNT="
    + str(len(target_layers))
)

print(
    "ADDITIONAL_LAYER_COUNT="
    + str(additional_layer_count)
)

print(
    "BASE_LAYERS_ARE_TARGET_PREFIX="
    + str(base_layers_are_target_prefix)
)


print(
    "\nIMAGE_STARTED=False"
)

print(
    "APP_ROUTE_CALLED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "PRODUCTION_DEPLOYMENT_ALLOWED=False"
)

print(
    "PRODUCTION_DEPLOYMENT_BLOCKER="
    + report["production_deployment_blocker"]
)

print(
    "NEXT_GATE="
    + report["next_gate"]
)


if not verification_pass:
    raise SystemExit(1)