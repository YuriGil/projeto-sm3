from pathlib import Path
from datetime import datetime
import codecs
import os
import shutil

worker = Path(
    r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py"
)

backup_root = Path(
    r"D:\MOLOTOV_SOCIAL_OS_RC7\sm3_backups"
)

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

    print(
        f"{label}_ANCHOR_COUNT={count}"
    )

    if count != 1:
        raise SystemExit(
            f"{label}_ANCHOR_INVALID:{count}"
        )

    text = text.replace(
        old,
        new,
        1,
    )


def replace_between(
    start_marker,
    end_marker,
    replacement,
    label,
):
    global text

    start_count = text.count(start_marker)
    end_count = text.count(end_marker)

    print(
        f"{label}_START_COUNT={start_count}"
    )

    print(
        f"{label}_END_COUNT={end_count}"
    )

    if start_count != 1:
        raise SystemExit(
            f"{label}_START_INVALID:{start_count}"
        )

    start = text.index(start_marker)

    end = text.find(
        end_marker,
        start + len(start_marker),
    )

    if end < 0:
        raise SystemExit(
            f"{label}_END_NOT_FOUND"
        )

    text = (
        text[:start]
        + replacement.rstrip()
        + NL
        + NL
        + text[end:]
    )


# ============================================================
# 0. PRECONDITIONS
# ============================================================

if 'WORKER_VERSION = "2.21.0"' not in text:
    raise SystemExit(
        "SM3_09C5_B1_EXPECTED_WORKER_2_21_0_NOT_FOUND"
    )

for forbidden in (
    "REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION",
    "PRODUCTION_REFERENCE_MEDIA_ARTIFACTS",
    "REFERENCE_MEDIA_ARTIFACTS",
    "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
    "SM3_REFERENCE_MEDIA_ACQUIRER_V2",
    "_persist_reference_media_artifact",
):
    if forbidden in text:
        raise SystemExit(
            f"SM3_09C5_B1_ALREADY_PATCHED:{forbidden}"
        )


# ============================================================
# 1. STORAGE ROOTS
# ============================================================

old = (
    'PRODUCTION_REFERENCE_MEDIA = '
    '(PRODUCTION_STATE / "reference_media").resolve()'
)

new = (
    old
    + NL
    + 'PRODUCTION_REFERENCE_MEDIA_ARTIFACTS = '
      '(PRODUCTION_STATE / "reference_media_artifacts").resolve()'
)

once(
    old,
    new,
    "B1_STATE_ARTIFACT_ROOT",
)


old = (
    'REFERENCE_MEDIA_SOURCES = '
    '(MEDIA_ROOT / "reference_sources").resolve()'
)

new = (
    'REFERENCE_MEDIA_ARTIFACTS = '
    '(MEDIA_ROOT / "reference_artifacts").resolve()'
    + NL
    + old
)

once(
    old,
    new,
    "B1_CAS_MEDIA_ROOT",
)


once(
    "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES, "
    "PRODUCTION_REFERENCE_MEDIA, "
    "PRODUCTION_REFERENCE_HARVEST_CANDIDATES,",

    "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES, "
    "PRODUCTION_REFERENCE_MEDIA, "
    "PRODUCTION_REFERENCE_MEDIA_ARTIFACTS, "
    "PRODUCTION_REFERENCE_HARVEST_CANDIDATES,",

    "B1_STARTUP_STATE_ROOT",
)


once(
    "PRODUCTION_REFERENCE_SCRAPER, "
    "REFERENCE_MEDIA_INBOX, "
    "REFERENCE_MEDIA_SOURCES):",

    "PRODUCTION_REFERENCE_SCRAPER, "
    "REFERENCE_MEDIA_INBOX, "
    "REFERENCE_MEDIA_ARTIFACTS, "
    "REFERENCE_MEDIA_SOURCES):",

    "B1_STARTUP_MEDIA_ROOT",
)


# ============================================================
# 2. WORKER + CONTRACT VERSIONS
# ============================================================

once(
    'WORKER_VERSION = "2.21.0"',
    'WORKER_VERSION = "2.22.0"',
    "B1_WORKER_VERSION",
)


old = NL.join([
    'REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION = "SM3_REFERENCE_MEDIA_ACQUISITION_V1"',
    'REFERENCE_MEDIA_ACQUISITION_VERSION = "SM3_REFERENCE_MEDIA_ACQUIRER_V1"',
])

