from pathlib import Path
from datetime import datetime
import shutil
import os
import codecs

worker = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py")
backup_root = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\sm3_backups")

raw = worker.read_bytes()
has_bom = raw.startswith(codecs.BOM_UTF8)

if has_bom:
    text = raw[len(codecs.BOM_UTF8):].decode("utf-8")
else:
    text = raw.decode("utf-8")

NL = "\r\n" if "\r\n" in text else "\n"


def once(old, new, label):
    global text
    count = text.count(old)
    print(f"{label}_ANCHOR_COUNT={count}")

    if count != 1:
        raise SystemExit(
            f"{label}_ANCHOR_INVALID:{count}"
        )

    text = text.replace(old, new, 1)


# ============================================================
# PRECONDITIONS
# ============================================================

if 'WORKER_VERSION = "2.20.0"' not in text:
    raise SystemExit(
        "SM3_D11_EXPECTED_VERSION_2_20_0_NOT_FOUND"
    )

for forbidden in (
    "REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION",
    "ReferenceItemTombstoneRequest",
    "production_reference_item_tombstone",
    "_require_reference_item_active",
):
    if forbidden in text:
        raise SystemExit(
            f"SM3_D11_ALREADY_PATCHED:{forbidden}"
        )


# ============================================================
# 1. STORAGE ROOT
# ============================================================

anchor = (
    'PRODUCTION_REFERENCE_ITEMS = '
    '(PRODUCTION_STATE / "reference_items").resolve()'
)

replacement = (
    anchor + NL +
    'PRODUCTION_REFERENCE_ITEM_TOMBSTONES = '
    '(PRODUCTION_STATE / "reference_item_tombstones").resolve()'
)

once(
    anchor,
    replacement,
    "D11_STORAGE_ROOT"
)

once(
    "PRODUCTION_REFERENCE_ITEMS, PRODUCTION_REFERENCE_METRICS,",
    "PRODUCTION_REFERENCE_ITEMS, "
    "PRODUCTION_REFERENCE_ITEM_TOMBSTONES, "
    "PRODUCTION_REFERENCE_METRICS,",
    "D11_STARTUP_ROOT"
)


# ============================================================
# 2. VERSION + CONTRACT
# ============================================================

once(
    'WORKER_VERSION = "2.20.0"',
    'WORKER_VERSION = "2.21.0"',
    "D11_WORKER_VERSION"
)

anchor = (
    'REFERENCE_ITEM_CONTRACT_VERSION = '
    '"SM3_REFERENCE_ITEM_V1"'
)

replacement = (
    anchor + NL +
    'REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION = '
    '"SM3_REFERENCE_ITEM_TOMBSTONE_V1"'
)

once(
    anchor,
    replacement,
    "D11_CONTRACT"
)


# ============================================================
# 3. REQUEST MODEL
# ============================================================

anchor = "class ReferenceMetricSnapshotRequest(BaseModel):"

model = NL.join([
    "class ReferenceItemTombstoneRequest(BaseModel):",
    "    reason: str",
    '    scope: Literal["ACTIVE_CORPUS"] = "ACTIVE_CORPUS"',
    '    source: Literal["HUMAN", "SYSTEM", "TEST_CLEANUP"] = "HUMAN"',
    "",
    "",
])

once(
    anchor,
    model + anchor,
    "D11_REQUEST_MODEL"
)


# ============================================================
# 4. TOMBSTONE PATHS
# ============================================================

anchor = "def _reference_metric_dir(profile_id: str,item_id: str) -> Path:"

helpers = NL.join([
    "def _reference_item_tombstone_dir(profile_id: str,item_id: str) -> Path:",
    "    return _ensure_under(",
    "        PRODUCTION_REFERENCE_ITEM_TOMBSTONES",
    "        / _safe_component(profile_id)",
    "        / _safe_component(item_id),",
    "        PRODUCTION_REFERENCE_ITEM_TOMBSTONES,",
    "    )",
    "",
    "",
    "def _reference_item_tombstone_path(",
    "    profile_id: str,",
    "    item_id: str,",
    "    tombstone_id: str,",
    ") -> Path:",
    "    return _ensure_under(",
    "        _reference_item_tombstone_dir(profile_id,item_id)",
    "        / f'{_safe_component(tombstone_id)}.json',",
    "        PRODUCTION_REFERENCE_ITEM_TOMBSTONES,",
    "    )",
    "",
    "",
])

once(
    anchor,
    helpers + anchor,
    "D11_TOMBSTONE_PATHS"
)


