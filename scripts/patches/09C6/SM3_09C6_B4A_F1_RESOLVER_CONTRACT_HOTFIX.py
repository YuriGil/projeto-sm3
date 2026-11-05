from pathlib import Path
from datetime import datetime
import ast
import codecs
import hashlib
import os
import re
import shutil


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = ROOT / "worker" / "worker_service.py"

BACKUPS = ROOT / "sm3_backups"

EXPECTED_BEFORE_SHA = (
    "227ecf9eefcdb020f1da6917a30d3271"
    "7d8f10d7addc2d615d044b4ef7ce39d7"
)


# ============================================================
# 1. EXACT BASELINE
# ============================================================

if not WORKER.exists():
    raise SystemExit(
        "SM3_09C6_B4A_F1_WORKER_NOT_FOUND"
    )


raw = WORKER.read_bytes()

before_sha = hashlib.sha256(
    raw
).hexdigest()


print(
    f"BEFORE_SHA256={before_sha}"
)


if before_sha != EXPECTED_BEFORE_SHA:
    raise SystemExit(
        "SM3_09C6_B4A_F1_BASELINE_SHA_MISMATCH:"
        f"{before_sha}"
    )


has_bom = raw.startswith(
    codecs.BOM_UTF8
)


if has_bom:

    text = raw[
        len(codecs.BOM_UTF8):
    ].decode("utf-8")

else:

    text = raw.decode("utf-8")


NL = (
    "\r\n"
    if "\r\n" in text
    else "\n"
)


if text.count(
    'WORKER_VERSION = "2.23.0"'
) != 1:
    raise SystemExit(
        "SM3_09C6_B4A_F1_EXPECTED_VERSION_2_23_0_NOT_FOUND"
    )


if 'WORKER_VERSION = "2.23.1"' in text:
    raise SystemExit(
        "SM3_09C6_B4A_F1_ALREADY_PATCHED"
    )


# ============================================================
# 2. PROVE RESOLVER CONTRACT BEFORE TOUCHING SOURCE
# ============================================================

resolver_start = text.index(
    "def _resolve_reference_acquisition_source("
)

resolver_end = text.index(
    "def _resolve_reference_inbox_ref(",
    resolver_start,
)

resolver_source = text[
    resolver_start:resolver_end
]

resolver_compact = "".join(
    resolver_source.split()
)


resolver_checks = {

    "LEGACY_RETURNS_PATH_AND_NONE":
        "returncanonical,None"
        in resolver_compact,

    "V2_RETURNS_BLOB_AND_ARTIFACT":
        "returnblob,artifact"
        in resolver_compact,
}


for label,value in resolver_checks.items():

    print(
        f"RESOLVER_{label}={value}"
    )


if False in resolver_checks.values():
    raise SystemExit(
        "SM3_09C6_B4A_F1_RESOLVER_CONTRACT_UNEXPECTED"
    )


# ============================================================
# 3. PROVE MECHANICAL ALREADY USES CONTRACT CORRECTLY
# ============================================================

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
)


mechanical_correct = (
    "source,media_artifact="
    "_resolve_reference_acquisition_source("
    "acquisition)"
    in mechanical_compact
)


print(
    "MECHANICAL_RESOLVER_UNPACK_CORRECT="
    f"{mechanical_correct}"
)


if not mechanical_correct:
    raise SystemExit(
        "SM3_09C6_B4A_F1_MECHANICAL_CONTRACT_UNEXPECTED"
    )


# ============================================================
# 4. LOCATE EXACT PRIORITY BUG
# ============================================================

priority_start = text.index(
    "def production_reference_priority_decision("
)

priority_end = text.index(
    '@app.get('
    + NL
    + '    "/production/reference-corpus/item/{item_id}/priority-decisions"',
    priority_start,
)

priority_source = text[
    priority_start:priority_end
]

priority_compact = "".join(
    priority_source.split()
)


bug_marker = (
    "source="
    "_resolve_reference_acquisition_source("
    "acquisition)"
)


fixed_marker = (
    "source,media_artifact="
    "_resolve_reference_acquisition_source("
    "acquisition)"
)


print(
    "PRIORITY_BUG_PRESENT="
    f"{bug_marker in priority_compact}"
)

print(
    "PRIORITY_ALREADY_FIXED="
    f"{fixed_marker in priority_compact}"
)


if bug_marker not in priority_compact:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_BUG_ANCHOR_NOT_FOUND"
    )


if fixed_marker in priority_compact:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_ALREADY_FIXED"
    )


# ============================================================
# 5. MINIMAL CONTRACT FIX
#
# Do not use tuple index magic.
# Mirror the already-approved Mechanical Analysis caller.
# ============================================================

