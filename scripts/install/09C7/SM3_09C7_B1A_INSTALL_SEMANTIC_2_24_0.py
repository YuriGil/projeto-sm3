from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import re
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = ROOT / "worker" / "worker_service.py"

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1A_STRUCTURAL_IMPLEMENTATION.json"
)


EXPECTED_BEFORE_SHA = (
    "3af5412234de7a7faa0e8b23116027b7"
    "cad25fe308698ca9188649ca3b1df8ba"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(code: str) -> None:
    raise SystemExit(code)


raw_before = WORKER.read_bytes()

before_sha = sha256_bytes(raw_before)


if before_sha != EXPECTED_BEFORE_SHA:
    fail(
        "SM3_09C7_B1A_PATCHER_SOURCE_SHA_INVALID:"
        + before_sha
    )


text = WORKER.read_text(
    encoding="utf-8-sig"
)


# ============================================================
# PRECONDITIONS
# ============================================================

if 'WORKER_VERSION = "2.23.1"' not in text:
    fail(
        "SM3_09C7_B1A_EXPECTED_VERSION_NOT_FOUND"
    )


for forbidden in (
    "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",
    "ReferenceSemanticAnalysisRequest",
    "PRODUCTION_REFERENCE_SEMANTIC_ANALYSES",
    "production_reference_semantic_analysis",
):
    if forbidden in text:
        fail(
            "SM3_09C7_B1A_ALREADY_PATCHED:"
            + forbidden
        )


def replace_once(
    source: str,
    old: str,
    new: str,
    label: str,
) -> str:

    count = source.count(old)

    if count != 1:
        fail(
            f"SM3_09C7_B1A_ANCHOR_INVALID:"
            f"{label}:{count}"
        )

    return source.replace(
        old,
        new,
        1,
    )


# ============================================================
# 1. VERSION
# ============================================================

text = replace_once(
    text,
    'WORKER_VERSION = "2.23.1"',
    'WORKER_VERSION = "2.24.0"',
    "WORKER_VERSION",
)


# ============================================================
# 2. STORAGE ROOT
# ============================================================

storage_anchor = (
    'PRODUCTION_REFERENCE_MECHANICAL_ANALYSES = '
    '(PRODUCTION_STATE / '
    '"reference_mechanical_analyses").resolve()'
)


storage_replacement = (
    storage_anchor
    + "\n"
    + 'PRODUCTION_REFERENCE_SEMANTIC_ANALYSES = '
    '(PRODUCTION_STATE / '
    '"reference_semantic_analyses").resolve()'
)


text = replace_once(
    text,
    storage_anchor,
    storage_replacement,
    "SEMANTIC_STORAGE_ROOT",
)


# ============================================================
# 3. STARTUP ROOT
# ============================================================

text = replace_once(
    text,
    (
        "PRODUCTION_REFERENCE_PRIORITY_DECISIONS, "
        "PRODUCTION_REFERENCE_MEDIA"
    ),
    (
        "PRODUCTION_REFERENCE_PRIORITY_DECISIONS, "
        "PRODUCTION_REFERENCE_SEMANTIC_ANALYSES, "
        "PRODUCTION_REFERENCE_MEDIA"
    ),
    "STARTUP_STORAGE_ROOT",
)


# ============================================================
# 4. CONTRACTS + STRICT SEMANTIC SCHEMA
# ============================================================

contract_anchor = (
    'REFERENCE_MECHANICAL_ANALYZER_VERSION = '
    '"SM3_REFERENCE_MECHANICAL_ANALYZER_V1"'
)


semantic_contracts = r'''
REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION = "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1"
REFERENCE_SEMANTIC_ANALYZER_VERSION = "SM3_REFERENCE_SEMANTIC_ANALYZER_V1"
REFERENCE_SEMANTIC_SCHEMA_VERSION = "SM3_REFERENCE_SEMANTIC_SCHEMA_V1"
REFERENCE_SEMANTIC_PROMPT_VERSION = "SM3_REFERENCE_SEMANTIC_PROMPT_V1"
REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION = "SM3_REFERENCE_SEMANTIC_PROVIDER_V1"

REFERENCE_SEMANTIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hook_duration_s": {
            "type": ["number", "null"]
        },
        "camera_motion": {
            "type": "string"
        },
        "subject_scale": {
            "type": "string"
        },
        "subject_coverage": {
            "type": ["number", "null"]
        },
        "text_density": {
            "type": "string"
        },
        "text_position": {
            "type": "string"
        },
        "transition_style": {
            "type": "string"
        },
        "speed_ramp": {
            "type": "string"
        },
        "identity_usage": {
            "type": "string"
        },
        "tattoo_presentation": {
            "type": "string"
        },
        "story_structure": {
            "type": "string"
        },
        "analysis_confidence": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100
        },
        "notes": {
            "type": "string"
        }
    },
    "required": [
        "hook_duration_s",
        "camera_motion",
        "subject_scale",
        "subject_coverage",
        "text_density",
        "text_position",
        "transition_style",
        "speed_ramp",
        "identity_usage",
        "tattoo_presentation",
        "story_structure",
        "analysis_confidence",
        "notes"
    ]
}
'''.strip()


text = replace_once(
    text,
    contract_anchor,
    (
        contract_anchor
        + "\n"
        + semantic_contracts
    ),
    "SEMANTIC_CONTRACTS",
)


# ============================================================
# 5. EXPLICIT REQUEST MODEL
# ============================================================

request_anchor = (
    "class ReferenceVideoAnalysisRequest(BaseModel):"
)


request_model = r'''
class ReferenceSemanticAnalysisRequest(BaseModel):
    reference_item_id: str
    acquisition_id: str
    mechanical_analysis_id: str
    priority_decision_id: str


'''.lstrip()


text = replace_once(
    text,
    request_anchor,
    request_model + request_anchor,
    "SEMANTIC_REQUEST_MODEL",
)


# ============================================================
# 6. PERSISTENCE / ELIGIBILITY / PROVIDER BOUNDARY
# ============================================================

helper_anchor = (
    "def _reference_video_analysis_dir("
)


helpers = r'''
def _reference_semantic_analysis_dir(
    profile_id: str,
    item_id: str,
) -> Path:
    return _ensure_under(
        PRODUCTION_REFERENCE_SEMANTIC_ANALYSES
        / _safe_component(profile_id)
        / _safe_component(item_id),
        PRODUCTION_REFERENCE_SEMANTIC_ANALYSES,
    )


def _reference_semantic_analysis_path(
    profile_id: str,
    item_id: str,
    analysis_id: str,
) -> Path:
    return _ensure_under(
        _reference_semantic_analysis_dir(
            profile_id,
            item_id,
        )
        / f"{_safe_component(analysis_id)}.json",
        PRODUCTION_REFERENCE_SEMANTIC_ANALYSES,
    )


def _verify_reference_semantic_analysis(
    rec: dict[str,Any],
) -> dict[str,Any]:

    if (
        rec.get("contract_version")
        != REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_MISMATCH",
        )

    if (
        rec.get("analyzer_version")
        != REFERENCE_SEMANTIC_ANALYZER_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYZER_VERSION_MISMATCH",
        )

    if (
        rec.get("semantic_schema_version")
        != REFERENCE_SEMANTIC_SCHEMA_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_SCHEMA_VERSION_MISMATCH",
        )

    if (
        rec.get("semantic_prompt_version")
        != REFERENCE_SEMANTIC_PROMPT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PROMPT_VERSION_MISMATCH",
        )

    expected=str(
        rec.get("semantic_analysis_sha256")
        or ""
    ).lower()

    if not re.fullmatch(
        r"[a-f0-9]{64}",
        expected,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_HASH_INVALID",
        )

    chk=dict(rec)

    chk.pop(
        "semantic_analysis_sha256",
        None,
    )

    if _canonical_sha256(chk)!=expected:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED",
        )

    if rec.get("copying_forbidden") is not True:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID",
        )

    if rec.get("foundation_override_allowed") is not False:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_FOUNDATION_POLICY_INVALID",
        )

    return rec


def _reference_semantic_load_acquisition(
    item: dict[str,Any],
    acquisition_id: str,
) -> dict[str,Any]:

    aid=str(
        acquisition_id
        or ""
    ).strip()

    if not aid:
        raise HTTPException(
            422,
            "REFERENCE_SEMANTIC_ACQUISITION_ID_REQUIRED",
        )

    path=_reference_media_path(
        item["reference_profile_id"],
        item["reference_item_id"],
        aid,
    )

    if not path.exists():
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ACQUISITION_NOT_FOUND",
        )

    rec=_verify_reference_media_acquisition(
        json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    )

    if (
        rec.get("reference_item_id")
        != item["reference_item_id"]
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ACQUISITION_ITEM_MISMATCH",
        )

    return rec


def _reference_semantic_load_mechanical(
    source_sha: str,
    mechanical_analysis_id: str,
) -> dict[str,Any]:

    mid=str(
        mechanical_analysis_id
        or ""
    ).strip()

    if not mid:
        raise HTTPException(
            422,
            "REFERENCE_SEMANTIC_MECHANICAL_ANALYSIS_ID_REQUIRED",
        )

    path=_reference_mechanical_analysis_path(
        source_sha,
        mid,
    )

    if not path.exists():
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MECHANICAL_ANALYSIS_NOT_FOUND",
        )

    rec=_verify_reference_mechanical_analysis(
        json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    )

    if (
        rec.get("mechanical_analysis_id")
        != mid
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MECHANICAL_ID_MISMATCH",
        )

    if (
        str(
            rec.get("source_sha256")
            or ""
        ).lower()
        != str(
            source_sha
            or ""
        ).lower()
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MECHANICAL_SOURCE_MISMATCH",
        )

    return rec


def _reference_semantic_contact_sheet(
    mechanical: dict[str,Any],
) -> Path:

    raw_path=str(
        mechanical.get(
            "contact_sheet_path"
        )
        or ""
    ).strip()

    expected_sha=str(
        mechanical.get(
            "contact_sheet_sha256"
        )
        or ""
    ).lower()

    if not raw_path:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONTACT_SHEET_REQUIRED",
        )

    if not re.fullmatch(
        r"[a-f0-9]{64}",
        expected_sha,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID",
        )

    path=Path(
        raw_path
    )

    if (
        not path.exists()
        or not path.is_file()
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONTACT_SHEET_NOT_FOUND",
        )

    actual_sha=sha256_file(
        path
    ).lower()

    if actual_sha!=expected_sha:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_MISMATCH",
        )

    return path


def _reference_semantic_authorizing_priority(
    item: dict[str,Any],
    source_sha: str,
    mechanical: dict[str,Any],
    priority_decision_id: str,
) -> dict[str,Any]:

    pid=str(
        priority_decision_id
        or ""
    ).strip()

    if not pid:
        raise HTTPException(
            422,
            "REFERENCE_SEMANTIC_PRIORITY_DECISION_ID_REQUIRED",
        )

    decisions=(
        _reference_priority_decisions_for_item(
            item["reference_item_id"]
        )
    )

    requested=None

    for rec in decisions:
        if (
            rec.get(
                "priority_decision_id"
            )
            == pid
        ):
            requested=(
                _verify_reference_priority_decision(
                    rec
                )
            )
            break

    if requested is None:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PRIORITY_DECISION_NOT_FOUND",
        )

    if (
        str(
            requested.get(
                "source_sha256"
            )
            or ""
        ).lower()
        != str(
            source_sha
            or ""
        ).lower()
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PRIORITY_SOURCE_MISMATCH",
        )

    if (
        requested.get(
            "mechanical_analysis_id"
        )
        != mechanical.get(
            "mechanical_analysis_id"
        )
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PRIORITY_MECHANICAL_MISMATCH",
        )

    evidence=(
        _reference_priority_current_evidence(
            item,
            mechanical,
        )
    )

    current_fingerprint=(
        evidence[
            "evidence_fingerprint"
        ]
    )

    if (
        requested.get(
            "evidence_fingerprint"
        )
        != current_fingerprint
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_STALE",
        )

    current_candidates=[
        _verify_reference_priority_decision(
            rec
        )
        for rec in decisions
        if (
            str(
                rec.get(
                    "source_sha256"
                )
                or ""
            ).lower()
            == str(
                source_sha
                or ""
            ).lower()
            and
            rec.get(
                "engine_version"
            )
            == REFERENCE_PRIORITY_ENGINE_VERSION
            and
            rec.get(
                "mechanical_analysis_id"
            )
            == mechanical.get(
                "mechanical_analysis_id"
            )
            and
            rec.get(
                "evidence_fingerprint"
            )
            == current_fingerprint
        )
    ]

    if not current_candidates:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_REQUIRED",
        )

    current=max(
        current_candidates,
        key=lambda rec:(
            str(
                rec.get(
                    "created_at"
                )
                or ""
            ),
            str(
                rec.get(
                    "priority_decision_id"
                )
                or ""
            ),
        ),
    )

    if (
        current.get(
            "priority_decision_id"
        )
        != pid
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PRIORITY_DECISION_NOT_CURRENT",
        )

    if not bool(
        current.get(
            "semantic_analysis_allowed"
        )
    ):
        raise HTTPException(
            409,
            (
                "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:"
                + str(
                    current.get(
                        "decision"
                    )
                    or "UNKNOWN"
                )
            ),
        )

    return current


def _reference_semantic_provider_analyze(
    contact_sheet: Path,
    item: dict[str,Any],
    mechanical: dict[str,Any],
) -> tuple[dict[str,Any],Optional[str]]:

    if VISION_PROVIDER!="openai":
        raise HTTPException(
            501,
            (
                "REFERENCE_SEMANTIC_PROVIDER_NOT_IMPLEMENTED:"
                + VISION_PROVIDER
            ),
        )

    if not OPENAI_API_KEY:
        raise HTTPException(
            503,
            "OPENAI_API_KEY_NOT_CONFIGURED",
        )

    mechanical_hint=json.dumps(
        mechanical.get(
            "mechanical"
        )
        or {},
        ensure_ascii=False,
        separators=(",",":"),
    )[:7000]

    prompt=f"""
Você é o analisador SEMÂNTICO DESCRITIVO do Projeto SM3.

A imagem é uma contact sheet CANÔNICA de um vídeo de referência externa.
A evidência mecânica abaixo foi calculada deterministicamente pelo Worker
e é a fonte objetiva de verdade.

Sua tarefa NÃO é recalcular cortes, cor, áudio, beat sync, duração ou
qualquer outra medição mecânica.

Extraia somente evidência semântica/visual abstrata:
- hook visual quando realmente inferível;
- movimento aparente de câmera;
- escala e cobertura do assunto;
- densidade e posição de texto;
- estilo aparente de transição;
- speed ramp somente se houver evidência visual suficiente;
- uso abstrato de identidade;
- apresentação da tattoo/processo/resultado;
- estrutura narrativa aparente.

Use UNKNOWN e null quando a contact sheet não sustentar uma conclusão.
Não converta ausência de evidência em certeza.

NÃO identifique pessoas.
NÃO copie identidade, marca, layout exato, personagens, desenhos ou
composição autoral.
NÃO avalie se o conteúdo é bom ou ruim.
NÃO altere a FOUNDATION do SM3.

Item:
network={item.get("network")}
item_type={item.get("item_type")}
caption={str(item.get("caption") or "")[:1500]}

Evidência mecânica canônica:
{mechanical_hint}

Responda estritamente no schema fornecido.
""".strip()

    payload={
        "model":VISION_MODEL,
        "input":[
            {
                "role":"user",
                "content":[
                    {
                        "type":"input_text",
                        "text":prompt,
                    },
                    {
                        "type":"input_image",
                        "image_url":
                            _image_data_url(
                                contact_sheet
                            ),
                        "detail":"high",
                    },
                ],
            }
        ],
        "text":{
            "format":{
                "type":"json_schema",
                "name":
                    "sm3_reference_semantic_analysis",
                "description":
                    "Abstract descriptive semantic features from canonical reference evidence.",
                "schema":
                    REFERENCE_SEMANTIC_SCHEMA,
                "strict":True,
            }
        },
    }

    headers={
        "Authorization":
            f"Bearer {OPENAI_API_KEY}",
        "Content-Type":
            "application/json",
    }

    response=None
    last_error=None

    for attempt in range(
        1,
        4,
    ):
        try:
            with httpx.Client(
                timeout=
                    VISION_TIMEOUT_SECONDS
            ) as client:
                response=client.post(
                    f"{OPENAI_BASE_URL}/responses",
                    headers={
                        **headers,
                        "X-Client-Request-Id":
                            (
                                "sm3-ref-semantic-"
                                + item[
                                    "reference_item_id"
                                ]
                                + f"-a{attempt}"
                            ),
                    },
                    json=payload,
                )

        except Exception as exc:
            last_error=(
                "NETWORK:"
                + type(exc).__name__
                + ":"
                + str(exc)
            )

            if attempt<3:
                time.sleep(
                    1.25
                    * (
                        2
                        ** (
                            attempt
                            - 1
                        )
                    )
                )
                continue

            raise HTTPException(
                502,
                (
                    "REFERENCE_SEMANTIC_PROVIDER_NETWORK_ERROR_AFTER_RETRY:"
                    + last_error
                ),
            )

        if response.status_code<400:
            break

        request_id=response.headers.get(
            "x-request-id",
            "",
        )

        last_error=(
            "HTTP_"
            + str(
                response.status_code
            )
            + ":request_id="
            + request_id
            + ":"
            + response.text[-4000:]
        )

        if (
            response.status_code
            in {
                408,
                409,
                429,
                500,
                502,
                503,
                504,
            }
            and
            attempt<3
        ):
            time.sleep(
                1.25
                * (
                    2
                    ** (
                        attempt
                        - 1
                    )
                )
            )
            continue

        raise HTTPException(
            502,
            (
                "REFERENCE_SEMANTIC_PROVIDER_ERROR:"
                + last_error
            ),
        )

    if (
        response is None
        or
        response.status_code>=400
    ):
        raise HTTPException(
            502,
            (
                "REFERENCE_SEMANTIC_PROVIDER_FAILED_AFTER_RETRY:"
                + (
                    last_error
                    or "UNKNOWN"
                )
            ),
        )

    data=response.json()

    raw_text=_extract_response_text(
        data
    )

    try:
        raw=json.loads(
            raw_text
        )

    except Exception:
        raise HTTPException(
            502,
            (
                "REFERENCE_SEMANTIC_PROVIDER_JSON_PARSE_ERROR:"
                + raw_text[:2000]
            ),
        )

    return (
        raw,
        data.get(
            "id"
        ),
    )


'''.lstrip()


text = replace_once(
    text,
    helper_anchor,
    helpers + helper_anchor,
    "SEMANTIC_HELPERS",
)


# ============================================================
# 7. SEMANTIC ROUTES
# ============================================================

route_anchor = (
    '@app.post("/production/reference-corpus/video-analysis")'
)


semantic_routes = r'''
@app.post("/production/reference-corpus/semantic-analysis")
def production_reference_semantic_analysis(
    req: ReferenceSemanticAnalysisRequest,
):
    item=_require_reference_item_active(
        req.reference_item_id
    )

    if item.get("item_type") not in {
        "REEL",
        "VIDEO",
        "STORY",
    }:
        raise HTTPException(
            422,
            "REFERENCE_SEMANTIC_ITEM_TYPE_NOT_VIDEO",
        )

    acquisition=(
        _reference_semantic_load_acquisition(
            item,
            req.acquisition_id,
        )
    )

    source,media_artifact=(
        _resolve_reference_acquisition_source(
            acquisition
        )
    )

    if media_artifact is None:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MEDIA_ARTIFACT_REQUIRED",
        )

    source_sha=str(
        acquisition.get(
            "source_sha256"
        )
        or ""
    ).lower()

    if not re.fullmatch(
        r"[a-f0-9]{64}",
        source_sha,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_SOURCE_SHA_INVALID",
        )

    if (
        sha256_file(
            source
        ).lower()
        != source_sha
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_SOURCE_SHA_MISMATCH",
        )

    media_artifact_id=str(
        media_artifact.get(
            "media_artifact_id"
        )
        or ""
    )

    if (
        media_artifact_id
        != str(
            acquisition.get(
                "media_artifact_id"
            )
            or ""
        )
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MEDIA_ARTIFACT_MISMATCH",
        )

    mechanical=(
        _reference_semantic_load_mechanical(
            source_sha,
            req.mechanical_analysis_id,
        )
    )

    priority=(
        _reference_semantic_authorizing_priority(
            item,
            source_sha,
            mechanical,
            req.priority_decision_id,
        )
    )

    contact_sheet=(
        _reference_semantic_contact_sheet(
            mechanical
        )
    )

    identity={
        "reference_item_id":
            req.reference_item_id,

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical[
                "mechanical_analysis_id"
            ],

        "mechanical_analysis_sha256":
            mechanical[
                "mechanical_analysis_sha256"
            ],

        "semantic_analyzer_version":
            REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            REFERENCE_SEMANTIC_PROMPT_VERSION,

        "vision_provider":
            VISION_PROVIDER,

        "vision_model":
            VISION_MODEL,
    }

    analysis_id=(
        "RSA_"
        + _canonical_sha256(
            identity
        )[:32]
    )

    path=_reference_semantic_analysis_path(
        item[
            "reference_profile_id"
        ],
        req.reference_item_id,
        analysis_id,
    )

    if path.exists():
        old=(
            _verify_reference_semantic_analysis(
                json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )
            )
        )

        return {
            "ok":True,
            "reused_existing":True,
            "analysis":old,
        }

    semantic,vision_response_id=(
        _reference_semantic_provider_analyze(
            contact_sheet,
            item,
            mechanical,
        )
    )

    semantic_confidence=int(
        semantic.get(
            "analysis_confidence"
        )
        or 0
    )

    if (
        semantic_confidence<0
        or
        semantic_confidence>100
    ):
        raise HTTPException(
            502,
            "REFERENCE_SEMANTIC_CONFIDENCE_INVALID",
        )

    rec={
        "ok":True,

        "semantic_analysis_id":
            analysis_id,

        "contract_version":
            REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION,

        "analyzer_version":
            REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            REFERENCE_SEMANTIC_PROMPT_VERSION,

        "provider_contract_version":
            REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,

        "reference_item_id":
            req.reference_item_id,

        "reference_profile_id":
            item[
                "reference_profile_id"
            ],

        "acquisition_id":
            acquisition[
                "acquisition_id"
            ],

        "media_artifact_id":
            media_artifact_id,

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical[
                "mechanical_analysis_id"
            ],

        "mechanical_analysis_sha256":
            mechanical[
                "mechanical_analysis_sha256"
            ],

        "priority_decision_id":
            priority[
                "priority_decision_id"
            ],

        "priority_evidence_fingerprint":
            priority[
                "evidence_fingerprint"
            ],

        "vision_provider":
            VISION_PROVIDER,

        "vision_model":
            VISION_MODEL,

        "vision_response_id":
            vision_response_id,

        "semantic_confidence":
            semantic_confidence,

        "semantic":
            semantic,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "copying_forbidden":
            True,

        "foundation_override_allowed":
            False,
    }

    rec[
        "semantic_analysis_sha256"
    ]=_canonical_sha256(
        rec
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _write_revision_once(
        path,
        rec,
    )

    persisted=(
        _verify_reference_semantic_analysis(
            json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        )
    )

    return {
        "ok":True,
        "reused_existing":False,
        "analysis":persisted,
    }


@app.get("/production/reference-corpus/item/{item_id}/semantic-analyses")
def production_reference_semantic_analyses(
    item_id: str,
):
    item=_load_reference_item(
        item_id
    )

    directory=(
        _reference_semantic_analysis_dir(
            item[
                "reference_profile_id"
            ],
            item_id,
        )
    )

    records=[]

    if directory.exists():
        for path in sorted(
            directory.glob(
                "RSA_*.json"
            )
        ):
            records.append(
                _verify_reference_semantic_analysis(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )
            )

    return {
        "ok":True,
        "contract_version":
            REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION,
        "reference_item_id":
            item_id,
        "count":
            len(records),
        "semantic_analyses":
            records,
    }


@app.get("/production/reference-corpus/item/{item_id}/semantic-analysis/latest")
def production_reference_semantic_analysis_latest(
    item_id: str,
):
    result=(
        production_reference_semantic_analyses(
            item_id
        )
    )

    records=(
        result[
            "semantic_analyses"
        ]
    )

    if not records:
        raise HTTPException(
            404,
            "REFERENCE_SEMANTIC_ANALYSIS_NOT_FOUND",
        )

    latest=max(
        records,
        key=lambda rec:(
            str(
                rec.get(
                    "created_at"
                )
                or ""
            ),
            str(
                rec.get(
                    "semantic_analysis_id"
                )
                or ""
            ),
        ),
    )

    return {
        "ok":True,
        "analysis":latest,
    }


'''.lstrip()


text = replace_once(
    text,
    route_anchor,
    semantic_routes + route_anchor,
    "SEMANTIC_ROUTES",
)


# ============================================================
# 8. DISABLE LEGACY VIDEO GENERATION
#    Historical GET stays untouched.
# ============================================================

def replace_function_body(
    source: str,
    function_name: str,
    replacement: str,
) -> str:

    tree=ast.parse(
        source
    )

    matches=[
        node
        for node in tree.body
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and
            node.name==function_name
        )
    ]

    if len(matches)!=1:
        fail(
            "SM3_09C7_B1A_FUNCTION_ANCHOR_INVALID:"
            + function_name
            + ":"
            + str(
                len(matches)
            )
        )

    node=matches[0]

    lines=source.splitlines(
        keepends=True
    )

    start=node.lineno-1
    end=node.end_lineno

    replacement_text=(
        replacement.rstrip()
        + "\n"
    )

    return (
        "".join(
            lines[:start]
        )
        + replacement_text
        + "".join(
            lines[end:]
        )
    )