new = NL.join([
    'REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION = "SM3_REFERENCE_MEDIA_ARTIFACT_V1"',
    'REFERENCE_MEDIA_ARTIFACT_STORE_VERSION = "SM3_REFERENCE_MEDIA_CAS_V1"',
    '',
    'REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS = {',
    '    "SM3_REFERENCE_MEDIA_ACQUISITION_V1"',
    '}',
    '',
    'REFERENCE_MEDIA_ACQUISITION_LEGACY_ACQUIRER_VERSIONS = {',
    '    "SM3_REFERENCE_MEDIA_ACQUIRER_V1"',
    '}',
    '',
    'REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION = "SM3_REFERENCE_MEDIA_ACQUISITION_V2"',
    'REFERENCE_MEDIA_ACQUISITION_VERSION = "SM3_REFERENCE_MEDIA_ACQUIRER_V2"',
])

once(
    old,
    new,
    "B1_VERSIONED_ACQUISITION_CONTRACTS",
)


# ============================================================
# 3. MEDIA ARTIFACT / CAS HELPERS
# ============================================================

anchor = (
    "def _reference_media_dir("
    "profile_id: str, item_id: str"
    ") -> Path:"
)

helpers = NL.join([
    "def _reference_media_artifact_sha(source_sha: str) -> str:",
    "    sha=str(source_sha or '').strip().lower()",
    "",
    "    if not re.fullmatch(r'[a-f0-9]{64}',sha):",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ARTIFACT_SOURCE_SHA_INVALID'",
    "        )",
    "",
    "    return sha",
    "",
    "",
    "def _reference_media_artifact_id(source_sha: str) -> str:",
    "    sha=_reference_media_artifact_sha(source_sha)",
    "    return 'MA_'+sha",
    "",
    "",
    "def _reference_media_artifact_state_dir(source_sha: str) -> Path:",
    "    sha=_reference_media_artifact_sha(source_sha)",
    "",
    "    return _ensure_under(",
    "        PRODUCTION_REFERENCE_MEDIA_ARTIFACTS",
    "        / sha[:2]",
    "        / sha,",
    "        PRODUCTION_REFERENCE_MEDIA_ARTIFACTS,",
    "    )",
    "",
    "",
    "def _reference_media_artifact_state_path(source_sha: str) -> Path:",
    "    sha=_reference_media_artifact_sha(source_sha)",
    "    artifact_id=_reference_media_artifact_id(sha)",
    "",
    "    return _ensure_under(",
    "        _reference_media_artifact_state_dir(sha)",
    "        / f'{_safe_component(artifact_id)}.json',",
    "        PRODUCTION_REFERENCE_MEDIA_ARTIFACTS,",
    "    )",
    "",
    "",
    "def _reference_media_artifact_blob_dir(source_sha: str) -> Path:",
    "    sha=_reference_media_artifact_sha(source_sha)",
    "",
    "    return _ensure_under(",
    "        REFERENCE_MEDIA_ARTIFACTS",
    "        / sha[:2]",
    "        / sha,",
    "        REFERENCE_MEDIA_ARTIFACTS,",
    "    )",
    "",
    "",
    "def _reference_media_artifact_blob_path(source_sha: str) -> Path:",
    "    return _ensure_under(",
    "        _reference_media_artifact_blob_dir(source_sha)",
    "        / 'source',",
    "        REFERENCE_MEDIA_ARTIFACTS,",
    "    )",
    "",
    "",
    "def _verify_reference_media_artifact(",
    "    rec: dict[str,Any],",
    ") -> dict[str,Any]:",
    "    if rec.get('contract_version') != REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_CONTRACT_MISMATCH'",
    "        )",
    "",
    "    if rec.get('store_version') != REFERENCE_MEDIA_ARTIFACT_STORE_VERSION:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_STORE_VERSION_MISMATCH'",
    "        )",
    "",
    "    source_sha=str(rec.get('source_sha256') or '').lower()",
    "",
    "    if not re.fullmatch(r'[a-f0-9]{64}',source_sha):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_SOURCE_SHA_INVALID'",
    "        )",
    "",
    "    expected_id=_reference_media_artifact_id(source_sha)",
    "",
    "    if rec.get('media_artifact_id') != expected_id:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_ID_MISMATCH'",
    "        )",
    "",
    "    expected_hash=str(",
    "        rec.get('media_artifact_sha256') or ''",
    "    ).lower()",
    "",
    "    if not re.fullmatch(r'[a-f0-9]{64}',expected_hash):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_HASH_INVALID'",
    "        )",
    "",
    "    chk=dict(rec)",
    "    chk.pop('media_artifact_sha256',None)",
    "",
    "    if _canonical_sha256(chk) != expected_hash:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_INTEGRITY_FAILED'",
    "        )",
    "",
    "    expected_blob=_reference_media_artifact_blob_path(",
    "        source_sha",
    "    )",
    "",
    "    local_ref=str(",
    "        rec.get('cas_local_media_ref') or ''",
    "    ).strip()",
    "",
    "    if not local_ref:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_CAS_REF_MISSING'",
    "        )",
    "",
    "    blob=_ensure_under(",
    "        MEDIA_ROOT / local_ref,",
    "        REFERENCE_MEDIA_ARTIFACTS,",
    "    )",
    "",
    "    if blob.resolve() != expected_blob.resolve():",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_CAS_PATH_MISMATCH'",
    "        )",
    "",
    "    if not blob.exists() or not blob.is_file():",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_BLOB_MISSING'",
    "        )",
    "",
    "    source_bytes=int(rec.get('source_bytes') or 0)",
    "",
    "    if source_bytes <= 0:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_BYTES_INVALID'",
    "        )",
    "",
    "    if int(blob.stat().st_size) != source_bytes:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_BYTES_MISMATCH'",
    "        )",
    "",
    "    if sha256_file(blob).lower() != source_sha:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_BLOB_HASH_MISMATCH'",
    "        )",
    "",
    "    return rec",
    "",
    "",
    "def _load_reference_media_artifact(",
    "    source_sha: str,",
    "    media_artifact_id: Optional[str] = None,",
    ") -> dict[str,Any]:",
    "    sha=_reference_media_artifact_sha(source_sha)",
    "    expected_id=_reference_media_artifact_id(sha)",
    "",
    "    if media_artifact_id is not None and media_artifact_id != expected_id:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ARTIFACT_ID_SOURCE_MISMATCH'",
    "        )",
    "",
    "    path=_reference_media_artifact_state_path(sha)",
    "",
    "    if not path.exists() or not path.is_file():",
    "        raise HTTPException(",
    "            404,",
    "            'REFERENCE_MEDIA_ARTIFACT_NOT_FOUND'",
    "        )",
    "",
    "    return _verify_reference_media_artifact(",
    "        json.loads(",
    "            path.read_text(encoding='utf-8')",
    "        )",
    "    )",
    "",
    "",
    "def _persist_reference_media_artifact(",
    "    source: Path,",
    "    meta: dict[str,Any],",
    ") -> dict[str,Any]:",
    "    if not source.exists() or not source.is_file():",
    "        raise HTTPException(",
    "            404,",
    "            'REFERENCE_MEDIA_ARTIFACT_SOURCE_MISSING'",
    "        )",
    "",
    "    source_sha=str(",
    "        meta.get('sha256') or sha256_file(source)",
    "    ).lower()",
    "",
    "    source_sha=_reference_media_artifact_sha(source_sha)",
    "    source_bytes=int(source.stat().st_size)",
    "",
    "    if source_bytes <= 0:",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ARTIFACT_SOURCE_EMPTY'",
    "        )",
    "",
    "    artifact_id=_reference_media_artifact_id(source_sha)",
    "    state_path=_reference_media_artifact_state_path(source_sha)",
    "    blob_dir=_reference_media_artifact_blob_dir(source_sha)",
    "    blob=_reference_media_artifact_blob_path(source_sha)",
    "",
    "    if state_path.exists():",
    "        old=_load_reference_media_artifact(",
    "            source_sha,",
    "            artifact_id,",
    "        )",
    "",
    "        if int(old.get('source_bytes') or 0) != source_bytes:",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_ARTIFACT_IDEMPOTENCY_BYTES_CONFLICT'",
    "            )",
    "",
    "        return {",
    "            'artifact':old,",
    "            'reused_existing':True,",
    "        }",
    "",
    "    blob_dir.mkdir(",
    "        parents=True,",
    "        exist_ok=True,",
    "    )",
    "",
    "    if blob.exists():",
    "        if int(blob.stat().st_size) != source_bytes:",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_ARTIFACT_CAS_BYTES_COLLISION'",
    "            )",
    "",
    "        if sha256_file(blob).lower() != source_sha:",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_ARTIFACT_CAS_HASH_COLLISION'",
    "            )",
    "    else:",
    "        tmp=_ensure_under(",
    "            blob_dir",
    "            / f'.source.{uuid4().hex}.tmp',",
    "            REFERENCE_MEDIA_ARTIFACTS,",
    "        )",
    "",
    "        shutil.copy2(source,tmp)",
    "",
    "        if int(tmp.stat().st_size) != source_bytes:",
    "            try:",
    "                tmp.unlink()",
    "            except FileNotFoundError:",
    "                pass",
    "",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_ARTIFACT_COPY_BYTES_MISMATCH'",
    "            )",
    "",
    "        if sha256_file(tmp).lower() != source_sha:",
    "            try:",
    "                tmp.unlink()",
    "            except FileNotFoundError:",
    "                pass",
    "",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_ARTIFACT_COPY_HASH_MISMATCH'",
    "            )",
    "",
    "        with tmp.open('rb') as fh:",
    "            os.fsync(fh.fileno())",
    "",
    "        os.replace(tmp,blob)",
    "        _sync_session_dir(blob_dir)",
    "",
    "    cas_ref=blob.relative_to(MEDIA_ROOT).as_posix()",
    "",
    "    rec={",
    "        'ok':True,",
    "        'media_artifact_id':artifact_id,",
    "        'contract_version':REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION,",
    "        'store_version':REFERENCE_MEDIA_ARTIFACT_STORE_VERSION,",
    "        'media_kind':'VIDEO',",
    "        'source_sha256':source_sha,",
    "        'source_bytes':source_bytes,",
    "        'duration_seconds':round(",
    "            float(meta.get('duration_seconds') or 0.0),",
    "            4,",
    "        ),",
    "        'has_audio':bool(meta.get('has_audio')),",
    "        'cas_local_media_ref':cas_ref,",
    "        'created_at':datetime.now(timezone.utc).isoformat(),",
    "        'copying_reference_identity_forbidden':True,",
    "        'foundation_override_allowed':False,",
    "    }",
    "",
    "    if rec['duration_seconds'] <= 0:",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ARTIFACT_DURATION_INVALID'",
    "        )",
    "",
    "    rec['media_artifact_sha256']=_canonical_sha256(rec)",
    "",
    "    state_path.parent.mkdir(",
    "        parents=True,",
    "        exist_ok=True,",
    "    )",
    "",
    "    _write_revision_once(",
    "        state_path,",
    "        rec,",
    "    )",
    "",
    "    persisted=_load_reference_media_artifact(",
    "        source_sha,",
    "        artifact_id,",
    "    )",
    "",
    "    return {",
    "        'artifact':persisted,",
    "        'reused_existing':False,",
    "    }",
    "",
    "",
])

