from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


candidate_root = Path(sys.argv[1])

candidate_worker = Path(sys.argv[2])
candidate_temporal = Path(sys.argv[3])
candidate_requirements = Path(sys.argv[4])
candidate_dockerfile = Path(sys.argv[5])

baseline_requirements = Path(sys.argv[6])
baseline_dockerfile = Path(sys.argv[7])

stage_worker = Path(sys.argv[8])
stage_temporal = Path(sys.argv[9])

manifest_file = Path(sys.argv[10])
a10_report_file = Path(sys.argv[11])
a11_r1_report_file = Path(sys.argv[12])

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
    "68758b81820c6128e5f72dc66c76e15"
    "af9d6585e86c4726583509379419f50e1"
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
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def rel(path: Path) -> str:
    return path.relative_to(
        candidate_root
    ).as_posix()


checks: dict[str, bool] = {}
details: dict[str, object] = {}


# ============================================================
# 1. CORE HASHES
# ============================================================

worker_sha = sha(
    candidate_worker
)

temporal_sha = sha(
    candidate_temporal
)

requirements_sha = sha(
    candidate_requirements
)

dockerfile_sha = sha(
    candidate_dockerfile
)


checks["WORKER_SHA_EXACT"] = (
    worker_sha == EXPECTED_WORKER_SHA
)

checks["TEMPORAL_SHA_EXACT"] = (
    temporal_sha == EXPECTED_TEMPORAL_SHA
)

checks["REQUIREMENTS_SHA_EXACT"] = (
    requirements_sha
    == EXPECTED_REQUIREMENTS_SHA
)

