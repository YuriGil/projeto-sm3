from __future__ import annotations

from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import os
import re
import shutil


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

SOURCE = (
    ROOT
    / "worker"
    / "worker_service.py"
)

BACKUP_DIR = (
    ROOT
    / "sm3_backups"
)

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B3C_B1_IMPLEMENT_ATTACH.json"
)

EXPECTED_OLD_SHA = (
    "602775ac25d314491283c5ffaaf0a9c54ee41e4828bb4fba9732ff6ef93c8733"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str):
    raise RuntimeError(message)


raw = SOURCE.read_bytes()

old_sha = sha256_bytes(raw)

if old_sha != EXPECTED_OLD_SHA:
    fail(
        "SOURCE_SHA_PRECONDITION_FAILED:"
        + old_sha
    )


had_bom = raw.startswith(
    b"\xef\xbb\xbf"
)

text = raw.decode(
    "utf-8-sig"
)


for forbidden_existing in (
    "SM3_REFERENCE_MEDIA_ATTACH_V1",
    "ReferenceMediaAttachRequest",
    "production_reference_media_attach",
    "/production/reference-corpus/reference-media/attach",
):

    if forbidden_existing in text:
        fail(
            "ATTACH_IMPLEMENTATION_ALREADY_PRESENT:"
            + forbidden_existing
        )


# ============================================================
# 1. WORKER VERSION
# ============================================================

version_pattern = re.compile(
    r'(?m)^WORKER_VERSION\s*=\s*["\']2\.24\.0["\']\s*$'
)

text,count = version_pattern.subn(
    'WORKER_VERSION = "2.24.1"',
    text,
    count=1,
)

if count != 1:
    fail(
        "WORKER_VERSION_ANCHOR_NOT_UNIQUE"
    )


# ============================================================
# 2. CONTRACT CONSTANT
# ============================================================

constant_pattern = re.compile(
    r'(?m)^(REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION\s*=\s*["\'][^"\']+["\']\s*)$'
)

match = constant_pattern.search(
    text
)

if match is None:
    fail(
        "REFERENCE_MEDIA_ACQUISITION_CONSTANT_ANCHOR_NOT_FOUND"
    )


constant_block = (
    'REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION = '
    '"SM3_REFERENCE_MEDIA_ATTACH_V1"\n'
    + match.group(1)
)

text = (
    text[:match.start()]
    + constant_block
    + text[match.end():]
)


# ============================================================
# 3. STRICT REQUEST MODEL
# ============================================================

model_anchor = (
    "class ReferenceMediaAcquireRequest(BaseModel):"
)

model_pos = text.find(
    model_anchor
)

if model_pos < 0:
    fail(
        "REFERENCE_MEDIA_ACQUIRE_MODEL_ANCHOR_NOT_FOUND"
    )


attach_model = '''class ReferenceMediaAttachRequest(BaseModel):
    model_config = {"extra": "forbid"}

    reference_item_id: str
    media_artifact_id: str
    expected_source_sha256: str
    source_kind: Literal["LOCAL_IMPORT", "DRIVE_UPLOAD", "MANUAL_DOWNLOAD"]
    original_filename: str
    notes: str


'''


text = (
    text[:model_pos]
    + attach_model
    + text[model_pos:]
)


# ============================================================
# 4. ATTACH ENDPOINT
# ============================================================

endpoint_anchor = (
    '@app.post("/production/reference-corpus/reference-media/acquire")'
)

endpoint_pos = text.find(
    endpoint_anchor
)

if endpoint_pos < 0:
    fail(
        "REFERENCE_MEDIA_ACQUIRE_ENDPOINT_ANCHOR_NOT_FOUND"
    )


