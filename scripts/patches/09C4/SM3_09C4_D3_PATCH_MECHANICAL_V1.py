from pathlib import Path
from datetime import datetime
import shutil
import os
import codecs

worker = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py")
backup_root = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\sm3_backups")

if not worker.exists():
    raise SystemExit("SM3_D3_WORKER_NOT_FOUND")

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
        raise SystemExit(f"{label}_ANCHOR_INVALID:{count}")
    text = text.replace(old, new, 1)

# ---------------------------------------------------------
# PRECONDITIONS
# ---------------------------------------------------------

if 'WORKER_VERSION = "2.19.0"' not in text:
    raise SystemExit("SM3_D3_EXPECTED_VERSION_2_19_0_NOT_FOUND")

for forbidden in (
    "REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_VERSION",
    "ReferenceMechanicalAnalysisRequest",
    "production_reference_mechanical_analysis",
):
    if forbidden in text:
        raise SystemExit(f"SM3_D3_ALREADY_PATCHED:{forbidden}")

# ---------------------------------------------------------
# 1. STORAGE ROOT
# ---------------------------------------------------------

anchor = (
    'PRODUCTION_REFERENCE_VIDEO_ANALYSES = '
    '(PRODUCTION_STATE / "reference_video_analyses").resolve()'
)

replacement = (
    anchor + NL +
    'PRODUCTION_REFERENCE_MECHANICAL_ANALYSES = '
    '(PRODUCTION_STATE / "reference_mechanical_analyses").resolve()'
)

once(
    anchor,
    replacement,
    "D3_STORAGE_ROOT"
)

# Ensure startup creates the directory.
once(
    "PRODUCTION_REFERENCE_VIDEO_ANALYSES, PRODUCTION_REFERENCE_MEDIA,",
    "PRODUCTION_REFERENCE_VIDEO_ANALYSES, "
    "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES, "
    "PRODUCTION_REFERENCE_MEDIA,",
    "D3_STARTUP_DIR"
)

# ---------------------------------------------------------
# 2. VERSION + CONTRACTS
# ---------------------------------------------------------

once(
    'WORKER_VERSION = "2.19.0"',
    'WORKER_VERSION = "2.20.0"',
    "D3_WORKER_VERSION"
)

anchor = (
    'REFERENCE_VIDEO_ANALYZER_VERSION = '
    '"SM3_REFERENCE_VIDEO_ANALYZER_V1"'
)

replacement = (
    anchor + NL +
    'REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_VERSION = '
    '"SM3_REFERENCE_MECHANICAL_ANALYSIS_V1"' + NL +
    'REFERENCE_MECHANICAL_ANALYZER_VERSION = '
    '"SM3_REFERENCE_MECHANICAL_ANALYZER_V1"'
)

once(
    anchor,
    replacement,
    "D3_CONTRACTS"
)

# ---------------------------------------------------------
# 3. REQUEST MODEL
# ---------------------------------------------------------

anchor = "class ReferenceVideoAnalysisRequest(BaseModel):"

model = NL.join([
    "class ReferenceMechanicalAnalysisRequest(BaseModel):",
    "    reference_item_id: str",
    "    acquisition_id: Optional[str] = None",
    "    use_latest_acquisition: bool = True",
    "",
    "",
])

once(
    anchor,
    model + anchor,
    "D3_REQUEST_MODEL"
)

# ---------------------------------------------------------
# 4. PERSISTENCE + VERIFIER
#
# Important:
# Mechanical analysis is MEDIA-centric.
# Storage/identity use source SHA, not ReferenceItem/path/preference.
# ---------------------------------------------------------

anchor = "def _reference_media_dir(profile_id: str, item_id: str) -> Path:"