pattern = re.compile(
    r"(?m)^"
    r"(?P<indent>[ \t]+)"
    r"source=_resolve_reference_acquisition_source\("
    r"\r?\n"
    r"(?P=indent)[ \t]+acquisition"
    r"\r?\n"
    r"(?P=indent)\)"
)


matches = list(
    pattern.finditer(
        priority_source
    )
)


print(
    "PRIORITY_BAD_CALL_MATCH_COUNT="
    f"{len(matches)}"
)


if len(matches) != 1:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_BAD_CALL_COUNT_INVALID:"
        f"{len(matches)}"
    )


priority_fixed = pattern.sub(
    lambda m: (
        m.group("indent")
        + "source,media_artifact="
        + "_resolve_reference_acquisition_source("
        + NL
        + m.group("indent")
        + "    acquisition"
        + NL
        + m.group("indent")
        + ")"
    ),
    priority_source,
    count=1,
)


text = (
    text[:priority_start]
    + priority_fixed
    + text[priority_end:]
)


# ============================================================
# 6. BUGFIX VERSION BUMP
# ============================================================

version_count = text.count(
    'WORKER_VERSION = "2.23.0"'
)


print(
    f"OLD_VERSION_COUNT={version_count}"
)


if version_count != 1:
    raise SystemExit(
        "SM3_09C6_B4A_F1_VERSION_ANCHOR_INVALID"
    )


text = text.replace(
    'WORKER_VERSION = "2.23.0"',
    'WORKER_VERSION = "2.23.1"',
    1,
)


# ============================================================
# 7. INDEPENDENT POST-PATCH STATIC CHECKS
# ============================================================

ast.parse(
    text
)

compile(
    text,
    str(WORKER),
    "exec",
)


priority_start = text.index(
    "def production_reference_priority_decision("
)

priority_end = text.index(
    '@app.get('
    + NL
    + '    "/production/reference-corpus/item/{item_id}/priority-decisions"',
    priority_start,
)

priority_after = text[
    priority_start:priority_end
]

priority_after_compact = "".join(
    priority_after.split()
)


checks = {

    "VERSION_2_23_1":
        text.count(
            'WORKER_VERSION = "2.23.1"'
        ) == 1,

    "OLD_VERSION_REMOVED":
        'WORKER_VERSION = "2.23.0"'
        not in text,

    "PRIORITY_RESOLVER_UNPACKED":
        (
            "source,media_artifact="
            "_resolve_reference_acquisition_source("
            "acquisition)"
            in priority_after_compact
        ),

    "PRIORITY_BAD_SINGLE_ASSIGN_REMOVED":
        (
            "source="
            "_resolve_reference_acquisition_source("
            "acquisition)"
            not in priority_after_compact
        ),

    "SOURCE_HASH_AFTER_RESOLUTION":
        (
            "source_sha=sha256_file(source).lower()"
            in priority_after_compact
        ),

    "MECHANICAL_UNPACK_PRESERVED":
        (
            "source,media_artifact="
            "_resolve_reference_acquisition_source("
            "acquisition)"
            in mechanical_compact
        ),

    "RESOLVER_LEGACY_CONTRACT_PRESERVED":
        (
            "returncanonical,None"
            in resolver_compact
        ),

    "RESOLVER_V2_CONTRACT_PRESERVED":
        (
            "returnblob,artifact"
            in resolver_compact
        ),

    "PRIORITY_CONTRACT_PRESERVED":
        "SM3_REFERENCE_PRIORITY_DECISION_V1"
        in text,

    "PRIORITY_ENGINE_PRESERVED":
        "SM3_REFERENCE_PRIORITY_ENGINE_V1"
        in text,

    "RMA_CONTRACT_PRESERVED":
        "SM3_REFERENCE_MECHANICAL_ANALYSIS_V1"
        in text,

    "MEDIA_ARTIFACT_PRESERVED":
        "SM3_REFERENCE_MEDIA_ARTIFACT_V1"
        in text,

    "CAS_PRESERVED":
        "SM3_REFERENCE_MEDIA_CAS_V1"
        in text,

    "VISION_GUARD_PRESERVED":
        text.count(
            "_require_reference_priority_semantic_allowed("
        ) >= 2,
}


for label,value in checks.items():

    print(
        f"{label}={value}"
    )


if False in checks.values():
    raise SystemExit(
        "SM3_09C6_B4A_F1_POST_PATCH_STATIC_CHECK_FAILED"
    )


# ============================================================
# 8. AST CONTRACT: PRIORITY MUST UNPACK EXACTLY 2 VALUES
# ============================================================

tree = ast.parse(
    text
)


