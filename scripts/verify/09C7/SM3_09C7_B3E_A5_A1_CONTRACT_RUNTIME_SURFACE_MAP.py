from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


a2_path = Path(sys.argv[1])
a3_path = Path(sys.argv[2])
worker_path = Path(sys.argv[3])
temporal_path = Path(sys.argv[4])
output_path = Path(sys.argv[5])


DISCOVERY_TERMS = [
    "platform",
    "dynamics",
    "evidence",
    "provenance",
    "uncertainty",
    "signal",
    "snapshot",
    "temporal",
    "validity",
    "expiry",
    "expire",
    "as_of",
    "hypothesis",
    "revision",
    "prediction",
    "outcome",
    "drift",
    "experiment",
    "confound",
    "signature",
    "taste",
    "confidence",
    "decay",
    "identity",
    "version",
    "causal",
    "observation",
]


RUNTIME_SYMBOL_TERMS = [
    "platform",
    "dynamics",
    "evidence",
    "signal",
    "snapshot",
    "temporal",
    "hypothesis",
    "prediction",
    "outcome",
    "drift",
    "experiment",
    "taste",
    "confidence",
    "provenance",
]


KNOWN_PLATFORM_ROUTE_PREFIX = (
    "/production/culture-intelligence/"
)


def sha256(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def flatten(
    value: Any,
    path: str = "$",
) -> list[dict[str, Any]]:

    rows: list[dict[str, Any]] = []

    if isinstance(value, dict):

        for key, child in value.items():

            rows.extend(
                flatten(
                    child,
                    f"{path}.{key}",
                )
            )

        return rows


    if isinstance(value, list):

        for index, child in enumerate(value):

            rows.extend(
                flatten(
                    child,
                    f"{path}[{index}]",
                )
            )

        return rows


    rows.append({
        "path": path,
        "value": value,
        "type": type(value).__name__,
    })

    return rows


def discovery_hit(
    path: str,
    value: Any,
) -> bool:

    haystack = (
        path
        + " "
        + (
            value
            if isinstance(value, str)
            else ""
        )
    ).lower()

    return any(
        term in haystack
        for term in DISCOVERY_TERMS
    )


def relevant_symbol(
    name: str,
) -> bool:

    lowered = name.lower()

    return any(
        term in lowered
        for term in RUNTIME_SYMBOL_TERMS
    )


def const_string(
    node: ast.AST,
) -> str | None:

    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
    ):
        return node.value

    return None


a2 = json.loads(
    a2_path.read_text(
        encoding="utf-8-sig"
    )
)

a3 = json.loads(
    a3_path.read_text(
        encoding="utf-8-sig"
    )
)


a2_flat = flatten(a2)
a3_flat = flatten(a3)


a2_contract_candidates = [
    row
    for row in a2_flat
    if discovery_hit(
        row["path"],
        row["value"],
    )
]


a3_contract_candidates = [
    row
    for row in a3_flat
    if discovery_hit(
        row["path"],
        row["value"],
    )
]


worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_tree = ast.parse(
    worker_source,
    filename=str(worker_path),
)


routes: list[dict[str, Any]] = []

functions: list[str] = []

classes: list[str] = []

constants: list[str] = []

relevant_strings: set[str] = set()

temporal_imports: list[str] = []

temporal_usage: dict[str, int] = {}


for node in ast.walk(worker_tree):

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        if relevant_symbol(node.name):
            functions.append(node.name)


        for decorator in node.decorator_list:

            if not isinstance(
                decorator,
                ast.Call,
            ):
                continue


            if not isinstance(
                decorator.func,
                ast.Attribute,
            ):
                continue


            method = (
                decorator.func.attr.lower()
            )


            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                continue


            if not decorator.args:
                continue


            route_path = const_string(
                decorator.args[0]
            )


            if route_path is None:
                continue


            routes.append({
                "method": method.upper(),
                "path": route_path,
                "function": node.name,
            })


    elif isinstance(
        node,
        ast.ClassDef,
    ):

        if relevant_symbol(node.name):
            classes.append(node.name)


    elif isinstance(
        node,
        ast.Constant,
    ):

        if isinstance(
            node.value,
            str,
        ):

            text = node.value

            lowered = text.lower()

            if any(
                term in lowered
                for term in RUNTIME_SYMBOL_TERMS
            ):

                relevant_strings.add(
                    text
                )


for node in worker_tree.body:

    if isinstance(
        node,
        (
            ast.Assign,
            ast.AnnAssign,
        ),
    ):

        target_names: list[str] = []


        if isinstance(
            node,
            ast.Assign,
        ):

            for target in node.targets:

                if isinstance(
                    target,
                    ast.Name,
                ):

                    target_names.append(
                        target.id
                    )


        if isinstance(
            node,
            ast.AnnAssign,
        ):

            if isinstance(
                node.target,
                ast.Name,
            ):

                target_names.append(
                    node.target.id
                )


        for name in target_names:

            if relevant_symbol(name):
                constants.append(name)


    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):

        temporal_imports.extend(
            alias.name
            for alias in node.names
        )


for name in temporal_imports:

    temporal_usage[name] = 0


for node in ast.walk(worker_tree):

    if not isinstance(
        node,
        ast.Name,
    ):
        continue

    if node.id in temporal_usage:
        temporal_usage[node.id] += 1


platform_routes = [
    route
    for route in routes
    if route["path"].startswith(
        KNOWN_PLATFORM_ROUTE_PREFIX
    )
]


