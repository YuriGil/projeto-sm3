from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


REPORT = Path(
    "/tmp/SM3_09C7_B3B_D3_V2_ACQUIRE_AUDIT.json"
)

SOURCE_PATH = Path(
    "/app/worker_service.py"
)

TARGET_FUNCTIONS = [
    "production_reference_media_acquire",
    "_resolve_reference_media_ref",
    "_persist_reference_media_artifact",
    "_verify_reference_media_artifact",
    "_verify_reference_media_acquisition",
    "_resolve_reference_acquisition_source",
    "_reference_media_path",
    "_reference_media_artifact_blob_path",
    "_reference_media_artifact_state_path",
]


source = SOURCE_PATH.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    source,
    filename=str(SOURCE_PATH),
)


def get_source(name: str):

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:
        return None

    try:
        return inspect.getsource(obj)
    except Exception:
        return None


function_sources = {}

for name in TARGET_FUNCTIONS:

    text = get_source(name)

    if text is not None:
        function_sources[name] = text


acquire_source = function_sources.get(
    "production_reference_media_acquire",
    "",
)


# ============================================================
# Discover every local helper called by acquire()
# ============================================================

acquire_calls = []

for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    if node.name != "production_reference_media_acquire":
        continue

    for child in ast.walk(node):

        if isinstance(
            child,
            ast.Call,
        ):

            fn = child.func

            if isinstance(
                fn,
                ast.Name,
            ):
                acquire_calls.append(
                    fn.id
                )

            elif isinstance(
                fn,
                ast.Attribute,
            ):
                try:
                    acquire_calls.append(
                        ast.unparse(fn)
                    )
                except Exception:
                    pass


acquire_calls = sorted(
    set(acquire_calls)
)


# ============================================================
# Discover likely acquisition / artifact ID helpers
# ============================================================

candidate_helpers = []

for name in dir(ws):

    lower = name.lower()

    if (
        "reference_media" not in lower
        and
        "media_artifact" not in lower
        and
        "acquisition" not in lower
    ):
        continue

    obj = getattr(
        ws,
        name,
        None,
    )

    if not callable(obj):
        continue

    try:
        sig = str(
            inspect.signature(obj)
        )
    except Exception:
        sig = None

    candidate_helpers.append({
        "name":
            name,

        "signature":
            sig,
    })


# ============================================================
# Important behavioral markers
# ============================================================

markers = {
    "acquire_calls_active_gate":
        "_require_reference_item_active"
        in acquire_source,

    "acquire_calls_resolve_media_ref":
        "_resolve_reference_media_ref"
        in acquire_source,

    "acquire_calls_persist_media_artifact":
        "_persist_reference_media_artifact"
        in acquire_source,

    "acquire_calls_verify_artifact":
        "_verify_reference_media_artifact"
        in acquire_source,

    "acquire_calls_verify_acquisition":
        "_verify_reference_media_acquisition"
        in acquire_source,

    "acquire_writes_revision_once":
        "_write_revision_once"
        in acquire_source,

    "acquire_mentions_cleanup":
        "cleanup_inbox_after_commit"
        in acquire_source,

    "acquire_mentions_media_artifact_id":
        "media_artifact_id"
        in acquire_source,

    "acquire_mentions_source_sha256":
        "source_sha256"
        in acquire_source,
}


persist_source = function_sources.get(
    "_persist_reference_media_artifact",
    "",
)


persist_markers = {
    "persist_checks_existing_blob":
        (
            ".exists()"
            in persist_source
            or
            "is_file()"
            in persist_source
        ),

    "persist_hashes_source":
        (
            "sha256"
            in persist_source.lower()
        ),

    "persist_uses_copy":
        (
            "copy"
            in persist_source.lower()
        ),

    "persist_uses_replace":
        (
            "replace("
            in persist_source
            or
            "os.replace"
            in persist_source
        ),

    "persist_uses_move":
        (
            "move("
            in persist_source
        ),

    "persist_unlinks_source":
        (
            ".unlink("
            in persist_source
        ),

    "persist_compares_source_and_destination":
        (
            "resolve()"
            in persist_source
            or
            "samefile"
            in persist_source.lower()
        ),
}


