from pathlib import Path
import hashlib

ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = ROOT / "worker" / "worker_service.py"

PATCHER = (
    ROOT
    / "scripts"
    / "patches"
    / "09C6"
    / "SM3_09C6_B1_PRIORITY_GATE_V1_PATCH.py"
)

EXPECTED_WORKER_SHA = (
    "6e699119f41fccabd9475b8fb833c22f"
    "53036005920a1fa5d6f93520bd7ae575"
)


# ============================================================
# 1. PROVE HOST WORKER WAS NOT MODIFIED
# ============================================================

if not WORKER.exists():
    raise SystemExit(
        "SM3_09C6_B1F_WORKER_NOT_FOUND"
    )

worker_raw = WORKER.read_bytes()

worker_sha = hashlib.sha256(
    worker_raw
).hexdigest()

print(f"WORKER_SHA256={worker_sha}")

if worker_sha != EXPECTED_WORKER_SHA:
    raise SystemExit(
        "SM3_09C6_B1F_WORKER_WAS_MODIFIED:"
        f"{worker_sha}"
    )


worker_text = WORKER.read_text(
    encoding="utf-8-sig"
)

if worker_text.count(
    'WORKER_VERSION = "2.22.0"'
) != 1:
    raise SystemExit(
        "SM3_09C6_B1F_EXPECTED_WORKER_2_22_0_NOT_FOUND"
    )

print("WORKER_BASELINE_UNCHANGED=True")


# ============================================================
# 2. LOAD PATCHER
# ============================================================

if not PATCHER.exists():
    raise SystemExit(
        "SM3_09C6_B1F_PATCHER_NOT_FOUND"
    )

text = PATCHER.read_text(
    encoding="utf-8-sig"
)


old = '''# Mechanical identity must remain media-centric.
mechanical_identity_marker = (
    '"source_sha256":source_sha,'
    '"analyzer_version":REFERENCE_MECHANICAL_ANALYZER_VERSION'
)

if mechanical_identity_marker not in text:
    raise SystemExit(
        "SM3_09C6_B1_RMA_IDENTITY_CHANGED"
    )
'''


new = '''# Mechanical identity must remain media-centric.
#
# Normalize whitespace and quote style before checking because
# the canonical RMA identity is intentionally formatted across
# multiple source lines.
mechanical_start = text.index(
    "def production_reference_mechanical_analysis("
)

mechanical_end = text.index(
    '@app.post("/production/reference-corpus/video-analysis")',
    mechanical_start,
)

mechanical_source = text[
    mechanical_start:mechanical_end
]

mechanical_compact = "".join(
    mechanical_source.split()
).replace('"', "'")

mechanical_identity_marker = (
    "analysis_id='RMA_'+_canonical_sha256({"
    "'source_sha256':source_sha,"
    "'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION,"
    "})[:32]"
)

print(
    "RMA_MEDIA_CENTRIC_IDENTITY_PRESENT="
    f"{mechanical_identity_marker in mechanical_compact}"
)

if mechanical_identity_marker not in mechanical_compact:
    raise SystemExit(
        "SM3_09C6_B1_RMA_IDENTITY_CHANGED"
    )
'''


count = text.count(old)

print(
    "OLD_RMA_ASSERTION_COUNT="
    f"{count}"
)

if count != 1:
    raise SystemExit(
        "SM3_09C6_B1F_OLD_ASSERTION_INVALID:"
        f"{count}"
    )


text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# 3. VERIFY PATCHER ITSELF
# ============================================================

compile(
    text,
    str(PATCHER),
    "exec",
)

if (
    "RMA_MEDIA_CENTRIC_IDENTITY_PRESENT="
    not in text
):
    raise SystemExit(
        "SM3_09C6_B1F_NEW_ASSERTION_MISSING"
    )


PATCHER.write_text(
    text,
    encoding="utf-8",
)


# Re-read exact persisted patcher.
persisted = PATCHER.read_text(
    encoding="utf-8"
)

compile(
    persisted,
    str(PATCHER),
    "exec",
)


print(
    "PATCHER_SHA256="
    + hashlib.sha256(
        PATCHER.read_bytes()
    ).hexdigest()
)

print(
    "SM3_09C6_B1F_PATCHER_FIX_PASS"
)
