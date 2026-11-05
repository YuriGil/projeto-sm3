from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


REPORT = Path(
    "/tmp/SM3_09C7_B3E_A1_D3_PLATFORM_DYNAMICS_DEEP_MAP.json"
)


TARGET_FUNCTIONS = [
    "production_platform_dynamics_evidence_ingest",
    "production_platform_preference_signal_ingest",
    "production_platform_dynamics_snapshot_build",
    "production_platform_dynamics_summary",
]


# ============================================================
# 1. EXACT ROUTE FUNCTIONS
# ============================================================

route_functions = []


for name in TARGET_FUNCTIONS:

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:

        route_functions.append({
            "name":
                name,

            "found":
                False,
        })

        continue

    try:
        signature = str(
            inspect.signature(
                obj
            )
        )
    except Exception:
        signature = None

    try:
        source = inspect.getsource(
            obj
        )
    except Exception as exc:
        source = (
            "SOURCE_UNAVAILABLE:"
            + repr(
                exc
            )
        )

    route_functions.append({
        "name":
            name,

        "found":
            True,

        "signature":
            signature,

        "source":
            source,
    })


# ============================================================
# 2. REQUEST MODEL DISCOVERY FROM SIGNATURES
# ============================================================

request_model_names = set()


for name in TARGET_FUNCTIONS:

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:
        continue

    try:
        sig = inspect.signature(
            obj
        )
    except Exception:
        continue

    for parameter in sig.parameters.values():

        annotation = (
            parameter.annotation
        )

        if annotation is inspect._empty:
            continue

        annotation_name = getattr(
            annotation,
            "__name__",
            None,
        )

        if annotation_name:
            request_model_names.add(
                annotation_name
            )


# ============================================================
# 3. RELEVANT MODELS
# ============================================================

models = []


candidate_model_names = set(
    request_model_names
)


for name in dir(ws):

    lower = name.lower()

    if (
        "platform" in lower
        and (
            "dynamic" in lower
            or
            "preference" in lower
            or
            "evidence" in lower
            or
            "snapshot" in lower
        )
    ):
        candidate_model_names.add(
            name
        )


for name in sorted(
    candidate_model_names
):

    obj = getattr(
        ws,
        name,
        None,
    )

    if not isinstance(
        obj,
        type,
    ):
        continue

    fields = []

    model_fields = getattr(
        obj,
        "model_fields",
        None,
    )

    if isinstance(
        model_fields,
        dict,
    ):

        for field_name,field in model_fields.items():

            annotation = str(
                getattr(
                    field,
                    "annotation",
                    None,
                )
            )

            default = getattr(
                field,
                "default",
                None,
            )

            fields.append({
                "name":
                    field_name,

                "annotation":
                    annotation,

                "default":
                    repr(
                        default
                    ),
            })

    try:
        source = inspect.getsource(
            obj
        )
    except Exception:
        source = None

    models.append({
        "class":
            name,

        "fields":
            fields,

        "source":
            source,
    })


# ============================================================
# 4. CONSTANTS
# ============================================================

constants = {}


for name in sorted(
    dir(ws)
):

    upper = name.upper()

    if not (
        "PLATFORM" in upper
        and (
            "DYNAMIC" in upper
            or
            "PREFERENCE" in upper
            or
            "EVIDENCE" in upper
            or
            "SIGNAL" in upper
            or
            "SNAPSHOT" in upper
        )
    ):
        continue

    try:
        value = getattr(
            ws,
            name
        )
    except Exception:
        continue

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
        constants[
            name
        ] = value

    elif isinstance(
        value,
        (
            list,
            tuple,
            set,
            dict,
        ),
    ):

        try:
            json.dumps(
                value,
                default=str,
            )

            constants[
                name
            ] = value

        except Exception:

            constants[
                name
            ] = repr(
                value
            )

    elif isinstance(
        value,
        Path,
    ):
        constants[
            name
        ] = str(
            value
        )


# ============================================================
# 5. HELPERS
# ============================================================

helpers = []


