from pathlib import Path
import ast
import hashlib
import re
import sys

worker = Path(
    r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py"
)

raw = worker.read_bytes()

text = raw.decode(
    "utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(worker),
)

lines = text.splitlines()

checks = []


def add(name, value):
    value = bool(value)

    checks.append(
        (name, value)
    )

    print(
        f"{name}={value}"
    )


def function_node(name):
    matches = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == name
    ]

    if len(matches) != 1:
        return None

    return matches[0]


def function_source(name):
    node = function_node(name)

    if node is None:
        return ""

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def assigned_literal(name):
    for node in tree.body:
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == name
            ):
                try:
                    return ast.literal_eval(
                        node.value
                    )
                except Exception:
                    return None

    return None


# ============================================================
# 1. SOURCE / SYNTAX
# ============================================================

add(
    "PYTHON_SYNTAX",
    True,
)

source_sha = hashlib.sha256(
    raw
).hexdigest()


# ============================================================
# 2. VERSION / CONTRACT CONSTANTS
# ============================================================

add(
    "WORKER_VERSION_2_22",
    assigned_literal(
        "WORKER_VERSION"
    ) == "2.22.0",
)

add(
    "MEDIA_ARTIFACT_CONTRACT_V1",
    assigned_literal(
        "REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION"
    )
    == "SM3_REFERENCE_MEDIA_ARTIFACT_V1",
)

add(
    "MEDIA_ARTIFACT_STORE_V1",
    assigned_literal(
        "REFERENCE_MEDIA_ARTIFACT_STORE_VERSION"
    )
    == "SM3_REFERENCE_MEDIA_CAS_V1",
)

add(
    "ACQUISITION_CURRENT_V2",
    assigned_literal(
        "REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION"
    )
    == "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
)

add(
    "ACQUIRER_CURRENT_V2",
    assigned_literal(
        "REFERENCE_MEDIA_ACQUISITION_VERSION"
    )
    == "SM3_REFERENCE_MEDIA_ACQUIRER_V2",
)

legacy_contracts = assigned_literal(
    "REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS"
)

legacy_acquirers = assigned_literal(
    "REFERENCE_MEDIA_ACQUISITION_LEGACY_ACQUIRER_VERSIONS"
)

add(
    "LEGACY_ACQUISITION_V1_READABLE",
    legacy_contracts
    == {
        "SM3_REFERENCE_MEDIA_ACQUISITION_V1"
    },
)

add(
    "LEGACY_ACQUIRER_V1_READABLE",
    legacy_acquirers
    == {
        "SM3_REFERENCE_MEDIA_ACQUIRER_V1"
    },
)


# ============================================================
# 3. STORAGE ROOTS
# ============================================================

add(
    "ARTIFACT_STATE_ROOT_PRESENT",
    'PRODUCTION_REFERENCE_MEDIA_ARTIFACTS = '
    '(PRODUCTION_STATE / "reference_media_artifacts").resolve()'
    in text,
)

add(
    "CAS_MEDIA_ROOT_PRESENT",
    'REFERENCE_MEDIA_ARTIFACTS = '
    '(MEDIA_ROOT / "reference_artifacts").resolve()'
    in text,
)

add(
    "LEGACY_SOURCE_ROOT_PRESERVED",
    'REFERENCE_MEDIA_SOURCES = '
    '(MEDIA_ROOT / "reference_sources").resolve()'
    in text,
)

startup_index = text.find(
    "for p in (MEDIA_ROOT,"
)

startup_end = text.find(
    "):",
    startup_index,
)

startup_block = ""

if (
    startup_index >= 0
    and startup_end >= 0
):
    startup_block = text[
        startup_index:
        startup_end + 2
    ]

add(
    "STARTUP_ARTIFACT_STATE_ROOT",
    "PRODUCTION_REFERENCE_MEDIA_ARTIFACTS"
    in startup_block,
)

add(
    "STARTUP_CAS_MEDIA_ROOT",
    "REFERENCE_MEDIA_ARTIFACTS"
    in startup_block,
)

add(
    "STARTUP_LEGACY_SOURCE_ROOT",
    "REFERENCE_MEDIA_SOURCES"
    in startup_block,
)


# ============================================================
# 4. REQUIRED HELPERS
# ============================================================