once(
    anchor,
    helpers + anchor,
    "B1_ARTIFACT_HELPERS",
)


# ============================================================
# 4. DUAL V1/V2 ACQUISITION VERIFIER
# ============================================================

start_marker = (
    "def _verify_reference_media_acquisition("
    "rec: dict[str, Any]"
    ") -> dict[str, Any]:"
)

end_marker = (
    "def _resolve_reference_inbox_ref("
    "ref: str"
    ") -> Path:"
)

replacement = NL.join([
    "def _verify_reference_media_acquisition(",
    "    rec: dict[str,Any],",
    ") -> dict[str,Any]:",
    "    contract=str(rec.get('contract_version') or '')",
    "    acquirer=str(rec.get('acquirer_version') or '')",
    "",
    "    is_current=(",
    "        contract == REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION",
    "        and acquirer == REFERENCE_MEDIA_ACQUISITION_VERSION",
    "    )",
    "",
    "    is_legacy=(",
    "        contract in REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS",
    "        and acquirer in REFERENCE_MEDIA_ACQUISITION_LEGACY_ACQUIRER_VERSIONS",
    "    )",
    "",
    "    if not is_current and not is_legacy:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION_PAIR_MISMATCH'",
    "        )",
    "",
    "    expected=str(",
    "        rec.get('acquisition_sha256') or ''",
    "    ).lower()",
    "",
    "    if not re.fullmatch(r'[a-f0-9]{64}',expected):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_HASH_INVALID'",
    "        )",
    "",
    "    chk=dict(rec)",
    "    chk.pop('acquisition_sha256',None)",
    "",
    "    if _canonical_sha256(chk) != expected:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_INTEGRITY_FAILED'",
    "        )",
    "",
    "    source_sha=str(",
    "        rec.get('source_sha256') or ''",
    "    ).lower()",
    "",
    "    if not re.fullmatch(r'[a-f0-9]{64}',source_sha):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_SOURCE_SHA_INVALID'",
    "        )",
    "",
    "    if is_legacy:",
    "        canonical=Path(",
    "            str(rec.get('canonical_resolved_path') or '')",
    "        )",
    "",
    "        canonical=_ensure_under(",
    "            canonical,",
    "            REFERENCE_MEDIA_SOURCES,",
    "        )",
    "",
    "        if not canonical.exists() or not canonical.is_file():",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_CANONICAL_FILE_MISSING'",
    "            )",
    "",
    "        if sha256_file(canonical).lower() != source_sha:",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_CANONICAL_FILE_HASH_MISMATCH'",
    "            )",
    "",
    "        source_bytes=int(rec.get('source_bytes') or 0)",
    "",
    "        if source_bytes > 0 and int(canonical.stat().st_size) != source_bytes:",
    "            raise HTTPException(",
    "                409,",
    "                'REFERENCE_MEDIA_CANONICAL_FILE_BYTES_MISMATCH'",
    "            )",
    "",
    "        return rec",
    "",
    "    media_artifact_id=str(",
    "        rec.get('media_artifact_id') or ''",
    "    ).strip()",
    "",
    "    if not media_artifact_id:",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_ARTIFACT_ID_MISSING'",
    "        )",
    "",
    "    artifact=_load_reference_media_artifact(",
    "        source_sha,",
    "        media_artifact_id,",
    "    )",
    "",
    "    if int(rec.get('source_bytes') or 0) != int(artifact.get('source_bytes') or 0):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_ARTIFACT_BYTES_MISMATCH'",
    "        )",
    "",
    "    if round(float(rec.get('duration_seconds') or 0.0),4) != round(float(artifact.get('duration_seconds') or 0.0),4):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_ARTIFACT_DURATION_MISMATCH'",
    "        )",
    "",
    "    if bool(rec.get('has_audio')) != bool(artifact.get('has_audio')):",
    "        raise HTTPException(",
    "            409,",
    "            'REFERENCE_MEDIA_ACQUISITION_ARTIFACT_AUDIO_MISMATCH'",
    "        )",
    "",
    "    return rec",
    "",
    "",
    "def _resolve_reference_acquisition_source(",
    "    acquisition: dict[str,Any],",
    ") -> tuple[Path,Optional[dict[str,Any]]]:",
    "    rec=_verify_reference_media_acquisition(acquisition)",
    "    contract=str(rec.get('contract_version') or '')",
    "",
    "    if contract in REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS:",
    "        canonical=_ensure_under(",
    "            Path(str(rec.get('canonical_resolved_path') or '')),",
    "            REFERENCE_MEDIA_SOURCES,",
    "        )",
    "",
    "        return canonical,None",
    "",
    "    source_sha=str(rec.get('source_sha256') or '').lower()",
    "    artifact=_load_reference_media_artifact(",
    "        source_sha,",
    "        str(rec.get('media_artifact_id') or ''),",
    "    )",
    "",
    "    blob=_reference_media_artifact_blob_path(source_sha)",
    "",
    "    return blob,artifact",
])

