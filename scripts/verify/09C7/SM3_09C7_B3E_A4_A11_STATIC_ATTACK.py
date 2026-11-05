from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path


candidate_root = Path(sys.argv[1])
candidate_worker = Path(sys.argv[2])
candidate_temporal = Path(sys.argv[3])
candidate_requirements = Path(sys.argv[4])
candidate_dockerfile = Path(sys.argv[5])

baseline_worker = Path(sys.argv[6])
baseline_requirements = Path(sys.argv[7])
baseline_dockerfile = Path(sys.argv[8])

stage_worker = Path(sys.argv[9])
stage_temporal = Path(sys.argv[10])

manifest_file = Path(sys.argv[11])
a10_report_file = Path(sys.argv[12])
attack_report_file = Path(sys.argv[13])


EXPECTED_WORKER_SHA = (
    "550664623791a9f8a021c165b47ea511"
    "3226287cab63f0732767c47c1663a77e"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)

EXPECTED_REQUIREMENTS_SHA = (
    "68758b81820c6128e5f72dc66c76e15a"
    "f9d6585e86c4726583509379419f50e1"
)

EXPECTED_DOCKERFILE_SHA = (
    "21e48d249a7d4c4360d64a1a079b610"
    "e620d2e470a6f04bdac9a75f56b0fc921"
)

WORKER_COPY = (
    "COPY worker/worker_service.py "
    "/app/worker_service.py"
)

TEMPORAL_COPY = (
    "COPY worker/SM3_platform_temporal_validity_v1_r2.py "
    "/app/SM3_platform_temporal_validity_v1_r2.py"
)

REQUIREMENTS_COPY = (
    "COPY worker/requirements-worker.txt "
    "/app/requirements.txt"
)

ALLOWED_FILES = {
    "deployment/media-worker.Dockerfile",
    "worker/requirements-worker.txt",
    "worker/worker_service.py",
    "worker/SM3_platform_temporal_validity_v1_r2.py",
}

