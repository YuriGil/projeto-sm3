from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import inspect
import json
import sys

sys.path.insert(0,"/app")

import worker_service as ws


TARGET_ITEM_ID = (
    "RI_500f8618a5796dc9b1fbded2f3bfff2e"
)

TARGET_V1_ACQUISITION_ID = (
    "RM_752bf6e605752cc568c4d9992a3fdcce"
)

TARGET_SOURCE_SHA = (
    "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"
)

STATE = Path(
    "/data/media/production_state"
)

SOURCE_FILE = Path(
    "/app/worker_service.py"
)

REPORT = Path(
    "/tmp/SM3_09C7_B3B_D2_CAS_V2_ASSOCIATION_MAP.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json_files(root: Path):
    rows=[]

    if not root.exists():
        return rows

    for path in root.rglob("*.json"):

        try:
            rec=json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        if isinstance(rec,dict):
            rows.append(
                (
                    path,
                    rec,
                )
            )

    return rows


# ============================================================
# 1. TARGET ITEM
# ============================================================

target_active=False
target_active_error=None
target_item=None


try:

    target_item=(
        ws._require_reference_item_active(
            TARGET_ITEM_ID
        )
    )

    target_active=True

except Exception as exc:

    target_active_error=str(
        getattr(
            exc,
            "detail",
            exc,
        )
    )


# ============================================================
# 2. ACQUISITIONS
# ============================================================

acquisition_records=[]


media_root=(
    STATE
    / "reference_media"
)


for path,rec in load_json_files(
    media_root
):

    if str(
        rec.get(
            "acquisition_id"
        )
        or ""
    ).startswith(
        "RM_"
    ):

        acquisition_records.append(
            (
                path,
                rec,
            )
        )


matching_acquisitions=[]

target_v1=None


for path,rec in acquisition_records:

    source_sha=str(
        rec.get(
            "source_sha256"
        )
        or ""
    ).lower()

    if (
        rec.get(
            "acquisition_id"
        )
        == TARGET_V1_ACQUISITION_ID
    ):
        target_v1=rec

    if source_sha!=TARGET_SOURCE_SHA:
        continue

    row={
        "path":
            str(path),

        "acquisition_id":
            rec.get(
                "acquisition_id"
            ),

        "contract_version":
            rec.get(
                "contract_version"
            ),

        "reference_item_id":
            rec.get(
                "reference_item_id"
            ),

        "reference_profile_id":
            rec.get(
                "reference_profile_id"
            ),

        "source_sha256":
            source_sha,

        "media_artifact_id":
            rec.get(
                "media_artifact_id"
            ),

        "resolve_ok":
            False,

        "resolved_source_path":
            None,

        "resolved_source_sha256":
            None,

        "resolved_media_artifact_id":
            None,

        "resolve_error":
            None,
    }


    try:

        source_path,artifact=(
            ws._resolve_reference_acquisition_source(
                rec
            )
        )

        row[
            "resolve_ok"
        ]=True

        row[
            "resolved_source_path"
        ]=str(
            source_path
        )

        if Path(
            source_path
        ).is_file():

            row[
                "resolved_source_sha256"
            ]=sha256_file(
                Path(
                    source_path
                )
            )

        if artifact is not None:

            row[
                "resolved_media_artifact_id"
            ]=artifact.get(
                "media_artifact_id"
            )

    except Exception as exc:

        row[
            "resolve_error"
        ]=str(
            getattr(
                exc,
                "detail",
                exc,
            )
        )


    matching_acquisitions.append(
        row
    )


# ============================================================
# 3. MEDIA ARTIFACT RECORDS
# ============================================================

artifact_root=(
    STATE
    / "reference_media_artifacts"
)


matching_artifacts=[]


for path,rec in load_json_files(
    artifact_root
):

    source_sha=str(
        rec.get(
            "source_sha256"
        )
        or rec.get(
            "sha256"
        )
        or rec.get(
            "content_sha256"
        )
        or ""
    ).lower()

    if source_sha!=TARGET_SOURCE_SHA:
        continue


    artifact_id=str(
        rec.get(
            "media_artifact_id"
        )
        or ""
    )


    matching_artifacts.append({
        "path":
            str(path),

        "media_artifact_id":
            artifact_id,

        "contract_version":
            rec.get(
                "contract_version"
            ),

        "store_version":
            rec.get(
                "store_version"
            ),

        "source_sha256":
            source_sha,

        "record_fields":
            sorted(
                rec.keys()
            ),

        "record":
            rec,
    })


# ============================================================
# 4. DERIVE UNIQUE CAS ARTIFACT ID FROM VALID V2 ACQUISITIONS
# ============================================================

valid_v2=[]


for row in matching_acquisitions:

    if (
        row[
            "contract_version"
        ]
        ==
        "SM3_REFERENCE_MEDIA_ACQUISITION_V2"
        and
        row[
            "resolve_ok"
        ]
        and
        row[
            "resolved_source_sha256"
        ]
        ==
        TARGET_SOURCE_SHA
        and
        row[
            "resolved_media_artifact_id"
        ]
    ):

        valid_v2.append(
            row
        )


artifact_ids=sorted(
    {
        str(
            row[
                "resolved_media_artifact_id"
            ]
        )
        for row in valid_v2
    }
)


unique_artifact_id=(
    artifact_ids[0]
    if len(
        artifact_ids
    )==1
    else None
)


# ============================================================
# 5. SOURCE / API INTROSPECTION
# ============================================================

source=SOURCE_FILE.read_text(
    encoding="utf-8-sig"
)


tree=ast.parse(
    source,
    filename=str(
        SOURCE_FILE
    ),
)


routes=[]


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    for decorator in node.decorator_list:

        if not isinstance(
            decorator,
            ast.Call,
        ):
            continue

        fn=decorator.func

        if not (
            isinstance(
                fn,
                ast.Attribute,
            )
            and
            isinstance(
                fn.value,
                ast.Name,
            )
            and
            fn.value.id=="app"
            and
            fn.attr
            in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }
        ):
            continue

        if not decorator.args:
            continue

        path_arg=decorator.args[0]

        if not (
            isinstance(
                path_arg,
                ast.Constant,
            )
            and
            isinstance(
                path_arg.value,
                str,
            )
        ):
            continue

        route_path=path_arg.value

        lower_path=route_path.lower()

        if (
            "media"
            not in lower_path
            and
            "acquisition"
            not in lower_path
            and
            "artifact"
            not in lower_path
        ):
            continue

        params=[]

        for arg in node.args.args:

            annotation=None

            if arg.annotation is not None:

                try:
                    annotation=ast.unparse(
                        arg.annotation
                    )
                except Exception:
                    annotation=None

            params.append({
                "name":
                    arg.arg,

                "annotation":
                    annotation,
            })


        routes.append({
            "method":
                fn.attr.upper(),

            "path":
                route_path,

            "function":
                node.name,

            "parameters":
                params,
        })