replace_between(
    start_marker,
    end_marker,
    replacement,
    "B1_DUAL_ACQUISITION_VERIFIER",
)


# ============================================================
# 5. MEDIA ARTIFACT READ ENDPOINTS
# ============================================================

anchor = (
    '@app.post("/production/reference-corpus/'
    'reference-media/acquire")'
)

routes = NL.join([
    '@app.get("/production/reference-corpus/reference-media/artifacts")',
    "def production_reference_media_artifacts():",
    "    artifacts=[]",
    "",
    "    if PRODUCTION_REFERENCE_MEDIA_ARTIFACTS.exists():",
    "        for p in PRODUCTION_REFERENCE_MEDIA_ARTIFACTS.glob(",
    "            '*/*/MA_*.json'",
    "        ):",
    "            artifacts.append(",
    "                _verify_reference_media_artifact(",
    "                    json.loads(",
    "                        p.read_text(encoding='utf-8')",
    "                    )",
    "                )",
    "            )",
    "",
    "    artifacts.sort(",
    "        key=lambda r:str(",
    "            r.get('source_sha256') or ''",
    "        )",
    "    )",
    "",
    "    return {",
    "        'ok':True,",
    "        'contract_version':REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION,",
    "        'store_version':REFERENCE_MEDIA_ARTIFACT_STORE_VERSION,",
    "        'count':len(artifacts),",
    "        'artifacts':artifacts,",
    "    }",
    "",
    "",
    '@app.get("/production/reference-corpus/reference-media/artifact/{media_artifact_id}")',
    "def production_reference_media_artifact_get(",
    "    media_artifact_id: str,",
    "):",
    "    raw=str(media_artifact_id or '').strip().lower()",
    "",
    "    if not re.fullmatch(r'ma_[a-f0-9]{64}',raw):",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ARTIFACT_ID_INVALID'",
    "        )",
    "",
    "    source_sha=raw[3:]",
    "",
    "    return _load_reference_media_artifact(",
    "        source_sha,",
    "        'MA_'+source_sha,",
    "    )",
    "",
    "",
])

