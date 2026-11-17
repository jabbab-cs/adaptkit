"""Write a demo copy of the RULE-BASED policy for trying out adaptive mode.

It is marked is_placeholder = true, so the example's researcher panel warns against using it
in a study. Its simple rules make adaptations easy to trigger on purpose.

    python -I python/scripts/make_rule_policy.py [output path]     (default: policies/demo.json)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptkit import baselines as B  # noqa: E402
from adaptkit.paths import POLICIES, RESULTS  # noqa: E402


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else POLICIES / "demo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    policy = B.base_policy(
        RESULTS / "ml" / "need_model.json", "rule-based", True,
        "Not trained. Hand-written rules.",
        "DEMO ONLY - do not use in a study. Many misses -> bigger targets, then spacious layout; some misses and slow -> bigger text, then bigger targets.")
    policy["table"] = B.rule_table()
    out.write_text(json.dumps(policy, indent=1), encoding="utf-8")
    print(f"wrote {out} | states with an action: {len(policy['table'])} of 3888")


if __name__ == "__main__":
    main()
