from pathlib import Path
import ast
import hashlib
import sys

worker = Path(
    r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py"
)

text = worker.read_text(encoding="utf-8-sig")


def result(name, value):
    print(f"{name}={bool(value)}")
    return bool(value)


checks = []


# ============================================================
# 1. PYTHON / VERSION / CONTRACT
# ============================================================

try:
    ast.parse(text)
    checks.append(result("PYTHON_SYNTAX", True))
except Exception as exc:
    print(f"PYTHON_SYNTAX_ERROR={exc}")
    checks.append(result("PYTHON_SYNTAX", False))


checks.append(
    result(
        "VERSION_2_21_COUNT1",
        text.count('WORKER_VERSION = "2.21.0"') == 1
    )
)

checks.append(
    result(
        "TOMBSTONE_CONTRACT_COUNT1",
        text.count(
            'REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION = '
            '"SM3_REFERENCE_ITEM_TOMBSTONE_V1"'
        ) == 1
    )
)

checks.append(
    result(
        "TOMBSTONE_ROOT_COUNT",
        text.count("PRODUCTION_REFERENCE_ITEM_TOMBSTONES") >= 5
    )
)


# ============================================================
# 2. MODELS / HELPERS / ROUTE EXACTLY ONCE
# ============================================================

markers = {
    "REQUEST_MODEL_COUNT1":
        "class ReferenceItemTombstoneRequest(BaseModel):",

    "VERIFY_FUNCTION_COUNT1":
        "def _verify_reference_item_tombstone(",

    "LOAD_TOMBSTONE_COUNT1":
        "def _load_reference_item_tombstone(",

    "EFFECTIVE_STATE_COUNT1":
        "def _reference_item_effective_state(",

    "ACTIVE_GATE_COUNT1":
        "def _require_reference_item_active(",

    "TOMBSTONE_ROUTE_COUNT1":
        '@app.post("/production/reference-corpus/item/{item_id}/tombstone")',

    "TOMBSTONE_FUNCTION_COUNT1":
        "def production_reference_item_tombstone(",
}

for name, marker in markers.items():
    checks.append(
        result(name, text.count(marker) == 1)
    )


# ============================================================
# 3. EXTRACT FUNCTION BLOCKS
# ============================================================

tree = ast.parse(text)

functions = {
    node.name: node
    for node in tree.body
    if isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef)
    )
}


def source_block(name):
    node = functions.get(name)

    if node is None:
        return ""

    return ast.get_source_segment(text, node) or ""


# ============================================================
# 4. HISTORICAL READS MUST REMAIN RAW / AUDITABLE
# ============================================================

historical = {
    "HISTORICAL_ITEM_GET_RAW":
        "production_reference_item_get",

    "HISTORICAL_METRICS_READ_RAW":
        "production_reference_metric_snapshots",

    "HISTORICAL_FEATURES_READ_RAW":
        "production_reference_features",

    "HISTORICAL_VIDEO_READ_RAW":
        "production_reference_video_analysis_latest",

    "HISTORICAL_MEDIA_READ_RAW":
        "production_reference_media_latest",
}

for check_name, fn in historical.items():
    block = source_block(fn)

    checks.append(
        result(
            check_name,
            "_load_reference_item(" in block
            or fn == "production_reference_media_latest"
        )
    )


# Item GET must expose effective state rather than hide history.
item_get = source_block(
    "production_reference_item_get"
)

checks.append(
    result(
        "ITEM_GET_EXPOSES_EFFECTIVE_STATE",
        "_reference_item_effective_state(" in item_get
        and "'effective_state':state" in item_get
        and "'tombstone':tombstone" in item_get
    )
)


# ============================================================
# 5. ALL NEW-PRODUCTION WRITERS MUST REQUIRE ACTIVE ITEM
# ============================================================

writers = {
    "GATE_METRIC_WRITE":
        "production_reference_metric_snapshot",

    "GATE_FEATURE_WRITE":
        "production_reference_feature",

    "GATE_MEDIA_UPLOAD":
        "production_reference_media_upload",

    "GATE_MEDIA_ACQUIRE":
        "production_reference_media_acquire",

    "GATE_MECHANICAL":
        "production_reference_mechanical_analysis",

    "GATE_VIDEO_ANALYSIS":
        "production_reference_video_analysis",
}

for check_name, fn in writers.items():
    block = source_block(fn)

    checks.append(
        result(
            check_name,
            "_require_reference_item_active(" in block
        )
    )


# ============================================================
# 6. ACTIVE GATE MUST FAIL CLOSED
# ============================================================

active_gate = source_block(
    "_require_reference_item_active"
)

checks.append(
    result(
        "ACTIVE_GATE_FAILS_CLOSED",
        "_reference_item_effective_state(" in active_gate
        and "state!='ACTIVE'" in active_gate
        and "REFERENCE_ITEM_TOMBSTONED" in active_gate
        and "HTTPException(" in active_gate
    )
)


# ============================================================
# 7. TOMBSTONE ITSELF MUST BE IMMUTABLE + HASHED + TERMINAL
# ============================================================

verify = source_block(
    "_verify_reference_item_tombstone"
)

endpoint = source_block(
    "production_reference_item_tombstone"
)

checks.append(
    result(
        "TOMBSTONE_HASH_VERIFICATION",
        "tombstone_sha256" in verify
        and "_canonical_sha256(chk)" in verify
        and "REFERENCE_ITEM_TOMBSTONE_INTEGRITY_FAILED"
        in verify
    )
)

checks.append(
    result(
        "TOMBSTONE_TERMINAL_GUARD",
        "rec.get('terminal') is not True" in verify
        and "REFERENCE_ITEM_TOMBSTONE_NOT_TERMINAL"
        in verify
    )
)