legacy_replacement = r'''
def production_reference_video_analysis(
    req: ReferenceVideoAnalysisRequest,
):
    _require_reference_item_active(
        req.reference_item_id
    )

    raise HTTPException(
        409,
        "REFERENCE_VIDEO_ANALYSIS_LEGACY_WRITE_DISABLED_USE_SEMANTIC_ANALYSIS",
    )
'''.lstrip()


text = replace_function_body(
    text,
    "production_reference_video_analysis",
    legacy_replacement,
)


# ============================================================
# 9. HEALTH CAPABILITY
# ============================================================

health_anchor = (
    '        "reference_video_analysis_contract": '
    'REFERENCE_VIDEO_ANALYSIS_CONTRACT_VERSION,'
)


health_semantic = r'''
        "reference_semantic_analysis": True,
        "reference_semantic_analysis_contract": REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION,
        "reference_semantic_analyzer": REFERENCE_SEMANTIC_ANALYZER_VERSION,
        "reference_semantic_schema": REFERENCE_SEMANTIC_SCHEMA_VERSION,
        "reference_semantic_prompt": REFERENCE_SEMANTIC_PROMPT_VERSION,
        "reference_semantic_provider_contract": REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,
        "reference_semantic_requires_explicit_ids": True,
        "reference_semantic_requires_current_priority": True,
        "reference_semantic_recalculates_mechanical": False,
        "reference_semantic_writes_feature_observation": False,
        "reference_semantic_local_path_persisted": False,
        "reference_video_analysis_legacy_write_disabled": True,
'''.rstrip()


