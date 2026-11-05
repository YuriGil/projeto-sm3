from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, "/app")

import worker_service as ws


STATE = Path("/data/media/production_state")

REPORT = Path(
    "/tmp/SM3_09C7_B3B_REAL_SEMANTIC_PREFLIGHT.json"
)


def load_records():
    records=[]

    for path in STATE.rglob("*.json"):
        try:
            rec=json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        if not isinstance(rec,dict):
            continue

        records.append(
            (
                path,
                rec,
            )
        )

    return records


def contract(rec):
    return str(
        rec.get("contract_version")
        or ""
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


records=load_records()


items={}
acquisitions={}
mechanicals={}
priorities={}
tombstones={}


for path,rec in records:

    cv=contract(rec)

    if cv=="SM3_REFERENCE_ITEM_V1":
        rid=str(
            rec.get("reference_item_id")
            or ""
        )
        if rid:
            items[rid]=rec

    elif cv in {
        "SM3_REFERENCE_MEDIA_ACQUISITION_V1",
        "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
    }:
        rid=str(
            rec.get("acquisition_id")
            or ""
        )
        if rid:
            acquisitions[rid]=rec

    elif cv=="SM3_REFERENCE_MECHANICAL_ANALYSIS_V1":
        rid=str(
            rec.get("mechanical_analysis_id")
            or ""
        )
        if rid:
            mechanicals[rid]=rec

    elif cv=="SM3_REFERENCE_PRIORITY_DECISION_V1":
        rid=str(
            rec.get("priority_decision_id")
            or ""
        )
        if rid:
            priorities[rid]=rec

    elif cv=="SM3_REFERENCE_ITEM_TOMBSTONE_V1":
        rid=str(
            rec.get("reference_item_id")
            or ""
        )
        if rid:
            tombstones.setdefault(
                rid,
                []
            ).append(rec)


item_rows=[]
ready_candidates=[]


for item_id in sorted(items):

    stored_item=items[item_id]

    row={
        "reference_item_id":
            item_id,

        "reference_profile_id":
            stored_item.get(
                "reference_profile_id"
            ),

        "item_type":
            stored_item.get(
                "item_type"
            ),

        "tombstone_record_count":
            len(
                tombstones.get(
                    item_id,
                    []
                )
            ),

        "active_gate":
            False,

        "active_gate_error":
            None,

        "acquisitions":
            [],
    }


    try:
        active_item=(
            ws._require_reference_item_active(
                item_id
            )
        )

        row["active_gate"]=True

    except Exception as exc:
        row["active_gate_error"]=str(
            getattr(
                exc,
                "detail",
                exc,
            )
        )

        item_rows.append(row)
        continue


    item_acquisitions=[
        rec
        for rec in acquisitions.values()
        if (
            str(
                rec.get(
                    "reference_item_id"
                )
                or ""
            )
            == item_id
        )
    ]


    for acquisition in sorted(
        item_acquisitions,
        key=lambda x:str(
            x.get(
                "acquisition_id"
            )
            or ""
        ),
    ):

        acquisition_id=str(
            acquisition.get(
                "acquisition_id"
            )
            or ""
        )

        source_sha=str(
            acquisition.get(
                "source_sha256"
            )
            or ""
        ).lower()

        acq_row={
            "acquisition_id":
                acquisition_id,

            "contract_version":
                acquisition.get(
                    "contract_version"
                ),

            "media_artifact_id":
                acquisition.get(
                    "media_artifact_id"
                ),

            "source_sha256":
                source_sha,

            "semantic_acquisition_load_ok":
                False,

            "source_resolution_ok":
                False,

            "media_artifact_ready":
                False,

            "source_hash_ok":
                False,

            "mechanical_candidates":
                [],
        }


        try:
            loaded_acquisition=(
                ws._reference_semantic_load_acquisition(
                    active_item,
                    acquisition_id,
                )
            )

            acq_row[
                "semantic_acquisition_load_ok"
            ]=True

        except Exception as exc:
            acq_row[
                "acquisition_error"
            ]=str(
                getattr(
                    exc,
                    "detail",
                    exc,
                )
            )

            row["acquisitions"].append(
                acq_row
            )

            continue


        try:
            source_path,media_artifact=(
                ws._resolve_reference_acquisition_source(
                    loaded_acquisition
                )
            )

            acq_row[
                "source_resolution_ok"
            ]=True

            acq_row[
                "resolved_source_path"
            ]=str(
                source_path
            )

            acq_row[
                "media_artifact_ready"
            ]=(
                media_artifact
                is not None
            )

            if Path(source_path).is_file():
                acq_row[
                    "source_hash_ok"
                ]=(
                    sha256_file(
                        Path(source_path)
                    ).lower()
                    == source_sha
                )

        except Exception as exc:
            acq_row[
                "source_resolution_error"
            ]=str(
                getattr(
                    exc,
                    "detail",
                    exc,
                )
            )

            row["acquisitions"].append(
                acq_row
            )

            continue


        matching_mechanicals=[
            rec
            for rec in mechanicals.values()
            if (
                str(
                    rec.get(
                        "source_sha256"
                    )
                    or ""
                ).lower()
                == source_sha
            )
        ]


        for mechanical in sorted(
            matching_mechanicals,
            key=lambda x:str(
                x.get(
                    "mechanical_analysis_id"
                )
                or ""
            ),
        ):

            mechanical_id=str(
                mechanical.get(
                    "mechanical_analysis_id"
                )
                or ""
            )

            mech_row={
                "mechanical_analysis_id":
                    mechanical_id,

                "mechanical_analysis_sha256":
                    mechanical.get(
                        "mechanical_analysis_sha256"
                    ),

                "contact_sheet_sha256":
                    mechanical.get(
                        "contact_sheet_sha256"
                    ),

                "mechanical_load_ok":
                    False,

                "contact_sheet_ok":
                    False,

                "priority_candidates":
                    [],
            }


            try:
                loaded_mechanical=(
                    ws._reference_semantic_load_mechanical(
                        source_sha,
                        mechanical_id,
                    )
                )

                mech_row[
                    "mechanical_load_ok"
                ]=True

            except Exception as exc:
                mech_row[
                    "mechanical_error"
                ]=str(
                    getattr(
                        exc,
                        "detail",
                        exc,
                    )
                )

                acq_row[
                    "mechanical_candidates"
                ].append(
                    mech_row
                )

                continue


            try:
                contact_sheet=(
                    ws._reference_semantic_contact_sheet(
                        loaded_mechanical
                    )
                )

                mech_row[
                    "contact_sheet_ok"
                ]=True

                mech_row[
                    "contact_sheet_path"
                ]=str(
                    contact_sheet
                )

            except Exception as exc:
                mech_row[
                    "contact_sheet_error"
                ]=str(
                    getattr(
                        exc,
                        "detail",
                        exc,
                    )
                )


            item_priorities=[
                rec
                for rec in priorities.values()
                if (
                    str(
                        rec.get(
                            "reference_item_id"
                        )
                        or ""
                    )
                    == item_id
                )
            ]


            for priority in sorted(
                item_priorities,
                key=lambda x:str(
                    x.get(
                        "priority_decision_id"
                    )
                    or ""
                ),
            ):

                priority_id=str(
                    priority.get(
                        "priority_decision_id"
                    )
                    or ""
                )

                priority_row={
                    "priority_decision_id":
                        priority_id,

                    "decision":
                        priority.get(
                            "decision"
                        ),

                    "eligibility":
                        priority.get(
                            "eligibility"
                        ),

                    "priority_score":
                        priority.get(
                            "priority_score"
                        ),

                    "semantic_analysis_allowed":
                        priority.get(
                            "semantic_analysis_allowed"
                        ),

                    "authorization_ok":
                        False,

                    "authorization_error":
                        None,
                }


                try:
                    authorized=(
                        ws._reference_semantic_authorizing_priority(
                            active_item,
                            source_sha,
                            loaded_mechanical,
                            priority_id,
                        )
                    )

                    priority_row[
                        "authorization_ok"
                    ]=True

                    priority_row[
                        "authorized_decision"
                    ]=authorized.get(
                        "decision"
                    )

                    priority_row[
                        "authorized_evidence_fingerprint"
                    ]=authorized.get(
                        "evidence_fingerprint"
                    )

                except Exception as exc:
                    priority_row[
                        "authorization_error"
                    ]=str(
                        getattr(
                            exc,
                            "detail",
                            exc,
                        )
                    )


                mech_row[
                    "priority_candidates"
                ].append(
                    priority_row
                )


                ready=all(
                    (
                        row[
                            "active_gate"
                        ],
                        acq_row[
                            "semantic_acquisition_load_ok"
                        ],
                        acq_row[
                            "source_resolution_ok"
                        ],
                        acq_row[
                            "media_artifact_ready"
                        ],
                        acq_row[
                            "source_hash_ok"
                        ],
                        mech_row[
                            "mechanical_load_ok"
                        ],
                        mech_row[
                            "contact_sheet_ok"
                        ],
                        priority_row[
                            "authorization_ok"
                        ],
                    )
                )


                if ready:
                    ready_candidates.append({
                        "reference_item_id":
                            item_id,

                        "reference_profile_id":
                            active_item.get(
                                "reference_profile_id"
                            ),

                        "acquisition_id":
                            acquisition_id,

                        "source_sha256":
                            source_sha,

                        "media_artifact_id":
                            loaded_acquisition.get(
                                "media_artifact_id"
                            ),

                        "mechanical_analysis_id":
                            mechanical_id,

                        "priority_decision_id":
                            priority_id,

                        "decision":
                            priority_row.get(
                                "authorized_decision"
                            ),

                        "semantic_analysis_allowed":
                            True,
                    })


            acq_row[
                "mechanical_candidates"
            ].append(
                mech_row
            )


        row[
            "acquisitions"
        ].append(
            acq_row
        )


    item_rows.append(
        row
    )


summary={
    "reference_item_count":
        len(items),

    "active_item_count":
        sum(
            1
            for row in item_rows
            if row[
                "active_gate"
            ]
        ),

    "tombstoned_or_inactive_item_count":
        sum(
            1
            for row in item_rows
            if not row[
                "active_gate"
            ]
        ),

    "acquisition_count":
        len(acquisitions),

    "mechanical_analysis_count":
        len(mechanicals),

    "priority_decision_count":
        len(priorities),

    "ready_candidate_count":
        len(
            ready_candidates
        ),
}


report={
    "phase":
        "09C7-B3B",

    "status":
        "REAL_SEMANTIC_CANARY_PREFLIGHT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "summary":
        summary,

    "ready_candidates":
        ready_candidates,

    "items":
        item_rows,

    "production_write_performed":
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
    "=== SM3 09C7-B3B REAL SEMANTIC CANARY PREFLIGHT ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)

print(
    "REFERENCE_ITEM_COUNT="
    + str(
        summary[
            "reference_item_count"
        ]
    )
)

print(
    "ACTIVE_ITEM_COUNT="
    + str(
        summary[
            "active_item_count"
        ]
    )
)

print(
    "INACTIVE_OR_TOMBSTONED_ITEM_COUNT="
    + str(
        summary[
            "tombstoned_or_inactive_item_count"
        ]
    )
)

print(
    "ACQUISITION_COUNT="
    + str(
        summary[
            "acquisition_count"
        ]
    )
)

print(
    "MECHANICAL_ANALYSIS_COUNT="
    + str(
        summary[
            "mechanical_analysis_count"
        ]
    )
)

print(
    "PRIORITY_DECISION_COUNT="
    + str(
        summary[
            "priority_decision_count"
        ]
    )
)

print(
    "READY_CANDIDATE_COUNT="
    + str(
        summary[
            "ready_candidate_count"
        ]
    )
)


for index,candidate in enumerate(
    ready_candidates,
    start=1,
):

    print(
        "READY_CANDIDATE_"
        + str(index)
        + "="
        + json.dumps(
            candidate,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "PRODUCTION_WRITE_PERFORMED=False"
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
    "SM3_09C7_B3B_REAL_SEMANTIC_CANARY_PREFLIGHT_COMPLETE"
)