# ============================================================
# 6. REQUEST MODELS
# ============================================================

request_models=[]


for node in tree.body:

    if not isinstance(
        node,
        ast.ClassDef,
    ):
        continue

    lower_name=node.name.lower()

    if (
        "media"
        not in lower_name
        and
        "acquisition"
        not in lower_name
        and
        "artifact"
        not in lower_name
    ):
        continue

    fields=[]

    for child in node.body:

        if not isinstance(
            child,
            ast.AnnAssign,
        ):
            continue

        if not isinstance(
            child.target,
            ast.Name,
        ):
            continue

        try:
            annotation=ast.unparse(
                child.annotation
            )
        except Exception:
            annotation=None

        default=None

        if child.value is not None:

            try:
                default=ast.unparse(
                    child.value
                )
            except Exception:
                default=None

        fields.append({
            "name":
                child.target.id,

            "annotation":
                annotation,

            "default":
                default,
        })


    request_models.append({
        "class":
            node.name,

        "fields":
            fields,
    })


# ============================================================
# 7. RELEVANT FUNCTIONS / HELPERS
# ============================================================

relevant_functions=[]


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    lower=node.name.lower()

    if (
        "reference_media"
        not in lower
        and
        "media_artifact"
        not in lower
        and
        "acquisition"
        not in lower
    ):
        continue

    try:
        sig=str(
            inspect.signature(
                getattr(
                    ws,
                    node.name
                )
            )
        )
    except Exception:
        sig=None

    relevant_functions.append({
        "name":
            node.name,

        "signature":
            sig,
    })


# ============================================================
# 8. CONTRACT CONSTANTS
# ============================================================

constants={}


for name in dir(ws):

    if not name.startswith(
        "REFERENCE_MEDIA"
    ):
        continue

    value=getattr(
        ws,
        name
    )

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            type(None),
        ),
    ):

        constants[name]=value


# ============================================================
# 9. ARCHITECTURAL FINDINGS
# ============================================================

target_v1_source_ok=(
    target_v1 is not None
    and
    str(
        target_v1.get(
            "source_sha256"
        )
        or ""
    ).lower()
    ==
    TARGET_SOURCE_SHA
)