text = replace_once(
    text,
    health_anchor,
    (
        health_anchor
        + "\n"
        + health_semantic
    ),
    "HEALTH_CAPABILITIES",
)


# ============================================================
# 10. CANDIDATE PYTHON PARSE
# ============================================================

try:
    tree=ast.parse(
        text,
        filename=str(
            WORKER
        ),
    )

except SyntaxError as exc:
    fail(
        (
            "SM3_09C7_B1A_CANDIDATE_SYNTAX_ERROR:"
            + str(
                exc.lineno
            )
            + ":"
            + str(
                exc.offset
            )
            + ":"
            + str(
                exc.msg
            )
        )
    )


functions={}

classes={}


for node in tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        functions[
            node.name
        ]=node

    if isinstance(
        node,
        ast.ClassDef,
    ):
        classes[
            node.name
        ]=node


lines=text.splitlines()


def segment(
    node: ast.AST,
) -> str:

    return "\n".join(
        lines[
            node.lineno-1:
            node.end_lineno
        ]
    )


def class_fields(
    name: str,
) -> list[str]:

    node=classes.get(
        name
    )

    if node is None:
        return []

    result=[]

    for child in node.body:

        if (
            isinstance(
                child,
                ast.AnnAssign,
            )
            and
            isinstance(
                child.target,
                ast.Name,
            )
        ):
            result.append(
                child.target.id
            )

    return result