helpers = NL.join([
    "def _reference_mechanical_analysis_dir(source_sha: str) -> Path:",
    "    sha=str(source_sha or '').strip().lower()",
    "    if not re.fullmatch(r'[a-f0-9]{64}',sha):",
    "        raise HTTPException(422,'REFERENCE_MECHANICAL_SOURCE_SHA_INVALID')",
    "    return _ensure_under(",
    "        PRODUCTION_REFERENCE_MECHANICAL_ANALYSES / sha[:2] / sha,",
    "        PRODUCTION_REFERENCE_MECHANICAL_ANALYSES,",
    "    )",
    "",
    "",
    "def _reference_mechanical_analysis_path(source_sha: str, analysis_id: str) -> Path:",
    "    return _ensure_under(",
    "        _reference_mechanical_analysis_dir(source_sha) / f'{_safe_component(analysis_id)}.json',",
    "        PRODUCTION_REFERENCE_MECHANICAL_ANALYSES,",
    "    )",
    "",
    "",
    "def _verify_reference_mechanical_analysis(rec: dict[str,Any]) -> dict[str,Any]:",
    "    if rec.get('contract_version')!=REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_VERSION:",
    "        raise HTTPException(409,'REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_MISMATCH')",
    "    if rec.get('analyzer_version')!=REFERENCE_MECHANICAL_ANALYZER_VERSION:",
    "        raise HTTPException(409,'REFERENCE_MECHANICAL_ANALYZER_VERSION_MISMATCH')",
    "    source_sha=str(rec.get('source_sha256') or '').lower()",
    "    if not re.fullmatch(r'[a-f0-9]{64}',source_sha):",
    "        raise HTTPException(409,'REFERENCE_MECHANICAL_SOURCE_SHA_INVALID')",
    "    expected=str(rec.get('mechanical_analysis_sha256') or '').lower()",
    "    if not re.fullmatch(r'[a-f0-9]{64}',expected):",
    "        raise HTTPException(409,'REFERENCE_MECHANICAL_ANALYSIS_HASH_INVALID')",
    "    chk=dict(rec)",
    "    chk.pop('mechanical_analysis_sha256',None)",
    "    if _canonical_sha256(chk)!=expected:",
    "        raise HTTPException(409,'REFERENCE_MECHANICAL_ANALYSIS_INTEGRITY_FAILED')",
    "    contact_path=str(rec.get('contact_sheet_path') or '').strip()",
    "    contact_sha=str(rec.get('contact_sheet_sha256') or '').lower()",
    "    if contact_path and contact_sha:",
    "        cp=Path(contact_path)",
    "        if cp.exists() and cp.is_file() and sha256_file(cp).lower()!=contact_sha:",
    "            raise HTTPException(409,'REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_MISMATCH')",
    "    return rec",
    "",
    "",
])

once(
    anchor,
    helpers + anchor,
    "D3_PERSISTENCE_HELPERS"
)

# ---------------------------------------------------------
# 5. ENDPOINT
# ---------------------------------------------------------

anchor = '@app.post("/production/reference-corpus/video-analysis")'