# ============================================================
# 5. TOMBSTONE VERIFIER + EFFECTIVE STATE + ACTIVE GATE
# ============================================================

anchor = '@app.post("/production/reference-corpus/profile")'

helpers = NL.join([
    "def _verify_reference_item_tombstone(rec: dict[str,Any]) -> dict[str,Any]:",
    "    if rec.get('contract_version')!=REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_CONTRACT_INVALID'",
    "        )",
    "",
    "    expected=str(rec.get('tombstone_sha256') or '').lower()",
    "",
    "    if not re.fullmatch(r'[a-f0-9]{64}',expected):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_HASH_INVALID'",
    "        )",
    "",
    "    chk=dict(rec)",
    "    chk.pop('tombstone_sha256',None)",
    "",
    "    if _canonical_sha256(chk)!=expected:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_INTEGRITY_FAILED'",
    "        )",
    "",
    "    if rec.get('scope')!='ACTIVE_CORPUS':",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_SCOPE_INVALID'",
    "        )",
    "",
    "    if rec.get('terminal') is not True:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_NOT_TERMINAL'",
    "        )",
    "",
    "    return rec",
    "",
    "",
    "def _load_reference_item_tombstone(",
    "    item: dict[str,Any],",
    ") -> Optional[dict[str,Any]]:",
    "    profile_id=str(item.get('reference_profile_id') or '')",
    "    item_id=str(item.get('reference_item_id') or '')",
    "",
    "    d=_reference_item_tombstone_dir(profile_id,item_id)",
    "",
    "    if not d.exists():",
    "        return None",
    "",
    "    paths=sorted(d.glob('RIT_*.json'))",
    "",
    "    if not paths:",
    "        return None",
    "",
    "    if len(paths)!=1:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_MULTIPLE_TERMINAL_TOMBSTONES'",
    "        )",
    "",
    "    rec=_verify_reference_item_tombstone(",
    "        json.loads(paths[0].read_text(encoding='utf-8'))",
    "    )",
    "",
    "    if rec.get('reference_item_id')!=item_id:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_ITEM_MISMATCH'",
    "        )",
    "",
    "    if rec.get('reference_profile_id')!=profile_id:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_ITEM_TOMBSTONE_PROFILE_MISMATCH'",
    "        )",
    "",
    "    return rec",
    "",
    "",
    "def _reference_item_effective_state(",
    "    item: dict[str,Any],",
    ") -> tuple[str,Optional[dict[str,Any]]]:",
    "    tombstone=_load_reference_item_tombstone(item)",
    "",
    "    if tombstone is not None:",
    "        return 'TOMBSTONED',tombstone",
    "",
    "    return 'ACTIVE',None",
    "",
    "",
    "def _require_reference_item_active(",
    "    item_id: str,",
    ") -> dict[str,Any]:",
    "    item=_load_reference_item(item_id)",
    "    state,_=_reference_item_effective_state(item)",
    "",
    "    if state!='ACTIVE':",
    "        raise HTTPException(",
    "            409,",
    "            f'REFERENCE_ITEM_TOMBSTONED:{item_id}'",
    "        )",
    "",
    "    return item",
    "",
    "",
])

once(
    anchor,
    helpers + anchor,
    "D11_STATE_HELPERS"
)


# ============================================================
# 6. EXISTING ITEM MUST NOT BE RESURRECTED
# ============================================================

old = NL.join([
    "    if p.exists():",
    "        old=_load_reference_item(iid)",
    '        keys=["reference_profile_id","network","item_type","platform_item_id","url","caption","published_at","source","local_media_ref","notes"]',
])

new = NL.join([
    "    if p.exists():",
    "        old=_load_reference_item(iid)",
    "        state,_=_reference_item_effective_state(old)",
    "",
    "        if state!='ACTIVE':",
    "            raise HTTPException(",
    "                409,",
    "                f'REFERENCE_ITEM_TOMBSTONED:{iid}'",
    "            )",
    "",
    '        keys=["reference_profile_id","network","item_type","platform_item_id","url","caption","published_at","source","local_media_ref","notes"]',
])

once(
    old,
    new,
    "D11_NO_RESURRECTION"
)


# ============================================================
# 7. ACTIVE LIST DEFAULT + AUDIT OPTION
# ============================================================

old = NL.join([
    '@app.get("/production/reference-corpus/profile/{profile_id}/items")',
    "def production_reference_items(profile_id: str):",
    "    _load_reference_profile(profile_id)",
    "    items=[]",
    "    d=_reference_item_dir(profile_id)",
    "    if d.exists():",
    '        for p in sorted(d.glob("RI_*.json")):',
    "            items.append(_load_reference_item(p.stem))",
    '    return {"ok":True,"contract_version":REFERENCE_ITEM_CONTRACT_VERSION,"reference_profile_id":profile_id,"count":len(items),"items":items}',
])