attach_endpoint = '''@app.post("/production/reference-corpus/reference-media/attach")
def production_reference_media_attach(
    req: ReferenceMediaAttachRequest,
):
    item = _require_reference_item_active(
        req.reference_item_id
    )

    if item.get("item_type") not in {
        "REEL",
        "VIDEO",
        "STORY",
    }:
        raise HTTPException(
            422,
            "REFERENCE_MEDIA_ATTACH_ITEM_TYPE_NOT_VIDEO",
        )

    expected_source_sha = str(
        req.expected_source_sha256
        or ""
    ).strip()

    if not re.fullmatch(
        r"[a-f0-9]{64}",
        expected_source_sha,
    ):
        raise HTTPException(
            422,
            "REFERENCE_MEDIA_ATTACH_EXPECTED_SOURCE_SHA_INVALID",
        )

    media_artifact_id = str(
        req.media_artifact_id
        or ""
    ).strip()

    if not media_artifact_id:
        raise HTTPException(
            422,
            "REFERENCE_MEDIA_ATTACH_ARTIFACT_ID_REQUIRED",
        )

    expected_artifact_id = (
        _reference_media_artifact_id(
            expected_source_sha
        )
    )

    if (
        media_artifact_id
        != expected_artifact_id
    ):
        raise HTTPException(
            409,
            "REFERENCE_MEDIA_ATTACH_ARTIFACT_ID_SOURCE_MISMATCH",
        )

    artifact = (
        _load_reference_media_artifact(
            expected_source_sha,
            media_artifact_id,
        )
    )

    artifact = (
        _verify_reference_media_artifact(
            artifact
        )
    )

    source_sha = str(
        artifact.get(
            "source_sha256"
        )
        or ""
    ).lower()

    if source_sha != expected_source_sha:
        raise HTTPException(
            409,
            "REFERENCE_MEDIA_ATTACH_ARTIFACT_SHA_MISMATCH",
        )

    if str(
        artifact.get(
            "media_artifact_id"
        )
        or ""
    ) != media_artifact_id:
        raise HTTPException(
            409,
            "REFERENCE_MEDIA_ATTACH_ARTIFACT_ID_MISMATCH",
        )

    original_filename = str(
        req.original_filename
        or ""
    ).strip()

    if not original_filename:
        raise HTTPException(
            422,
            "REFERENCE_MEDIA_ATTACH_ORIGINAL_FILENAME_REQUIRED",
        )

    profile_id = item[
        "reference_profile_id"
    ]

    acquisition_id = (
        "RM_"
        + _canonical_sha256({
            "reference_item_id":
                req.reference_item_id,

            "source_sha256":
                source_sha,

            "acquirer_version":
                REFERENCE_MEDIA_ACQUISITION_VERSION,
        })[:32]
    )

    path = _reference_media_path(
        profile_id,
        req.reference_item_id,
        acquisition_id,
    )

    stable = {
        "acquisition_id":
            acquisition_id,

        "contract_version":
            REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,

        "acquirer_version":
            REFERENCE_MEDIA_ACQUISITION_VERSION,

        "reference_item_id":
            req.reference_item_id,

        "reference_profile_id":
            profile_id,

        "source_kind":
            req.source_kind,

        "media_artifact_id":
            media_artifact_id,

        "source_sha256":
            source_sha,

        "source_bytes":
            artifact[
                "source_bytes"
            ],

        "duration_seconds":
            artifact[
                "duration_seconds"
            ],

        "has_audio":
            artifact[
                "has_audio"
            ],

        "original_filename":
            original_filename,

        "notes":
            str(
                req.notes
                or ""
            ),

        "copying_reference_identity_forbidden":
            True,

        "foundation_override_allowed":
            False,
    }

    if path.exists():
        old = (
            _verify_reference_media_acquisition(
                json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )
            )
        )

        for key,value in stable.items():
            if old.get(key) != value:
                raise HTTPException(
                    409,
                    "REFERENCE_MEDIA_ATTACH_IDEMPOTENCY_CONFLICT",
                )

        return {
            "ok":
                True,

            "reused_existing":
                True,

            "attached_existing_artifact":
                True,

            "media_artifact_reused":
                True,

            "media_artifact":
                artifact,

            "acquisition":
                old,
        }

    rec = {
        **stable,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    rec[
        "acquisition_sha256"
    ] = _canonical_sha256(
        rec
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _write_revision_once(
        path,
        rec,
    )

    persisted = (
        _verify_reference_media_acquisition(
            json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        )
    )

    return {
        "ok":
            True,

        "reused_existing":
            False,

        "attached_existing_artifact":
            True,

        "media_artifact_reused":
            True,

        "media_artifact":
            artifact,

        "acquisition":
            persisted,
    }


'''


text = (
    text[:endpoint_pos]
    + attach_endpoint
    + text[endpoint_pos:]
)


# ============================================================
# 5. HEALTH FLAGS
# ============================================================

health_pattern = re.compile(
    r'''(?m)^
    (?P<indent>\s*)
    ["']reference_media_content_addressed_storage["']
    \s*:\s*True,\s*
    $''',
    re.VERBOSE,
)

health_match = health_pattern.search(
    text
)

if health_match is None:
    fail(
        "HEALTH_MEDIA_CAS_ANCHOR_NOT_FOUND"
    )


indent = health_match.group(
    "indent"
)

health_block = (
    health_match.group(0)
    + "\n"
    + indent
    + '"reference_media_attach_existing_artifact": True,'
    + "\n"
    + indent
    + '"reference_media_attach_contract": REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION,'
    + "\n"
    + indent
    + '"reference_media_attach_preserves_acquisition_v2": True,'
    + "\n"
    + indent
    + '"reference_media_attach_requires_expected_sha": True,'
    + "\n"
    + indent
    + '"reference_media_attach_blob_copy": False,'
)