once(
    anchor,
    routes + anchor,
    "B1_ARTIFACT_ROUTES",
)


# ============================================================
# 6. NEW ACQUISITIONS WRITE V2 + CAS
# ============================================================

start_marker = (
    '@app.post("/production/reference-corpus/'
    'reference-media/acquire")'
)

end_marker = (
    '@app.get("/production/reference-corpus/'
    'reference-media")'
)

replacement = NL.join([
    '@app.post("/production/reference-corpus/reference-media/acquire")',
    "def production_reference_media_acquire(",
    "    req: ReferenceMediaAcquireRequest,",
    "):",
    "    item=_require_reference_item_active(",
    "        req.reference_item_id",
    "    )",
    "",
    "    if item.get('item_type') not in {'REEL','VIDEO','STORY'}:",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ACQUISITION_ITEM_TYPE_NOT_VIDEO'",
    "        )",
    "",
    "    source=_resolve_reference_inbox_ref(",
    "        req.inbox_media_ref",
    "    )",
    "",
    "    meta=ffprobe(source)",
    "",
    "    if not meta.get('video'):",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ACQUISITION_VIDEO_STREAM_NOT_FOUND'",
    "        )",
    "",
    "    duration=float(",
    "        meta.get('duration_seconds') or 0.0",
    "    )",
    "",
    "    if duration <= 0:",
    "        raise HTTPException(",
    "            422,",
    "            'REFERENCE_MEDIA_ACQUISITION_DURATION_INVALID'",
    "        )",
    "",
    "    artifact_result=_persist_reference_media_artifact(",
    "        source,",
    "        meta,",
    "    )",
    "",
    "    artifact=artifact_result['artifact']",
    "    source_sha=artifact['source_sha256']",
    "    profile_id=item['reference_profile_id']",
    "",
    "    acquisition_id='RM_'+_canonical_sha256({",
    "        'reference_item_id':req.reference_item_id,",
    "        'source_sha256':source_sha,",
    "        'acquirer_version':REFERENCE_MEDIA_ACQUISITION_VERSION,",
    "    })[:32]",
    "",
    "    path=_reference_media_path(",
    "        profile_id,",
    "        req.reference_item_id,",
    "        acquisition_id,",
    "    )",
    "",
    "    stable={",
    "        'acquisition_id':acquisition_id,",
    "        'contract_version':REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,",
    "        'acquirer_version':REFERENCE_MEDIA_ACQUISITION_VERSION,",
    "        'reference_item_id':req.reference_item_id,",
    "        'reference_profile_id':profile_id,",
    "        'source_kind':req.source_kind,",
    "        'media_artifact_id':artifact['media_artifact_id'],",
    "        'source_sha256':source_sha,",
    "        'source_bytes':artifact['source_bytes'],",
    "        'duration_seconds':artifact['duration_seconds'],",
    "        'has_audio':artifact['has_audio'],",
    "        'original_filename':str(",
    "            req.original_filename or source.name",
    "        ).strip(),",
    "        'notes':str(req.notes or '').strip(),",
    "        'copying_reference_identity_forbidden':True,",
    "        'foundation_override_allowed':False,",
    "    }",
    "",
    "    blob=_reference_media_artifact_blob_path(source_sha)",
    "",
    "    if path.exists():",
    "        old=_verify_reference_media_acquisition(",
    "            json.loads(",
    "                path.read_text(encoding='utf-8')",
    "            )",
    "        )",
    "",
    "        for k,v in stable.items():",
    "            if old.get(k) != v:",
    "                raise HTTPException(",
    "                    409,",
    "                    'REFERENCE_MEDIA_ACQUISITION_IDEMPOTENCY_CONFLICT'",
    "                )",
    "",
    "        if (",
    "            req.cleanup_inbox_after_commit",
    "            and source.resolve() != blob.resolve()",
    "        ):",
    "            try:",
    "                source.unlink()",
    "            except FileNotFoundError:",
    "                pass",
    "",
    "        return {",
    "            'ok':True,",
    "            'reused_existing':True,",
    "            'media_artifact_reused':True,",
    "            'media_artifact':artifact,",
    "            'acquisition':old,",
    "        }",
    "",
    "    rec={",
    "        **stable,",
    "        'created_at':datetime.now(timezone.utc).isoformat(),",
    "    }",
    "",
    "    rec['acquisition_sha256']=_canonical_sha256(rec)",
    "",
    "    path.parent.mkdir(",
    "        parents=True,",
    "        exist_ok=True,",
    "    )",
    "",
    "    _write_revision_once(path,rec)",
    "",
    "    persisted=_verify_reference_media_acquisition(",
    "        json.loads(",
    "            path.read_text(encoding='utf-8')",
    "        )",
    "    )",
    "",
    "    if (",
    "        req.cleanup_inbox_after_commit",
    "        and source.resolve() != blob.resolve()",
    "    ):",
    "        try:",
    "            source.unlink()",
    "        except FileNotFoundError:",
    "            pass",
    "",
    "    return {",
    "        'ok':True,",
    "        'reused_existing':False,",
    "        'media_artifact_reused':bool(",
    "            artifact_result.get('reused_existing')",
    "        ),",
    "        'media_artifact':artifact,",
    "        'acquisition':persisted,",
    "    }",
])

