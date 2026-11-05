from pathlib import Path
import hashlib
import shutil


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

GATE = (
    ROOT
    / "scripts"
    / "verify"
    / "09C6"
    / "SM3_09C6_B2_PRIORITY_STATIC_GATE.py"
)

EXPECTED_WORKER_SHA = (
    "227ecf9eefcdb020f1da6917a30d3271"
    "7d8f10d7addc2d615d044b4ef7ce39d7"
)


if not GATE.exists():
    raise SystemExit(
        "SM3_09C6_B2R_GATE_NOT_FOUND"
    )


text = GATE.read_text(
    encoding="utf-8-sig"
)


# ============================================================
# A. UPDATE EXPECTED WORKER SHA
# ============================================================

old_sha = '''EXPECTED_SHA = (
    "c759258bbfd3d86bc66d8810f2528056"
    "24fb0ed8a9b9b5c7f93c06e5bc086512"
)'''

new_sha = '''EXPECTED_SHA = (
    "227ecf9eefcdb020f1da6917a30d3271"
    "7d8f10d7addc2d615d044b4ef7ce39d7"
)'''


sha_count = text.count(
    old_sha
)

print(
    f"OLD_EXPECTED_SHA_COUNT={sha_count}"
)

if sha_count != 1:
    raise SystemExit(
        "SM3_09C6_B2R_SHA_ANCHOR_INVALID:"
        f"{sha_count}"
    )


text = text.replace(
    old_sha,
    new_sha,
    1,
)


# ============================================================
# B. FIX HUMAN PRIORITY FALSE NEGATIVE
#
# compact() intentionally normalizes double quotes to single.
# The previous assertion searched for the pre-normalized form.
# ============================================================

old_human = '''check(
    "HUMAN_PRIORITY_FROM_PROFILE",
    (
        "_load_reference_profile("
        in evidence_src
        and
        'profile.get("human_priority",50)'
        in compact(evidence_src)
    ),
)'''


new_human = '''check(
    "HUMAN_PRIORITY_FROM_PROFILE",
    (
        "_load_reference_profile("
        in evidence_src
        and
        "profile.get('human_priority',50)"
        in compact(evidence_src)
    ),
)'''


human_count = text.count(
    old_human
)

print(
    f"OLD_HUMAN_CHECK_COUNT={human_count}"
)

if human_count != 1:
    raise SystemExit(
        "SM3_09C6_B2R_HUMAN_CHECK_ANCHOR_INVALID:"
        f"{human_count}"
    )


text = text.replace(
    old_human,
    new_human,
    1,
)


# ============================================================
# C. VERIFY THE GATE SCRIPT ITSELF BEFORE REPLACING
# ============================================================

compile(
    text,
    str(GATE),
    "exec",
)


if EXPECTED_WORKER_SHA not in text.replace(
    '"\n    "',
    "",
):
    # Not relied upon as the main check; explicit fragments below
    # are authoritative.
    pass


for marker in (
    "227ecf9eefcdb020f1da6917a30d3271",
    "7d8f10d7addc2d615d044b4ef7ce39d7",
    "profile.get('human_priority',50)",
    "MECHANICAL_CONTACT_SHEET_PHYSICALLY_VERIFIED",
    "VERIFIER_RECOMPUTES_DECISION_IDENTITY",
    "VERIFIER_RECOMPUTES_EVIDENCE_FINGERPRINT",
    "VERIFIER_RECOMPUTES_PRIORITY_SCORE",
):
    if marker not in text:
        raise SystemExit(
            "SM3_09C6_B2R_REQUIRED_MARKER_MISSING:"
            f"{marker}"
        )


# ============================================================
# D. BACKUP VERIFIER ONLY
# ============================================================

backup = GATE.with_name(
    "SM3_09C6_B2_PRIORITY_STATIC_GATE_pre_B2R.py"
)

shutil.copy2(
    GATE,
    backup,
)


# ============================================================
# E. PERSIST UPDATED VERIFIER
# ============================================================

GATE.write_text(
    text,
    encoding="utf-8",
)


persisted = GATE.read_text(
    encoding="utf-8"
)

compile(
    persisted,
    str(GATE),
    "exec",
)


print(
    "GATE_SHA256="
    + hashlib.sha256(
        GATE.read_bytes()
    ).hexdigest()
)

print(
    f"GATE_BACKUP={backup}"
)

print(
    "WORKER_MODIFIED=False"
)

print(
    "SM3_09C6_B2R_GATE_REBASE_PASS"
)