text = (
    text[:health_match.start()]
    + health_block
    + text[health_match.end():]
)


# ============================================================
# 6. SYNTAX / AST VALIDATION BEFORE WRITE
# ============================================================

compile(
    text,
    str(SOURCE),
    "exec",
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)


def classes_by_name(name):
    return [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and
            node.name == name
        )
    ]


def functions_by_name(name):
    return [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and
            node.name == name
        )
    ]


model_nodes = classes_by_name(
    "ReferenceMediaAttachRequest"
)

endpoint_nodes = functions_by_name(
    "production_reference_media_attach"
)


if len(model_nodes) != 1:
    fail(
        "STATIC_ATTACH_MODEL_COUNT_INVALID"
    )

if len(endpoint_nodes) != 1:
    fail(
        "STATIC_ATTACH_ENDPOINT_COUNT_INVALID"
    )


model_node = model_nodes[0]

model_fields = [
    child.target.id
    for child in model_node.body
    if (
        isinstance(
            child,
            ast.AnnAssign,
        )
        and
        isinstance(
            child.target,
            ast.Name,
        )
    )
]


expected_fields = [
    "reference_item_id",
    "media_artifact_id",
    "expected_source_sha256",
    "source_kind",
    "original_filename",
    "notes",
]


endpoint_node = endpoint_nodes[0]

endpoint_source = ast.get_source_segment(
    text,
    endpoint_node,
) or ""


call_names = set()

attribute_call_names = set()


for node in ast.walk(
    endpoint_node
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue

    fn = node.func

    if isinstance(
        fn,
        ast.Name,
    ):
        call_names.add(
            fn.id
        )

    elif isinstance(
        fn,
        ast.Attribute,
    ):
        attribute_call_names.add(
            fn.attr
        )


required_calls = {
    "_require_reference_item_active",
    "_reference_media_artifact_id",
    "_load_reference_media_artifact",
    "_verify_reference_media_artifact",
    "_canonical_sha256",
    "_reference_media_path",
    "_verify_reference_media_acquisition",
    "_write_revision_once",
}


for required in required_calls:

    if required not in call_names:
        fail(
            "STATIC_REQUIRED_CALL_MISSING:"
            + required
        )


for forbidden in (
    "_persist_reference_media_artifact",
    "_resolve_reference_inbox_ref",
    "_resolve_reference_media_ref",
    "ffprobe",
    "sha256_file",
):

    if forbidden in call_names:
        fail(
            "STATIC_FORBIDDEN_CALL_PRESENT:"
            + forbidden
        )


for forbidden_attr in (
    "unlink",
    "replace",
    "copy",
    "copy2",
    "move",
):

    if forbidden_attr in attribute_call_names:
        fail(
            "STATIC_FORBIDDEN_FILE_MUTATION_PRESENT:"
            + forbidden_attr
        )


route_matches = (
    text.count(
        '@app.post("/production/reference-corpus/reference-media/attach")'
    )
)


checks = {
    "worker_version_2_24_1":
        bool(
            re.search(
                r'(?m)^WORKER_VERSION\s*=\s*["\']2\.24\.1["\']\s*$',
                text,
            )
        ),

    "attach_contract_constant":
        (
            'REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION = "SM3_REFERENCE_MEDIA_ATTACH_V1"'
            in text
        ),

    "request_model_singleton":
        len(model_nodes) == 1,

    "request_exact_fields":
        model_fields
        == expected_fields,

    "request_extra_forbid":
        '"extra": "forbid"'
        in ast.get_source_segment(
            text,
            model_node,
        ),

    "route_singleton":
        route_matches == 1,

    "active_gate":
        "_require_reference_item_active"
        in call_names,

    "artifact_identity_check":
        "_reference_media_artifact_id"
        in call_names,

    "artifact_load":
        "_load_reference_media_artifact"
        in call_names,

    "artifact_verify":
        "_verify_reference_media_artifact"
        in call_names,

    "acquisition_v2_contract":
        "REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION"
        in endpoint_source,

    "acquisition_v2_version":
        "REFERENCE_MEDIA_ACQUISITION_VERSION"
        in endpoint_source,

    "deterministic_rm_identity":
        '"reference_item_id"'
        in endpoint_source
        and
        '"source_sha256"'
        in endpoint_source
        and
        '"acquirer_version"'
        in endpoint_source,

    "write_revision_once":
        "_write_revision_once"
        in call_names,

    "verify_persisted_acquisition":
        "_verify_reference_media_acquisition"
        in call_names,

    "response_attach_true":
        '"attached_existing_artifact"'
        in endpoint_source,

    "response_artifact_reused_true":
        '"media_artifact_reused"'
        in endpoint_source,

    "no_artifact_persist_call":
        "_persist_reference_media_artifact"
        not in call_names,

    "no_inbox_resolver":
        "_resolve_reference_inbox_ref"
        not in call_names,

    "no_ffprobe":
        "ffprobe"
        not in call_names,

    "no_unlink":
        "unlink"
        not in attribute_call_names,

    "no_copy":
        "copy"
        not in attribute_call_names
        and
        "copy2"
        not in attribute_call_names,

    "no_move":
        "move"
        not in attribute_call_names,

    "no_replace":
        "replace"
        not in attribute_call_names,

    "health_attach_enabled":
        '"reference_media_attach_existing_artifact": True'
        in text,

    "health_contract":
        '"reference_media_attach_contract": REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION'
        in text,

    "health_preserves_v2":
        '"reference_media_attach_preserves_acquisition_v2": True'
        in text,

    "health_requires_expected_sha":
        '"reference_media_attach_requires_expected_sha": True'
        in text,

    "health_blob_copy_false":
        '"reference_media_attach_blob_copy": False'
        in text,
}


failed = [
    name
    for name,value in checks.items()
    if not value
]


if failed:
    fail(
        "STATIC_VALIDATION_FAILED:"
        + ",".join(
            failed
        )
    )


# ============================================================
# 7. BACKUP + ATOMIC HOST WRITE
# ============================================================

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

stamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    BACKUP_DIR
    / (
        "worker_2_24_0_pre_09C7_B3C_B1_"
        + stamp
        + ".py"
    )
)