endpoint = NL.join([
    '@app.post("/production/reference-corpus/mechanical-analysis")',
    "def production_reference_mechanical_analysis(req: ReferenceMechanicalAnalysisRequest):",
    "    item=_load_reference_item(req.reference_item_id)",
    "    if item.get('item_type') not in {'REEL','VIDEO','STORY'}:",
    "        raise HTTPException(422,'REFERENCE_MECHANICAL_ANALYSIS_ITEM_TYPE_NOT_VIDEO')",
    "",
    "    profile_id=item['reference_profile_id']",
    "",
    "    if req.acquisition_id:",
    "        acquisition_path=_reference_media_path(profile_id,req.reference_item_id,req.acquisition_id)",
    "        if not acquisition_path.exists():",
    "            raise HTTPException(404,'REFERENCE_MEDIA_ACQUISITION_NOT_FOUND')",
    "        acquisition=_verify_reference_media_acquisition(",
    "            json.loads(acquisition_path.read_text(encoding='utf-8'))",
    "        )",
    "    else:",
    "        if not req.use_latest_acquisition:",
    "            raise HTTPException(422,'REFERENCE_MECHANICAL_ACQUISITION_REQUIRED')",
    "        acquisition=_latest_reference_media_for_item(req.reference_item_id)",
    "        if acquisition is None:",
    "            raise HTTPException(404,'REFERENCE_MEDIA_ACQUISITION_NOT_FOUND')",
    "",
    "    canonical=Path(str(acquisition.get('canonical_resolved_path') or ''))",
    "    source=_ensure_under(canonical,REFERENCE_MEDIA_SOURCES)",
    "",
    "    meta=ffprobe(source)",
    "    if not meta.get('video'):",
    "        raise HTTPException(422,'REFERENCE_MECHANICAL_VIDEO_STREAM_NOT_FOUND')",
    "",
    "    source_sha=str(meta.get('sha256') or sha256_file(source)).lower()",
    "    acquisition_sha=str(acquisition.get('source_sha256') or '').lower()",
    "",
    "    if source_sha!=acquisition_sha:",
    "        raise HTTPException(409,'REFERENCE_MECHANICAL_ACQUISITION_SHA_MISMATCH')",
    "",
    "    duration=float(meta.get('duration_seconds') or 0.0)",
    "    if duration<=0:",
    "        raise HTTPException(422,'REFERENCE_MECHANICAL_DURATION_INVALID')",
    "",
    "    analysis_id='RMA_'+_canonical_sha256({",
    "        'source_sha256':source_sha,",
    "        'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION,",
    "    })[:32]",
    "",
    "    path=_reference_mechanical_analysis_path(source_sha,analysis_id)",
    "",
    "    resolved_from={",
    "        'reference_item_id':req.reference_item_id,",
    "        'reference_profile_id':profile_id,",
    "        'acquisition_id':acquisition.get('acquisition_id'),",
    "    }",
    "",
    "    if path.exists():",
    "        old=_verify_reference_mechanical_analysis(",
    "            json.loads(path.read_text(encoding='utf-8'))",
    "        )",
    "        return {",
    "            'ok':True,",
    "            'reused_existing':True,",
    "            'resolved_from':resolved_from,",
    "            'analysis':old,",
    "        }",
    "",
    "    work=_ensure_under(",
    "        CONTACTS/'reference_mechanical_analysis'/source_sha[:2]/source_sha,",
    "        CONTACTS,",
    "    )",
    "    work.mkdir(parents=True,exist_ok=True)",
    "",
    "    contact_sheet=_ensure_under(work/'contact_sheet.jpg',CONTACTS)",
    "    sampling=make_contact_sheet(source,contact_sheet,duration)",
    "",
    "    cut=_reference_cut_metrics(source,duration)",
    "    audio=_reference_audio_onsets(source)",
    "    beat=_reference_beat_sync(cut.get('scene_times') or [],audio)",
    "",
    "    frame_times=[",
    "        float(x)",
    "        for x in (sampling.get('frame_times_seconds') or [])",
    "    ]",
    "",
    "    color=_reference_color_stats(source,frame_times,work)",
    "",
    "    mechanical={",
    "        'duration_seconds':round(duration,4),",
    "        'has_audio':bool(meta.get('has_audio')),",
    "        'scene_count':int(cut.get('scene_count') or 0),",
    "        'cuts_per_10s':cut.get('cuts_per_10s'),",
    "        'median_shot_s':cut.get('median_shot_s'),",
    "        'scene_detection_ok':bool(cut.get('scene_detection_ok')),",
    "        'scene_detection_error':cut.get('scene_detection_error'),",
    "        'beat_sync':beat.get('beat_sync'),",
    "        'cut_onset_match_ratio':beat.get('cut_onset_match_ratio'),",
    "        'matched_cuts':beat.get('matched_cuts'),",
    "        'audio_onset_count':len(audio.get('onset_times') or []),",
    "        'audio_evidence_reason':audio.get('reason'),",
    "        **color,",
    "        'sampling':sampling,",
    "    }",
    "",
    "    mechanical_conf=90 if (",
    "        cut.get('scene_detection_ok')",
    "        and sampling.get('fallback_used') is False",
    "    ) else 72",
    "",
    "    if not meta.get('has_audio'):",
    "        mechanical_conf=min(mechanical_conf,85)",
    "",
    "    rec={",
    "        'ok':True,",
    "        'mechanical_analysis_id':analysis_id,",
    "        'contract_version':REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_VERSION,",
    "        'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION,",
    "        'source_sha256':source_sha,",
    "        'source_bytes':int(source.stat().st_size),",
    "        'duration_seconds':round(duration,4),",
    "        'has_audio':bool(meta.get('has_audio')),",
    "        'mechanical_confidence':mechanical_conf,",
    "        'mechanical':mechanical,",
    "        'contact_sheet_path':str(contact_sheet),",
    "        'contact_sheet_sha256':sha256_file(contact_sheet),",
    "        'created_at':datetime.now(timezone.utc).isoformat(),",
    "        'copying_forbidden':True,",
    "        'foundation_override_allowed':False,",
    "    }",
    "",
    "    rec['mechanical_analysis_sha256']=_canonical_sha256(rec)",
    "",
    "    path.parent.mkdir(parents=True,exist_ok=True)",
    "    _write_revision_once(path,rec)",
    "",
    "    persisted=_verify_reference_mechanical_analysis(",
    "        json.loads(path.read_text(encoding='utf-8'))",
    "    )",
    "",
    "    return {",
    "        'ok':True,",
    "        'reused_existing':False,",
    "        'resolved_from':resolved_from,",
    "        'analysis':persisted,",
    "    }",
    "",
    "",
])

