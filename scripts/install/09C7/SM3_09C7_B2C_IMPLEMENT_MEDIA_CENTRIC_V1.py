from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import re
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = (
    ROOT
    / "worker"
    / "worker_service.py"
)

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B2C_MEDIA_CENTRIC_IMPLEMENTATION.json"
)

EXPECTED_SHA = (
    "8ca08d498d41cb732341c368d8aaa03e"
    "252a4c6eeef81a430201199a2e05f882"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(code: str) -> None:
    raise SystemExit(code)


def replace_function(
    source: str,
    name: str,
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
            node.name==name
        )
    ]

    if len(matches)!=1:

        fail(
            "SM3_09C7_B2C_FUNCTION_COUNT_INVALID:"
            + name
            + ":"
            + str(len(matches))
        )

    node=matches[0]

    lines=source.splitlines(
        keepends=True
    )

    return (
        "".join(
            lines[:node.lineno-1]
        )
        + replacement.rstrip()
        + "\n\n"
        + "".join(
            lines[node.end_lineno:]
        )
    )


def source_of_function(
    source: str,
    name: str,
) -> str:

    tree=ast.parse(
        source
    )

    lines=source.splitlines()

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
            node.name==name
        )
    ]

    if len(matches)!=1:
        return ""

    node=matches[0]

    return "\n".join(
        lines[
            node.lineno-1:
            node.end_lineno
        ]
    )


def function_args(
    source: str,
    name: str,
) -> list[str]:

    tree=ast.parse(
        source
    )

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
            node.name==name
        ):

            return [
                arg.arg
                for arg in node.args.args
            ]

    return []


def assigned_dict_keys(
    source: str,
    function_name: str,
    variable_name: str,
):

    tree=ast.parse(
        source
    )

    fn=None

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
            node.name==function_name
        ):
            fn=node
            break

    if fn is None:
        return None

    matches=[]

    for node in ast.walk(
        fn
    ):

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not isinstance(
            node.value,
            ast.Dict,
        ):
            continue

        if not any(
            isinstance(
                target,
                ast.Name,
            )
            and
            target.id==variable_name
            for target in node.targets
        ):
            continue

        keys=[]

        for key in node.value.keys:

            if isinstance(
                key,
                ast.Constant,
            ):
                keys.append(
                    str(key.value)
                )

            else:
                keys.append(
                    None
                )

        matches.append(
            keys
        )

    if len(matches)!=1:
        return None

    return matches[0]


raw=WORKER.read_bytes()

before_sha=sha256_bytes(
    raw
)


if before_sha!=EXPECTED_SHA:

    fail(
        "SM3_09C7_B2C_SOURCE_SHA_INVALID:"
        + before_sha
    )


text=WORKER.read_text(
    encoding="utf-8-sig"
)


if text.count(
    'WORKER_VERSION = "2.24.0"'
)!=1:

    fail(
        "SM3_09C7_B2C_WORKER_VERSION_INVALID"
    )


# ============================================================
# 1. MEDIA-CENTRIC STORAGE
# ============================================================

text=replace_function(
    text,
    "_reference_semantic_analysis_dir",
    r'''
def _reference_semantic_analysis_dir(
    source_sha256: str,
) -> Path:

    source_sha=str(
        source_sha256
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

    return _ensure_under(
        PRODUCTION_REFERENCE_SEMANTIC_ANALYSES
        / source_sha[:2]
        / source_sha,
        PRODUCTION_REFERENCE_SEMANTIC_ANALYSES,
    )
'''.lstrip(),
)


