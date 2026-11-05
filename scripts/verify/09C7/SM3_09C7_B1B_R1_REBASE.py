from pathlib import Path
import hashlib
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

BASE = (
    ROOT
    / "scripts"
    / "verify"
    / "09C7"
    / "SM3_09C7_B1B_SEMANTIC_STATIC_GATE.py"
)

OUT = (
    ROOT
    / "scripts"
    / "verify"
    / "09C7"
    / "SM3_09C7_B1B_R1_SEMANTIC_STATIC_GATE.py"
)


def fail(code):
    raise SystemExit(code)


def once(
    text,
    old,
    new,
    label,
):
    count=text.count(old)

    print(
        label
        + "_COUNT="
        + str(count)
    )

    if count!=1:
        fail(
            "SM3_09C7_B1B_R1_REBASE_ANCHOR_INVALID:"
            + label
            + ":"
            + str(count)
        )

    return text.replace(
        old,
        new,
        1,
    )


text=BASE.read_text(
    encoding="utf-8-sig"
)


# ============================================================
# 1. CURRENT AUTHORITATIVE SOURCE SHA
# ============================================================

old=r'''EXPECTED_SHA = (
    "9124c4241ada437639de165ff725c92d"
    "73ea46ed0c71969f86a7b41a4076c3c9"
)'''


new=r'''EXPECTED_SHA = (
    "8ca08d498d41cb732341c368d8aaa03e"
    "252a4c6eeef81a430201199a2e05f882"
)'''


text=once(
    text,
    old,
    new,
    "EXPECTED_SHA",
)


# ============================================================
# 2. ADD B1C REPORT TO LINEAGE
# ============================================================

old=r'''B1A = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1A_STRUCTURAL_IMPLEMENTATION.json"
)

REPORT = ('''


new=r'''B1A = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1A_STRUCTURAL_IMPLEMENTATION.json"
)

B1C = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1C_RSA_VERIFIER_HARDENING.json"
)

REPORT = ('''


text=once(
    text,
    old,
    new,
    "B1C_REPORT_PATH",
)


# ============================================================
# 3. PRESERVE OLD REPORT / CREATE R1 REPORT
# ============================================================

text=once(
    text,
    '"SM3_09C7_B1B_SEMANTIC_STATIC_GATE.json"',
    '"SM3_09C7_B1B_R1_SEMANTIC_STATIC_GATE.json"',
    "R1_REPORT_NAME",
)


# ============================================================
# 4. LOAD B1C
# ============================================================

old=r'''b1a = json.loads(
    B1A.read_text(
        encoding="utf-8-sig"
    )
)


add(
    "A2_FREEZE_STATUS_FROZEN",'''


new=r'''b1a = json.loads(
    B1A.read_text(
        encoding="utf-8-sig"
    )
)


b1c = json.loads(
    B1C.read_text(
        encoding="utf-8-sig"
    )
)


add(
    "A2_FREEZE_STATUS_FROZEN",'''


text=once(
    text,
    old,
    new,
    "LOAD_B1C",
)


# ============================================================
# 5. B1A -> B1C -> CURRENT SOURCE LINEAGE
# ============================================================

old=r'''add(
    "B1A_SOURCE_SHA_MATCH",
    b1a["source_sha_after"]
    == sha,
)


add(
    "B1A_48_OF_48",'''


new=r'''add(
    "B1A_SOURCE_IS_B1C_PARENT",
    b1a["source_sha_after"]
    == b1c["source_sha_before"],
    (
        str(b1a["source_sha_after"])
        + "->"
        + str(b1c["source_sha_before"])
    ),
)


add(
    "B1C_STATUS_VALID",
    b1c["status"]
    == "RSA_VERIFIER_HARDENED",
)


add(
    "B1C_SOURCE_SHA_MATCH_CURRENT",
    b1c["source_sha_after"]
    == sha,
    b1c["source_sha_after"],
)


add(
    "B1C_21_OF_21",
    (
        b1c["check_count"] == 21
        and
        b1c["pass_count"] == 21
        and
        b1c["fail_count"] == 0
    ),
)


add(
    "B1C_HARDENINGS_CONFIRMED",
    (
        b1c["provider_contract_verified"] is True
        and
        b1c["deterministic_identity_rebuilt"] is True
        and
        b1c["semantic_payload_actually_validated"] is True
    ),
)


add(
    "B1A_48_OF_48",'''


text=once(
    text,
    old,
    new,
    "SOURCE_LINEAGE",
)


# ============================================================
# 6. REPLACE WEAK PAYLOAD CHECK
# ============================================================

old=r'''add(
    "RSA_VERIFIER_VALIDATES_SEMANTIC_PAYLOAD",
    (
        "semantic"
        in verify_src
        and
        "REFERENCE_SEMANTIC_SCHEMA"
        in verify_src
    ),
)'''


new=r'''payload_validation_markers = (
    "schema=REFERENCE_SEMANTIC_SCHEMA",
    "REFERENCE_SEMANTIC_PAYLOAD_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_REQUIRED_FIELDS_MISSING",
    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_CONFIDENCE_INVALID",
    "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH",
)


add(
    "RSA_VERIFIER_VALIDATES_SEMANTIC_PAYLOAD",
    all(
        marker
        in verify_src
        for marker
        in payload_validation_markers
    ),
    [
        marker
        for marker
        in payload_validation_markers
        if marker
        not in verify_src
    ],
)'''


text=once(
    text,
    old,
    new,
    "STRONG_PAYLOAD_CHECK",
)


# ============================================================
# 7. IDENTIFY THIS AS R1
# ============================================================

text=text.replace(
    "09C7-B1B",
    "09C7-B1B-R1",
)


# Filename token uses underscores and is therefore not covered
# by the phase-label replacement above.


# ============================================================
# 8. PYTHON PARSE BEFORE WRITING
# ============================================================

compile(
    text,
    str(OUT),
    "exec",
)


OUT.write_text(
    text,
    encoding="utf-8",
)


out_sha=hashlib.sha256(
    OUT.read_bytes()
).hexdigest()


print(
    "SM3_09C7_B1B_R1_REBASE_PASS"
)

print(
    "R1_VERIFIER="
    + str(OUT)
)

print(
    "R1_VERIFIER_SHA256="
    + out_sha
)

sys.exit(0)