checks=[]


def add(
    name: str,
    value: bool,
) -> None:

    checks.append({
        "check":name,
        "pass":bool(
            value
        ),
    })


# ============================================================
# 11. STATIC INVARIANTS BEFORE WRITE
# ============================================================

add(
    "VERSION_2_24_0",
    'WORKER_VERSION = "2.24.0"'
    in text,
)


add(
    "SEMANTIC_STORAGE_ROOT_ONCE",
    text.count(
        "PRODUCTION_REFERENCE_SEMANTIC_ANALYSES ="
    ) == 1,
)


add(
    "SEMANTIC_CONTRACT_ONCE",
    text.count(
        "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1"
    ) >= 1,
)


add(
    "SEMANTIC_ANALYZER_ONCE",
    text.count(
        "SM3_REFERENCE_SEMANTIC_ANALYZER_V1"
    ) >= 1,
)


add(
    "SEMANTIC_SCHEMA_VERSION_PRESENT",
    "SM3_REFERENCE_SEMANTIC_SCHEMA_V1"
    in text,
)


add(
    "SEMANTIC_PROMPT_VERSION_PRESENT",
    "SM3_REFERENCE_SEMANTIC_PROMPT_V1"
    in text,
)


add(
    "SEMANTIC_PROVIDER_CONTRACT_PRESENT",
    "SM3_REFERENCE_SEMANTIC_PROVIDER_V1"
    in text,
)


