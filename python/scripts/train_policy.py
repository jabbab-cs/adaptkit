"""Train and compare policies on simulated users. ALL RESULTS HERE ARE SIMULATED.

    python -I python/scripts/train_policy.py --split val          # tuning: uses validation users only
    python -I python/scripts/train_policy.py --split test --final # once, at the end: held-out test users

Writes workspace/results/rl/ (evaluation tables). With --final also policies/ (the trained
policy files shipped with the kit) and the Layer B sample in workspace/synthetic/.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from adaptkit import baselines as B  # noqa: E402
from adaptkit import qlearning as Q  # noqa: E402
from adaptkit.data.findlater import EVENT_COLUMNS  # noqa: E402
from adaptkit.env import DEFAULT_WEIGHTS  # noqa: E402
from adaptkit.paths import POLICIES, PROCESSED as PROC, RESULTS, SYNTHETIC as SYN  # noqa: E402
from adaptkit.simulator import ASSUMPTIONS, users_from_table  # noqa: E402

NEED = RESULTS / "ml" / "need_model.json"
OUT = RESULTS / "rl"

EPISODES = 300_000
SENS_EPISODES = 150_000
EVAL_SESSIONS_PER_USER = 30
SEEDS = (42, 7, 123)


def evaluate(policy, users, assumptions, weights, label, seed=1000):
    rows = []
    for ui, user in enumerate(users):
        runs = [Q.run_policy(user, policy, assumptions, weights, seed + ui * 1000 + k)[0] for k in range(EVAL_SESSIONS_PER_USER)]
        rows.append({"policy": label, "session": user.session, "device": user.device, "motor_impairment": user.motor_impairment,
                     "low_vision": user.low_vision, **{k: float(np.mean([r[k] for r in runs])) for k in runs[0]}})
    return pd.DataFrame(rows)


def paired_ci(a, b, rng, n=2000):
    d = a.to_numpy() - b.to_numpy()
    means = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
    return float(d.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def groups(df):
    yield "all", df
    for device, g in df.groupby("device"):
        yield device, g
        for imp, gg in g.groupby("motor_impairment"):
            yield f"{device} / {'motor impairment' if imp else 'no motor impairment'}", gg
    yield "low vision", df[df["low_vision"] == 1]


def compare(all_rows, rng):
    """Mean per group, and each policy's difference from static with a bootstrap 95% interval across people."""
    out = []
    static = all_rows[all_rows["policy"] == "static"].set_index("session")
    for label, df in all_rows.groupby("policy"):
        for name, g in groups(df):
            if g.empty:
                continue
            base = static.loc[g["session"]]
            row = {"policy": label, "group": name, "people": int(len(g)),
                   "miss_rate": round(g["miss_rate"].mean(), 4), "time_ms": round(g["time_ms"].mean(), 1),
                   "reward": round(g["reward"].mean(), 2), "changes": round(g["changes"].mean(), 2),
                   "end_target": round(g["end_target"].mean(), 2), "end_text": round(g["end_text"].mean(), 2),
                   "end_contrast": round(g["end_contrast"].mean(), 2), "end_layout": round(g["end_layout"].mean(), 2)}
            for m in ("miss_rate", "time_ms", "reward"):
                mean, lo, hi = paired_ci(g.set_index("session")[m], base[m], rng)
                digits = 4 if m == "miss_rate" else 2
                row[f"{m}_diff"], row[f"{m}_lo"], row[f"{m}_hi"] = round(mean, digits), round(lo, digits), round(hi, digits)
            out.append(row)
    return pd.DataFrame(out)