required_functions = (
    "_reference_media_artifact_sha",
    "_reference_media_artifact_id",
    "_reference_media_artifact_state_dir",
    "_reference_media_artifact_state_path",
    "_reference_media_artifact_blob_dir",
    "_reference_media_artifact_blob_path",
    "_verify_reference_media_artifact",
    "_load_reference_media_artifact",
    "_persist_reference_media_artifact",
    "_verify_reference_media_acquisition",
    "_resolve_reference_acquisition_source",
)

for name in required_functions:
    add(
        "FUNCTION_" + name.upper(),
        function_node(name)
        is not None,
    )


# ============================================================
# 5. CAS IDENTITY MUST BE CONTENT-CENTRIC
# ============================================================

artifact_id_src = function_source(
    "_reference_media_artifact_id"
)

add(
    "ARTIFACT_ID_SHA_ONLY",
    "'MA_'+sha"
    in artifact_id_src
    and "profile"
    not in artifact_id_src
    and "item"
    not in artifact_id_src,
)


state_dir_src = function_source(
    "_reference_media_artifact_state_dir"
)

add(
    "ARTIFACT_STATE_PATH_SHA_ONLY",
    "sha[:2]"
    in state_dir_src
    and "/ sha"
    in state_dir_src
    and "profile"
    not in state_dir_src
    and "item"
    not in state_dir_src,
)


blob_dir_src = function_source(
    "_reference_media_artifact_blob_dir"
)

add(
    "CAS_BLOB_PATH_SHA_ONLY",
    "sha[:2]"
    in blob_dir_src
    and "/ sha"
    in blob_dir_src
    and "profile"
    not in blob_dir_src
    and "item"
    not in blob_dir_src,
)


blob_path_src = function_source(
    "_reference_media_artifact_blob_path"
)

add(
    "CAS_EXTENSION_INDEPENDENT_SOURCE_NAME",
    "/ 'source'"
    in blob_path_src,
)


# ============================================================
# 6. ARTIFACT VERIFIER FAIL-CLOSED
# ============================================================

artifact_verify = function_source(
    "_verify_reference_media_artifact"
)

artifact_verify_markers = (
    "REFERENCE_MEDIA_ARTIFACT_CONTRACT_MISMATCH",
    "REFERENCE_MEDIA_ARTIFACT_STORE_VERSION_MISMATCH",
    "REFERENCE_MEDIA_ARTIFACT_ID_MISMATCH",
    "REFERENCE_MEDIA_ARTIFACT_INTEGRITY_FAILED",
    "REFERENCE_MEDIA_ARTIFACT_CAS_PATH_MISMATCH",
    "REFERENCE_MEDIA_ARTIFACT_BLOB_MISSING",
    "REFERENCE_MEDIA_ARTIFACT_BYTES_MISMATCH",
    "REFERENCE_MEDIA_ARTIFACT_BLOB_HASH_MISMATCH",
)

add(
    "ARTIFACT_VERIFIER_FAIL_CLOSED",
    all(
        marker in artifact_verify
        for marker in artifact_verify_markers
    ),
)


add(
    "ARTIFACT_HASH_VERIFIED",
    "_canonical_sha256(chk)"
    in artifact_verify,
)

add(
    "CAS_BYTES_VERIFIED",
    "blob.stat().st_size"
    in artifact_verify,
)

add(
    "CAS_SHA_VERIFIED",
    "sha256_file(blob)"
    in artifact_verify,
)


# ============================================================
# 7. ARTIFACT WRITE-ONCE / ATOMIC CAS
# ============================================================

persist_src = function_source(
    "_persist_reference_media_artifact"
)

add(
    "ARTIFACT_REUSE_BEFORE_COPY",
    "if state_path.exists():"
    in persist_src
    and "_load_reference_media_artifact("
    in persist_src,
)

add(
    "CAS_EXISTING_BLOB_VERIFIED",
    "if blob.exists():"
    in persist_src
    and "REFERENCE_MEDIA_ARTIFACT_CAS_BYTES_COLLISION"
    in persist_src
    and "REFERENCE_MEDIA_ARTIFACT_CAS_HASH_COLLISION"
    in persist_src,
)

