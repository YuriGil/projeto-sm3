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
        raise RuntimeError(f"RESULT_MISSING:{result_path}")

    result = load_json(result_path)
    proposal = result.get("proposal")
    if not isinstance(proposal, dict):
        raise RuntimeError("PROPOSAL_MISSING_OR_INVALID")

    platforms = proposal.get("platforms")
    if not isinstance(platforms, list):
        raise RuntimeError("PLATFORMS_MISSING_OR_INVALID")

    expected_pairs = {
        ("INSTAGRAM", "REELS"),
        ("TIKTOK", "FOR_YOU"),
    }

    observed_pairs = set()
    all_unique = True
    timeline_reports = []

    for platform in platforms:
        if not isinstance(platform, dict):
            raise RuntimeError("PLATFORM_ITEM_INVALID")

        pair = (
            str(platform.get("platform", "")),
            str(platform.get("surface", "")),
        )
        observed_pairs.add(pair)

        timeline = platform.get("timeline")
        if not isinstance(timeline, list):
            raise RuntimeError(f"TIMELINE_INVALID:{pair}")

        ids = [
            str(item.get("candidate_id", ""))
            for item in timeline
            if isinstance(item, dict)
        ]

        if len(ids) != len(timeline):
            raise RuntimeError(f"TIMELINE_ITEM_INVALID:{pair}")

        unique_count = len(set(ids))
        scope_unique = len(ids) == unique_count
        all_unique = all_unique and scope_unique

        timeline_reports.append({
            "platform": pair[0],
            "surface": pair[1],
            "candidate_ids": ids,
            "timeline_count": len(ids),
            "unique_count": unique_count,
            "unique": scope_unique,
        })

    platform_set_pass = observed_pairs == expected_pairs
    platform_count_pass = len(platforms) == 2
    result_pass = all([
        platform_set_pass,
        platform_count_pass,
        all_unique,
    ])

    for item in timeline_reports:
        scope = f'{item["platform"]}/{item["surface"]}'
        print(f"TIMELINE_SCOPE={scope}")
        print("TIMELINE_CANDIDATE_IDS=" + "|".join(item["candidate_ids"]))
        print(f'TIMELINE_COUNT={item["timeline_count"]}')
        print(f'TIMELINE_UNIQUE_COUNT={item["unique_count"]}')
        print(f'TIMELINE_UNIQUENESS_PASS={item["unique"]}')

    print(f"PLATFORM_COUNT_PASS={platform_count_pass}")
    print(f"PLATFORM_SET_PASS={platform_set_pass}")
    print(f"ALL_TIMELINES_UNIQUE={all_unique}")
    print(f"RESULT_SHA256={sha(result_path)}")
    print(f"V4_R1_DIRECT_RESULT_VERIFY_PASS={result_pass}")

    return 0 if result_pass else 1

if __name__ == "__main__":
    raise SystemExit(main())
