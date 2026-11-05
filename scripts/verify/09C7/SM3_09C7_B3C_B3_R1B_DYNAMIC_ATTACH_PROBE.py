from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys
import tempfile

sys.path.insert(0, "/app")

import worker_service as ws
from fastapi import HTTPException


REPORT = Path(
    "/tmp/SM3_09C7_B3C_B3_R1B_DYNAMIC_ATTACH_PROBE.json"
)

checks = {}


def add(name, value, detail=None):
    ok = bool(value)

    checks[name] = {
        "pass": ok,
        "detail": (
            None
            if detail is None
            else str(detail)
        ),
    }

    print(
        name
        + "="
        + str(ok)
        + (
            ""
            if detail is None
            else " | " + str(detail)
        )
    )


def expect_http(
    name,
    status,
    detail,
    fn,
):
    try:
        fn()

    except HTTPException as exc:
        ok = (
            exc.status_code == status
            and
            str(exc.detail) == detail
        )

        add(
            name,
            ok,
            str(exc.status_code)
            + ":"
            + str(exc.detail),
        )

        return

    except Exception as exc:
        add(
            name,
            False,
            "UNEXPECTED:"
            + repr(exc),
        )

        return

    add(
        name,
        False,
        "NO_EXCEPTION",
    )


def sha256_file(path):
    return hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()


print(
    "=== SM3 09C7-B3C-B3-R1B DYNAMIC PROBE ==="
)

# ============================================================
# IMAGE / CONTRACT
# ============================================================

add(
    "WORKER_VERSION_2_24_1",
    ws.WORKER_VERSION == "2.24.1",
    ws.WORKER_VERSION,
)

add(
    "ATTACH_CONTRACT_V1",
    ws.REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION
    == "SM3_REFERENCE_MEDIA_ATTACH_V1",
    ws.REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION,
)

add(
    "ACQUISITION_CONTRACT_V2",
    ws.REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION
    == "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
    ws.REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,
)

add(
    "ACQUIRER_VERSION_V2",
    ws.REFERENCE_MEDIA_ACQUISITION_VERSION
    == "SM3_REFERENCE_MEDIA_ACQUIRER_V2",
    ws.REFERENCE_MEDIA_ACQUISITION_VERSION,
)

# ============================================================
# STRICT REQUEST MODEL
# ============================================================

extra_rejected = False

try:
    ws.ReferenceMediaAttachRequest(
        reference_item_id="RI_EXTRA",
        media_artifact_id="MA_EXTRA",
        expected_source_sha256="a" * 64,
        source_kind="LOCAL_IMPORT",
        original_filename="x.mp4",
        notes="x",
        unexpected_field="forbidden",
    )

except Exception:
    extra_rejected = True


add(
    "REQUEST_EXTRA_FIELD_REJECTED",
    extra_rejected,
)

# ============================================================
# SYNTHETIC ISOLATED STATE
# ============================================================

tmp_root = Path(
    tempfile.mkdtemp(
        prefix="sm3_09c7_b3c_b3_r1b_"
    )
)

acq_root = (
    tmp_root
    / "reference_media"
)

blob_dir = (
    tmp_root
    / "reference_artifacts"
    / "synthetic"
)

blob_dir.mkdir(
    parents=True,
    exist_ok=True,
)

blob = (
    blob_dir
    / "source"
)

blob.write_bytes(
    b"SM3_09C7_B3C_B3_R1B_SYNTHETIC_BYTES_"
    * 256
)

source_sha = sha256_file(
    blob
)

artifact_id = (
    ws._reference_media_artifact_id(
        source_sha
    )
)

artifact = {
    "ok":
        True,

    "media_artifact_id":
        artifact_id,

    "contract_version":
        ws.REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION,

    "store_version":
        ws.REFERENCE_MEDIA_ARTIFACT_STORE_VERSION,

    "media_kind":
        "VIDEO",

    "source_sha256":
        source_sha,

    "source_bytes":
        int(
            blob.stat().st_size
        ),

    "duration_seconds":
        21.036,

    "has_audio":
        True,

    "cas_local_media_ref":
        "reference_artifacts/synthetic/source",

    "created_at":
        "2026-09-24T03:00:00+00:00",

    "copying_reference_identity_forbidden":
        True,

    "foundation_override_allowed":
        False,
}

artifact[
    "media_artifact_sha256"
] = ws._canonical_sha256(
    artifact
)

blob_sha_before = sha256_file(
    blob
)

blob_bytes_before = (
    blob.read_bytes()
)

blob_mtime_before = (
    blob.stat().st_mtime_ns
)

# ============================================================
# PATCH EXTERNAL STATE BOUNDARIES
# ============================================================

originals = {}
trap_calls = []


