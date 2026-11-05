from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


SOURCE = Path("/app/worker_service.py")

REPORT = Path(
    "/tmp/SM3_09C7_B3D_A10_METRIC_ACQUISITION_CAPABILITY.json"
)


text = SOURCE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)


# ============================================================
# 1. PROVIDER CONSTANTS / CONFIG
# ============================================================

provider_defaults = getattr(
    ws,
    "REFERENCE_PROVIDER_DEFAULTS",
    None,
)

constants = {}

for name in dir(ws):

    upper = name.upper()

    if not any(
        token in upper
        for token in (
            "PROVIDER",
            "SCRAPER",
            "DISCOVERY",
            "HARVEST",
            "METRICOOL",
            "OBSERVATION",
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
        constants[name] = value

    elif isinstance(
        value,
        (
            dict,
            list,
            tuple,
            set,
        ),
    ):
        try:
            json.dumps(
                value,
                default=str,
            )
            constants[name] = value
        except Exception:
            constants[name] = str(
                value
            )


# ============================================================
# 2. IMPORTED NETWORK CLIENTS
# ============================================================

network_imports = []

for node in tree.body:

    if isinstance(
        node,
        ast.Import,
    ):

        for alias in node.names:

            root = alias.name.split(
                "."
            )[0]

            if root in {
                "requests",
                "httpx",
                "aiohttp",
                "urllib",
                "socket",
            }:
                network_imports.append(
                    alias.name
                )

    elif isinstance(
        node,
        ast.ImportFrom,
    ):

        module = str(
            node.module
            or ""
        )

        root = module.split(
            "."
        )[0]

        if root in {
            "requests",
            "httpx",
            "aiohttp",
            "urllib",
            "socket",
        }:
            network_imports.append(
                module
            )


network_imports = sorted(
    set(
        network_imports
    )
)


# ============================================================
# 3. RELEVANT REQUEST MODELS
# ============================================================

models = []


for node in tree.body:

    if not isinstance(
        node,
        ast.ClassDef,
    ):
        continue

    lower = node.name.lower()

    if not any(
        token in lower
        for token in (
            "provider",
            "scraper",
            "discovery",
            "observation",
            "harvest",
            "metric",
        )
    ):
        continue

    fields = []

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
            annotation = ast.unparse(
                child.annotation
            )
        except Exception:
            annotation = None

        try:
            default = (
                ast.unparse(
                    child.value
                )
                if child.value is not None
                else None
            )
        except Exception:
            default = None

        fields.append({
            "name":
                child.target.id,

            "annotation":
                annotation,

            "default":
                default,
        })

    models.append({
        "class":
            node.name,

        "fields":
            fields,
    })


# ============================================================
# 4. ROUTES
# ============================================================

routes = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    route_method = None
    route_path = None

    for decorator in node.decorator_list:

        if not isinstance(
            decorator,
            ast.Call,
        ):
            continue

        fn = decorator.func

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
            fn.value.id == "app"
            and
            fn.attr in {
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

        arg = decorator.args[0]

        if not (
            isinstance(
                arg,
                ast.Constant,
            )
            and
            isinstance(
                arg.value,
                str,
            )
        ):
            continue

        route_method = (
            fn.attr.upper()
        )

        route_path = arg.value

    if not route_path:
        continue

    combined = (
        node.name
        + "\n"
        + route_path
    ).lower()

    if not any(
        token in combined
        for token in (
            "provider",
            "scraper",
            "discovery",
            "observation",
            "harvest",
            "metric",
        )
    ):
        continue

    try:
        source = inspect.getsource(
            getattr(
                ws,
                node.name,
            )
        )
    except Exception:
        source = ""

    source_lower = source.lower()

    network_markers = []

    for marker in (
        "requests.",
        "httpx.",
        "aiohttp.",
        "urlopen(",
        "urllib.request",
        "socket.",
        "curl ",
        "wget ",
    ):
        if marker in source_lower:
            network_markers.append(
                marker
            )

    provider_literals = sorted(
        set(
            re.findall(
                r'''provider\s*=\s*["']([^"']+)["']''',
                source,
            )
        )
    )

    routes.append({
        "method":
            route_method,

        "path":
            route_path,

        "function":
            node.name,

        "network_markers":
            network_markers,

        "provider_literals":
            provider_literals,

        "has_direct_network_call":
            bool(
                network_markers
            ),

        "source":
            source,
    })


# ============================================================
# 5. ALL RELEVANT FUNCTIONS
# ============================================================

functions = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    lower_name = (
        node.name.lower()
    )

    if not any(
        token in lower_name
        for token in (
            "provider",
            "scraper",
            "discovery",
            "observation",
            "harvest",
            "metric",
        )
    ):
        continue

    try:
        source = inspect.getsource(
            getattr(
                ws,
                node.name,
            )
        )
    except Exception:
        continue

    lower = source.lower()

    network_markers = []

    for marker in (
        "requests.",
        "httpx.",
        "aiohttp.",
        "urlopen(",
        "urllib.request",
        "socket.",
        "curl ",
        "wget ",
    ):
        if marker in lower:
            network_markers.append(
                marker
            )

    functions.append({
        "name":
            node.name,

        "network_markers":
            network_markers,

        "has_direct_network_call":
            bool(
                network_markers
            ),

        "mentions_metric_fields":
            any(
                token in lower
                for token in (
                    "views",
                    "likes",
                    "comments",
                    "interactions",
                    "engagement",
                )
            ),

        "source":
            source,
    })


# ============================================================
# 6. HARDCODED PROVIDER ASSIGNMENTS
# ============================================================

hardcoded_providers = []


pattern = re.compile(
    r'''provider\s*=\s*["']([^"']+)["']'''
)


for lineno,line in enumerate(
    text.splitlines(),
    start=1,
):

    matches = pattern.findall(
        line
    )

    for value in matches:

        start = max(
            1,
            lineno - 5,
        )

        end = min(
            len(
                text.splitlines()
            ),
            lineno + 5,
        )

        lines = text.splitlines()

        context = "\n".join(
            f"{n}:{lines[n-1]}"
            for n in range(
                start,
                end + 1,
            )
        )

        hardcoded_providers.append({
            "line":
                lineno,

            "provider":
                value,

            "context":
                context,
        })


# ============================================================
# 7. FUNCTIONS CAPABLE OF DIRECT NETWORK I/O
# ============================================================

network_functions = [
    row
    for row in functions
    if row[
        "has_direct_network_call"
    ]
]


# ============================================================
# 8. ROUTE CLASSIFICATION
# ============================================================

route_classification = []


for row in routes:

    src = row[
        "source"
    ].lower()

    classification = []

    if row[
        "has_direct_network_call"
    ]:
        classification.append(
            "DIRECT_NETWORK_ACQUISITION"
        )

    if any(
        token in src
        for token in (
            "req.observations",
            "req.posts",
            "req.raw",
            "req.likes",
            "req.views",
            "req.comments",
            "req.interactions",
            "req.engagement",
        )
    ):
        classification.append(
            "INGRESS_ACCEPTS_PRECOLLECTED_DATA"
        )

    if (
        "production_reference_metric_snapshot"
        in src
    ):
        classification.append(
            "CAN_PERSIST_METRIC_SNAPSHOT"
        )

    if (
        "production_reference_harvest("
        in src
    ):
        classification.append(
            "CALLS_HARVEST"
        )

    if (
        'provider="metricool"'
        in src
        or
        "provider='metricool'"
        in src
    ):
        classification.append(
            "HARDCODES_METRICOOL_PROVIDER"
        )

    if not classification:
        classification.append(
            "OTHER"
        )

    route_classification.append({
        "method":
            row[
                "method"
            ],

        "path":
            row[
                "path"
            ],

        "function":
            row[
                "function"
            ],

        "classification":
            classification,

        "provider_literals":
            row[
                "provider_literals"
            ],

        "network_markers":
            row[
                "network_markers"
            ],
    })


# ============================================================
# 9. HEALTH CAPABILITY FLAGS
# ============================================================

health = ws.health()

health_subset = {}

for key,value in health.items():

    lower = str(
        key
    ).lower()

    if any(
        token in lower
        for token in (
            "provider",
            "scraper",
            "discovery",
            "observation",
            "harvest",
            "metric",
        )
    ):
        health_subset[
            key
        ] = value


# ============================================================
# 10. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3D-A10",

    "status":
        "METRIC_ACQUISITION_CAPABILITY_MAP_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "provider_defaults":
        provider_defaults,

    "provider_related_constants":
        constants,

    "network_imports":
        network_imports,

    "request_models":
        models,

    "routes":
        routes,

    "route_classification":
        route_classification,

    "network_functions":
        network_functions,

    "hardcoded_provider_assignments":
        hardcoded_providers,

    "health":
        health_subset,

    "production_write_performed":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "metric_api_called":
        False,

    "priority_api_called":
        False,

    "semantic_api_called":
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
# 11. CONSOLE SUMMARY
# ============================================================

print(
    "=== PROVIDER DEFAULTS ==="
)

print(
    json.dumps(
        provider_defaults,
        indent=2,
        ensure_ascii=False,
        default=str,
    )
)


print(
    "\n=== NETWORK IMPORTS ==="
)

print(
    json.dumps(
        network_imports,
        ensure_ascii=False,
    )
)


print(
    "\n=== ROUTE CLASSIFICATION ==="
)

for row in route_classification:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== DIRECT NETWORK FUNCTIONS ==="
)

print(
    "DIRECT_NETWORK_FUNCTION_COUNT="
    + str(
        len(
            network_functions
        )
    )
)

for row in network_functions:

    print(
        "NETWORK_FUNCTION="
        + row[
            "name"
        ]
        + " MARKERS="
        + json.dumps(
            row[
                "network_markers"
            ],
            separators=(",",":"),
        )
    )


print(
    "\n=== HARDCODED PROVIDER ASSIGNMENTS ==="
)

for row in hardcoded_providers:

    print("")
    print(
        "LINE="
        + str(
            row[
                "line"
            ]
        )
        + " PROVIDER="
        + row[
            "provider"
        ]
    )

    print(
        row[
            "context"
        ]
    )


print(
    "\n=== HEALTH CAPABILITIES ==="
)

print(
    json.dumps(
        health_subset,
        indent=2,
        ensure_ascii=False,
        default=str,
    )
)


print(
    "\n=== REQUEST MODELS ==="
)

for row in models:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== RELEVANT ROUTE SOURCES ==="
)

for row in routes:

    print(
        "\n--- "
        + str(
            row[
                "method"
            ]
        )
        + " "
        + row[
            "path"
        ]
        + " :: "
        + row[
            "function"
        ]
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
    "METRIC_API_CALLED=False"
)

print(
    "PRIORITY_API_CALLED=False"
)

print(
    "SEMANTIC_API_CALLED=False"
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
    "SM3_09C7_B3D_A10_METRIC_ACQUISITION_CAPABILITY_MAP_COMPLETE"
)