replace_between(
    start_marker,
    end_marker,
    replacement,
    "B1_V2_ACQUISITION_WRITER",
)


# ============================================================
# 7. MIXED V1/V2 LIST RESPONSE
# ============================================================

old = (
    '    return {"ok":True,'
    '"contract_version":REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,'
    '"count":len(acquisitions),'
    '"acquisitions":acquisitions}'
)

new = NL.join([
    "    return {",
    "        'ok':True,",
    "        'contract_version':REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,",
    "        'legacy_contract_versions':sorted(",
    "            REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS",
    "        ),",
    "        'media_artifact_contract':REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION,",
    "        'count':len(acquisitions),",
    "        'acquisitions':acquisitions,",
    "    }",
])

once(
    old,
    new,
    "B1_MIXED_LIST_RESPONSE",
)


# ============================================================
# 8. MECHANICAL ANALYSIS RESOLVES V1 OR V2
# ============================================================

old = NL.join([
    "    canonical=Path(str(acquisition.get('canonical_resolved_path') or ''))",
    "    source=_ensure_under(canonical,REFERENCE_MEDIA_SOURCES)",
])

new = NL.join([
    "    source,media_artifact=_resolve_reference_acquisition_source(",
    "        acquisition",
    "    )",
])

once(
    old,
    new,
    "B1_MECHANICAL_SOURCE_RESOLVER",
)