priority_node = None


for node in tree.body:

    if (
        isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and
        node.name
        == "production_reference_priority_decision"
    ):

        priority_node = node

        break


if priority_node is None:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_FUNCTION_NOT_FOUND"
    )


resolver_assignments = []


for node in ast.walk(
    priority_node
):

    if not isinstance(
        node,
        ast.Assign,
    ):
        continue

    if not isinstance(
        node.value,
        ast.Call,
    ):
        continue

    if not isinstance(
        node.value.func,
        ast.Name,
    ):
        continue

    if (
        node.value.func.id
        != "_resolve_reference_acquisition_source"
    ):
        continue

    resolver_assignments.append(
        node
    )


print(
    "PRIORITY_RESOLVER_ASSIGNMENT_COUNT="
    f"{len(resolver_assignments)}"
)


if len(resolver_assignments) != 1:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_RESOLVER_ASSIGNMENT_INVALID"
    )


assignment = resolver_assignments[0]


if len(
    assignment.targets
) != 1:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_ASSIGNMENT_TARGET_INVALID"
    )


target = assignment.targets[0]


ast_unpack_valid = (
    isinstance(
        target,
        ast.Tuple,
    )
    and
    len(target.elts) == 2
    and
    all(
        isinstance(
            elt,
            ast.Name,
        )
        for elt in target.elts
    )
    and
    [
        elt.id
        for elt in target.elts
    ]
    == [
        "source",
        "media_artifact",
    ]
)


print(
    "PRIORITY_AST_TWO_VALUE_UNPACK="
    f"{ast_unpack_valid}"
)


if not ast_unpack_valid:
    raise SystemExit(
        "SM3_09C6_B4A_F1_PRIORITY_AST_UNPACK_INVALID"
    )


# ============================================================
# 9. BACKUP
# ============================================================

BACKUPS.mkdir(
    parents=True,
    exist_ok=True,
)


stamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)


backup = (
    BACKUPS
    / (
        "worker_2_23_0_pre_09C6_B4A_resolver_fix_"
        + stamp
        + ".py"
    )
)


shutil.copy2(
    WORKER,
    backup,
)


# ============================================================
# 10. ATOMIC HOST SOURCE INSTALL
# ============================================================

encoded = text.encode(
    "utf-8"
)


if has_bom:

    encoded = (
        codecs.BOM_UTF8
        + encoded
    )


tmp = WORKER.with_name(
    WORKER.name
    + ".09C6_B4A_F1.tmp"
)


tmp.write_bytes(
    encoded
)


tmp_raw = tmp.read_bytes()

tmp_text = tmp_raw


if tmp_text.startswith(
    codecs.BOM_UTF8
):

    tmp_text = tmp_text[
        len(codecs.BOM_UTF8):
    ]


compile(
    tmp_text.decode(
        "utf-8"
    ),
    str(WORKER),
    "exec",
)


os.replace(
    tmp,
    WORKER,
)


# ============================================================
# 11. READ-BACK
# ============================================================

final_raw = WORKER.read_bytes()

after_sha = hashlib.sha256(
    final_raw
).hexdigest()


final_text = WORKER.read_text(
    encoding="utf-8-sig"
)


ast.parse(
    final_text
)

compile(
    final_text,
    str(WORKER),
    "exec",
)


if after_sha == before_sha:
    raise SystemExit(
        "SM3_09C6_B4A_F1_SOURCE_UNCHANGED"
    )


if final_text.count(
    'WORKER_VERSION = "2.23.1"'
) != 1:
    raise SystemExit(
        "SM3_09C6_B4A_F1_FINAL_VERSION_INVALID"
    )


print()
print(
    f"BACKUP={backup}"
)

print(
    f"BEFORE_SHA256={before_sha}"
)

print(
    f"AFTER_SHA256={after_sha}"
)

print(
    "WORKER_VERSION=2.23.1"
)

print(
    "ROOT_CAUSE=RESOLVER_TUPLE_WAS_NOT_UNPACKED"
)

print(
    "FIX=SOURCE_AND_MEDIA_ARTIFACT_TWO_VALUE_UNPACK"
)

print(
    "RESOLVER_CONTRACT_CHANGED=False"
)

print(
    "MECHANICAL_PATH_CHANGED=False"
)

print(
    "PRIORITY_ENGINE_POLICY_CHANGED=False"
)

print(
    "PRIORITY_SCORING_CHANGED=False"
)

print(
    "VISION_POLICY_CHANGED=False"
)

print(
    "CONTAINER_DEPLOYED=False"
)

print()

print(
    "SM3_09C6_B4A_F1_RESOLVER_CONTRACT_HOTFIX_PASS"
)
