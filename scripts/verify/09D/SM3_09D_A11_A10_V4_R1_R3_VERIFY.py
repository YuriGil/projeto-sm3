
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def main() -> int:
    root = Path(sys.argv[1]).resolve()
    result_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_RESULT.json"

    if not result_path.is_file():
        raise RuntimeError("RESULT_MISSING:" + str(result_path))

    result = load_json(result_path)
    proposal = result.get("proposal")

    if not isinstance(proposal, dict):
        raise RuntimeError("PROPOSAL_INVALID")

    platforms = proposal.get("platforms")
    if not isinstance(platforms, list):
        raise RuntimeError("PLATFORMS_INVALID")

    expected_pairs = {
        ("INSTAGRAM", "REELS"),
        ("TIKTOK", "FOR_YOU"),
    }

    observed_pairs = set()
    all_unique = True
    all_cardinality = True

    for platform in platforms:
        if not isinstance(platform, dict):
            raise RuntimeError("PLATFORM_ITEM_INVALID")

        scope = (
            str(platform.get("platform", "")),
            str(platform.get("surface", "")),
        )

        observed_pairs.add(scope)

        timeline = platform.get("timeline")
        if not isinstance(timeline, list):
            raise RuntimeError("TIMELINE_INVALID:" + repr(scope))

        ids = [
            str(item.get("candidate_id", ""))
            for item in timeline
            if isinstance(item, dict)
        ]

        if len(ids) != len(timeline):
            raise RuntimeError("TIMELINE_ITEM_INVALID:" + repr(scope))

        unique_ids = set(ids)
        unique_pass = len(ids) == len(unique_ids)
        cardinality_pass = 3 <= len(ids) <= 6

        all_unique = all_unique and unique_pass
        all_cardinality = all_cardinality and cardinality_pass

        print("TIMELINE_SCOPE=" + scope[0] + "/" + scope[1])
        print("TIMELINE_CANDIDATE_IDS=" + "|".join(ids))
        print("TIMELINE_COUNT=" + str(len(ids)))
        print("TIMELINE_UNIQUE_COUNT=" + str(len(unique_ids)))
        print("TIMELINE_UNIQUENESS_PASS=" + str(unique_pass))
        print("TIMELINE_CARDINALITY_PASS=" + str(cardinality_pass))

    platform_set_pass = observed_pairs == expected_pairs
    platform_count_pass = len(platforms) == 2

    result_pass = all([
        platform_set_pass,
        platform_count_pass,
        all_unique,
        all_cardinality,
    ])

    print("PLATFORM_COUNT_PASS=" + str(platform_count_pass))
    print("PLATFORM_SET_PASS=" + str(platform_set_pass))
    print("ALL_TIMELINES_UNIQUE=" + str(all_unique))
    print("ALL_TIMELINES_CARDINALITY_PASS=" + str(all_cardinality))
    print("RESULT_SHA256=" + sha(result_path))
    print("V4_R1_R3_DIRECT_RESULT_VERIFY_PASS=" + str(result_pass))

    return 0 if result_pass else 1

if __name__ == "__main__":
    raise SystemExit(main())