text=replace_function(
    text,
    "_reference_semantic_analysis_path",
    r'''
def _reference_semantic_analysis_path(
    source_sha256: str,
    analysis_id: str,
) -> Path:

    return _ensure_under(
        _reference_semantic_analysis_dir(
            source_sha256
        )
        / f"{_safe_component(analysis_id)}.json",
        PRODUCTION_REFERENCE_SEMANTIC_ANALYSES,
    )


def _reference_semantic_source_shas_for_item(
    item_id: str,
) -> tuple[dict[str,Any],list[str]]:

    item=_load_reference_item(
        item_id
    )

    media_dir=_reference_media_dir(
        item["reference_profile_id"],
        item_id,
    )

    source_shas=set()

    if media_dir.exists():

        for path in sorted(
            media_dir.glob(
                "RM_*.json"
            )
        ):

            acquisition=(
                _verify_reference_media_acquisition(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )
            )

            if (
                acquisition.get(
                    "reference_item_id"
                )
                != item_id
            ):
                raise HTTPException(
                    409,
                    "REFERENCE_SEMANTIC_READER_ACQUISITION_ITEM_MISMATCH",
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
                    "REFERENCE_SEMANTIC_READER_SOURCE_SHA_INVALID",
                )

            source_shas.add(
                source_sha
            )

    return (
        item,
        sorted(
            source_shas
        ),
    )
'''.lstrip(),
)


# ============================================================
# 2. MEDIA-CENTRIC RSA VERIFIER
# ============================================================