add(
    "REQUEST_MODEL_FOUND",
    "ReferenceSemanticAnalysisRequest"
    in classes,
)


add(
    "REQUEST_FIELDS_EXACT",
    class_fields(
        "ReferenceSemanticAnalysisRequest"
    )
    == [
        "reference_item_id",
        "acquisition_id",
        "mechanical_analysis_id",
        "priority_decision_id",
    ],
)


semantic_fn=functions.get(
    "production_reference_semantic_analysis"
)


provider_fn=functions.get(
    "_reference_semantic_provider_analyze"
)


legacy_fn=functions.get(
    "production_reference_video_analysis"
)


add(
    "SEMANTIC_ENDPOINT_FOUND",
    semantic_fn is not None,
)


add(
    "SEMANTIC_PROVIDER_BOUNDARY_FOUND",
    provider_fn is not None,
)


add(
    "LEGACY_ENDPOINT_FOUND",
    legacy_fn is not None,
)


semantic_src=(
    segment(
        semantic_fn
    )
    if semantic_fn
    else ""
)


provider_src=(
    segment(
        provider_fn
    )
    if provider_fn
    else ""
)


legacy_src=(
    segment(
        legacy_fn
    )
    if legacy_fn
    else ""
)


add(
    "SEMANTIC_NO_LOCAL_MEDIA_REQUEST",
    "local_media_ref"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_PREFERENCE_SIGNAL",
    "preference_signal"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_REQUEST_NOTES",
    "req.notes"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_CONTACT_REGENERATION",
    "make_contact_sheet"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_CUT_RECOMPUTE",
    "_reference_cut_metrics"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_AUDIO_RECOMPUTE",
    "_reference_audio_onsets"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_COLOR_RECOMPUTE",
    "_reference_color_stats"
    not in semantic_src,
)


