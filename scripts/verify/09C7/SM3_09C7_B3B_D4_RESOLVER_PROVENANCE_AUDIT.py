from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


TARGET_ITEM = "RI_500f8618a5796dc9b1fbded2f3bfff2e"
TARGET_ACQ = "RM_752bf6e605752cc568c4d9992a3fdcce"
SHA = "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"

LEGACY = Path(
    "/data/media/reference_sources/"
    "RP_0a468e360f9ae70383b235f10e445233/"
    "RI_500f8618a5796dc9b1fbded2f3bfff2e/"
    + SHA
    + ".mp4"
)

CAS = Path(
    "/data/media/reference_artifacts/2d/"
    + SHA
    + "/source"
)

REPORT = Path(
    "/tmp/SM3_09C7_B3B_D4_RESOLVER_PROVENANCE_AUDIT.json"
)


def test_resolve(label, value):
    row = {
        "label": label,
        "input": str(value),
        "ok": False,
        "resolved": None,
        "error": None,
    }

    try:
        result = ws._resolve_reference_inbox_ref(str(value))

        row["ok"] = True
        row["resolved"] = str(result)

    except Exception as exc:
        row["error"] = str(
            getattr(exc, "detail", exc)
        )

    return row


# ------------------------------------------------------------
# Locate exact legacy acquisition
# ------------------------------------------------------------

legacy_record = None
legacy_path = None

root = Path(
    "/data/media/production_state/reference_media"
)

for path in root.rglob("*.json"):

    try:
        rec = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        continue

    if rec.get("acquisition_id") == TARGET_ACQ:
        legacy_record = rec
        legacy_path = path
        break


if legacy_record is None:
    raise RuntimeError(
        "TARGET_LEGACY_ACQUISITION_NOT_FOUND"
    )


# ------------------------------------------------------------
# Existing V2 provenance examples for same media
# ------------------------------------------------------------

v2_examples = []

for path in root.rglob("*.json"):

    try:
        rec = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        continue

    if (
        rec.get("contract_version")
        == "SM3_REFERENCE_MEDIA_ACQUISITION_V2"
        and
        str(rec.get("source_sha256") or "").lower()
        == SHA
    ):

        v2_examples.append({
            "acquisition_id":
                rec.get("acquisition_id"),

            "reference_item_id":
                rec.get("reference_item_id"),

            "source_kind":
                rec.get("source_kind"),

            "original_filename":
                rec.get("original_filename"),

            "notes":
                rec.get("notes"),

            "media_artifact_id":
                rec.get("media_artifact_id"),
        })


# ------------------------------------------------------------
# Resolve tests
# ------------------------------------------------------------

resolver_tests = [
    test_resolve(
        "LEGACY_ABSOLUTE",
        LEGACY,
    ),

    test_resolve(
        "CAS_ABSOLUTE",
        CAS,
    ),

    test_resolve(
        "CAS_RELATIVE_TO_MEDIA_ROOT",
        "reference_artifacts/2d/"
        + SHA
        + "/source",
    ),
]


# ------------------------------------------------------------
# Source of actual resolver
# ------------------------------------------------------------

resolver_source = inspect.getsource(
    ws._resolve_reference_inbox_ref
)


report = {
    "phase":
        "09C7-B3B-D4",

    "status":
        "ACTUAL_RESOLVER_PROVENANCE_AUDIT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "legacy_acquisition_path":
        str(legacy_path),

    "legacy_acquisition":{
        "acquisition_id":
            legacy_record.get("acquisition_id"),

        "contract_version":
            legacy_record.get("contract_version"),

        "reference_item_id":
            legacy_record.get("reference_item_id"),

        "reference_profile_id":
            legacy_record.get("reference_profile_id"),

        "source_kind":
            legacy_record.get("source_kind"),

        "original_filename":
            legacy_record.get("original_filename"),

        "notes":
            legacy_record.get("notes"),

        "source_sha256":
            legacy_record.get("source_sha256"),

        "canonical_resolved_path":
            legacy_record.get("canonical_resolved_path"),
    },

    "legacy_file_exists":
        LEGACY.is_file(),

    "cas_file_exists":
        CAS.is_file(),

    "resolver_tests":
        resolver_tests,

    "resolver_source":
        resolver_source,

    "same_sha_v2_examples":
        v2_examples,

    "production_write_performed":
        False,

    "api_write_called":
        False,

    "semantic_api_called":
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


print("=== SM3 09C7-B3B-D4 RESOLVER + PROVENANCE ===")

print("WORKER_VERSION=" + str(ws.WORKER_VERSION))

print("")
print("=== LEGACY V1 ===")

for key in (
    "acquisition_id",
    "contract_version",
    "reference_item_id",
    "reference_profile_id",
    "source_kind",
    "original_filename",
    "notes",
    "source_sha256",
    "canonical_resolved_path",
):
    print(
        key.upper()
        + "="
        + str(
            report["legacy_acquisition"].get(key)
            or ""
        )
    )

print("LEGACY_FILE_EXISTS=" + str(LEGACY.is_file()))
print("CAS_FILE_EXISTS=" + str(CAS.is_file()))


print("")
print("=== ACTUAL RESOLVER SOURCE ===")
print(resolver_source)


print("")
print("=== RESOLVER TESTS ===")

for row in resolver_tests:
    print(
        row["label"]
        + "_OK="
        + str(row["ok"])
    )

    print(
        row["label"]
        + "_RESOLVED="
        + str(row["resolved"] or "")
    )

    print(
        row["label"]
        + "_ERROR="
        + str(row["error"] or "")
    )


print("")
print("=== SAME-SHA V2 PROVENANCE EXAMPLES ===")

for row in v2_examples:
    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print("")
print("PRODUCTION_WRITE_PERFORMED=False")
print("API_WRITE_CALLED=False")
print("SEMANTIC_API_CALLED=False")
print("PROVIDER_CALLED=False")
print("MODEL_CALLED=False")
print("REPORT=" + str(REPORT))

print(
    "SM3_09C7_B3B_D4_ACTUAL_RESOLVER_PROVENANCE_AUDIT_COMPLETE"
)