text=replace_function(
    text,
    "_verify_reference_semantic_analysis",
    r'''
def _verify_reference_semantic_analysis(
    rec: dict[str,Any],
) -> dict[str,Any]:

    # --------------------------------------------------------
    # Contract versions
    # --------------------------------------------------------

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

    if (
        rec.get("provider_contract_version")
        != REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_MISMATCH",
        )


    # --------------------------------------------------------
    # Creation provenance.
    #
    # These fields describe the context that authorized the
    # FIRST provider generation. They do not define identity.
    # --------------------------------------------------------

    creation_reference_item_id=str(
        rec.get(
            "creation_reference_item_id"
        )
        or ""
    ).strip()

    creation_reference_profile_id=str(
        rec.get(
            "creation_reference_profile_id"
        )
        or ""
    ).strip()

    creation_acquisition_id=str(
        rec.get(
            "creation_acquisition_id"
        )
        or ""
    ).strip()

    creation_priority_decision_id=str(
        rec.get(
            "creation_priority_decision_id"
        )
        or ""
    ).strip()

    media_artifact_id=str(
        rec.get(
            "media_artifact_id"
        )
        or ""
    ).strip()

    mechanical_analysis_id=str(
        rec.get(
            "mechanical_analysis_id"
        )
        or ""
    ).strip()

    vision_provider=str(
        rec.get(
            "vision_provider"
        )
        or ""
    ).strip()

    vision_model=str(
        rec.get(
            "vision_model"
        )
        or ""
    ).strip()


    required_strings={
        "creation_reference_item_id":
            creation_reference_item_id,

        "creation_reference_profile_id":
            creation_reference_profile_id,

        "creation_acquisition_id":
            creation_acquisition_id,

        "creation_priority_decision_id":
            creation_priority_decision_id,

        "media_artifact_id":
            media_artifact_id,

        "mechanical_analysis_id":
            mechanical_analysis_id,

        "vision_provider":
            vision_provider,

        "vision_model":
            vision_model,
    }


    for field,value in required_strings.items():

        if not value:

            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_PROVENANCE_REQUIRED:"
                    + field
                ),
            )


    source_sha=str(
        rec.get(
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


    mechanical_sha=str(
        rec.get(
            "mechanical_analysis_sha256"
        )
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        mechanical_sha,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MECHANICAL_HASH_INVALID",
        )


    contact_sheet_sha=str(
        rec.get(
            "contact_sheet_sha256"
        )
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        contact_sheet_sha,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID",
        )


    priority_fingerprint=str(
        rec.get(
            "creation_priority_evidence_fingerprint"
        )
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        priority_fingerprint,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PRIORITY_EVIDENCE_HASH_INVALID",
        )


    # --------------------------------------------------------
    # Item / execution context is forbidden as direct RSA state.
    # Creation context uses explicit creation_* names.
    # --------------------------------------------------------

    for forbidden_field in (
        "reference_item_id",
        "reference_profile_id",
        "acquisition_id",
        "priority_decision_id",
        "priority_evidence_fingerprint",
        "local_media_ref",
        "source_resolved_path",
        "contact_sheet_path",
        "preference_signal",
        "network",
        "item_type",
        "caption",
    ):

        if forbidden_field in rec:

            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD:"
                    + forbidden_field
                ),
            )


    # --------------------------------------------------------
    # Semantic payload
    # --------------------------------------------------------

    semantic=rec.get(
        "semantic"
    )


    if not isinstance(
        semantic,
        dict,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_INVALID",
        )


    schema=REFERENCE_SEMANTIC_SCHEMA


    expected_fields=set(
        schema.get(
            "properties",
            {},
        ).keys()
    )


    required_fields=set(
        schema.get(
            "required",
            [],
        )
    )


    actual_fields=set(
        semantic.keys()
    )


    if actual_fields!=expected_fields:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID",
        )


    if not required_fields.issubset(
        actual_fields
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_REQUIRED_FIELDS_MISSING",
        )


    nullable_number_fields={
        "hook_duration_s",
        "subject_coverage",
    }


    for field in nullable_number_fields:

        value=semantic.get(
            field
        )

        if value is None:
            continue

        if (
            isinstance(
                value,
                bool,
            )
            or
            not isinstance(
                value,
                (
                    int,
                    float,
                ),
            )
        ):
            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID:"
                    + field
                ),
            )


    string_fields=(
        expected_fields
        - nullable_number_fields
        - {
            "analysis_confidence"
        }
    )


    for field in string_fields:

        if not isinstance(
            semantic.get(
                field
            ),
            str,
        ):
            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID:"
                    + field
                ),
            )


    payload_confidence=semantic.get(
        "analysis_confidence"
    )


    if (
        isinstance(
            payload_confidence,
            bool,
        )
        or
        not isinstance(
            payload_confidence,
            int,
        )
        or
        payload_confidence<0
        or
        payload_confidence>100
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_CONFIDENCE_INVALID",
        )


    record_confidence=rec.get(
        "semantic_confidence"
    )


    if (
        isinstance(
            record_confidence,
            bool,
        )
        or
        not isinstance(
            record_confidence,
            int,
        )
        or
        record_confidence<0
        or
        record_confidence>100
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONFIDENCE_INVALID",
        )


    if record_confidence!=payload_confidence:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH",
        )


    # --------------------------------------------------------
    # MEDIA-CENTRIC deterministic RSA identity
    # --------------------------------------------------------

    identity={
        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical_analysis_id,

        "mechanical_analysis_sha256":
            mechanical_sha,

        "contact_sheet_sha256":
            contact_sheet_sha,

        "semantic_analyzer_version":
            REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            REFERENCE_SEMANTIC_PROMPT_VERSION,

        "semantic_provider_contract_version":
            REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,

        "vision_provider":
            vision_provider,

        "vision_model":
            vision_model,
    }


    expected_analysis_id=(
        "RSA_"
        + _canonical_sha256(
            identity
        )[:32]
    )


    actual_analysis_id=str(
        rec.get(
            "semantic_analysis_id"
        )
        or ""
    )


    if actual_analysis_id!=expected_analysis_id:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_IDENTITY_MISMATCH",
        )


    # --------------------------------------------------------
    # Safety policy
    # --------------------------------------------------------

    if rec.get(
        "copying_forbidden"
    ) is not True:

        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID",
        )


    if rec.get(
        "foundation_override_allowed"
    ) is not False:

        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_FOUNDATION_POLICY_INVALID",
        )


    # --------------------------------------------------------
    # Canonical record integrity
    # --------------------------------------------------------

    expected_hash=str(
        rec.get(
            "semantic_analysis_sha256"
        )
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        expected_hash,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_HASH_INVALID",
        )


    chk=dict(
        rec
    )


    chk.pop(
        "semantic_analysis_sha256",
        None,
    )


    if _canonical_sha256(
        chk
    )!=expected_hash:

        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED",
        )


    return rec
'''.lstrip(),
)


# ============================================================
# 3. PROVIDER BOUNDARY — NO ITEM CONTEXT
# ============================================================