new = NL.join([
    '@app.get("/production/reference-corpus/profile/{profile_id}/items")',
    "def production_reference_items(",
    "    profile_id: str,",
    "    include_tombstoned: bool = False,",
    "):",
    "    _load_reference_profile(profile_id)",
    "    items=[]",
    "    d=_reference_item_dir(profile_id)",
    "",
    "    if d.exists():",
    '        for p in sorted(d.glob("RI_*.json")):',
    "            item=_load_reference_item(p.stem)",
    "            state,tombstone=_reference_item_effective_state(item)",
    "",
    "            if state=='TOMBSTONED' and not include_tombstoned:",
    "                continue",
    "",
    "            items.append({",
    "                **item,",
    "                'effective_state':state,",
    "                'tombstone':tombstone,",
    "            })",
    "",
    "    return {",
    "        'ok':True,",
    "        'contract_version':REFERENCE_ITEM_CONTRACT_VERSION,",
    "        'tombstone_contract_version':REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION,",
    "        'reference_profile_id':profile_id,",
    "        'include_tombstoned':include_tombstoned,",
    "        'count':len(items),",
    "        'items':items,",
    "    }",
])

once(
    old,
    new,
    "D11_ACTIVE_LIST"
)


# ============================================================
# 8. HISTORICAL GET ENRICHED, STILL ALLOWED
# ============================================================

old = NL.join([
    '@app.get("/production/reference-corpus/item/{item_id}")',
    "def production_reference_item_get(item_id: str):",
    "    return _load_reference_item(item_id)",
])

new = NL.join([
    '@app.get("/production/reference-corpus/item/{item_id}")',
    "def production_reference_item_get(item_id: str):",
    "    item=_load_reference_item(item_id)",
    "    state,tombstone=_reference_item_effective_state(item)",
    "    return {",
    "        **item,",
    "        'effective_state':state,",
    "        'tombstone':tombstone,",
    "    }",
])

once(
    old,
    new,
    "D11_HISTORICAL_GET"
)


# ============================================================
# 9. TOMBSTONE ENDPOINT
# ============================================================

anchor = '@app.post("/production/reference-corpus/metric-snapshot")'

endpoint = NL.join([
    '@app.post("/production/reference-corpus/item/{item_id}/tombstone")',
    "def production_reference_item_tombstone(",
    "    item_id: str,",
    "    req: ReferenceItemTombstoneRequest,",
    "):",
    "    item=_load_reference_item(item_id)",
    "",
    "    reason=str(req.reason or '').strip()",
    "",
    "    if not reason:",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_ITEM_TOMBSTONE_REASON_REQUIRED'",
    "        )",
    "",
    "    if len(reason)>1000:",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_ITEM_TOMBSTONE_REASON_TOO_LONG'",
    "        )",
    "",
    "    identity={",
    "        'reference_item_id':item_id,",
    "        'scope':req.scope,",
    "        'contract_version':REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION,",
    "    }",
    "",
    "    tombstone_id='RIT_'+_canonical_sha256(identity)[:32]",
    "",
    "    path=_reference_item_tombstone_path(",
    "        item['reference_profile_id'],",
    "        item_id,",
    "        tombstone_id,",
    "    )",
    "",
    "    if path.exists():",
    "        old=_verify_reference_item_tombstone(",
    "            json.loads(path.read_text(encoding='utf-8'))",
    "        )",
    "",
    "        if (",
    "            old.get('reason')!=reason",
    "            or old.get('source')!=req.source",
    "            or old.get('scope')!=req.scope",
    "        ):",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_ITEM_TOMBSTONE_IMMUTABLE_INPUT_MISMATCH'",
    "            )",
    "",
    "        return {",
    "            'ok':True,",
    "            'reused_existing':True,",
    "            'tombstone':old,",
    "        }",
    "",
    "    rec={",
    "        'ok':True,",
    "        'tombstone_id':tombstone_id,",
    "        'contract_version':REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION,",
    "        'policy_version':REFERENCE_CORPUS_POLICY_VERSION,",
    "        'reference_item_id':item_id,",
    "        'reference_profile_id':item['reference_profile_id'],",
    "        'scope':req.scope,",
    "        'reason':reason,",
    "        'source':req.source,",
    "        'terminal':True,",
    "        'blocks_new_processing':True,",
    "        'preserves_history':True,",
    "        'preserves_media_provenance':True,",
    "        'created_at':datetime.now(timezone.utc).isoformat(),",
    "    }",
    "",
    "    rec['tombstone_sha256']=_canonical_sha256(rec)",
    "",
    "    path.parent.mkdir(parents=True,exist_ok=True)",
    "    _write_revision_once(path,rec)",
    "",
    "    persisted=_verify_reference_item_tombstone(",
    "        json.loads(path.read_text(encoding='utf-8'))",
    "    )",
    "",
    "    return {",
    "        'ok':True,",
    "        'reused_existing':False,",
    "        'tombstone':persisted,",
    "    }",
    "",
    "",
])