resolve_source = function_sources.get(
    "_resolve_reference_media_ref",
    "",
)


resolve_markers = {
    "resolver_mentions_media_root":
        "MEDIA_ROOT"
        in resolve_source,

    "resolver_mentions_reference_artifacts":
        "reference_artifacts"
        in resolve_source,

    "resolver_rejects_outside_root":
        (
            "relative_to"
            in resolve_source
            or
            "is_relative_to"
            in resolve_source
        ),
}


# ============================================================
# Request model
# ============================================================

model_fields = {}

model = getattr(
    ws,
    "ReferenceMediaAcquireRequest",
    None,
)

if model is not None:

    fields = getattr(
        model,
        "model_fields",
        {}
    )

    for name,field in fields.items():

        model_fields[name] = {
            "required":
                field.is_required(),

            "default":
                (
                    None
                    if field.default is None
                    else str(field.default)
                ),

            "annotation":
                str(field.annotation),
        }


# ============================================================
# Report
# ============================================================

report = {
    "phase":
        "09C7-B3B-D3",

    "status":
        "V2_ACQUIRE_WRITE_PATH_AUDIT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "request_model_fields":
        model_fields,

    "acquire_calls":
        acquire_calls,

    "acquire_markers":
        markers,

    "persist_artifact_markers":
        persist_markers,

    "resolve_media_ref_markers":
        resolve_markers,

    "function_sources":
        function_sources,

    "candidate_helpers":
        sorted(
            candidate_helpers,
            key=lambda row:row[
                "name"
            ],
        ),

    "production_write_performed":
        False,

    "api_write_called":
        False,

    "semantic_api_called":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== SM3 09C7-B3B-D3 V2 ACQUIRE AUDIT ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)


print(
    "\n=== ACQUIRE CALLS ==="
)

for name in acquire_calls:
    print(name)


print(
    "\n=== ACQUIRE MARKERS ==="
)

for name,value in markers.items():

    print(
        name.upper()
        + "="
        + str(value)
    )


print(
    "\n=== PERSIST ARTIFACT MARKERS ==="
)

for name,value in persist_markers.items():

    print(
        name.upper()
        + "="
        + str(value)
    )


print(
    "\n=== RESOLVER MARKERS ==="
)

for name,value in resolve_markers.items():

    print(
        name.upper()
        + "="
        + str(value)
    )


print(
    "\n=== REQUEST MODEL ==="
)

for name,value in model_fields.items():

    print(
        name
        + "="
        + json.dumps(
            value,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== FUNCTION SOURCE: production_reference_media_acquire ==="
)

print(
    function_sources.get(
        "production_reference_media_acquire",
        "NOT_FOUND",
    )
)


print(
    "\n=== FUNCTION SOURCE: _resolve_reference_media_ref ==="
)

print(
    function_sources.get(
        "_resolve_reference_media_ref",
        "NOT_FOUND",
    )
)


print(
    "\n=== FUNCTION SOURCE: _persist_reference_media_artifact ==="
)

print(
    function_sources.get(
        "_persist_reference_media_artifact",
        "NOT_FOUND",
    )
)


print(
    "\n=== FUNCTION SOURCE: _verify_reference_media_acquisition ==="
)

print(
    function_sources.get(
        "_verify_reference_media_acquisition",
        "NOT_FOUND",
    )
)


print(
    "\n=== CANDIDATE HELPERS ==="
)

for row in sorted(
    candidate_helpers,
    key=lambda x:x[
        "name"
    ],
):

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\nPRODUCTION_WRITE_PERFORMED=False"
)

print(
    "API_WRITE_CALLED=False"
)

print(
    "SEMANTIC_API_CALLED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(REPORT)
)

print(
    "SM3_09C7_B3B_D3_V2_ACQUIRE_WRITE_PATH_AUDIT_COMPLETE"
)