add(
    "SEMANTIC_NO_FEATURE_WRITE",
    (
        "production_reference_feature"
        not in semantic_src
        and
        "ReferenceFeatureObservationRequest"
        not in semantic_src
    ),
)


add(
    "ENGINE_NO_DIRECT_HTTP",
    "httpx.Client"
    not in semantic_src,
)


add(
    "PROVIDER_OWNS_HTTP",
    "httpx.Client"
    in provider_src,
)


add(
    "SEMANTIC_USES_EXPLICIT_ACQUISITION",
    "_reference_semantic_load_acquisition"
    in semantic_src,
)


add(
    "SEMANTIC_USES_CANONICAL_MECHANICAL",
    "_reference_semantic_load_mechanical"
    in semantic_src,
)


add(
    "SEMANTIC_USES_EXPLICIT_PRIORITY",
    "_reference_semantic_authorizing_priority"
    in semantic_src,
)


add(
    "SEMANTIC_USES_CANONICAL_CONTACT",
    "_reference_semantic_contact_sheet"
    in semantic_src,
)


add(
    "SEMANTIC_ID_RSA",
    '"RSA_"'
    in semantic_src,
)


add(
    "SEMANTIC_WRITES_ONCE",
    "_write_revision_once"
    in semantic_src,
)


add(
    "SEMANTIC_HAS_NO_LOCAL_PATH_PROVENANCE",
    (
        "source_resolved_path"
        not in semantic_src
        and
        "contact_sheet_path"
        not in semantic_src
    ),
)