for name in sorted(
    dir(ws)
):

    lower = name.lower()

    if not (
        "platform" in lower
        and (
            "dynamic" in lower
            or
            "preference" in lower
            or
            "evidence" in lower
            or
            "snapshot" in lower
        )
    ):
        continue

    obj = getattr(
        ws,
        name,
        None,
    )

    if not callable(
        obj
    ):
        continue

    if name in TARGET_FUNCTIONS:
        continue

    try:
        signature = str(
            inspect.signature(
                obj
            )
        )
    except Exception:
        signature = None

    try:
        source = inspect.getsource(
            obj
        )
    except Exception:
        source = None

    helpers.append({
        "name":
            name,

        "signature":
            signature,

        "source":
            source,
    })


# ============================================================
# 6. SEMANTIC FEATURE DETECTION
# ============================================================

combined_source = "\n".join(
    str(
        row.get(
            "source"
        )
        or ""
    )
    for row in (
        route_functions
        + helpers
    )
).lower()


feature_detection = {

    "confidence_mentions":
        combined_source.count(
            "confidence"
        ),

    "decay_mentions":
        combined_source.count(
            "decay"
        ),

    "drift_mentions":
        combined_source.count(
            "drift"
        ),

    "hypothesis_mentions":
        combined_source.count(
            "hypothesis"
        ),

    "prediction_mentions":
        combined_source.count(
            "prediction"
        ),

    "experiment_mentions":
        combined_source.count(
            "experiment"
        ),

    "counterevidence_mentions":
        combined_source.count(
            "counter"
        ),

    "evidence_mentions":
        combined_source.count(
            "evidence"
        ),

    "preference_mentions":
        combined_source.count(
            "preference"
        ),

    "snapshot_mentions":
        combined_source.count(
            "snapshot"
        ),

    "surface_mentions":
        combined_source.count(
            "surface"
        ),

    "platform_mentions":
        combined_source.count(
            "platform"
        ),

    "time_window_mentions":
        (
            combined_source.count(
                "window"
            )
            +
            combined_source.count(
                "effective_from"
            )
            +
            combined_source.count(
                "observed_at"
            )
        ),
}


# ============================================================
# 7. STORAGE ROOT DISCOVERY
# ============================================================

storage_roots = {}


for name in sorted(
    dir(ws)
):

    upper = name.upper()

    if not (
        "PLATFORM" in upper
        and (
            "DYNAMIC" in upper
            or
            "PREFERENCE" in upper
        )
    ):
        continue

    try:
        value = getattr(
            ws,
            name
        )
    except Exception:
        continue

    if isinstance(
        value,
        Path,
    ):

        storage_roots[
            name
        ] = str(
            value
        )


# ============================================================
# 8. STORAGE INVENTORY
# ============================================================

storage_inventory = []


for constant_name,path_text in storage_roots.items():

    root = Path(
        path_text
    )

    row = {
        "constant":
            constant_name,

        "path":
            str(
                root
            ),

        "exists":
            root.exists(),

        "file_count":
            0,

        "files":
            [],
    }

    if root.exists():

        files = [
            p
            for p in root.rglob("*")
            if p.is_file()
        ]

        row[
            "file_count"
        ] = len(
            files
        )

        for path in files[:50]:

            sample = {
                "path":
                    str(
                        path
                    ),

                "size":
                    path.stat().st_size,
            }

            if path.suffix.lower() == ".json":

                try:
                    rec = json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )

                    if isinstance(
                        rec,
                        dict,
                    ):

                        sample[
                            "contract_version"
                        ] = rec.get(
                            "contract_version"
                        )

                        sample[
                            "keys"
                        ] = sorted(
                            rec.keys()
                        )

                        for key in (
                            "evidence_id",
                            "signal_id",
                            "snapshot_id",
                            "platform",
                            "surface",
                            "status",
                            "created_at",
                            "observed_at",
                        ):

                            if key in rec:

                                sample[
                                    key
                                ] = rec[
                                    key
                                ]

                except Exception as exc:

                    sample[
                        "json_error"
                    ] = repr(
                        exc
                    )

            row[
                "files"
            ].append(
                sample
            )

    storage_inventory.append(
        row
    )