checks["DOCKERFILE_SHA_EXACT"] = (
    dockerfile_sha
    == EXPECTED_DOCKERFILE_SHA
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

candidate_files = []
candidate_dirs = []
symlinks = []


for path in candidate_root.rglob("*"):

    relative = rel(
        path
    )

    if path.is_symlink():
        symlinks.append(
            relative
        )

    if path.is_file():

        candidate_files.append(
            relative
        )

    elif path.is_dir():

        candidate_dirs.append(
            relative
        )


candidate_files = sorted(
    candidate_files
)

candidate_dirs = sorted(
    candidate_dirs
)

symlinks = sorted(
    symlinks
)


unexpected_files = sorted(
    set(candidate_files)
    - ALLOWED_FILES
)

missing_files = sorted(
    ALLOWED_FILES
    - set(candidate_files)
)


pycache_entries = sorted(
    entry
    for entry in (
        candidate_files
        + candidate_dirs
    )
    if "__pycache__"
    in entry.split("/")
)


compiled_files = sorted(
    entry
    for entry in candidate_files
    if (
        entry.endswith(".pyc")
        or entry.endswith(".pyo")
    )
)


checks["CANDIDATE_FILE_SET_EXACT"] = (
    set(candidate_files)
    == ALLOWED_FILES
)

checks["NO_UNEXPECTED_FILES"] = (
    len(unexpected_files)
    == 0
)

checks["NO_MISSING_FILES"] = (
    len(missing_files)
    == 0
)

checks["NO_PYCACHE"] = (
    len(pycache_entries)
    == 0
)

checks["NO_COMPILED_PYTHON_ARTIFACTS"] = (
    len(compiled_files)
    == 0
)

checks["NO_SYMLINKS"] = (
    len(symlinks)
    == 0
)


details["candidate_files"] = (
    candidate_files
)

details["candidate_dirs"] = (
    candidate_dirs
)

details["unexpected_files"] = (
    unexpected_files
)

details["missing_files"] = (
    missing_files
)

details["pycache_entries"] = (
    pycache_entries
)

details["compiled_python_files"] = (
    compiled_files
)

details["symlinks"] = (
    symlinks
)


# ============================================================
# 3. DOCKERFILE EXACT-DIFF ATTACK
# ============================================================

baseline_text = (
    baseline_dockerfile
    .read_bytes()
    .decode("utf-8-sig")
)

candidate_text = (
    candidate_dockerfile
    .read_bytes()
    .decode("utf-8-sig")
)


if "\r\n" in baseline_text:

    newline = "\r\n"

else:

    newline = "\n"


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


insert_count = (
    candidate_text.count(
        insert_block
    )
)


reconstructed = (
    candidate_text.replace(
        insert_block,
        reverse_block,
    )
)


checks["DOCKERFILE_SINGLE_INSERT_BLOCK"] = (
    insert_count == 1
)

checks["DOCKERFILE_RECONSTRUCTS_BASELINE_EXACTLY"] = (
    reconstructed
    == baseline_text
)

checks["DOCKERFILE_DIFF_ONLY_TEMPORAL_COPY"] = (
    insert_count == 1
    and reconstructed == baseline_text
)


dockerfile_lines = [
    line.strip()
    for line in candidate_text.splitlines()
]


copy_add_lines = [
    line
    for line in dockerfile_lines
    if (
        line.startswith("COPY ")
        or line.startswith("ADD ")
    )
]


checks["DOCKERFILE_COPY_ADD_COUNT_EXACT"] = (
    len(copy_add_lines)
    == 3
)

checks["DOCKERFILE_REQUIREMENTS_COPY_EXACT_ONCE"] = (
    copy_add_lines.count(
        REQUIREMENTS_COPY
    )
    == 1
)

checks["DOCKERFILE_WORKER_COPY_EXACT_ONCE"] = (
    copy_add_lines.count(
        WORKER_COPY
    )
    == 1
)

checks["DOCKERFILE_TEMPORAL_COPY_EXACT_ONCE"] = (
    copy_add_lines.count(
        TEMPORAL_COPY
    )
    == 1
)


broad_copy_hits = [
    line
    for line in copy_add_lines
    if line in {
        "COPY worker/ /app/",
        "ADD worker/ /app/",
        "COPY . /app/",
        "ADD . /app/",
        "COPY ./ /app/",
        "ADD ./ /app/",
    }
]


wildcard_copy_hits = [
    line
    for line in copy_add_lines
    if (
        "*" in line
        or "?" in line
    )
]


remote_add_hits = [
    line
    for line in copy_add_lines
    if (
        line.startswith(
            "ADD http://"
        )
        or line.startswith(
            "ADD https://"
        )
    )
]


checks["NO_BROAD_DIRECTORY_COPY"] = (
    len(broad_copy_hits)
    == 0
)

checks["NO_WILDCARD_COPY"] = (
    len(wildcard_copy_hits)
    == 0
)

checks["NO_REMOTE_ADD"] = (
    len(remote_add_hits)
    == 0
)


details["copy_add_lines"] = (
    copy_add_lines
)


# ============================================================
# 4. COPY SOURCES
# ============================================================

copy_sources = [
    candidate_root
    / "worker"
    / "requirements-worker.txt",

    candidate_root
    / "worker"
    / "worker_service.py",

    candidate_root
    / "worker"
    / "SM3_platform_temporal_validity_v1_r2.py",
]


checks["ALL_EXPLICIT_COPY_SOURCES_EXIST"] = all(
    path.is_file()
    for path in copy_sources
)


# ============================================================
# 5. WORKER AST
#    No py_compile. No candidate writes.
# ============================================================

worker_source = (
    candidate_worker.read_text(
        encoding="utf-8-sig"
    )
)


worker_tree = ast.parse(
    worker_source,
    filename=str(
        candidate_worker
    ),
)


worker_versions = []
temporal_imports = []


for node in worker_tree.body:

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
                and target.id
                == "WORKER_VERSION"
                and isinstance(
                    node.value,
                    ast.Constant,
                )
                and isinstance(
                    node.value.value,
                    str,
                )
            ):

                worker_versions.append(
                    node.value.value
                )


    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):

        temporal_imports.append(
            node
        )