platform_dynamics_routes = [
    route
    for route in platform_routes
    if (
        "platform-dynamics"
        in route["path"]
        or
        "platform-preference"
        in route["path"]
    )
]


temporal_source = temporal_path.read_text(
    encoding="utf-8-sig"
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(temporal_path),
)


temporal_functions = sorted({
    node.name
    for node in ast.walk(temporal_tree)
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
})


temporal_classes = sorted({
    node.name
    for node in ast.walk(temporal_tree)
    if isinstance(
        node,
        ast.ClassDef,
    )
})


concept_presence: dict[str, dict[str, Any]] = {}


for term in DISCOVERY_TERMS:

    contract_a2_count = sum(
        1
        for row in a2_contract_candidates
        if term in (
            row["path"]
            + " "
            + (
                row["value"]
                if isinstance(
                    row["value"],
                    str,
                )
                else ""
            )
        ).lower()
    )


    contract_a3_count = sum(
        1
        for row in a3_contract_candidates
        if term in (
            row["path"]
            + " "
            + (
                row["value"]
                if isinstance(
                    row["value"],
                    str,
                )
                else ""
            )
        ).lower()
    )


    runtime_symbol_count = sum(
        1
        for name in (
            functions
            + classes
            + constants
        )
        if term in name.lower()
    )


    runtime_string_count = sum(
        1
        for value in relevant_strings
        if term in value.lower()
    )


    concept_presence[term] = {
        "a2_contract_hit_count":
            contract_a2_count,

        "a3_contract_hit_count":
            contract_a3_count,

        "runtime_symbol_hit_count":
            runtime_symbol_count,

        "runtime_string_hit_count":
            runtime_string_count,
    }


result = {
    "contract_version":
        "SM3_BLACK_BOX_DYNAMICS_V2_RUNTIME_SURFACE_EVIDENCE_V1",

    "a2_sha256":
        sha256(a2_path),

    "a3_sha256":
        sha256(a3_path),

    "worker_sha256":
        sha256(worker_path),

    "temporal_sha256":
        sha256(temporal_path),

    "a2_leaf_count":
        len(a2_flat),

    "a3_leaf_count":
        len(a3_flat),

    "a2_contract_candidate_count":
        len(a2_contract_candidates),

    "a3_contract_candidate_count":
        len(a3_contract_candidates),

    "a2_contract_candidates":
        a2_contract_candidates,

    "a3_contract_candidates":
        a3_contract_candidates,

    "worker_route_count":
        len(routes),

    "worker_routes":
        sorted(
            routes,
            key=lambda x: (
                x["path"],
                x["method"],
            ),
        ),

    "platform_route_count":
        len(platform_routes),

    "platform_routes":
        sorted(
            platform_routes,
            key=lambda x: (
                x["path"],
                x["method"],
            ),
        ),

    "platform_dynamics_route_count":
        len(platform_dynamics_routes),

    "platform_dynamics_routes":
        sorted(
            platform_dynamics_routes,
            key=lambda x: (
                x["path"],
                x["method"],
            ),
        ),

    "relevant_function_count":
        len(set(functions)),

    "relevant_functions":
        sorted(set(functions)),

    "relevant_class_count":
        len(set(classes)),

    "relevant_classes":
        sorted(set(classes)),

    "relevant_constant_count":
        len(set(constants)),

    "relevant_constants":
        sorted(set(constants)),

    "relevant_string_count":
        len(relevant_strings),

    "relevant_strings":
        sorted(relevant_strings),

    "temporal_imports":
        sorted(set(temporal_imports)),

    "temporal_import_usage":
        temporal_usage,

    "temporal_module_functions":
        temporal_functions,

    "temporal_module_classes":
        temporal_classes,

    "concept_presence":
        concept_presence,

    "classification_performed":
        False,

    "implementation_authorized":
        False,

    "evidence_map_pass":
        (
            len(a2_flat) > 0
            and len(a3_flat) > 0
            and len(routes) > 0
            and len(temporal_imports) > 0
        ),
}


output_path.write_text(
    json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "A2_LEAF_COUNT="
    + str(result["a2_leaf_count"])
)

print(
    "A3_LEAF_COUNT="
    + str(result["a3_leaf_count"])
)

print(
    "A2_CONTRACT_CANDIDATE_COUNT="
    + str(
        result[
            "a2_contract_candidate_count"
        ]
    )
)

print(
    "A3_CONTRACT_CANDIDATE_COUNT="
    + str(
        result[
            "a3_contract_candidate_count"
        ]
    )
)

print(
    "WORKER_ROUTE_COUNT="
    + str(result["worker_route_count"])
)

print(
    "PLATFORM_ROUTE_COUNT="
    + str(result["platform_route_count"])
)

print(
    "PLATFORM_DYNAMICS_ROUTE_COUNT="
    + str(
        result[
            "platform_dynamics_route_count"
        ]
    )
)

print(
    "RELEVANT_FUNCTION_COUNT="
    + str(
        result[
            "relevant_function_count"
        ]
    )
)

print(
    "RELEVANT_CLASS_COUNT="
    + str(
        result[
            "relevant_class_count"
        ]
    )
)

print(
    "RELEVANT_CONSTANT_COUNT="
    + str(
        result[
            "relevant_constant_count"
        ]
    )
)

print(
    "TEMPORAL_IMPORT_COUNT="
    + str(
        len(
            result[
                "temporal_imports"
            ]
        )
    )
)

print(
    "EVIDENCE_MAP_PASS="
    + str(
        result[
            "evidence_map_pass"
        ]
    )
)


if not result["evidence_map_pass"]:

    raise SystemExit(1)