once(
    anchor,
    endpoint + anchor,
    "D11_ENDPOINT"
)


# ============================================================
# 10. OPERATIONAL ACTIVE GATES
# ============================================================

replacements = [
    (
        "def production_reference_metric_snapshot(req: ReferenceMetricSnapshotRequest):"
        + NL +
        "    item=_load_reference_item(req.reference_item_id)",
        "def production_reference_metric_snapshot(req: ReferenceMetricSnapshotRequest):"
        + NL +
        "    item=_require_reference_item_active(req.reference_item_id)",
        "D11_GATE_METRIC_WRITE",
    ),
    (
        "def production_reference_feature(req: ReferenceFeatureObservationRequest):"
        + NL +
        "    item=_load_reference_item(req.reference_item_id)",
        "def production_reference_feature(req: ReferenceFeatureObservationRequest):"
        + NL +
        "    item=_require_reference_item_active(req.reference_item_id)",
        "D11_GATE_FEATURE_WRITE",
    ),
    (
        "    item = _load_reference_item(item_id)"
        + NL +
        '    if item.get("item_type") not in {"REEL","VIDEO","STORY"}:',
        "    item = _require_reference_item_active(item_id)"
        + NL +
        '    if item.get("item_type") not in {"REEL","VIDEO","STORY"}:',
        "D11_GATE_MEDIA_UPLOAD",
    ),
    (
        "def production_reference_media_acquire(req: ReferenceMediaAcquireRequest):"
        + NL +
        "    item=_load_reference_item(req.reference_item_id)",
        "def production_reference_media_acquire(req: ReferenceMediaAcquireRequest):"
        + NL +
        "    item=_require_reference_item_active(req.reference_item_id)",
        "D11_GATE_MEDIA_ACQUIRE",
    ),
    (
        "def production_reference_mechanical_analysis(req: ReferenceMechanicalAnalysisRequest):"
        + NL +
        "    item=_load_reference_item(req.reference_item_id)",
        "def production_reference_mechanical_analysis(req: ReferenceMechanicalAnalysisRequest):"
        + NL +
        "    item=_require_reference_item_active(req.reference_item_id)",
        "D11_GATE_MECHANICAL",
    ),
    (
        "def production_reference_video_analysis(req: ReferenceVideoAnalysisRequest):"
        + NL +
        "    item=_load_reference_item(req.reference_item_id)",
        "def production_reference_video_analysis(req: ReferenceVideoAnalysisRequest):"
        + NL +
        "    item=_require_reference_item_active(req.reference_item_id)",
        "D11_GATE_VIDEO_ANALYSIS",
    ),
]

for old,new,label in replacements:
    once(old,new,label)


# ============================================================
# 11. DISCOVERY MUST NOT RESURRECT
# ============================================================

old = NL.join([
    "                if item_path.exists():",
    "                    reference_item = {",
    "                        **_load_reference_item(",
    "                            reference_item_id",
    "                        ),",
    '                        "reused_existing": True,',
    "                    }",
])

new = NL.join([
    "                if item_path.exists():",
    "                    existing_item=_load_reference_item(",
    "                        reference_item_id",
    "                    )",
    "                    state,tombstone=_reference_item_effective_state(",
    "                        existing_item",
    "                    )",
    "",
    "                    reference_item = {",
    "                        **existing_item,",
    "                        'effective_state':state,",
    "                        'tombstone':tombstone,",
    "                        'processing_blocked':state!='ACTIVE',",
    '                        "reused_existing": True,',
    "                    }",
])

once(
    old,
    new,
    "D11_DISCOVERY_NO_RESURRECTION"
)


# ============================================================
# 12. HARVEST MUST NOT REPROMOTE TOMBSTONED ITEM
# ============================================================

old = NL.join([
    "            if existing:",
    "                item_rec = _load_reference_item(iid)",
    "                should_promote = True",
    "            elif should_promote:",
])