# ============================================================
# 9. CONTRACT LITERALS
# ============================================================

source_text = Path(
    "/app/worker_service.py"
).read_text(
    encoding="utf-8-sig"
)


all_contracts = sorted(
    set(
        re.findall(
            r"SM3_[A-Z0-9_]+_V[0-9]+",
            source_text,
        )
    )
)


platform_contracts = [
    value
    for value in all_contracts
    if (
        "PLATFORM" in value
        or
        "PREFERENCE" in value
        or
        "DYNAMIC" in value
    )
]


# ============================================================
# 10. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3E-A1-D3",

    "status":
        "PLATFORM_DYNAMICS_DEEP_CONTRACT_MAP_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "route_functions":
        route_functions,

    "request_models":
        models,

    "constants":
        constants,

    "helpers":
        helpers,

    "feature_detection":
        feature_detection,

    "storage_roots":
        storage_roots,

    "storage_inventory":
        storage_inventory,

    "platform_contract_literals":
        platform_contracts,

    "production_write_performed":
        False,

    "network_request_performed":
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
        default=str,
    ),
    encoding="utf-8",
)


# ============================================================
# 11. CONSOLE OUTPUT
# ============================================================

print(
    "=== PLATFORM DYNAMICS ROUTES ==="
)

for row in route_functions:

    print("")
    print(
        "FUNCTION="
        + row[
            "name"
        ]
    )

    print(
        "FOUND="
        + str(
            row[
                "found"
            ]
        )
    )

    if row.get(
        "signature"
    ):

        print(
            "SIGNATURE="
            + row[
                "signature"
            ]
        )


print(
    "\n=== PLATFORM DYNAMICS REQUEST MODELS ==="
)

for model in models:

    print(
        "\nMODEL="
        + model[
            "class"
        ]
    )

    for field in model[
        "fields"
    ]:

        print(
            "  FIELD="
            + field[
                "name"
            ]
            + " TYPE="
            + field[
                "annotation"
            ]
            + " DEFAULT="
            + field[
                "default"
            ]
        )


print(
    "\n=== PLATFORM DYNAMICS CONSTANTS ==="
)

for name in sorted(
    constants
):

    print(
        name
        + "="
        + str(
            constants[
                name
            ]
        )
    )


print(
    "\n=== FEATURE DETECTION ==="
)

for name,value in feature_detection.items():

    print(
        name.upper()
        + "="
        + str(
            value
        )
    )


print(
    "\n=== PLATFORM CONTRACT LITERALS ==="
)

for value in platform_contracts:

    print(
        value
    )


print(
    "\n=== STORAGE INVENTORY ==="
)

for row in storage_inventory:

    print("")
    print(
        "ROOT_CONSTANT="
        + row[
            "constant"
        ]
    )

    print(
        "ROOT_PATH="
        + row[
            "path"
        ]
    )

    print(
        "EXISTS="
        + str(
            row[
                "exists"
            ]
        )
    )

    print(
        "FILE_COUNT="
        + str(
            row[
                "file_count"
            ]
        )
    )

    for sample in row[
        "files"
    ]:

        print(
            json.dumps(
                sample,
                ensure_ascii=False,
                separators=(",",":"),
            )
        )


print(
    "\n=== EXACT ROUTE SOURCES ==="
)

for row in route_functions:

    if not row.get(
        "source"
    ):
        continue

    print(
        "\n--- "
        + row[
            "name"
        ]
        + " ---"
    )

    print(
        row[
            "source"
        ]
    )


print(
    "\n=== HELPER SOURCES ==="
)

for row in helpers:

    print(
        "\n--- "
        + row[
            "name"
        ]
        + " "
        + str(
            row[
                "signature"
            ]
        )
        + " ---"
    )

    print(
        row[
            "source"
        ]
    )


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
)

print(
    "NETWORK_REQUEST_PERFORMED=False"
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
    "SM3_09C7_B3E_A1_D3_PLATFORM_DYNAMICS_DEEP_CONTRACT_MAP_COMPLETE"
)