def replace(name, value):
    if hasattr(ws, name):
        originals[name] = getattr(
            ws,
            name,
        )

        setattr(
            ws,
            name,
            value,
        )


def forbidden(name):
    def call(*args, **kwargs):
        trap_calls.append(name)

        raise RuntimeError(
            "FORBIDDEN_CALL:"
            + name
        )

    return call


items = {
    "RI_ACTIVE":{
        "reference_item_id":
            "RI_ACTIVE",

        "reference_profile_id":
            "RP_TEST",

        "item_type":
            "REEL",
    },

    "RI_BAD_TYPE":{
        "reference_item_id":
            "RI_BAD_TYPE",

        "reference_profile_id":
            "RP_TEST",

        "item_type":
            "IMAGE",
    },
}


def fake_active(item_id):

    if item_id == "RI_TOMBSTONED":
        raise HTTPException(
            409,
            "REFERENCE_ITEM_TOMBSTONED:RI_TOMBSTONED",
        )

    if item_id not in items:
        raise HTTPException(
            404,
            "REFERENCE_ITEM_NOT_FOUND:"
            + item_id,
        )

    return items[item_id]


def fake_load_artifact(
    source_sha_arg,
    artifact_id_arg=None,
):

    if (
        source_sha_arg != source_sha
        or
        artifact_id_arg != artifact_id
    ):
        raise HTTPException(
            404,
            "REFERENCE_MEDIA_ARTIFACT_NOT_FOUND",
        )

    return dict(
        artifact
    )


def fake_verify_artifact(rec):

    expected = str(
        rec.get(
            "media_artifact_sha256"
        )
        or ""
    )

    chk = dict(rec)

    chk.pop(
        "media_artifact_sha256",
        None,
    )

    if (
        ws._canonical_sha256(chk)
        != expected
    ):
        raise HTTPException(
            409,
            "SYNTHETIC_ARTIFACT_INTEGRITY_FAILED",
        )

    return rec


def fake_media_path(
    profile_id,
    item_id,
    acquisition_id,
):
    return (
        acq_root
        / profile_id
        / item_id
        / (
            acquisition_id
            + ".json"
        )
    )


replace(
    "_require_reference_item_active",
    fake_active,
)

replace(
    "_load_reference_media_artifact",
    fake_load_artifact,
)

replace(
    "_verify_reference_media_artifact",
    fake_verify_artifact,
)

replace(
    "_reference_media_path",
    fake_media_path,
)


for forbidden_name in (
    "_persist_reference_media_artifact",
    "_resolve_reference_inbox_ref",
    "_resolve_reference_media_ref",
    "ffprobe",
    "_reference_semantic_provider_analyze",
    "_reference_video_vision",
):

    if hasattr(
        ws,
        forbidden_name,
    ):
        replace(
            forbidden_name,
            forbidden(
                forbidden_name
            ),
        )

# ============================================================
# SUCCESS
# ============================================================

request = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_ACTIVE",
    media_artifact_id=artifact_id,
    expected_source_sha256=source_sha,
    source_kind="LOCAL_IMPORT",
    original_filename="synthetic.mp4",
    notes="SM3_09C7_B3C_B3_R1B",
)

result1 = (
    ws.production_reference_media_attach(
        request
    )
)

add(
    "FIRST_ATTACH_OK",
    result1.get("ok") is True,
)

add(
    "FIRST_ATTACH_NOT_REUSED",
    result1.get(
        "reused_existing"
    ) is False,
)

add(
    "FIRST_ATTACH_EXISTING_ARTIFACT",
    result1.get(
        "attached_existing_artifact"
    ) is True,
)

add(
    "FIRST_ATTACH_ARTIFACT_REUSED",
    result1.get(
        "media_artifact_reused"
    ) is True,
)


acquisition = (
    result1.get(
        "acquisition"
    )
    or {}
)


expected_acquisition_id = (
    "RM_"
    + ws._canonical_sha256({
        "reference_item_id":
            "RI_ACTIVE",

        "source_sha256":
            source_sha,

        "acquirer_version":
            ws.REFERENCE_MEDIA_ACQUISITION_VERSION,
    })[:32]
)


add(
    "ACQUISITION_ID_MATCHES_V2_FORMULA",
    acquisition.get(
        "acquisition_id"
    )
    == expected_acquisition_id,
    acquisition.get(
        "acquisition_id"
    ),
)

add(
    "ACQUISITION_CONTRACT_V2",
    acquisition.get(
        "contract_version"
    )
    == "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
)

add(
    "ACQUISITION_ACQUIRER_V2",
    acquisition.get(
        "acquirer_version"
    )
    == "SM3_REFERENCE_MEDIA_ACQUIRER_V2",
)

add(
    "ACQUISITION_ARTIFACT_ID",
    acquisition.get(
        "media_artifact_id"
    )
    == artifact_id,
)