checks.append(
    result(
        "TOMBSTONE_APPEND_ONLY_WRITE",
        "_write_revision_once(path,rec)" in endpoint
        and "_replace_current_durably" not in endpoint
    )
)

checks.append(
    result(
        "TOMBSTONE_PRESERVES_HISTORY",
        "'preserves_history':True" in endpoint
        and "'preserves_media_provenance':True"
        in endpoint
        and "'blocks_new_processing':True"
        in endpoint
    )
)


# ============================================================
# 8. ORIGINAL REFERENCE ITEM MUST REMAIN IMMUTABLE
# ============================================================

create_item = source_block(
    "production_reference_item"
)

checks.append(
    result(
        "BASE_ITEM_STILL_WRITE_ONCE",
        "_write_revision_once(p,stable)" in create_item
        and "_replace_current_durably" not in create_item
    )
)

checks.append(
    result(
        "BASE_ITEM_NO_RESURRECTION",
        "_reference_item_effective_state(old)"
        in create_item
        and "REFERENCE_ITEM_TOMBSTONED"
        in create_item
    )
)


# ============================================================
# 9. ACTIVE LIST DEFAULT / AUDITABLE INCLUDE
# ============================================================

items_list = source_block(
    "production_reference_items"
)

checks.append(
    result(
        "ACTIVE_LIST_DEFAULT_FILTER",
        "include_tombstoned: bool = False"
        in items_list
        and "state=='TOMBSTONED'"
        in items_list
        and "continue" in items_list
    )
)

checks.append(
    result(
        "ACTIVE_LIST_AUDIT_MODE",
        "'effective_state':state" in items_list
        and "'tombstone':tombstone"
        in items_list
        and "'include_tombstoned':include_tombstoned"
        in items_list
    )
)


# ============================================================
# 10. DISCOVERY MUST NOT RESURRECT
# ============================================================

discovery_ok = (
    "processing_blocked" in text
    and "state!='ACTIVE'" in text
    and text.count(
        "_reference_item_effective_state("
    ) >= 4
)

checks.append(
    result(
        "DISCOVERY_NO_RESURRECTION",
        discovery_ok
    )
)


# ============================================================
# 11. HARVEST MUST NOT REPROMOTE TOMBSTONED ITEMS
# ============================================================

harvest_ok = (
    "promotion_blocked_reason" in text
    and "'REFERENCE_ITEM_TOMBSTONED'"
    in text
    and "should_promote=False" in text
    and "item_rec=None" in text
)

checks.append(
    result(
        "HARVEST_NO_REPROMOTION",
        harvest_ok
    )
)


# ============================================================
# 12. RMA MUST REMAIN MEDIA-CENTRIC AND UNCHANGED
# ============================================================

mechanical = source_block(
    "production_reference_mechanical_analysis"
)

checks.append(
    result(
        "RMA_IDENTITY_STILL_MEDIA_CENTRIC",
        "'source_sha256':source_sha" in mechanical
        and "'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION"
        in mechanical
        and "'reference_item_id':req.reference_item_id"
        not in mechanical[
            mechanical.find("analysis_id="):
            mechanical.find("path=_reference_mechanical_analysis_path")
        ]
    )
)

checks.append(
    result(
        "MECHANICAL_REUSE_BEFORE_REPROCESS",
        "if path.exists():" in mechanical
        and "'reused_existing':True" in mechanical
        and mechanical.find("if path.exists():")
            < mechanical.find("make_contact_sheet(")
    )
)


# ============================================================
# 13. NO DESTRUCTIVE MEDIA CLEANUP INTRODUCED
# ============================================================

tombstone_section_ok = (
    ".unlink(" not in endpoint
    and "shutil.rmtree" not in endpoint
    and "os.remove(" not in endpoint
)

checks.append(
    result(
        "TOMBSTONE_NON_DESTRUCTIVE",
        tombstone_section_ok
    )
)


# ============================================================
# 14. HEALTH EXPOSURE
# ============================================================

checks.append(
    result(
        "HEALTH_TOMBSTONE_CONTRACT",
        '"reference_item_tombstone_contract": '
        "REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION"
        in text
    )
)

checks.append(
    result(
        "HEALTH_ACTIVE_GATE",
        '"reference_item_tombstone_active_gate": True'
        in text
    )
)

checks.append(
    result(
        "HEALTH_HISTORY_PRESERVED",
        '"reference_item_tombstone_preserves_history": True'
        in text
    )
)

checks.append(
    result(
        "HEALTH_MEDIA_PROVENANCE_PRESERVED",
        '"reference_item_tombstone_preserves_media_provenance": True'
        in text
    )
)


# ============================================================
# 15. SOURCE HASH
# ============================================================

sha = hashlib.sha256(worker.read_bytes()).hexdigest()

print()
print(f"SOURCE_SHA256={sha}")

print()
print(
    f"PASS_COUNT={sum(1 for x in checks if x)}"
)
print(
    f"CHECK_COUNT={len(checks)}"
)


# ============================================================
# FINAL
# ============================================================

if all(checks):
    print()
    print(
        "SM3_09C4_D12_TOMBSTONE_STATIC_GATE_PASS"
    )
    sys.exit(0)

print()
print(
    "SM3_09C4_D12_TOMBSTONE_STATIC_GATE_FAIL"
)

failed = [
    i + 1
    for i, ok in enumerate(checks)
    if not ok
]

print(
    "FAILED_CHECK_INDEXES="
    + ",".join(map(str,failed))
)

sys.exit(1)