shutil.copy2(
    SOURCE,
    backup,
)


new_bytes = text.encode(
    "utf-8"
)

if had_bom:
    new_bytes = (
        b"\xef\xbb\xbf"
        + new_bytes
    )


tmp = SOURCE.with_name(
    SOURCE.name
    + ".09C7_B3C_B1.tmp"
)

tmp.write_bytes(
    new_bytes
)

os.replace(
    tmp,
    SOURCE,
)


persisted = SOURCE.read_bytes()

new_sha = sha256_bytes(
    persisted
)


if new_sha == old_sha:
    fail(
        "SOURCE_SHA_DID_NOT_CHANGE"
    )


# ============================================================
# 8. FINAL REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3C-B1",

    "status":
        "HOST_ONLY_IMPLEMENTATION_PASS",

    "worker_version_before":
        "2.24.0",

    "worker_version_after":
        "2.24.1",

    "source_sha256_before":
        old_sha,

    "source_sha256_after":
        new_sha,

    "backup":
        str(backup),

    "contract":
        "SM3_REFERENCE_MEDIA_ATTACH_V1",

    "endpoint":
        "POST /production/reference-corpus/reference-media/attach",

    "output_acquisition_contract":
        "SM3_REFERENCE_MEDIA_ACQUISITION_V2",

    "request_fields":
        expected_fields,

    "check_count":
        len(checks),

    "pass_count":
        sum(
            1
            for value in checks.values()
            if value
        ),

    "fail_count":
        len(failed),

    "failed_checks":
        failed,

    "checks":
        checks,

    "build_executed":
        False,

    "runtime_restarted":
        False,

    "api_write_called":
        False,

    "production_state_modified":
        False,

    "model_called":
        False,
}


REPORT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== SM3 09C7-B3C-B1 HOST PATCH ==="
)

print(
    "BACKUP="
    + str(backup)
)

print(
    "SOURCE_SHA_BEFORE="
    + old_sha
)

print(
    "SOURCE_SHA_AFTER="
    + new_sha
)

print(
    "WORKER_VERSION_AFTER=2.24.1"
)

print(
    "CONTRACT=SM3_REFERENCE_MEDIA_ATTACH_V1"
)

print(
    "ENDPOINT=POST /production/reference-corpus/reference-media/attach"
)

print(
    "STATIC_CHECK_COUNT="
    + str(len(checks))
)

print(
    "STATIC_PASS_COUNT="
    + str(
        sum(
            1
            for value in checks.values()
            if value
        )
    )
)

print(
    "STATIC_FAIL_COUNT="
    + str(len(failed))
)

print(
    "BUILD_EXECUTED=False"
)

print(
    "RUNTIME_RESTARTED=False"
)

print(
    "API_WRITE_CALLED=False"
)

print(
    "PRODUCTION_STATE_MODIFIED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(REPORT)
)

print(
    "SM3_09C7_B3C_B1_HOST_IMPLEMENTATION_PASS"
)
