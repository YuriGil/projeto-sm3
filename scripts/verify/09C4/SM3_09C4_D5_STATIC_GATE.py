from pathlib import Path
import re
import ast
import hashlib

worker = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py")

text = worker.read_text(encoding="utf-8-sig")

print("=== SM3 09C4-D5 - 2.20.0 STATIC GATE ===")

# ---------------------------------------------------------
# 1. SYNTAX
# ---------------------------------------------------------

ast.parse(text)
compile(text, str(worker), "exec")

print("PYTHON_SYNTAX=PASS")


# ---------------------------------------------------------
# 2. VERSION
# ---------------------------------------------------------

version_count = text.count('WORKER_VERSION = "2.20.0"')

print(f"VERSION_2_20_COUNT={version_count}")

if version_count != 1:
    raise SystemExit("SM3_D5_VERSION_INVALID")


# ---------------------------------------------------------
# 3. NOVO CONTRATO / ROOT / MODEL / ENDPOINT
# ---------------------------------------------------------

checks = {
    "MECHANICAL_STORAGE_ROOT":
        'PRODUCTION_REFERENCE_MECHANICAL_ANALYSES = '
        '(PRODUCTION_STATE / "reference_mechanical_analyses").resolve()',

    "MECHANICAL_CONTRACT":
        'REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_VERSION = '
        '"SM3_REFERENCE_MECHANICAL_ANALYSIS_V1"',

    "MECHANICAL_ANALYZER":
        'REFERENCE_MECHANICAL_ANALYZER_VERSION = '
        '"SM3_REFERENCE_MECHANICAL_ANALYZER_V1"',

    "MECHANICAL_REQUEST_MODEL":
        "class ReferenceMechanicalAnalysisRequest(BaseModel):",

    "MECHANICAL_VERIFIER":
        "def _verify_reference_mechanical_analysis(",

    "MECHANICAL_ROUTE":
        '@app.post("/production/reference-corpus/mechanical-analysis")',

    "MECHANICAL_FUNCTION":
        "def production_reference_mechanical_analysis(",
}

for label, marker in checks.items():

    count = text.count(marker)

    print(f"{label}_COUNT={count}")

    if count != 1:
        raise SystemExit(
            f"SM3_D5_{label}_INVALID:{count}"
        )


# ---------------------------------------------------------
# 4. STORAGE ROOT PRECISA ESTAR NO STARTUP
# ---------------------------------------------------------

startup_marker = (
    "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES, "
    "PRODUCTION_REFERENCE_MEDIA,"
)

startup_ok = startup_marker in text

print(
    f"MECHANICAL_ROOT_IN_STARTUP={startup_ok}"
)

if not startup_ok:
    raise SystemExit(
        "SM3_D5_MECHANICAL_ROOT_NOT_IN_STARTUP"
    )


# ---------------------------------------------------------
# 5. V1 PRECISA CONTINUAR EXISTINDO
# ---------------------------------------------------------

v1_checks = {
    "V1_ROUTE":
        '@app.post("/production/reference-corpus/video-analysis")',

    "V1_FUNCTION":
        "def production_reference_video_analysis(",

    "V1_CONTRACT":
        'REFERENCE_VIDEO_ANALYSIS_CONTRACT_VERSION = '
        '"SM3_REFERENCE_VIDEO_ANALYSIS_V1"',

    "V1_ANALYZER":
        'REFERENCE_VIDEO_ANALYZER_VERSION = '
        '"SM3_REFERENCE_VIDEO_ANALYZER_V1"',
}

for label, marker in v1_checks.items():

    count = text.count(marker)

    print(f"{label}_COUNT={count}")

    if count != 1:
        raise SystemExit(
            f"SM3_D5_{label}_INVALID:{count}"
        )


# ---------------------------------------------------------
# 6. ISOLAR BLOCO MECHANICAL
# ---------------------------------------------------------

m_start = text.index(
    "def production_reference_mechanical_analysis("
)

m_end = text.index(
    '@app.post("/production/reference-corpus/video-analysis")',
    m_start
)

mechanical = text[m_start:m_end]