def trained_policy(train_users, assumptions, weights, episodes, seed, use_need, warm=True, keep_q=False):
    kind_note = "with" if use_need else "without"
    policy = B.base_policy(
        NEED, "q-learning", False,
        "Simulated users calibrated on Findlater & Zhang (2020), train split; need model and bins from real windows of the same split.",
        f"Tabular Q-learning {kind_note} the need score. {episodes} training sessions. Decisions are frozen in the study.", seed)
    q, visits = Q.train(train_users, policy, assumptions, weights, episodes, seed, use_need, warm)
    policy["table"] = Q.greedy_table(q, visits, use_need)
    if keep_q:
        policy["q_values"] = {k: [round(q[k].get(a, float("nan")), 3) if a in q[k] else None for a in policy["actions"]] for k in q}
    return policy, q, visits


def write_layer_b(policy, users, assumptions, weights):
    """A readable sample of simulated sessions in the AdaptKit event format. Every row is_synthetic = 1."""
    SYN.mkdir(parents=True, exist_ok=True)
    rows = []
    for ui, user in enumerate(users[:100]):
        _, (events, log) = Q.run_policy(user, policy, assumptions, weights, 5000 + ui, collect=True)
        actions = {i: (a, u) for i, a, u in log}
        level = dict(target=0, text=0, contrast=0, layout=0)
        for i, e in enumerate(events):
            action = actions.get(i, (None, None))[0]
            rows.append({"source": "simulated", "is_synthetic": 1, "participant": f"S{user.session}", "session": f"S{user.session}",
                         "device": e["device"], "platform": "web" if e["device"] == "mouse" else "mobile", "condition": "adaptive",
                         "task": "simulated", "trial": i, "target_w": e["target_w"], "amplitude": e["amplitude"], "hit": e["hit"],
                         "time_ms": e["time_ms"], "misses": e["misses"], "ui_target_level": level["target"], "ui_text_level": level["text"],
                         "ui_contrast": level["contrast"], "ui_layout": level["layout"], "policy_action": action, "undo": 0, "outlier": 0})
            if action and action != "none":
                from adaptkit.features import apply_action
                level = apply_action(level, action, policy)
    with (SYN / "sim_events_sample.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EVENT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["val", "test"], default="val")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--no-sensitivity", action="store_true")
    args = ap.parse_args()
    if args.split == "test" and not args.final:
        sys.exit("Test users are evaluated once, at the end: pass --final.")

    OUT.mkdir(parents=True, exist_ok=True)
    table = pd.read_csv(PROC / "simulator_users.csv")
    train_users = users_from_table(table[table["split"] == "train"])
    eval_users = users_from_table(table[table["split"] == args.split])
    mid, weights = ASSUMPTIONS["mid"], DEFAULT_WEIGHTS
    rng = np.random.default_rng(42)
    started = time.time()

    static = B.base_policy(NEED, "static", False, "No training: never changes the interface.", "Baseline.")
    rule = B.base_policy(NEED, "rule-based", False, "No training: hand-written rules.", "Baseline and warm start.")
    rule["table"] = B.rule_table()
    hybrid, q, visits = trained_policy(train_users, mid, weights, EPISODES, SEEDS[0], True, keep_q=True)
    print(f"hybrid trained {time.time() - started:.0f}s | states seen {len(q)} | in table {len(hybrid['table'])}", flush=True)
    rl_only, _, _ = trained_policy(train_users, mid, weights, EPISODES, SEEDS[0], False)
    print(f"rl-only trained {time.time() - started:.0f}s", flush=True)

    rows = pd.concat([evaluate(p, eval_users, mid, weights, name) for name, p in
                      (("static", static), ("rule", rule), ("rl_only", rl_only), ("hybrid", hybrid))])
    summary = compare(rows, rng)
    summary.to_csv(OUT / f"comparison_{args.split}.csv", index=False)
    print(summary[["policy", "group", "people", "miss_rate", "miss_rate_diff", "miss_rate_lo", "miss_rate_hi", "time_ms", "time_ms_diff",
                   "time_ms_lo", "time_ms_hi", "reward_diff", "changes", "end_target", "end_text", "end_contrast", "end_layout"]].to_string(index=False), flush=True)

    actions = {}
    for a in hybrid["table"].values():
        actions[a] = actions.get(a, 0) + 1
    extra = {"split": args.split, "simulated": True, "episodes": EPISODES, "eval_sessions_per_user": EVAL_SESSIONS_PER_USER, "weights": weights,
             "assumptions": mid, "states_seen": len(q), "table_size": len(hybrid["table"]), "table_actions": actions}

    # Does a different random seed learn something equally good?
    def brief(d):
        return {"miss_rate": round(float(d["miss_rate"].mean()), 4), "time_ms": round(float(d["time_ms"].mean()), 1), "reward": round(float(d["reward"].mean()), 2)}

    static_reward = float(rows[rows["policy"] == "static"]["reward"].mean())
    stability = {"static_reward": round(static_reward, 2)}
    for name, use_need in (("hybrid", True), ("rl_only", False)):
        stability[name] = {str(SEEDS[0]): brief(rows[rows["policy"] == name])}
        for seed in SEEDS[1:]:
            p, _, _ = trained_policy(train_users, mid, weights, EPISODES, seed, use_need)
            stability[name][str(seed)] = brief(evaluate(p, eval_users, mid, weights, name))
            print(f"{name} seed {seed}: {stability[name][str(seed)]} ({time.time() - started:.0f}s)", flush=True)
    print("seed stability:", json.dumps(stability), flush=True)
    extra["seed_stability"] = stability

    if not args.no_sensitivity:
        scenarios = {
            "assumptions_low": (ASSUMPTIONS["low"], weights),
            "assumptions_high": (ASSUMPTIONS["high"], weights),
            "layout_cost_low": (mid, {**weights, "layout": 0.02}),
            "layout_cost_high": (mid, {**weights, "layout": 0.10}),
            "errors_count_double": (mid, {**weights, "error": 2.0}),
            "time_counts_half": (mid, {**weights, "time": 0.25}),
        }
        sens = {}
        for name, (assume, w) in scenarios.items():
            p, _, _ = trained_policy(train_users, assume, w, SENS_EPISODES, SEEDS[0], True)
            st = evaluate(static, eval_users, assume, w, "static")
            ad = evaluate(p, eval_users, assume, w, "hybrid")
            lv = ad["low_vision"] == 1
            sens[name] = {
                "miss_rate_static": round(st["miss_rate"].mean(), 4), "miss_rate_hybrid": round(ad["miss_rate"].mean(), 4),
                "time_ms_static": round(st["time_ms"].mean(), 1), "time_ms_hybrid": round(ad["time_ms"].mean(), 1),
                "end_target": round(ad["end_target"].mean(), 2), "end_text": round(ad["end_text"].mean(), 2),
                "end_contrast": round(ad["end_contrast"].mean(), 2), "end_layout": round(ad["end_layout"].mean(), 2),
                "low_vision_end_text": round(ad[lv]["end_text"].mean(), 2),
            }
            print(f"{name}: {sens[name]} ({time.time() - started:.0f}s)", flush=True)
        extra["sensitivity"] = sens

    (OUT / f"evaluation_{args.split}.json").write_text(json.dumps(extra, indent=2), encoding="utf-8")

    if args.final:
        POLICIES.mkdir(parents=True, exist_ok=True)
        (OUT / "policy_hybrid_with_q_values.json").write_text(json.dumps(hybrid, indent=1), encoding="utf-8")
        live = {k: v for k, v in hybrid.items() if k != "q_values"}
        (POLICIES / "default.json").write_text(json.dumps(live, indent=1), encoding="utf-8")
        (POLICIES / "rl-only.json").write_text(json.dumps(rl_only, indent=1), encoding="utf-8")
        (POLICIES / "rule-based.json").write_text(json.dumps(rule, indent=1), encoding="utf-8")
        n = write_layer_b(hybrid, train_users, mid, weights)
        print(f"wrote policies; Layer B sample {n} rows", flush=True)
    print(f"done in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
