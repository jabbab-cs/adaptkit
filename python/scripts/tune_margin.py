"""Choose the minimum advantage ('margin') a change needs before the AI makes it. VALIDATION users only.

    python -I python/scripts/tune_margin.py          (from the adaptkit folder)

Trains the hybrid policy once, then builds tables with different margins and compares them.
All results are SIMULATED.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

import train_policy as T  # noqa: E402
from adaptkit import baselines as B  # noqa: E402
from adaptkit import qlearning as Q  # noqa: E402
from adaptkit.env import DEFAULT_WEIGHTS  # noqa: E402
from adaptkit.simulator import ASSUMPTIONS, users_from_table  # noqa: E402

MARGINS = (0.0, 0.25, 0.5, 1.0, 2.0)


def main():
    started = time.time()
    table = pd.read_csv(T.PROC / "simulator_users.csv")
    train_users = users_from_table(table[table["split"] == "train"])
    val_users = users_from_table(table[table["split"] == "val"])
    mid, weights = ASSUMPTIONS["mid"], DEFAULT_WEIGHTS

    policy, q, visits = T.trained_policy(train_users, mid, weights, T.EPISODES, T.SEEDS[0], True)
    print(f"trained in {time.time() - started:.0f}s", flush=True)
    static = B.base_policy(T.NEED, "static", False, "-", "-")
    st = T.evaluate(static, val_users, mid, weights, "static")
    out = {"static": {"reward": round(st["reward"].mean(), 2)}}
    for margin in MARGINS:
        policy["table"] = Q.greedy_table(q, visits, True, margin)
        d = T.evaluate(policy, val_users, mid, weights, "hybrid")
        res = {"table_size": len(policy["table"])}
        for name, g in (("all", d), ("mouse", d[d["device"] == "mouse"]), ("touch", d[d["device"] == "touch"])):
            base = st.set_index("session").loc[g["session"]]
            res[name] = {"reward_vs_static": round(g["reward"].mean() - base["reward"].mean(), 2),
                         "miss_rate": round(g["miss_rate"].mean(), 4), "changes": round(g["changes"].mean(), 2),
                         "end_target": round(g["end_target"].mean(), 2), "end_text": round(g["end_text"].mean(), 2),
                         "end_contrast": round(g["end_contrast"].mean(), 2)}
        out[str(margin)] = res
        print(margin, json.dumps(res), flush=True)
    (T.OUT / "margin_tuning_val.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
