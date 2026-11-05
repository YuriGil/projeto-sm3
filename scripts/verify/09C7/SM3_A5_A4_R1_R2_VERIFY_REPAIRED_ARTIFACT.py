import json
import sys
from pathlib import Path

p = Path(sys.argv[1])

d = json.loads(
    p.read_text(
        encoding="utf-8-sig"
    )
)

units = {
    u["unit_id"]: u
    for u in d["sequence"]
}

i04 = units["A5-I04"]
i06 = units["A5-I06"]

checks = [
    d["contract_version"] == "SM3_BLACK_BOX_DYNAMICS_V2_IMPLEMENTATION_SEQUENCE_FREEZE_V2",
    d["revision"] == 2,
    d["artifact_encoding"] == "UTF-8",
    d["artifact_encoding_repair_revision"] == 1,
    d["implementation_authorized"] is False,
    d["canonical_source_mutation_authorized"] is False,
    d["production_mutation_authorized"] is False,
    "MOLÖTOV" in i04["purpose"],
    "MOLÃ" not in i04["purpose"],
    i06["prerequisites"] == [
        "A5-I01",
        "A5-I02",
        "A5-I03",
        "A5-I04",
    ],
]

print("REPAIRED_ARTIFACT_VERIFY_PASS=" + str(all(checks)))
print("I04_PURPOSE=" + i04["purpose"])
print("I06_PREREQUISITES=" + "|".join(i06["prerequisites"]))
print("NEXT_GATE=" + d["next_gate"])

raise SystemExit(0 if all(checks) else 1)