add(
    "LEGACY_WRITE_DISABLED",
    "REFERENCE_VIDEO_ANALYSIS_LEGACY_WRITE_DISABLED_USE_SEMANTIC_ANALYSIS"
    in legacy_src,
)


add(
    "LEGACY_NO_VISION_CALL",
    "_reference_video_vision"
    not in legacy_src,
)


add(
    "LEGACY_NO_MECHANICAL_RECOMPUTE",
    (
        "make_contact_sheet"
        not in legacy_src
        and
        "_reference_cut_metrics"
        not in legacy_src
        and
        "_reference_audio_onsets"
        not in legacy_src
        and
        "_reference_color_stats"
        not in legacy_src
    ),
)


add(
    "LEGACY_NO_FEATURE_WRITE",
    "production_reference_feature"
    not in legacy_src,
)


add(
    "HISTORICAL_VIDEO_GET_PRESERVED",
    "production_reference_video_analysis_latest"
    in functions,
)


add(
    "SEMANTIC_LIST_READER_PRESENT",
    "production_reference_semantic_analyses"
    in functions,
)


add(
    "SEMANTIC_LATEST_READER_PRESENT",
    "production_reference_semantic_analysis_latest"
    in functions,
)


add(
    "HEALTH_SEMANTIC_EXPORTED",
    '"reference_semantic_analysis": True'
    in text,
)


add(
    "HEALTH_NO_MECHANICAL_RECALC",
    '"reference_semantic_recalculates_mechanical": False'
    in text,
)


add(
    "HEALTH_NO_FEATURE_WRITE",
    '"reference_semantic_writes_feature_observation": False'
    in text,
)


add(
    "HEALTH_NO_LOCAL_PATH_PERSISTENCE",
    '"reference_semantic_local_path_persisted": False'
    in text,
)


# Old helper may remain for historical source compatibility,
# but there must be no caller after the migration.

vision_callers=[]