EXPECTED_TEMPORAL_IMPORTS = sorted([
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TemporalValidityError",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def norm_rel(path: Path) -> str:
    return path.relative_to(candidate_root).as_posix()


checks: dict[str, bool] = {}
details: dict[str, object] = {}
failures: list[str] = []


# ============================================================
# 1. EXACT FILE HASHES
# ============================================================

actual_worker_sha = sha(candidate_worker)
actual_temporal_sha = sha(candidate_temporal)
actual_requirements_sha = sha(candidate_requirements)
actual_dockerfile_sha = sha(candidate_dockerfile)

checks["WORKER_SHA_EXACT"] = (
    actual_worker_sha == EXPECTED_WORKER_SHA
)

checks["TEMPORAL_SHA_EXACT"] = (
    actual_temporal_sha == EXPECTED_TEMPORAL_SHA
)

checks["REQUIREMENTS_SHA_EXACT"] = (
    actual_requirements_sha == EXPECTED_REQUIREMENTS_SHA
)

checks["DOCKERFILE_SHA_EXACT"] = (
    actual_dockerfile_sha == EXPECTED_DOCKERFILE_SHA
)

checks["WORKER_EQUALS_AUDITED_STAGE"] = (
    candidate_worker.read_bytes()
    == stage_worker.read_bytes()
)

checks["TEMPORAL_EQUALS_AUDITED_STAGE"] = (
    candidate_temporal.read_bytes()
    == stage_temporal.read_bytes()
)

checks["REQUIREMENTS_EQUALS_PRODUCTION"] = (
    candidate_requirements.read_bytes()
    == baseline_requirements.read_bytes()
)


# ============================================================
# 2. CANDIDATE TREE HYGIENE
# ============================================================

all_files: list[str] = []
all_dirs: list[str] = []
symlinks: list[str] = []

for path in candidate_root.rglob("*"):

    rel = norm_rel(path)

    if path.is_symlink():
        symlinks.append(rel)

    if path.is_file():
        all_files.append(rel)

    elif path.is_dir():
        all_dirs.append(rel)


all_files = sorted(all_files)
all_dirs = sorted(all_dirs)
symlinks = sorted(symlinks)

unexpected_files = sorted(
    set(all_files) - ALLOWED_FILES
)

missing_files = sorted(
    ALLOWED_FILES - set(all_files)
)

pycache_entries = sorted(
    p
    for p in all_files + all_dirs
    if "__pycache__" in p.split("/")
)

compiled_python_files = sorted(
    p
    for p in all_files
    if p.endswith(".pyc")
    or p.endswith(".pyo")
)


checks["CANDIDATE_FILE_SET_EXACT"] = (
    set(all_files) == ALLOWED_FILES
)

checks["NO_UNEXPECTED_FILES"] = (
    len(unexpected_files) == 0
)

checks["NO_MISSING_FILES"] = (
    len(missing_files) == 0
)

checks["NO_PYCACHE"] = (
    len(pycache_entries) == 0
)

checks["NO_COMPILED_PYTHON_ARTIFACTS"] = (
    len(compiled_python_files) == 0
)

checks["NO_SYMLINKS"] = (
    len(symlinks) == 0
)

details["candidate_files"] = all_files
details["candidate_directories"] = all_dirs
details["unexpected_files"] = unexpected_files
details["missing_files"] = missing_files
details["pycache_entries"] = pycache_entries
details["compiled_python_files"] = compiled_python_files
details["symlinks"] = symlinks


# ============================================================
# 3. DOCKERFILE BYTE/TEXT ATTACK
# ============================================================

baseline_bytes = baseline_dockerfile.read_bytes()
candidate_bytes = candidate_dockerfile.read_bytes()

baseline_text = baseline_bytes.decode("utf-8-sig")
candidate_text = candidate_bytes.decode("utf-8-sig")


if "\r\n" in baseline_text:
    newline = "\r\n"
    newline_style = "CRLF"
else:
    newline = "\n"
    newline_style = "LF"


insert_block = (
    WORKER_COPY
    + newline
    + TEMPORAL_COPY
    + newline
)

reverse_block = (
    WORKER_COPY
    + newline
)

insert_count = candidate_text.count(insert_block)

reconstructed_baseline = candidate_text.replace(
    insert_block,
    reverse_block,
)


checks["DOCKERFILE_SINGLE_INSERT_BLOCK"] = (
    insert_count == 1
)

checks["DOCKERFILE_RECONSTRUCTS_BASELINE_EXACTLY"] = (
    reconstructed_baseline == baseline_text
)

checks["DOCKERFILE_BASELINE_DIFF_ONLY_TEMPORAL_COPY"] = (
    insert_count == 1
    and reconstructed_baseline == baseline_text
)


candidate_lines = [
    line.strip()
    for line in candidate_text.splitlines()
]

copy_add_lines = [
    line
    for line in candidate_lines
    if line.startswith("COPY ")
    or line.startswith("ADD ")
]


checks["DOCKERFILE_COPY_ADD_COUNT_EXACT"] = (
    len(copy_add_lines) == 3
)

checks["DOCKERFILE_REQUIREMENTS_COPY_EXACT_ONCE"] = (
    copy_add_lines.count(REQUIREMENTS_COPY) == 1
)

checks["DOCKERFILE_WORKER_COPY_EXACT_ONCE"] = (
    copy_add_lines.count(WORKER_COPY) == 1
)

checks["DOCKERFILE_TEMPORAL_COPY_EXACT_ONCE"] = (
    copy_add_lines.count(TEMPORAL_COPY) == 1
)


broad_copy_patterns = (
    "COPY worker/ /app/",
    "ADD worker/ /app/",
    "COPY . /app/",
    "ADD . /app/",
    "COPY ./ /app/",
    "ADD ./ /app/",
)


broad_copy_hits = [
    line
    for line in copy_add_lines
    if line in broad_copy_patterns
]


wildcard_copy_hits = [
    line
    for line in copy_add_lines
    if "*" in line
    or "?" in line
]


remote_add_hits = [
    line
    for line in copy_add_lines
    if line.startswith("ADD http://")
    or line.startswith("ADD https://")
]


checks["NO_BROAD_DIRECTORY_COPY"] = (
    len(broad_copy_hits) == 0
)

checks["NO_WILDCARD_COPY"] = (
    len(wildcard_copy_hits) == 0
)

checks["NO_REMOTE_ADD"] = (
    len(remote_add_hits) == 0
)


details["dockerfile_newline_style"] = newline_style
details["copy_add_lines"] = copy_add_lines
details["broad_copy_hits"] = broad_copy_hits
details["wildcard_copy_hits"] = wildcard_copy_hits
details["remote_add_hits"] = remote_add_hits


# ============================================================
# 4. VERIFY COPY SOURCES RESOLVE INSIDE CANDIDATE
# ============================================================

copy_sources = {
    "worker/requirements-worker.txt":
        candidate_root / "worker/requirements-worker.txt",

    "worker/worker_service.py":
        candidate_root / "worker/worker_service.py",

    "worker/SM3_platform_temporal_validity_v1_r2.py":
        candidate_root
        / "worker/SM3_platform_temporal_validity_v1_r2.py",
}


copy_source_state = {
    source: path.is_file()
    for source, path in copy_sources.items()
}


checks["ALL_EXPLICIT_COPY_SOURCES_EXIST"] = all(
    copy_source_state.values()
)

details["copy_source_state"] = copy_source_state


# ============================================================
# 5. WORKER AST / TEMPORAL IMPORT ATTACK
# ============================================================

worker_source = candidate_worker.read_text(
    encoding="utf-8-sig"
)

worker_tree = ast.parse(
    worker_source,
    filename=str(candidate_worker),
)


versions: list[str] = []
temporal_imports: list[ast.ImportFrom] = []


for node in worker_tree.body:

    if isinstance(node, ast.Assign):

        for target in node.targets:

            if (
                isinstance(target, ast.Name)
                and target.id == "WORKER_VERSION"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                versions.append(node.value.value)

    if (
        isinstance(node, ast.ImportFrom)
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):
        temporal_imports.append(node)


imported_symbols: list[str] = []

if len(temporal_imports) == 1:

    imported_symbols = sorted(
        alias.name
        for alias in temporal_imports[0].names
    )


checks["WORKER_VERSION_SINGLE_EXACT"] = (
    versions == ["2.35.1"]
)

checks["TEMPORAL_IMPORT_COUNT_EXACT"] = (
    len(temporal_imports) == 1
)

checks["TEMPORAL_IMPORT_SYMBOLS_EXACT"] = (
    imported_symbols == EXPECTED_TEMPORAL_IMPORTS
)


details["worker_versions"] = versions
details["temporal_import_count"] = len(temporal_imports)
details["temporal_import_symbols"] = imported_symbols


# ============================================================
# 6. TEMPORAL MODULE AST ATTACK
# ============================================================

temporal_source = candidate_temporal.read_text(
    encoding="utf-8-sig"
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(candidate_temporal),
)


constants: dict[str, object] = {}


for node in temporal_tree.body:

    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(node.value, ast.Constant):
        continue

    for target in node.targets:

        if isinstance(target, ast.Name):
            constants[target.id] = node.value.value


checks["TEMPORAL_POLICY_EXACT"] = (
    constants.get(
        "TEMPORAL_VALIDITY_POLICY_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
)

checks["TEMPORAL_ENGINE_EXACT"] = (
    constants.get(
        "TEMPORAL_VALIDITY_ENGINE_VERSION"
    )
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
)

checks["TEMPORAL_REVISION_EXACT"] = (
    constants.get(
        "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
    )
    == "R2"
)


# ============================================================
# 7. A10 MANIFEST SELF-CONSISTENCY ATTACK
# ============================================================

manifest = load_json(manifest_file)
a10_report = load_json(a10_report_file)


checks["MANIFEST_CONTRACT_EXACT"] = (
    manifest.get("contract_version")
    == "SM3_PRODUCTION_PACKAGING_CANDIDATE_V1"
)

checks["MANIFEST_STATUS_MATERIALIZED"] = (
    manifest.get("status") == "MATERIALIZED"
)

checks["MANIFEST_WORKER_HASH_MATCHES"] = (
    manifest["files"]["worker"]["sha256"]
    == actual_worker_sha
)

checks["MANIFEST_TEMPORAL_HASH_MATCHES"] = (
    manifest["files"]["temporal"]["sha256"]
    == actual_temporal_sha
)

checks["MANIFEST_REQUIREMENTS_HASH_MATCHES"] = (
    manifest["files"]["requirements"]["sha256"]
    == actual_requirements_sha
)

checks["MANIFEST_DOCKERFILE_HASH_MATCHES"] = (
    manifest["files"]["dockerfile"]["sha256"]
    == actual_dockerfile_sha
)

checks["MANIFEST_PACKAGING_COUNTS_EXACT"] = (
    manifest["packaging"]["copy_add_count"] == 3
    and manifest["packaging"]["worker_service_copy_count"] == 1
    and manifest["packaging"]["temporal_module_copy_count"] == 1
    and manifest["packaging"]["broad_worker_directory_copy_count"] == 0
)

checks["A10_REPORT_MATERIALIZATION_PASS"] = (
    a10_report.get("materialization_pass") is True
)

checks["A10_REPORT_CANONICAL_HOST_UNCHANGED"] = (
    a10_report.get("canonical_host_unchanged") is True
)

checks["A10_REPORT_PRODUCTION_ISOLATION_PASS"] = (
    a10_report.get("production_isolation_pass") is True
)

checks["A10_REPORT_BUILD_NOT_EXECUTED"] = (
    a10_report.get("build_executed") is False
)

checks["A10_REPORT_DEPLOY_NOT_EXECUTED"] = (
    a10_report.get("production_deployment_performed") is False
)


# ============================================================
# 8. CLASSIFY FAILURES
# ============================================================

for name, value in checks.items():

    if not value:
        failures.append(name)


critical_failures = [
    name
    for name in failures
    if name in {
        "WORKER_SHA_EXACT",
        "TEMPORAL_SHA_EXACT",
        "DOCKERFILE_SHA_EXACT",
        "DOCKERFILE_RECONSTRUCTS_BASELINE_EXACTLY",
        "DOCKERFILE_BASELINE_DIFF_ONLY_TEMPORAL_COPY",
        "WORKER_VERSION_SINGLE_EXACT",
        "TEMPORAL_IMPORT_COUNT_EXACT",
        "TEMPORAL_IMPORT_SYMBOLS_EXACT",
        "TEMPORAL_POLICY_EXACT",
        "TEMPORAL_ENGINE_EXACT",
        "TEMPORAL_REVISION_EXACT",
        "ALL_EXPLICIT_COPY_SOURCES_EXIST",
        "NO_BROAD_DIRECTORY_COPY",
        "NO_REMOTE_ADD",
        "NO_SYMLINKS",
    }
]


hygiene_failures = [
    name
    for name in failures
    if name in {
        "CANDIDATE_FILE_SET_EXACT",
        "NO_UNEXPECTED_FILES",
        "NO_PYCACHE",
        "NO_COMPILED_PYTHON_ARTIFACTS",
    }
]


attack_pass = len(failures) == 0


if attack_pass:

    classification = (
        "STATIC_ATTACK_PASS"
    )

    next_gate = (
        "09C7-B3E-A4-A12_"
        "PRODUCTION_PACKAGING_CANDIDATE_ISOLATED_BUILD"
    )

elif (
    len(critical_failures) == 0
    and len(hygiene_failures) > 0
):

    classification = (
        "CANDIDATE_HYGIENE_REMEDIATION_REQUIRED"
    )

    next_gate = (
        "09C7-B3E-A4-A11-R1_"
        "CANDIDATE_HYGIENE_REMEDIATION"
    )

else:

    classification = (
        "STATIC_ATTACK_BLOCKED"
    )

    next_gate = (
        "09C7-B3E-A4-A11_REMEDIATION_REQUIRED"
    )


report = {
    "phase":
        "09C7-B3E-A4-A11",

    "contract_version":
        "SM3_PRODUCTION_PACKAGING_STATIC_ATTACK_V1",

    "classification":
        classification,

    "check_count":
        len(checks),

    "pass_count":
        sum(
            1
            for value in checks.values()
            if value
        ),

    "failure_count":
        len(failures),

    "failures":
        failures,

    "critical_failures":
        critical_failures,

    "hygiene_failures":
        hygiene_failures,

    "checks":
        checks,

    "details":
        details,

    "attack_pass":
        attack_pass,

    "build_executed":
        False,

    "compose_up_executed":
        False,

    "production_deployment_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "production_deployment_allowed":
        False,

    "next_gate":
        next_gate,
}


attack_report_file.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== A4-A11 STATIC ATTACK ==="
)

print(
    "CLASSIFICATION="
    + classification
)

print(
    "CHECK_COUNT="
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
    "CRITICAL_FAILURE_COUNT="
    + str(len(critical_failures))
)

print(
    "HYGIENE_FAILURE_COUNT="
    + str(len(hygiene_failures))
)


for failure in failures:

    print(
        "FAILURE="
        + failure
    )


print(
    "CANDIDATE_FILE_COUNT="
    + str(len(all_files))
)

for file_name in all_files:

    print(
        "CANDIDATE_FILE="
        + file_name
    )


print(
    "UNEXPECTED_FILE_COUNT="
    + str(len(unexpected_files))
)

for file_name in unexpected_files:

    print(
        "UNEXPECTED_FILE="
        + file_name
    )


print(
    "PYCACHE_ENTRY_COUNT="
    + str(len(pycache_entries))
)

for entry in pycache_entries:

    print(
        "PYCACHE_ENTRY="
        + entry
    )


print(
    "COMPILED_PYTHON_FILE_COUNT="
    + str(len(compiled_python_files))
)


print(
    "COPY_ADD_COUNT="
    + str(len(copy_add_lines))
)

for line in copy_add_lines:

    print(
        "COPY_ADD="
        + line
    )


print(
    "DOCKERFILE_DIFF_ONLY_TEMPORAL_COPY="
    + str(
        checks[
            "DOCKERFILE_BASELINE_DIFF_ONLY_TEMPORAL_COPY"
        ]
    )
)

print(
    "WORKER_VERSION="
    + (
        versions[0]
        if len(versions) == 1
        else "INVALID"
    )
)

print(
    "TEMPORAL_IMPORT_COUNT="
    + str(len(temporal_imports))
)

print(
    "ALL_EXPLICIT_COPY_SOURCES_EXIST="
    + str(
        checks[
            "ALL_EXPLICIT_COPY_SOURCES_EXIST"
        ]
    )
)

print(
    "ATTACK_PASS="
    + str(attack_pass)
)

print(
    "BUILD_EXECUTED=False"
)

print(
    "COMPOSE_UP_EXECUTED=False"
)

print(
    "PRODUCTION_DEPLOYMENT_PERFORMED=False"
)

print(
    "NEXT_GATE="
    + next_gate
)


if not attack_pass:
    raise SystemExit(1)