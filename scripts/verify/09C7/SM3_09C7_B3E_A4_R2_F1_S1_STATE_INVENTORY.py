from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(
    "/data/media/production_state"
)

OUTPUT = Path(
    sys.argv[1]
)


INTERESTING_KEYS = (
    "contract_version",
    "store_version",
    "status",
    "created_at",
    "updated_at",
    "observed_at",
    "captured_at",
    "generated_at",
    "platform",
    "surface",
    "provider",
    "engine_version",
    "profile_id",
    "reference_item_id",
    "job_id",
    "run_id",
    "queue_id",
    "snapshot_id",
    "signal_id",
    "observation_id",
)


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def inspect_json(
    path: Path,
):

    try:

        if path.stat().st_size > 4 * 1024 * 1024:
            return None

        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            value,
            dict,
        ):
            return None

        selected = {}

        for key in INTERESTING_KEYS:

            if key in value:

                selected[
                    key
                ] = value[
                    key
                ]

        return selected

    except Exception:

        return None


files = []


if ROOT.exists():

    for path in sorted(
        ROOT.rglob(
            "*"
        )
    ):

        if not path.is_file():
            continue

        try:

            stat = path.stat()

            digest = sha256_file(
                path
            )

            record = {
                "path":
                    path.relative_to(
                        ROOT
                    ).as_posix(),

                "size":
                    stat.st_size,

                "mtime_ns":
                    stat.st_mtime_ns,

                "mtime_utc":
                    datetime.fromtimestamp(
                        stat.st_mtime,
                        timezone.utc,
                    ).isoformat(),

                "sha256":
                    digest,
            }

            metadata = inspect_json(
                path
            )

            if metadata is not None:

                record[
                    "json_metadata"
                ] = metadata

            files.append(
                record
            )

        except Exception as exc:

            files.append({
                "path":
                    path.relative_to(
                        ROOT
                    ).as_posix(),

                "scan_error":
                    repr(
                        exc
                    ),
            })


valid_files = [
    item
    for item in files
    if "mtime_ns" in item
]


latest = sorted(
    valid_files,
    key=lambda item: item[
        "mtime_ns"
    ],
    reverse=True,
)[:20]


report = {
    "captured_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "root":
        str(
            ROOT
        ),

    "file_count":
        len(
            valid_files
        ),

    "scan_error_count":
        sum(
            1
            for item in files
            if "scan_error" in item
        ),

    "files":
        valid_files,

    "latest_20":
        latest,

    "production_write_performed":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


OUTPUT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
        default=str,
    ),
    encoding="utf-8",
)


print(
    "CAPTURED_AT="
    + report[
        "captured_at"
    ]
)

print(
    "FILE_COUNT="
    + str(
        report[
            "file_count"
        ]
    )
)

print(
    "SCAN_ERROR_COUNT="
    + str(
        report[
            "scan_error_count"
        ]
    )
)


print(
    "=== LATEST 10 ==="
)

for item in latest[:10]:

    print(
        item[
            "mtime_utc"
        ]
        + " | "
        + item[
            "path"
        ]
        + " | "
        + str(
            item[
                "size"
            ]
        )
        + " bytes | "
        + item[
            "sha256"
        ][:16]
    )

    metadata = item.get(
        "json_metadata"
    )

    if metadata:

        print(
            "  META="
            + json.dumps(
                metadata,
                ensure_ascii=False,
                default=str,
            )
        )