for name,node in functions.items():

    for child in ast.walk(
        node
    ):
        if not isinstance(
            child,
            ast.Call,
        ):
            continue

        fn=child.func

        if (
            isinstance(
                fn,
                ast.Name,
            )
            and
            fn.id
            == "_reference_video_vision"
        ):
            vision_callers.append(
                name
            )


add(
    "LEGACY_VISION_HELPER_HAS_ZERO_CALLERS",
    len(
        vision_callers
    ) == 0,
)


# Objective mechanical values are forbidden from the semantic schema.

schema_node=None


for node in tree.body:

    if not isinstance(
        node,
        ast.Assign,
    ):
        continue

    for target in node.targets:

        if (
            isinstance(
                target,
                ast.Name,
            )
            and
            target.id
            == "REFERENCE_SEMANTIC_SCHEMA"
        ):
            schema_node=node


schema_src=(
    segment(
        schema_node
    )
    if schema_node
    else ""
)


for forbidden_field in (
    "cuts_per_10s",
    "median_shot_s",
    "beat_sync",
    "color_contrast",
    "color_saturation",
    "color_temperature",
    "sharpness_grain",
):
    add(
        (
            "SCHEMA_FORBIDS_"
            + forbidden_field.upper()
        ),
        forbidden_field
        not in schema_src,
    )


failed=[
    row
    for row in checks
    if not row["pass"]
]


if failed:
    REPORT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT.write_text(
        json.dumps(
            {
                "phase":
                    "09C7-B1A",

                "status":
                    "CANDIDATE_REJECTED",

                "source_sha_before":
                    before_sha,

                "candidate_checks":
                    checks,

                "failed_checks":
                    [
                        row["check"]
                        for row in failed
                    ],

                "host_written":
                    False,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fail(
        "SM3_09C7_B1A_CANDIDATE_STATIC_GATE_FAILED:"
        + ",".join(
            row["check"]
            for row in failed
        )
    )


# ============================================================
# 12. ATOMIC HOST WRITE
# ============================================================

candidate_bytes=text.encode(
    "utf-8"
)

candidate_sha=sha256_bytes(
    candidate_bytes
)


tmp=WORKER.with_name(
    WORKER.name
    + ".09C7_B1A.tmp"
)


tmp.write_bytes(
    candidate_bytes
)


# Re-parse exact bytes that will replace source.

written_candidate=tmp.read_text(
    encoding="utf-8"
)


ast.parse(
    written_candidate,
    filename=str(
        tmp
    ),
)


tmp.replace(
    WORKER
)


after_bytes=WORKER.read_bytes()

after_sha=sha256_bytes(
    after_bytes
)


if after_sha!=candidate_sha:
    fail(
        "SM3_09C7_B1A_POST_WRITE_SHA_MISMATCH"
    )


if after_sha==before_sha:
    fail(
        "SM3_09C7_B1A_SOURCE_DID_NOT_CHANGE"
    )


# ============================================================
# 13. REPORT
# ============================================================

report={
    "phase":
        "09C7-B1A",

    "status":
        "HOST_STRUCTURAL_IMPLEMENTATION_WRITTEN",

    "worker_version_before":
        "2.23.1",

    "worker_version_after":
        "2.24.0",

    "source_sha_before":
        before_sha,

    "source_sha_after":
        after_sha,

    "candidate_check_count":
        len(
            checks
        ),

    "candidate_pass_count":
        len(
            checks
        ),

    "candidate_fail_count":
        0,

    "vision_helper_callers_after":
        vision_callers,

    "host_written":
        True,

    "runtime_deployed":
        False,

    "model_called":
        False,

    "semantic_record_created":
        False,

    "contracts":{
        "semantic_analysis":
            "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",

        "semantic_analyzer":
            "SM3_REFERENCE_SEMANTIC_ANALYZER_V1",

        "semantic_schema":
            "SM3_REFERENCE_SEMANTIC_SCHEMA_V1",

        "semantic_prompt":
            "SM3_REFERENCE_SEMANTIC_PROMPT_V1",

        "semantic_provider":
            "SM3_REFERENCE_SEMANTIC_PROVIDER_V1",
    },

    "routes":[
        "/production/reference-corpus/semantic-analysis",
        "/production/reference-corpus/item/{item_id}/semantic-analyses",
        "/production/reference-corpus/item/{item_id}/semantic-analysis/latest",
    ],

    "checks":
        checks,
}


REPORT.parent.mkdir(
    parents=True,
    exist_ok=True,
)


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "SM3_09C7_B1A_PATCHER_PASS"
)

print(
    "HOST_SHA_BEFORE="
    + before_sha
)

print(
    "HOST_SHA_AFTER="
    + after_sha
)

print(
    "WORKER_VERSION_AFTER=2.24.0"
)

print(
    "STRUCTURAL_CHECK_COUNT="
    + str(
        len(checks)
    )
)

print(
    "STRUCTURAL_PASS_COUNT="
    + str(
        len(checks)
    )
)

print(
    "STRUCTURAL_FAIL_COUNT=0"
)

print(
    "VISION_HELPER_CALLER_COUNT_AFTER="
    + str(
        len(
            vision_callers
        )
    )
)

print(
    "HOST_WRITTEN=True"
)

print(
    "RUNTIME_DEPLOYED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "SEMANTIC_RECORD_CREATED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)