once(
    anchor,
    endpoint + anchor,
    "D3_ENDPOINT"
)

# ---------------------------------------------------------
# FINAL STATIC ASSERTIONS
# ---------------------------------------------------------

required = [
    'WORKER_VERSION = "2.20.0"',
    'SM3_REFERENCE_MECHANICAL_ANALYSIS_V1',
    'SM3_REFERENCE_MECHANICAL_ANALYZER_V1',
    'class ReferenceMechanicalAnalysisRequest',
    'def _verify_reference_mechanical_analysis',
    '@app.post("/production/reference-corpus/mechanical-analysis")',
    "production_reference_video_analysis(req: ReferenceVideoAnalysisRequest)",
]

for marker in required:
    if marker not in text:
        raise SystemExit(f"SM3_D3_REQUIRED_MARKER_MISSING:{marker}")

# Explicit architectural guardrails.
mechanical_start = text.index(
    'def production_reference_mechanical_analysis'
)
mechanical_end = text.index(
    '@app.post("/production/reference-corpus/video-analysis")',
    mechanical_start
)
mechanical_block = text[mechanical_start:mechanical_end]

for forbidden in (
    "_reference_video_vision(",
    "production_reference_feature(",
    "ReferenceFeatureObservationRequest(",
    "preference_signal",
    "OPENAI_API_KEY",
):
    if forbidden in mechanical_block:
        raise SystemExit(
            f"SM3_D3_MECHANICAL_BOUNDARY_VIOLATION:{forbidden}"
        )

# Python syntax validation BEFORE replacing authoritative source.
compile(text, str(worker), "exec")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = backup_root / f"worker_2_19_0_pre_09C4D_{stamp}.py"
backup.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(worker,backup)

encoded = text.encode("utf-8")
if has_bom:
    encoded = codecs.BOM_UTF8 + encoded

tmp = worker.with_suffix(".py.09C4D.tmp")
tmp.write_bytes(encoded)
os.replace(tmp,worker)

print()
print(f"BACKUP={backup}")
print(f"WORKER={worker}")
print("NEW_VERSION=2.20.0")
print("MECHANICAL_CONTRACT=SM3_REFERENCE_MECHANICAL_ANALYSIS_V1")
print("MECHANICAL_ANALYZER=SM3_REFERENCE_MECHANICAL_ANALYZER_V1")
print("OPENAI_IN_MECHANICAL_ENDPOINT=False")
print("FEATURE_WRITE_IN_MECHANICAL_ENDPOINT=False")
print("PREFERENCE_IN_MECHANICAL_ENDPOINT=False")
print()
print("SM3_09C4_D3_SOURCE_PATCH_PASS")