imported_symbols = []


if len(temporal_imports) == 1:

    imported_symbols = sorted(
        alias.name
        for alias in temporal_imports[0].names
    )


checks["WORKER_VERSION_SINGLE_EXACT"] = (
    worker_versions
    == ["2.35.1"]
)

checks["TEMPORAL_IMPORT_COUNT_EXACT"] = (
    len(temporal_imports)
    == 1
)

checks["TEMPORAL_IMPORT_SYMBOLS_EXACT"] = (
    imported_symbols
    == EXPECTED_TEMPORAL_IMPORTS
)


details["worker_versions"] = (
    worker_versions
)

details["temporal_import_symbols"] = (
    imported_symbols
)


# ============================================================
# 6. TEMPORAL AST
# ============================================================

temporal_source = (
    candidate_temporal.read_text(
        encoding="utf-8-sig"
    )
)


temporal_tree = ast.parse(
    temporal_source,
    filename=str(
        candidate_temporal
    ),
)


constants = {}


for node in temporal_tree.body:

    if not isinstance(
        node,
        ast.Assign,
    ):

        continue


    if not isinstance(
        node.value,
        ast.Constant,
    ):

        continue


    for target in node.targets:

        if isinstance(
            target,
            ast.Name,
        ):

            constants[
                target.id
            ] = node.value.value


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
# 7. A10 MANIFEST CONSISTENCY
# ============================================================

manifest = load_json(
    manifest_file
)

a10_report = load_json(
    a10_report_file
)


checks["MANIFEST_CONTRACT_EXACT"] = (
    manifest.get(
        "contract_version"
    )
    == "SM3_PRODUCTION_PACKAGING_CANDIDATE_V1"
)


manifest_hashes_match = (
    manifest["files"]["worker"]["sha256"]
    == worker_sha
    and
    manifest["files"]["temporal"]["sha256"]
    == temporal_sha
    and
    manifest["files"]["requirements"]["sha256"]
    == requirements_sha
    and
    manifest["files"]["dockerfile"]["sha256"]
    == dockerfile_sha
)


checks["MANIFEST_ALL_FILE_HASHES_MATCH"] = (
    manifest_hashes_match
)


checks["MANIFEST_PACKAGING_COUNTS_EXACT"] = (
    manifest["packaging"]["copy_add_count"]
    == 3
    and
    manifest["packaging"]["worker_service_copy_count"]
    == 1
    and
    manifest["packaging"]["temporal_module_copy_count"]
    == 1
    and
    manifest["packaging"]["broad_worker_directory_copy_count"]
    == 0
)


checks["A10_REPORT_MATERIALIZATION_PASS"] = (
    a10_report.get(
        "materialization_pass"
    )
    is True
)


checks["A10_REPORT_CANONICAL_HOST_UNCHANGED"] = (
    a10_report.get(
        "canonical_host_unchanged"
    )
    is True
)


checks["A10_REPORT_PRODUCTION_ISOLATION_PASS"] = (
    a10_report.get(
        "production_isolation_pass"
    )
    is True
)


# ============================================================
# 8. A11-R1 REMEDIATION CONSISTENCY
# ============================================================

r1 = load_json(
    a11_r1_report_file
)


checks["R1_REMEDIATION_PASS"] = (
    r1.get(
        "remediation_pass"
    )
    is True
)


checks["R1_CANDIDATE_FILE_COUNT_AFTER_EXACT"] = (
    r1.get(
        "candidate_file_count_after"
    )
    == 4
)


checks["R1_UNEXPECTED_FILE_COUNT_AFTER_ZERO"] = (
    r1.get(
        "unexpected_file_count_after"
    )
    == 0
)


checks["R1_COMPILED_AND_PYCACHE_AFTER_ZERO"] = (
    r1.get(
        "compiled_python_file_count_after"
    )
    == 0
    and
    r1.get(
        "pycache_entry_count_after"
    )
    == 0
)