text=replace_function(
    text,
    "_reference_semantic_provider_analyze",
    r'''
def _reference_semantic_provider_analyze(
    contact_sheet: Path,
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

Não utilize caption, perfil, rede social, métricas, preferência,
ReferenceItem ou qualquer outro contexto externo à mídia canônica.

Evidência mecânica canônica:
{mechanical_hint}

Responda estritamente no schema fornecido.
""".strip()


    payload={
        "model":
            VISION_MODEL,

        "input":[
            {
                "role":
                    "user",

                "content":[
                    {
                        "type":
                            "input_text",

                        "text":
                            prompt,
                    },
                    {
                        "type":
                            "input_image",

                        "image_url":
                            _image_data_url(
                                contact_sheet
                            ),

                        "detail":
                            "high",
                    },
                ],
            }
        ],

        "text":{
            "format":{
                "type":
                    "json_schema",

                "name":
                    "sm3_reference_semantic_analysis",

                "description":
                    "Abstract descriptive semantic features from canonical media evidence.",

                "schema":
                    REFERENCE_SEMANTIC_SCHEMA,

                "strict":
                    True,
            }
        },
    }


    headers={
        "Authorization":
            f"Bearer {OPENAI_API_KEY}",

        "Content-Type":
            "application/json",
    }


    source_sha=str(
        mechanical.get(
            "source_sha256"
        )
        or ""
    ).lower()


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
                                + source_sha[:16]
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

        semantic=json.loads(
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
        semantic,
        data.get(
            "id"
        ),
    )
'''.lstrip(),
)


# ============================================================
# 4. MEDIA-CENTRIC SEMANTIC ENGINE
# ============================================================

text=replace_function(
    text,
    "production_reference_semantic_analysis",
    r'''
def production_reference_semantic_analysis(
    req: ReferenceSemanticAnalysisRequest,
):

    item=_require_reference_item_active(
        req.reference_item_id
    )


    if item.get(
        "item_type"
    ) not in {
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


    contact_sheet=(
        _reference_semantic_contact_sheet(
            mechanical
        )
    )


    contact_sheet_sha=str(
        mechanical.get(
            "contact_sheet_sha256"
        )
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        contact_sheet_sha,
    ):

        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID",
        )


    requested_priority_id=str(
        req.priority_decision_id
        or ""
    ).strip()


    if not requested_priority_id:

        raise HTTPException(
            422,
            "REFERENCE_SEMANTIC_PRIORITY_DECISION_ID_REQUIRED",
        )


    # --------------------------------------------------------
    # MEDIA-CENTRIC IDENTITY
    # --------------------------------------------------------

    identity={
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

        "contact_sheet_sha256":
            contact_sheet_sha,

        "semantic_analyzer_version":
            REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            REFERENCE_SEMANTIC_PROMPT_VERSION,

        "semantic_provider_contract_version":
            REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,

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
        source_sha,
        analysis_id,
    )


    # --------------------------------------------------------
    # CACHE HIT:
    # item/acquisition/source/mechanical were already verified.
    # Priority generation permission is NOT needed to reuse
    # already-existing semantic evidence.
    # --------------------------------------------------------

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
            "ok":
                True,

            "reused_existing":
                True,

            "provider_called":
                False,

            "priority_generation_allow_checked":
                False,

            "request_context":{
                "reference_item_id":
                    req.reference_item_id,

                "acquisition_id":
                    req.acquisition_id,

                "mechanical_analysis_id":
                    req.mechanical_analysis_id,

                "priority_decision_id":
                    requested_priority_id,
            },

            "analysis":
                old,
        }


    # --------------------------------------------------------
    # CACHE MISS:
    # NOW Priority must authorize the expensive provider call.
    # --------------------------------------------------------

    priority=(
        _reference_semantic_authorizing_priority(
            item,
            source_sha,
            mechanical,
            requested_priority_id,
        )
    )


    semantic,vision_response_id=(
        _reference_semantic_provider_analyze(
            contact_sheet,
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
        "ok":
            True,

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

        "creation_reference_item_id":
            req.reference_item_id,

        "creation_reference_profile_id":
            item[
                "reference_profile_id"
            ],

        "creation_acquisition_id":
            acquisition[
                "acquisition_id"
            ],

        "creation_priority_decision_id":
            priority[
                "priority_decision_id"
            ],

        "creation_priority_evidence_fingerprint":
            priority[
                "evidence_fingerprint"
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

        "contact_sheet_sha256":
            contact_sheet_sha,

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
        "ok":
            True,

        "reused_existing":
            False,

        "provider_called":
            True,

        "priority_generation_allow_checked":
            True,

        "request_context":{
            "reference_item_id":
                req.reference_item_id,

            "acquisition_id":
                req.acquisition_id,

            "mechanical_analysis_id":
                req.mechanical_analysis_id,

            "priority_decision_id":
                requested_priority_id,
        },

        "analysis":
            persisted,
    }
'''.lstrip(),
)