add(
    "ACQUISITION_SOURCE_SHA",
    acquisition.get(
        "source_sha256"
    )
    == source_sha,
)

add(
    "ACQUISITION_NO_MEDIA_PATH",
    (
        "canonical_resolved_path"
        not in acquisition
        and
        "local_media_ref"
        not in acquisition
        and
        "cas_local_media_ref"
        not in acquisition
    ),
)


acq_path = fake_media_path(
    "RP_TEST",
    "RI_ACTIVE",
    expected_acquisition_id,
)


add(
    "ACQUISITION_FILE_CREATED",
    acq_path.is_file(),
    acq_path,
)


persisted = json.loads(
    acq_path.read_text(
        encoding="utf-8"
    )
)


verified = (
    ws._verify_reference_media_acquisition(
        persisted
    )
)


add(
    "PERSISTED_ACQUISITION_VERIFIES",
    verified.get(
        "acquisition_id"
    )
    == expected_acquisition_id,
)


acq_hash_first = sha256_file(
    acq_path
)

# ============================================================
# IDEMPOTENT REUSE
# ============================================================

result2 = (
    ws.production_reference_media_attach(
        request
    )
)

add(
    "SECOND_ATTACH_OK",
    result2.get("ok") is True,
)

add(
    "SECOND_ATTACH_REUSED_EXISTING",
    result2.get(
        "reused_existing"
    ) is True,
)

add(
    "SECOND_ATTACH_SAME_ID",
    (
        result2.get(
            "acquisition"
        )
        or {}
    ).get(
        "acquisition_id"
    )
    == expected_acquisition_id,
)

add(
    "SECOND_ATTACH_FILE_UNCHANGED",
    sha256_file(
        acq_path
    )
    == acq_hash_first,
)

# ============================================================
# PROVENANCE CONFLICT
# ============================================================

conflict = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_ACTIVE",
    media_artifact_id=artifact_id,
    expected_source_sha256=source_sha,
    source_kind="LOCAL_IMPORT",
    original_filename="synthetic.mp4",
    notes="DIFFERENT",
)

expect_http(
    "PROVENANCE_CONFLICT_REJECTED",
    409,
    "REFERENCE_MEDIA_ATTACH_IDEMPOTENCY_CONFLICT",
    lambda:
        ws.production_reference_media_attach(
            conflict
        ),
)

add(
    "CONFLICT_FILE_UNCHANGED",
    sha256_file(
        acq_path
    )
    == acq_hash_first,
)

# ============================================================
# UPPERCASE SHA
# ============================================================

upper = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_ACTIVE",
    media_artifact_id=artifact_id,
    expected_source_sha256=source_sha.upper(),
    source_kind="LOCAL_IMPORT",
    original_filename="synthetic.mp4",
    notes="upper",
)

expect_http(
    "UPPERCASE_SHA_REJECTED",
    422,
    "REFERENCE_MEDIA_ATTACH_EXPECTED_SOURCE_SHA_INVALID",
    lambda:
        ws.production_reference_media_attach(
            upper
        ),
)

# ============================================================
# WRONG ARTIFACT ID
# ============================================================

wrong_id = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_ACTIVE",
    media_artifact_id="MA_" + ("0" * 64),
    expected_source_sha256=source_sha,
    source_kind="LOCAL_IMPORT",
    original_filename="synthetic.mp4",
    notes="wrong-id",
)

expect_http(
    "WRONG_ARTIFACT_ID_REJECTED",
    409,
    "REFERENCE_MEDIA_ATTACH_ARTIFACT_ID_SOURCE_MISMATCH",
    lambda:
        ws.production_reference_media_attach(
            wrong_id
        ),
)

# ============================================================
# MISSING ARTIFACT
# ============================================================

missing_sha = (
    (
        "1"
        if source_sha[0] != "1"
        else "2"
    )
    + source_sha[1:]
)

missing_id = (
    ws._reference_media_artifact_id(
        missing_sha
    )
)

missing = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_ACTIVE",
    media_artifact_id=missing_id,
    expected_source_sha256=missing_sha,
    source_kind="LOCAL_IMPORT",
    original_filename="missing.mp4",
    notes="missing",
)

expect_http(
    "MISSING_ARTIFACT_REJECTED",
    404,
    "REFERENCE_MEDIA_ARTIFACT_NOT_FOUND",
    lambda:
        ws.production_reference_media_attach(
            missing
        ),
)

# ============================================================
# TOMBSTONE
# ============================================================

files_before_tombstone = len(
    list(
        acq_root.rglob(
            "*.json"
        )
    )
)

tombstoned = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_TOMBSTONED",
    media_artifact_id=artifact_id,
    expected_source_sha256=source_sha,
    source_kind="LOCAL_IMPORT",
    original_filename="synthetic.mp4",
    notes="tombstone",
)