add(
    "CAS_TEMP_COPY_VERIFIED",
    "shutil.copy2(source,tmp)"
    in persist_src
    and "REFERENCE_MEDIA_ARTIFACT_COPY_BYTES_MISMATCH"
    in persist_src
    and "REFERENCE_MEDIA_ARTIFACT_COPY_HASH_MISMATCH"
    in persist_src,
)

add(
    "CAS_FSYNC_BEFORE_REPLACE",
    "os.fsync"
    in persist_src
    and "os.replace(tmp,blob)"
    in persist_src,
)

add(
    "ARTIFACT_METADATA_WRITE_ONCE",
    "_write_revision_once("
    in persist_src,
)

add(
    "ARTIFACT_PERSISTS_RELATIVE_REF",
    "blob.relative_to(MEDIA_ROOT).as_posix()"
    in persist_src
    and "'cas_local_media_ref':cas_ref"
    in persist_src,
)

add(
    "ARTIFACT_NO_ABSOLUTE_PATH_FIELD",
    "cas_resolved_path"
    not in persist_src
    and "canonical_resolved_path"
    not in persist_src,
)


# ============================================================
# 8. DUAL V1/V2 ACQUISITION VERIFIER
# ============================================================

acq_verify = function_source(
    "_verify_reference_media_acquisition"
)

add(
    "ACQUISITION_DUAL_READER",
    "is_current"
    in acq_verify
    and "is_legacy"
    in acq_verify,
)

add(
    "LEGACY_READER_USES_CANONICAL_PATH",
    "canonical_resolved_path"
    in acq_verify
    and "REFERENCE_MEDIA_SOURCES"
    in acq_verify,
)

add(
    "V2_READER_REQUIRES_ARTIFACT_ID",
    "REFERENCE_MEDIA_ACQUISITION_ARTIFACT_ID_MISSING"
    in acq_verify
    and "_load_reference_media_artifact("
    in acq_verify,
)

add(
    "V2_ACQUISITION_ARTIFACT_CROSSCHECK",
    "REFERENCE_MEDIA_ACQUISITION_ARTIFACT_BYTES_MISMATCH"
    in acq_verify
    and "REFERENCE_MEDIA_ACQUISITION_ARTIFACT_DURATION_MISMATCH"
    in acq_verify
    and "REFERENCE_MEDIA_ACQUISITION_ARTIFACT_AUDIO_MISMATCH"
    in acq_verify,
)


# ============================================================
# 9. SOURCE RESOLVER SUPPORTS V1 + V2
# ============================================================

resolver_src = function_source(
    "_resolve_reference_acquisition_source"
)

add(
    "RESOLVER_SUPPORTS_LEGACY_V1",
    "REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS"
    in resolver_src
    and "canonical_resolved_path"
    in resolver_src,
)

add(
    "RESOLVER_SUPPORTS_V2_CAS",
    "_load_reference_media_artifact("
    in resolver_src
    and "_reference_media_artifact_blob_path("
    in resolver_src,
)


# ============================================================
# 10. V2 WRITER
# ============================================================

writer_src = function_source(
    "production_reference_media_acquire"
)

add(
    "V2_WRITER_USES_MEDIA_ARTIFACT",
    "_persist_reference_media_artifact("
    in writer_src
    and "'media_artifact_id':artifact['media_artifact_id']"
    in writer_src,
)

add(
    "V2_WRITER_CURRENT_CONTRACT",
    "'contract_version':REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION"
    in writer_src
    and "'acquirer_version':REFERENCE_MEDIA_ACQUISITION_VERSION"
    in writer_src,
)

add(
    "V2_WRITER_NO_CANONICAL_ABSOLUTE_PATH",
    "canonical_resolved_path"
    not in writer_src
    and "canonical_local_media_ref"
    not in writer_src,
)

add(
    "V2_ACQUISITION_REMAINS_ITEM_CENTRIC_EVENT",
    "'reference_item_id':req.reference_item_id"
    in writer_src
    and "'source_sha256':source_sha"
    in writer_src
    and "'acquirer_version':REFERENCE_MEDIA_ACQUISITION_VERSION"
    in writer_src,
)

add(
    "V2_WRITER_CLEANUP_ONLY_INBOX_SOURCE",
    "source.unlink()"
    in writer_src
    and "blob.unlink()"
    not in writer_src,
)


# ============================================================
# 11. ARTIFACT ROUTES
# ============================================================