checks["R1_CANDIDATE_CORE_UNCHANGED"] = (
    r1.get(
        "candidate_core_unchanged"
    )
    is True
)


checks["R1_CANONICAL_HOST_UNCHANGED"] = (
    r1.get(
        "canonical_host_unchanged"
    )
    is True
)


checks["R1_PRODUCTION_ISOLATION_PASS"] = (
    r1.get(
        "production_isolation_pass"
    )
    is True
)


# ============================================================
# 9. FINAL ATTACK CLASSIFICATION
# ============================================================

failures = [
    name
    for name, value in checks.items()
    if not value
]


check_count = len(
    checks
)

pass_count = (
    check_count
    - len(failures)
)


attack_pass = (
    len(failures)
    == 0
)


if attack_pass:

    classification = (
        "STATIC_REATTACK_PASS"
    )

    next_gate = (
        "09C7-B3E-A4-A12_"
        "PRODUCTION_PACKAGING_CANDIDATE_ISOLATED_BUILD"
    )

else:

    classification = (
        "STATIC_REATTACK_BLOCKED"
    )

    next_gate = (
        "09C7-B3E-A4-A11-R2_"
        "REMEDIATION_REQUIRED"
    )


report = {
    "phase":
        "09C7-B3E-A4-A11-R2",

    "contract_version":
        "SM3_PRODUCTION_PACKAGING_STATIC_REATTACK_V1",

    "classification":
        classification,

    "check_count":
        check_count,

    "pass_count":
        pass_count,

    "failure_count":
        len(failures),

    "failures":
        failures,

    "checks":
        checks,

    "details":
        details,

    "candidate_file_count":
        len(candidate_files),

    "unexpected_file_count":
        len(unexpected_files),

    "pycache_entry_count":
        len(pycache_entries),

    "compiled_python_file_count":
        len(compiled_files),

    "attack_pass":
        attack_pass,

    "candidate_writes_performed":
        False,

    "candidate_python_compile_executed":
        False,

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
    "=== A4-A11-R2 STATIC REATTACK ==="
)

print(
    "CLASSIFICATION="
    + classification
)

print(
    "CHECK_COUNT="
    + str(check_count)
)

print(
    "PASS_COUNT="
    + str(pass_count)
)

print(
    "FAILURE_COUNT="
    + str(len(failures))
)


for failure in failures:

    print(
        "FAILURE="
        + failure
    )


print(
    "CANDIDATE_FILE_COUNT="
    + str(len(candidate_files))
)

print(
    "UNEXPECTED_FILE_COUNT="
    + str(len(unexpected_files))
)

print(
    "PYCACHE_ENTRY_COUNT="
    + str(len(pycache_entries))
)

print(
    "COMPILED_PYTHON_FILE_COUNT="
    + str(len(compiled_files))
)


for item in candidate_files:

    print(
        "CANDIDATE_FILE="
        + item
    )


print(
    "DOCKERFILE_DIFF_ONLY_TEMPORAL_COPY="
    + str(
        checks[
            "DOCKERFILE_DIFF_ONLY_TEMPORAL_COPY"
        ]
    )
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
    "WORKER_VERSION_SINGLE_EXACT="
    + str(
        checks[
            "WORKER_VERSION_SINGLE_EXACT"
        ]
    )
)

print(
    "TEMPORAL_IMPORT_SYMBOLS_EXACT="
    + str(
        checks[
            "TEMPORAL_IMPORT_SYMBOLS_EXACT"
        ]
    )
)

print(
    "CANDIDATE_PYTHON_COMPILE_EXECUTED=False"
)

print(
    "CANDIDATE_WRITES_PERFORMED=False"
)

print(
    "BUILD_EXECUTED=False"
)

print(
    "ATTACK_PASS="
    + str(attack_pass)
)

print(
    "NEXT_GATE="
    + next_gate
)


if not attack_pass:
    raise SystemExit(1)