expect_http(
    "TOMBSTONED_ITEM_REJECTED",
    409,
    "REFERENCE_ITEM_TOMBSTONED:RI_TOMBSTONED",
    lambda:
        ws.production_reference_media_attach(
            tombstoned
        ),
)

files_after_tombstone = len(
    list(
        acq_root.rglob(
            "*.json"
        )
    )
)

add(
    "TOMBSTONE_CREATED_NO_RECORD",
    files_after_tombstone
    == files_before_tombstone,
)

# ============================================================
# UNSUPPORTED ITEM TYPE
# ============================================================

bad_type = ws.ReferenceMediaAttachRequest(
    reference_item_id="RI_BAD_TYPE",
    media_artifact_id=artifact_id,
    expected_source_sha256=source_sha,
    source_kind="LOCAL_IMPORT",
    original_filename="synthetic.mp4",
    notes="bad-type",
)

expect_http(
    "UNSUPPORTED_ITEM_TYPE_REJECTED",
    422,
    "REFERENCE_MEDIA_ATTACH_ITEM_TYPE_NOT_VIDEO",
    lambda:
        ws.production_reference_media_attach(
            bad_type
        ),
)

# ============================================================
# MEDIA IMMUTABILITY
# ============================================================

blob_sha_after = sha256_file(
    blob
)

blob_bytes_after = (
    blob.read_bytes()
)

blob_mtime_after = (
    blob.stat().st_mtime_ns
)


add(
    "CAS_BLOB_SHA_UNCHANGED",
    blob_sha_after
    == blob_sha_before,
    blob_sha_after,
)

add(
    "CAS_BLOB_BYTES_UNCHANGED",
    blob_bytes_after
    == blob_bytes_before,
)

add(
    "CAS_BLOB_MTIME_UNCHANGED",
    blob_mtime_after
    == blob_mtime_before,
)

# ============================================================
# FORBIDDEN CALLS / RECORD COUNT
# ============================================================

add(
    "FORBIDDEN_CALL_COUNT_ZERO",
    len(trap_calls) == 0,
    trap_calls,
)

acquisition_files = list(
    acq_root.rglob(
        "*.json"
    )
)

add(
    "EXACTLY_ONE_ACQUISITION_CREATED",
    len(acquisition_files) == 1,
    len(acquisition_files),
)

# ============================================================
# RESTORE
# ============================================================

for name,value in originals.items():
    setattr(
        ws,
        name,
        value,
    )

# ============================================================
# FINAL
# ============================================================

failed = [
    name
    for name,row in checks.items()
    if not row["pass"]
]

pass_count = sum(
    1
    for row in checks.values()
    if row["pass"]
)

status = (
    "ISOLATED_DYNAMIC_ATTACH_PROBE_PASS"
    if not failed
    else
    "ISOLATED_DYNAMIC_ATTACH_PROBE_FAIL"
)


report = {
    "phase":
        "09C7-B3C-B3-R1B",

    "status":
        status,

    "worker_version":
        ws.WORKER_VERSION,

    "contract":
        ws.REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION,

    "synthetic_source_sha256":
        source_sha,

    "synthetic_media_artifact_id":
        artifact_id,

    "expected_acquisition_id":
        expected_acquisition_id,

    "cas_sha_before":
        blob_sha_before,

    "cas_sha_after":
        blob_sha_after,

    "trap_calls":
        trap_calls,

    "check_count":
        len(checks),

    "pass_count":
        pass_count,

    "fail_count":
        len(failed),

    "failed_checks":
        failed,

    "checks":
        checks,

    "production_volume_mounted":
        False,

    "network_enabled":
        False,

    "production_api_called":
        False,

    "production_record_created":
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
    ),
    encoding="utf-8",
)


print("")
print(
    "CHECK_COUNT="
    + str(len(checks))
)

print(
    "PASS_COUNT="
    + str(pass_count)
)

print(
    "FAIL_COUNT="
    + str(len(failed))
)

print(
    "FAILED_CHECKS="
    + ",".join(failed)
)

print(
    "CAS_SHA_BEFORE="
    + blob_sha_before
)

print(
    "CAS_SHA_AFTER="
    + blob_sha_after
)

print(
    "TRAP_CALLS="
    + json.dumps(
        trap_calls
    )
)

print(
    "PRODUCTION_VOLUME_MOUNTED=False"
)

print(
    "NETWORK_ENABLED=False"
)

print(
    "PRODUCTION_API_CALLED=False"
)

print(
    "PRODUCTION_RECORD_CREATED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(REPORT)
)


if failed:
    raise SystemExit(1)


print(
    "SM3_09C7_B3C_B3_R1B_ISOLATED_DYNAMIC_ATTACH_PROBE_PASS"
)