add(
    "ARTIFACT_LIST_ROUTE",
    text.count(
        '@app.get("/production/reference-corpus/reference-media/artifacts")'
    ) == 1,
)

add(
    "ARTIFACT_GET_ROUTE",
    text.count(
        '@app.get("/production/reference-corpus/reference-media/artifact/{media_artifact_id}")'
    ) == 1,
)


# ============================================================
# 12. MIXED ACQUISITION LIST
# ============================================================

list_src = function_source(
    "production_reference_media_list"
)

add(
    "MEDIA_LIST_EXPOSES_LEGACY_VERSIONS",
    "legacy_contract_versions"
    in list_src
    and "REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS"
    in list_src,
)

add(
    "MEDIA_LIST_EXPOSES_ARTIFACT_CONTRACT",
    "media_artifact_contract"
    in list_src,
)


# ============================================================
# 13. MECHANICAL ANALYSIS MUST STAY MEDIA-CENTRIC
# ============================================================

mechanical_src = function_source(
    "production_reference_mechanical_analysis"
)

add(
    "MECHANICAL_USES_DUAL_SOURCE_RESOLVER",
    "_resolve_reference_acquisition_source("
    in mechanical_src,
)

add(
    "MECHANICAL_PROVENANCE_ARTIFACT_OPTIONAL",
    "'media_artifact_id':acquisition.get('media_artifact_id')"
    in mechanical_src
    and "'acquisition_contract_version':acquisition.get('contract_version')"
    in mechanical_src,
)

identity_match = re.search(
    r"analysis_id\s*=\s*'RMA_'\s*\+\s*_canonical_sha256\(\{(.*?)\}\)\[:32\]",
    mechanical_src,
    re.S,
)

identity_block = (
    identity_match.group(1)
    if identity_match
    else ""
)

add(
    "RMA_IDENTITY_SOURCE_SHA_PRESENT",
    "'source_sha256':source_sha"
    in identity_block,
)

add(
    "RMA_IDENTITY_ANALYZER_PRESENT",
    "'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION"
    in identity_block,
)

add(
    "RMA_IDENTITY_NOT_ITEM_CENTRIC",
    bool(identity_block)
    and "reference_item_id"
    not in identity_block
    and "acquisition_id"
    not in identity_block
    and "media_artifact_id"
    not in identity_block,
)


# ============================================================
# 14. HEALTH CAPABILITIES
# ============================================================

health_src = function_source(
    "health"
)

health_markers = (
    '"reference_media_acquisition_contract": REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION',
    '"reference_media_acquisition_legacy_readable": sorted(REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS)',
    '"reference_media_artifact_contract": REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION',
    '"reference_media_artifact_store_version": REFERENCE_MEDIA_ARTIFACT_STORE_VERSION',
    '"reference_media_content_addressed_storage": True',
    '"reference_media_cas_identity": "SHA256_BYTES"',
    '"reference_media_v2_absolute_path_persisted": False',
    '"reference_media_v1_legacy_sources_read_only": True',
)

add(
    "HEALTH_MEDIA_ARTIFACT_CAPABILITIES",
    all(
        marker in health_src
        for marker in health_markers
    ),
)


# ============================================================
# 15. NO SOURCE-LEVEL LEGACY MIGRATION / DELETE
# ============================================================

add(
    "NO_LEGACY_MIGRATION_FUNCTION",
    "migrate_reference_media"
    not in text.lower()
    and "delete_legacy_reference_media"
    not in text.lower(),
)


# ============================================================
# FINAL
# ============================================================

pass_count = sum(
    1
    for _, value in checks
    if value
)

check_count = len(checks)

failed = [
    name
    for name, value in checks
    if not value
]

print()
print(
    f"SOURCE_SHA256={source_sha}"
)

print()
print(
    f"PASS_COUNT={pass_count}"
)

print(
    f"CHECK_COUNT={check_count}"
)

if failed:
    print()
    print(
        "FAILED_CHECKS="
        + ",".join(failed)
    )

    print()
    print(
        "SM3_09C5_B2_MEDIA_ARTIFACT_STATIC_GATE_FAIL"
    )

    sys.exit(1)

print()
print(
    "SM3_09C5_B2_MEDIA_ARTIFACT_STATIC_GATE_PASS"
)