# ============================================================
# 5. ITEM READER BECOMES CONTEXTUAL VIEW OVER MEDIA RSA
# ============================================================

text=replace_function(
    text,
    "production_reference_semantic_analyses",
    r'''
def production_reference_semantic_analyses(
    item_id: str,
):

    item,source_shas=(
        _reference_semantic_source_shas_for_item(
            item_id
        )
    )


    records=[]
    seen_ids=set()


    for source_sha in source_shas:

        directory=(
            _reference_semantic_analysis_dir(
                source_sha
            )
        )


        if not directory.exists():
            continue


        for path in sorted(
            directory.glob(
                "RSA_*.json"
            )
        ):

            rec=(
                _verify_reference_semantic_analysis(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )
            )


            if (
                str(
                    rec.get(
                        "source_sha256"
                    )
                    or ""
                ).lower()
                != source_sha
            ):

                raise HTTPException(
                    409,
                    "REFERENCE_SEMANTIC_READER_STORAGE_SOURCE_MISMATCH",
                )


            analysis_id=str(
                rec.get(
                    "semantic_analysis_id"
                )
                or ""
            )


            if analysis_id in seen_ids:
                continue


            seen_ids.add(
                analysis_id
            )


            records.append(
                rec
            )


    return {
        "ok":
            True,

        "contract_version":
            REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION,

        "reference_item_id":
            item_id,

        "reference_profile_id":
            item[
                "reference_profile_id"
            ],

        "source_sha256s":
            source_shas,

        "count":
            len(records),

        "semantic_analyses":
            records,
    }
'''.lstrip(),
)


text=replace_function(
    text,
    "production_reference_semantic_analysis_latest",
    r'''
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
        "ok":
            True,

        "reference_item_id":
            item_id,

        "analysis":
            latest,
    }
'''.lstrip(),
)


# ============================================================
# 6. HEALTH MUST DESCRIBE REAL CACHE / MEDIA-CENTRIC POLICY
# ============================================================

old_health = (
    '        "reference_semantic_requires_current_priority": True,'
)


new_health = '''        "reference_semantic_requires_current_priority": False,
        "reference_semantic_generation_requires_current_priority": True,
        "reference_semantic_cache_hit_requires_generation_allow": False,
        "reference_semantic_media_centric": True,
        "reference_semantic_item_context_in_provider": False,
        "reference_semantic_contact_sheet_hash_in_identity": True,
        "reference_semantic_storage_media_centric": True,'''


health_count=text.count(
    old_health
)


if health_count!=1:

    fail(
        "SM3_09C7_B2C_HEALTH_ANCHOR_INVALID:"
        + str(health_count)
    )


text=text.replace(
    old_health,
    new_health,
    1,
)


# ============================================================
# 7. CANDIDATE PARSE
# ============================================================

try:

    ast.parse(
        text,
        filename=str(WORKER),
    )

except SyntaxError as exc:

    fail(
        (
            "SM3_09C7_B2C_CANDIDATE_SYNTAX_ERROR:"
            + str(exc.lineno)
            + ":"
            + str(exc.offset)
            + ":"
            + str(exc.msg)
        )
    )


# ============================================================
# 8. ARCHITECTURAL CANDIDATE GATE
# ============================================================

checks=[]


def add(
    name: str,
    value: bool,
    detail="",
):

    checks.append({
        "check":
            name,

        "pass":
            bool(value),

        "detail":
            str(detail),
    })