target_v1_has_artifact=bool(
    (
        target_v1
        or {}
    ).get(
        "media_artifact_id"
    )
)


valid_v2_count=len(
    valid_v2
)


same_media_reused_across_v2_items=(
    len(
        {
            str(
                row[
                    "reference_item_id"
                ]
            )
            for row in valid_v2
        }
    )
    >= 2
    and
    len(
        artifact_ids
    )
    == 1
)


target_source_has_valid_cas=(
    len(
        artifact_ids
    )
    == 1
    and
    valid_v2_count
    >= 1
)


target_needs_v2_association=(
    target_active
    and
    target_v1_source_ok
    and
    not target_v1_has_artifact
    and
    target_source_has_valid_cas
)


report={
    "phase":
        "09C7-B3B-D2",

    "status":
        "CAS_V2_ASSOCIATION_FEASIBILITY_MAP_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "target":{
        "reference_item_id":
            TARGET_ITEM_ID,

        "active":
            target_active,

        "active_error":
            target_active_error,

        "legacy_acquisition_id":
            TARGET_V1_ACQUISITION_ID,

        "source_sha256":
            TARGET_SOURCE_SHA,

        "legacy_acquisition_found":
            target_v1
            is not None,

        "legacy_source_matches":
            target_v1_source_ok,

        "legacy_has_media_artifact":
            target_v1_has_artifact,
    },

    "matching_acquisitions":
        matching_acquisitions,

    "matching_media_artifacts":
        matching_artifacts,

    "valid_v2_acquisitions":
        valid_v2,

    "unique_media_artifact_ids":
        artifact_ids,

    "canonical_media_artifact_id":
        unique_artifact_id,

    "findings":{
        "valid_v2_acquisition_count":
            valid_v2_count,

        "target_source_has_valid_cas":
            target_source_has_valid_cas,

        "same_media_reused_across_v2_items":
            same_media_reused_across_v2_items,

        "target_active_item_needs_v2_association":
            target_needs_v2_association,
    },

    "routes":
        routes,

    "request_models":
        request_models,

    "relevant_functions":
        sorted(
            relevant_functions,
            key=lambda row:row[
                "name"
            ],
        ),

    "reference_media_constants":
        constants,

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
    "=== SM3 09C7-B3B-D2 CAS / V2 ASSOCIATION MAP ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)

print(
    "TARGET_ITEM_ACTIVE="
    + str(
        target_active
    )
)

print(
    "TARGET_V1_ACQUISITION_FOUND="
    + str(
        target_v1
        is not None
    )
)

print(
    "TARGET_V1_SOURCE_MATCH="
    + str(
        target_v1_source_ok
    )
)

print(
    "TARGET_V1_HAS_MEDIA_ARTIFACT="
    + str(
        target_v1_has_artifact
    )
)

print(
    "VALID_V2_ACQUISITION_COUNT="
    + str(
        valid_v2_count
    )
)

print(
    "UNIQUE_MEDIA_ARTIFACT_IDS="
    + ",".join(
        artifact_ids
    )
)

print(
    "CANONICAL_MEDIA_ARTIFACT_ID="
    + str(
        unique_artifact_id
        or ""
    )
)

print(
    "TARGET_SOURCE_HAS_VALID_CAS="
    + str(
        target_source_has_valid_cas
    )
)

print(
    "SAME_MEDIA_REUSED_ACROSS_V2_ITEMS="
    + str(
        same_media_reused_across_v2_items
    )
)

print(
    "TARGET_ACTIVE_ITEM_NEEDS_V2_ASSOCIATION="
    + str(
        target_needs_v2_association
    )
)


print(
    "\n=== MATCHING ACQUISITIONS ==="
)

for row in matching_acquisitions:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== MATCHING MEDIA ARTIFACTS ==="
)

for row in matching_artifacts:

    compact={
        "media_artifact_id":
            row[
                "media_artifact_id"
            ],

        "contract_version":
            row[
                "contract_version"
            ],

        "source_sha256":
            row[
                "source_sha256"
            ],

        "record_fields":
            row[
                "record_fields"
            ],
    }

    print(
        json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== MEDIA / ACQUISITION ROUTES ==="
)

for row in routes:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== MEDIA / ACQUISITION REQUEST MODELS ==="
)

for row in request_models:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== RELEVANT HELPERS ==="
)

for row in sorted(
    relevant_functions,
    key=lambda item:item[
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
    + str(
        REPORT
    )
)

print(
    "SM3_09C7_B3B_D2_CAS_V2_ASSOCIATION_FEASIBILITY_MAP_COMPLETE"
)