old = NL.join([
    "    resolved_from={",
    "        'reference_item_id':req.reference_item_id,",
    "        'reference_profile_id':profile_id,",
    "        'acquisition_id':acquisition.get('acquisition_id'),",
    "    }",
])

new = NL.join([
    "    resolved_from={",
    "        'reference_item_id':req.reference_item_id,",
    "        'reference_profile_id':profile_id,",
    "        'acquisition_id':acquisition.get('acquisition_id'),",
    "        'media_artifact_id':acquisition.get('media_artifact_id'),",
    "        'acquisition_contract_version':acquisition.get('contract_version'),",
    "    }",
])

once(
    old,
    new,
    "B1_MECHANICAL_RESOLUTION_PROVENANCE",
)


# ============================================================
# 9. HEALTH / CAPABILITIES
# ============================================================

old = NL.join([
    '        "reference_media_acquisition": True,',
    '        "reference_media_acquisition_contract": REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,',
    '        "reference_media_acquirer_version": REFERENCE_MEDIA_ACQUISITION_VERSION,',
    '        "reference_media_canonical_copy_verified": True,',
    '        "reference_media_remote_scraping_required": False,',
    '        "reference_media_source_immutable": True,',
])

new = NL.join([
    '        "reference_media_acquisition": True,',
    '        "reference_media_acquisition_contract": REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION,',
    '        "reference_media_acquisition_legacy_readable": sorted(REFERENCE_MEDIA_ACQUISITION_LEGACY_CONTRACT_VERSIONS),',
    '        "reference_media_acquirer_version": REFERENCE_MEDIA_ACQUISITION_VERSION,',
    '        "reference_media_artifact_contract": REFERENCE_MEDIA_ARTIFACT_CONTRACT_VERSION,',
    '        "reference_media_artifact_store_version": REFERENCE_MEDIA_ARTIFACT_STORE_VERSION,',
    '        "reference_media_content_addressed_storage": True,',
    '        "reference_media_cas_identity": "SHA256_BYTES",',
    '        "reference_media_v2_absolute_path_persisted": False,',
    '        "reference_media_v1_legacy_sources_read_only": True,',
    '        "reference_media_canonical_copy_verified": True,',
    '        "reference_media_remote_scraping_required": False,',
    '        "reference_media_source_immutable": True,',
])

once(
    old,
    new,
    "B1_HEALTH_CAPABILITIES",
)


# ============================================================
# 10. STATIC ARCHITECTURE ASSERTIONS
# ============================================================