expected_identity=[
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "contact_sheet_sha256",
    "semantic_analyzer_version",
    "semantic_schema_version",
    "semantic_prompt_version",
    "semantic_provider_contract_version",
    "vision_provider",
    "vision_model",
]


endpoint_identity=assigned_dict_keys(
    text,
    "production_reference_semantic_analysis",
    "identity",
)


verifier_identity=assigned_dict_keys(
    text,
    "_verify_reference_semantic_analysis",
    "identity",
)


endpoint_src=source_of_function(
    text,
    "production_reference_semantic_analysis",
)


provider_src=source_of_function(
    text,
    "_reference_semantic_provider_analyze",
)


verifier_src=source_of_function(
    text,
    "_verify_reference_semantic_analysis",
)


reader_src=source_of_function(
    text,
    "production_reference_semantic_analyses",
)


storage_src=source_of_function(
    text,
    "_reference_semantic_analysis_dir",
)


path_src=source_of_function(
    text,
    "_reference_semantic_analysis_path",
)


record_keys=assigned_dict_keys(
    text,
    "production_reference_semantic_analysis",
    "rec",
)


add(
    "WORKER_REMAINS_2_24_0",
    text.count(
        'WORKER_VERSION = "2.24.0"'
    )==1,
)


add(
    "STORAGE_DIR_SOURCE_SHA_ONLY",
    function_args(
        text,
        "_reference_semantic_analysis_dir",
    )==[
        "source_sha256"
    ],
)


add(
    "STORAGE_PATH_MEDIA_CENTRIC",
    function_args(
        text,
        "_reference_semantic_analysis_path",
    )==[
        "source_sha256",
        "analysis_id",
    ],
)


add(
    "STORAGE_USES_SHA_PREFIX",
    (
        "source_sha[:2]"
        in storage_src
        and
        "/ source_sha"
        in storage_src
    ),
)


add(
    "ITEM_SOURCE_VIEW_HELPER_PRESENT",
    (
        "def _reference_semantic_source_shas_for_item"
        in text
    ),
)


add(
    "ITEM_READER_USES_SOURCE_VIEW",
    "_reference_semantic_source_shas_for_item"
    in reader_src,
)


add(
    "ENDPOINT_IDENTITY_EXACT_MEDIA_CENTRIC",
    endpoint_identity==expected_identity,
    endpoint_identity,
)


add(
    "VERIFIER_IDENTITY_EXACT_MEDIA_CENTRIC",
    verifier_identity==expected_identity,
    verifier_identity,
)


add(
    "IDENTITY_EXCLUDES_REFERENCE_ITEM",
    (
        endpoint_identity is not None
        and
        "reference_item_id"
        not in endpoint_identity
    ),
)


add(
    "IDENTITY_INCLUDES_CONTACT_SHA",
    (
        endpoint_identity is not None
        and
        "contact_sheet_sha256"
        in endpoint_identity
    ),
)


add(
    "IDENTITY_INCLUDES_PROVIDER_CONTRACT",
    (
        endpoint_identity is not None
        and
        "semantic_provider_contract_version"
        in endpoint_identity
    ),
)


add(
    "PROVIDER_ARGS_MEDIA_ONLY",
    function_args(
        text,
        "_reference_semantic_provider_analyze",
    )==[
        "contact_sheet",
        "mechanical",
    ],
)


add(
    "PROVIDER_NO_ITEM_GET",
    "item.get("
    not in provider_src,
)


add(
    "PROVIDER_NO_CAPTION_CONTEXT",
    "caption="
    not in provider_src,
)


add(
    "PROVIDER_NO_NETWORK_CONTEXT",
    "network="
    not in provider_src,
)


add(
    "PROVIDER_NO_ITEM_TYPE_CONTEXT",
    "item_type="
    not in provider_src,
)


add(
    "PROVIDER_PROMPT_EXPLICITLY_FORBIDS_EXTERNAL_CONTEXT",
    (
        "Não utilize caption"
        in provider_src
        and
        "ReferenceItem"
        in provider_src
    ),
)


cache_index=endpoint_src.find(
    "if path.exists():"
)


priority_index=endpoint_src.find(
    "_reference_semantic_authorizing_priority("
)


