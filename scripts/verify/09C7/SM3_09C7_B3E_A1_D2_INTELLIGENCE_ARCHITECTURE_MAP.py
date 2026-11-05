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
    "/tmp/SM3_09C7_B3E_A1_D2_INTELLIGENCE_ARCHITECTURE_MAP.json"
)


KEYWORDS = (
    "culture",
    "network",
    "intelligence",
    "experiment",
    "learning",
    "metric",
    "priority",
    "semantic",
    "behavior",
    "opportunity",
    "creator_request",
    "creatorrequest",
    "taste",
    "foundation",
    "feedback",
    "strategy",
    "trend",
    "performance",
)


PROPOSED_CONTRACT_LITERALS = (
    "SM3_NETWORK_STATE_V1",
    "SM3_RANKING_HYPOTHESIS_V1",
    "SM3_BEHAVIOR_EVIDENCE_V1",
    "SM3_PLATFORM_CHANGE_SIGNAL_V1",
    "SM3_EXPERIMENT_V1",
    "SM3_TASTE_MODEL_V1",
    "SM3_REFERENCE_METRIC_ACQUISITION_V1",
)


text = SOURCE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)


# ============================================================
# 3. EXACT PROPOSED CONTRACT COLLISION CHECK
# ============================================================

proposed_contract_presence = {}

for literal in PROPOSED_CONTRACT_LITERALS:

    proposed_contract_presence[
        literal
    ] = (
        literal in text
    )


# ============================================================
# 4. RELEVANT VERSION / CONTRACT CONSTANTS
# ============================================================

constants = {}


for name in sorted(
    dir(ws)
):

    upper = name.upper()

    if not any(
        token.upper() in upper
        for token in KEYWORDS
    ):
        continue

    if not any(
        marker in upper
        for marker in (
            "CONTRACT",
            "VERSION",
            "SCHEMA",
            "ENGINE",
            "POLICY",
            "MODEL",
            "PROMPT",
            "ANALYZER",
            "ROUTER",
            "THRESHOLD",
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


# ============================================================
# 5. HEALTH INTELLIGENCE FLAGS
# ============================================================

health = ws.health()

health_subset = {}


for key,value in health.items():

    lower = str(
        key
    ).lower()

    if any(
        token in lower
        for token in KEYWORDS
    ):
        health_subset[
            key
        ] = value


# ============================================================
# 6. ROUTES
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

        route_path = arg.value

        combined = (
            node.name
            + "\n"
            + route_path
        ).lower()

        if not any(
            token in combined
            for token in KEYWORDS
        ):
            continue

        routes.append({
            "method":
                fn.attr.upper(),

            "path":
                route_path,

            "function":
                node.name,
        })


# ============================================================
# 7. REQUEST / RECORD MODELS
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
        for token in KEYWORDS
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
# 8. RELEVANT FUNCTIONS
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

    lower = node.name.lower()

    if not any(
        token in lower
        for token in KEYWORDS
    ):
        continue

    try:
        signature = str(
            inspect.signature(
                getattr(
                    ws,
                    node.name
                )
            )
        )
    except Exception:
        signature = None

    functions.append({
        "name":
            node.name,

        "signature":
            signature,
    })


# ============================================================
# 9. CONTRACT LITERALS ACTUALLY PRESENT
# ============================================================

contract_literals = sorted(
    set(
        re.findall(
            r'SM3_[A-Z0-9_]+_V[0-9]+',
            text,
        )
    )
)


relevant_contract_literals = [
    literal
    for literal in contract_literals
    if any(
        token.upper() in literal
        for token in KEYWORDS
    )
]


# ============================================================
# 10. ARCHITECTURE CAPABILITY SUMMARY
# ============================================================

def contains_fragment(fragment: str) -> bool:

    f = fragment.lower()

    return (
        f in text.lower()
    )


capabilities = {
    "culture_intelligence_present":
        contains_fragment(
            "CULTURE"
        ),

    "network_state_literal_present":
        proposed_contract_presence[
            "SM3_NETWORK_STATE_V1"
        ],

    "ranking_hypothesis_literal_present":
        proposed_contract_presence[
            "SM3_RANKING_HYPOTHESIS_V1"
        ],

    "behavior_evidence_literal_present":
        proposed_contract_presence[
            "SM3_BEHAVIOR_EVIDENCE_V1"
        ],

    "platform_change_literal_present":
        proposed_contract_presence[
            "SM3_PLATFORM_CHANGE_SIGNAL_V1"
        ],

    "experiment_v1_literal_present":
        proposed_contract_presence[
            "SM3_EXPERIMENT_V1"
        ],

    "taste_model_literal_present":
        proposed_contract_presence[
            "SM3_TASTE_MODEL_V1"
        ],

    "metric_acquisition_literal_present":
        proposed_contract_presence[
            "SM3_REFERENCE_METRIC_ACQUISITION_V1"
        ],

    "creative_opportunity_mentions":
        text.lower().count(
            "opportunity"
        ),

    "creator_request_mentions":
        (
            text.lower().count(
                "creator_request"
            )
            +
            text.lower().count(
                "creatorrequest"
            )
        ),

    "experiment_mentions":
        text.lower().count(
            "experiment"
        ),

    "culture_mentions":
        text.lower().count(
            "culture"
        ),

    "learning_mentions":
        text.lower().count(
            "learning"
        ),

    "trend_mentions":
        text.lower().count(
            "trend"
        ),

    "performance_mentions":
        text.lower().count(
            "performance"
        ),
}


# ============================================================
# 11. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3E-A1-D2",

    "status":
        "CURRENT_INTELLIGENCE_ARCHITECTURE_MAP_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "runtime_source":
        str(
            SOURCE
        ),

    "proposed_contract_presence":
        proposed_contract_presence,

    "relevant_constants":
        constants,

    "health":
        health_subset,

    "routes":
        routes,

    "models":
        models,

    "functions":
        functions,

    "relevant_contract_literals":
        relevant_contract_literals,

    "capabilities":
        capabilities,

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
# 12. CONSOLE
# ============================================================

print(
    "=== CURRENT WORKER ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)


print(
    "\n=== PROPOSED CONTRACT COLLISION CHECK ==="
)

for name,value in proposed_contract_presence.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print(
    "\n=== RELEVANT CONTRACT / VERSION CONSTANTS ==="
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
    "\n=== HEALTH INTELLIGENCE FLAGS ==="
)

for name in sorted(
    health_subset
):

    print(
        name
        + "="
        + str(
            health_subset[
                name
            ]
        )
    )


print(
    "\n=== RELEVANT ROUTES ==="
)

for row in routes:

    print(
        row[
            "method"
        ]
        + " "
        + row[
            "path"
        ]
        + " :: "
        + row[
            "function"
        ]
    )


print(
    "\n=== RELEVANT MODELS ==="
)

for row in models:

    print(
        "MODEL="
        + row[
            "class"
        ]
    )

    for field in row[
        "fields"
    ]:

        print(
            "  FIELD="
            + field[
                "name"
            ]
            + " TYPE="
            + str(
                field[
                    "annotation"
                ]
            )
            + " DEFAULT="
            + str(
                field[
                    "default"
                ]
            )
        )


print(
    "\n=== RELEVANT CONTRACT LITERALS ==="
)

for literal in relevant_contract_literals:

    print(
        literal
    )


print(
    "\n=== CAPABILITY SUMMARY ==="
)

for name,value in capabilities.items():

    print(
        name.upper()
        + "="
        + str(
            value
        )
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
    "SM3_09C7_B3E_A1_D2_CURRENT_INTELLIGENCE_ARCHITECTURE_MAP_COMPLETE"
)