required = (
    'WORKER_VERSION = "2.22.0"',
    'SM3_REFERENCE_MEDIA_ARTIFACT_V1',
    'SM3_REFERENCE_MEDIA_CAS_V1',
    'SM3_REFERENCE_MEDIA_ACQUISITION_V1',
    'SM3_REFERENCE_MEDIA_ACQUISITION_V2',
    'SM3_REFERENCE_MEDIA_ACQUIRER_V1',
    'SM3_REFERENCE_MEDIA_ACQUIRER_V2',
    'def _verify_reference_media_artifact(',
    'def _persist_reference_media_artifact(',
    'def _resolve_reference_acquisition_source(',
    "'media_artifact_id':artifact['media_artifact_id']",
    "'media_artifact_id':acquisition.get('media_artifact_id')",
    '"reference_media_content_addressed_storage": True',
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            f"SM3_09C5_B1_REQUIRED_MARKER_MISSING:{marker}"
        )


# New V2 writer MUST NOT persist absolute/local canonical paths.
writer_start = text.index(
    "def production_reference_media_acquire("
)

writer_end = text.index(
    '@app.get("/production/reference-corpus/reference-media")',
    writer_start,
)

writer_block = text[
    writer_start:writer_end
]

for forbidden in (
    "canonical_resolved_path",
    "canonical_local_media_ref",
    "REFERENCE_MEDIA_SOURCES/",
):
    if forbidden in writer_block:
        raise SystemExit(
            f"SM3_09C5_B1_V2_WRITER_FORBIDDEN:{forbidden}"
        )


# Legacy reader MUST still retain canonical_resolved_path.
verifier_start = text.index(
    "def _verify_reference_media_acquisition("
)

verifier_end = text.index(
    "def _resolve_reference_inbox_ref(",
    verifier_start,
)

verifier_block = text[
    verifier_start:verifier_end
]

if "canonical_resolved_path" not in verifier_block:
    raise SystemExit(
        "SM3_09C5_B1_LEGACY_PATH_READER_MISSING"
    )

if "REFERENCE_MEDIA_ARTIFACTS" not in text:
    raise SystemExit(
        "SM3_09C5_B1_CAS_ROOT_MISSING"
    )


# Mechanical identity MUST remain media-centric.
mechanical_start = text.index(
    "def production_reference_mechanical_analysis("
)

mechanical_end = text.index(
    "def production_reference_video_analysis(",
    mechanical_start,
)

mechanical_block = text[
    mechanical_start:mechanical_end
]

identity_start = mechanical_block.index(
    "analysis_id='RMA_'"
)

identity_end = mechanical_block.index(
    "path=_reference_mechanical_analysis_path",
    identity_start,
)

identity_block = mechanical_block[
    identity_start:identity_end
]

if "'reference_item_id'" in identity_block:
    raise SystemExit(
        "SM3_09C5_B1_RMA_IDENTITY_REGRESSION_ITEM_CENTRIC"
    )

if "'source_sha256':source_sha" not in identity_block:
    raise SystemExit(
        "SM3_09C5_B1_RMA_SOURCE_SHA_IDENTITY_MISSING"
    )


# Syntax validation BEFORE replacing authoritative source.
compile(
    text,
    str(worker),
    "exec",
)


# ============================================================
# 11. BACKUP + ATOMIC REPLACE
# ============================================================

stamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = (
    backup_root
    / f"worker_2_21_0_pre_09C5_media_artifact_{stamp}.py"
)

backup.parent.mkdir(
    parents=True,
    exist_ok=True,
)

shutil.copy2(
    worker,
    backup,
)

encoded = text.encode("utf-8")

if has_bom:
    encoded = codecs.BOM_UTF8 + encoded

tmp = worker.with_suffix(
    ".py.09C5B1.tmp"
)

tmp.write_bytes(encoded)

os.replace(
    tmp,
    worker,
)


print()
print(f"BACKUP={backup}")
print(f"WORKER={worker}")
print("NEW_VERSION=2.22.0")
print(
    "MEDIA_ARTIFACT_CONTRACT="
    "SM3_REFERENCE_MEDIA_ARTIFACT_V1"
)
print(
    "MEDIA_ARTIFACT_STORE="
    "SM3_REFERENCE_MEDIA_CAS_V1"
)
print(
    "ACQUISITION_LEGACY_READ="
    "SM3_REFERENCE_MEDIA_ACQUISITION_V1"
)
print(
    "ACQUISITION_CURRENT_WRITE="
    "SM3_REFERENCE_MEDIA_ACQUISITION_V2"
)
print("CAS_IDENTITY=SHA256_BYTES")
print("V1_FILES_MOVED=False")
print("V1_FILES_DELETED=False")
print("V2_ABSOLUTE_PATH_PERSISTED=False")
print("RMA_IDENTITY_CHANGED=False")
print()
print(
    "SM3_09C5_B1_MEDIA_ARTIFACT_SOURCE_PATCH_PASS"
)