# ---------------------------------------------------------
# 7. GUARDA DE FRONTEIRA
# ---------------------------------------------------------

forbidden = (
    "_reference_video_vision(",
    "production_reference_feature(",
    "ReferenceFeatureObservationRequest(",
    "preference_signal",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "VISION_MODEL",
)

for marker in forbidden:

    present = marker in mechanical

    print(
        f"MECHANICAL_FORBIDDEN_{marker[:24]}={present}"
    )

    if present:
        raise SystemExit(
            f"SM3_D5_MECHANICAL_BOUNDARY_VIOLATION:{marker}"
        )

print("MECHANICAL_BOUNDARY=PASS")


# ---------------------------------------------------------
# 8. IDENTIDADE RMA DEVE SER MEDIA-CENTRIC
# ---------------------------------------------------------

identity_start = mechanical.index(
    "analysis_id='RMA_'"
)

identity_end = mechanical.index(
    "path=_reference_mechanical_analysis_path",
    identity_start
)

identity = mechanical[
    identity_start:identity_end
]

required_identity = (
    "'source_sha256':source_sha",
    "'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION",
)

for marker in required_identity:

    if marker not in identity:
        raise SystemExit(
            f"SM3_D5_RMA_IDENTITY_MISSING:{marker}"
        )

identity_forbidden = (
    "reference_item_id",
    "reference_profile_id",
    "local_media_ref",
    "preference_signal",
    "notes",
    "VISION_MODEL",
)

for marker in identity_forbidden:

    if marker in identity:
        raise SystemExit(
            f"SM3_D5_RMA_IDENTITY_NOT_MEDIA_CENTRIC:{marker}"
        )

print("RMA_IDENTITY_MEDIA_CENTRIC=PASS")


# ---------------------------------------------------------
# 9. AQUISIÇÃO DEVE SER VERIFICADA
# ---------------------------------------------------------

required_acquisition = (
    "_verify_reference_media_acquisition(",
    "_latest_reference_media_for_item(",
    "REFERENCE_MECHANICAL_ACQUISITION_SHA_MISMATCH",
)

for marker in required_acquisition:

    if marker not in mechanical:
        raise SystemExit(
            f"SM3_D5_ACQUISITION_GUARD_MISSING:{marker}"
        )

print("VERIFIED_ACQUISITION_BOUNDARY=PASS")


# ---------------------------------------------------------
# 10. CONTACT SHEET FAIL-CLOSED
# ---------------------------------------------------------

contact_markers = (
    "REFERENCE_MECHANICAL_CONTACT_SHEET_REF_MISSING",
    "REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_INVALID",
    "REFERENCE_MECHANICAL_CONTACT_SHEET_MISSING",
    "REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_MISMATCH",
)

for marker in contact_markers:

    count = text.count(marker)

    print(f"{marker}_COUNT={count}")

    if count != 1:
        raise SystemExit(
            f"SM3_D5_CONTACT_GUARD_INVALID:{marker}:{count}"
        )

print("CONTACT_SHEET_FAIL_CLOSED=PASS")


# ---------------------------------------------------------
# 11. V1 AINDA DEVE CONTER VISION
# ---------------------------------------------------------

v1_start = text.index(
    "def production_reference_video_analysis("
)

v1_end = text.index(
    '@app.get("/production/reference-corpus/video-analysis/{item_id}/latest")',
    v1_start
)

v1_block = text[v1_start:v1_end]

if "_reference_video_vision(" not in v1_block:
    raise SystemExit(
        "SM3_D5_V1_VISION_PATH_MISSING"
    )

if "production_reference_feature(" not in v1_block:
    raise SystemExit(
        "SM3_D5_V1_FEATURE_PATH_MISSING"
    )

print("LEGACY_V1_BEHAVIOR_PRESERVED=PASS")


# ---------------------------------------------------------
# 12. SOURCE HASH
# ---------------------------------------------------------

sha = hashlib.sha256(
    worker.read_bytes()
).hexdigest()

print(f"SOURCE_SHA256={sha}")

print()
print("SM3_09C4_D5_STATIC_GATE_PASS")