new = NL.join([
    "            if existing:",
    "                item_rec=_load_reference_item(iid)",
    "                state,tombstone=_reference_item_effective_state(item_rec)",
    "",
    "                if state=='TOMBSTONED':",
    "                    should_promote=False",
    "                    cand['promotion_blocked_reason']='REFERENCE_ITEM_TOMBSTONED'",
    "                    cand['reference_item_tombstone_id']=tombstone.get('tombstone_id') if tombstone else None",
    "                    item_rec=None",
    "",
    "                if state=='ACTIVE':",
    "                    should_promote=True",
    "",
    "            elif should_promote:",
])

once(
    old,
    new,
    "D11_HARVEST_NO_REPROMOTION"
)


# ============================================================
# 13. HEALTH CAPABILITY
# ============================================================

anchor = (
    '"reference_item_contract": '
    'REFERENCE_ITEM_CONTRACT_VERSION,'
)

replacement = (
    anchor + NL +
    '        "reference_item_tombstone_contract": '
    'REFERENCE_ITEM_TOMBSTONE_CONTRACT_VERSION,' + NL +
    '        "reference_item_tombstone_active_gate": True,' + NL +
    '        "reference_item_tombstone_preserves_history": True,' + NL +
    '        "reference_item_tombstone_preserves_media_provenance": True,'
)

once(
    anchor,
    replacement,
    "D11_HEALTH"
)


# ============================================================
# 14. STATIC ARCHITECTURAL ASSERTIONS
# ============================================================

required = (
    'WORKER_VERSION = "2.21.0"',
    'SM3_REFERENCE_ITEM_TOMBSTONE_V1',
    "class ReferenceItemTombstoneRequest",
    "def _verify_reference_item_tombstone",
    "def _require_reference_item_active",
    '@app.post("/production/reference-corpus/item/{item_id}/tombstone")',
    "include_tombstoned: bool = False",
    "REFERENCE_ITEM_TOMBSTONED",
    "promotion_blocked_reason",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            f"SM3_D11_REQUIRED_MARKER_MISSING:{marker}"
        )


# Historical readers MUST still use raw loader.
historical_required = (
    "def production_reference_item_get(item_id: str):",
    "def production_reference_metric_snapshots(item_id: str):",
    "def production_reference_video_analysis_latest(item_id: str):",
    "def production_reference_features(item_id: str):",
)

for marker in historical_required:
    if marker not in text:
        raise SystemExit(
            f"SM3_D11_HISTORICAL_READER_MISSING:{marker}"
        )


# Production writers MUST use active gate.
active_gate_functions = (
    "production_reference_metric_snapshot",
    "production_reference_feature",
    "production_reference_media_upload",
    "production_reference_media_acquire",
    "production_reference_mechanical_analysis",
    "production_reference_video_analysis",
)

for fn in active_gate_functions:
    pos=text.index(f"def {fn}")
    next_def=text.find("\ndef ",pos+4)
    next_route=text.find("\n@app.",pos+4)

    candidates=[
        x for x in (next_def,next_route)
        if x!=-1
    ]

    end=min(candidates) if candidates else len(text)
    block=text[pos:end]

    if "_require_reference_item_active(" not in block:
        raise SystemExit(
            f"SM3_D11_ACTIVE_GATE_MISSING:{fn}"
        )


# Python syntax validation before replacing authoritative source.
compile(text,str(worker),"exec")


# ============================================================
# BACKUP + ATOMIC SOURCE REPLACE
# ============================================================

stamp=datetime.now().strftime("%Y%m%d_%H%M%S")

backup=(
    backup_root
    / f"worker_2_20_0_pre_tombstone_{stamp}.py"
)

backup.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(worker,backup)

encoded=text.encode("utf-8")

if has_bom:
    encoded=codecs.BOM_UTF8+encoded

tmp=worker.with_suffix(".py.09C4D11.tmp")
tmp.write_bytes(encoded)
os.replace(tmp,worker)


print()
print(f"BACKUP={backup}")
print(f"WORKER={worker}")
print("NEW_VERSION=2.21.0")
print(
    "TOMBSTONE_CONTRACT="
    "SM3_REFERENCE_ITEM_TOMBSTONE_V1"
)
print("BASE_ITEM_IMMUTABLE=True")
print("HISTORICAL_READS_PRESERVED=True")
print("NEW_PROCESSING_BLOCKED=True")
print("MEDIA_PROVENANCE_PRESERVED=True")
print("HARVEST_REPROMOTION_BLOCKED=True")
print("DISCOVERY_RESURRECTION_BLOCKED=True")
print()
print("SM3_09C4_D11_SOURCE_PATCH_PASS")