provider_index=endpoint_src.find(
    "_reference_semantic_provider_analyze("
)


add(
    "CACHE_CHECK_BEFORE_PRIORITY_GATE",
    (
        cache_index>=0
        and
        priority_index>cache_index
    ),
    (
        str(cache_index)
        + ":"
        + str(priority_index)
    ),
)


add(
    "PRIORITY_GATE_BEFORE_PROVIDER_ON_CACHE_MISS",
    (
        priority_index>=0
        and
        provider_index>priority_index
    ),
)


cache_segment=(
    endpoint_src[
        cache_index:
        priority_index
    ]
    if (
        cache_index>=0
        and
        priority_index>cache_index
    )
    else ""
)


add(
    "CACHE_HIT_NO_PRIORITY_ALLOW_CHECK",
    "_reference_semantic_authorizing_priority"
    not in cache_segment,
)


add(
    "CACHE_HIT_NO_PROVIDER_CALL",
    "_reference_semantic_provider_analyze"
    not in cache_segment,
)


add(
    "CACHE_RESPONSE_MARKS_PROVIDER_FALSE",
    '"provider_called":\n                False'
    in cache_segment,
)


add(
    "CACHE_RESPONSE_MARKS_PRIORITY_ALLOW_FALSE",
    '"priority_generation_allow_checked":\n                False'
    in cache_segment,
)


required_creation_fields={
    "creation_reference_item_id",
    "creation_reference_profile_id",
    "creation_acquisition_id",
    "creation_priority_decision_id",
    "creation_priority_evidence_fingerprint",
}


add(
    "RECORD_HAS_CREATION_PROVENANCE",
    (
        record_keys is not None
        and
        required_creation_fields.issubset(
            set(record_keys)
        )
    ),
    record_keys,
)


for forbidden_field in (
    "reference_item_id",
    "reference_profile_id",
    "acquisition_id",
    "priority_decision_id",
    "priority_evidence_fingerprint",
    "contact_sheet_path",
    "local_media_ref",
    "preference_signal",
):

    add(
        (
            "RECORD_FORBIDS_DIRECT_"
            + forbidden_field.upper()
        ),
        (
            record_keys is not None
            and
            forbidden_field
            not in record_keys
        ),
    )


add(
    "RECORD_PERSISTS_CONTACT_HASH",
    (
        record_keys is not None
        and
        "contact_sheet_sha256"
        in record_keys
    ),
)


add(
    "VERIFIER_REQUIRES_CONTACT_HASH",
    (
        "contact_sheet_sha256"
        in verifier_src
        and
        "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID"
        in verifier_src
    ),
)


add(
    "VERIFIER_FORBIDS_OLD_DIRECT_ITEM_CONTEXT",
    (
        '"reference_item_id"'
        in verifier_src
        and
        "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD"
        in verifier_src
    ),
)


add(
    "READER_IS_HISTORICAL_NOT_ACTIVE_GATE",
    "_require_reference_item_active"
    not in reader_src,
)


add(
    "HEALTH_MEDIA_CENTRIC_TRUE",
    '"reference_semantic_media_centric": True'
    in text,
)


add(
    "HEALTH_PROVIDER_ITEM_CONTEXT_FALSE",
    '"reference_semantic_item_context_in_provider": False'
    in text,
)


add(
    "HEALTH_CONTACT_HASH_IDENTITY_TRUE",
    '"reference_semantic_contact_sheet_hash_in_identity": True'
    in text,
)


add(
    "HEALTH_STORAGE_MEDIA_CENTRIC_TRUE",
    '"reference_semantic_storage_media_centric": True'
    in text,
)


add(
    "HEALTH_CACHE_ALLOW_FALSE",
    '"reference_semantic_cache_hit_requires_generation_allow": False'
    in text,
)


add(
    "HEALTH_GENERATION_CURRENT_PRIORITY_TRUE",
    '"reference_semantic_generation_requires_current_priority": True'
    in text,
)


add(
    "LEGACY_WRITE_STILL_DISABLED",
    "REFERENCE_VIDEO_ANALYSIS_LEGACY_WRITE_DISABLED_USE_SEMANTIC_ANALYSIS"
    in source_of_function(
        text,
        "production_reference_video_analysis",
    ),
)


add(
    "SEMANTIC_DOES_NOT_WRITE_FEATURE",
    (
        "production_reference_feature"
        not in endpoint_src
        and
        "ReferenceFeatureObservationRequest"
        not in endpoint_src
    ),
)


add(
    "SEMANTIC_DOES_NOT_RECALCULATE_MECHANICAL",
    all(
        marker
        not in endpoint_src
        for marker in (
            "make_contact_sheet",
            "_reference_cut_metrics",
            "_reference_audio_onsets",
            "_reference_color_stats",
        )
    ),
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
                    "09C7-B2C",

                "status":
                    "CANDIDATE_REJECTED",

                "source_sha_before":
                    before_sha,

                "check_count":
                    len(checks),

                "pass_count":
                    len(checks)-len(failed),

                "fail_count":
                    len(failed),

                "failed_checks":[
                    row["check"]
                    for row in failed
                ],

                "host_written":
                    False,

                "checks":
                    checks,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    fail(
        "SM3_09C7_B2C_CANDIDATE_GATE_FAILED:"
        + ",".join(
            row["check"]
            for row in failed
        )
    )


# ============================================================
# 9. ATOMIC WRITE
# ============================================================

candidate_bytes=text.encode(
    "utf-8"
)


candidate_sha=sha256_bytes(
    candidate_bytes
)


tmp=WORKER.with_name(
    WORKER.name
    + ".09C7_B2C.tmp"
)


tmp.write_bytes(
    candidate_bytes
)


ast.parse(
    tmp.read_text(
        encoding="utf-8"
    ),
    filename=str(tmp),
)


tmp.replace(
    WORKER
)


after_sha=sha256_bytes(
    WORKER.read_bytes()
)


if after_sha!=candidate_sha:

    fail(
        "SM3_09C7_B2C_POST_WRITE_SHA_MISMATCH"
    )


if after_sha==before_sha:

    fail(
        "SM3_09C7_B2C_SOURCE_DID_NOT_CHANGE"
    )


# ============================================================
# 10. REPORT
# ============================================================

report={
    "phase":
        "09C7-B2C",

    "status":
        "MEDIA_CENTRIC_V1_IMPLEMENTED_HOST_ONLY",

    "worker_version":
        "2.24.0",

    "source_sha_before":
        before_sha,

    "source_sha_after":
        after_sha,

    "check_count":
        len(checks),

    "pass_count":
        len(checks),

    "fail_count":
        0,

    "identity_fields":
        expected_identity,

    "provider_item_context_allowed":
        False,

    "storage_media_centric":
        True,

    "contact_sheet_sha256_in_identity":
        True,

    "cache_hit_provider_call":
        False,

    "cache_hit_priority_generation_allow_required":
        False,

    "cache_miss_priority_generation_allow_required":
        True,

    "runtime_deployed":
        False,

    "build_executed":
        False,

    "model_called":
        False,

    "semantic_record_created":
        False,

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
    "SM3_09C7_B2C_PATCHER_PASS"
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
    "CHECK_COUNT="
    + str(len(checks))
)

print(
    "PASS_COUNT="
    + str(len(checks))
)

print(
    "FAIL_COUNT=0"
)

print(
    "IDENTITY_MEDIA_CENTRIC=True"
)

print(
    "CONTACT_SHEET_SHA256_IN_IDENTITY=True"
)

print(
    "PROVIDER_ITEM_CONTEXT_ALLOWED=False"
)

print(
    "STORAGE_MEDIA_CENTRIC=True"
)

print(
    "CACHE_HIT_PROVIDER_CALL=False"
)

print(
    "CACHE_HIT_PRIORITY_GENERATION_ALLOW_REQUIRED=False"
)

print(
    "CACHE_MISS_PRIORITY_GENERATION_ALLOW_REQUIRED=True"
)

print(
    "RUNTIME_DEPLOYED=False"
)

print(
    "BUILD_EXECUTED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "SEMANTIC_RECORD_CREATED=False"
)

print(
    "REPORT="
    + str(REPORT)
)

sys.exit(0)
