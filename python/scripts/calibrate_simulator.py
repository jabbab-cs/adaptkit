"""Fit one simulated user per real session, then check the simulator against real people.

    python -I python/scripts/calibrate_simulator.py          (from the adaptkit folder)

Writes workspace/processed/simulator_users.csv, workspace/results/sim/validation.json and charts.
Validation uses only the unadapted conditions the real participants saw:
  A. Same person, new trials: fit on the first half of a held-out session, predict the second half.
  B. New people: simulate users from the TRAIN split and compare with real TEST participants.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import ks_2samp, pearsonr  # noqa: E402

from adaptkit.fitts import fit_mt_by_condition, fit_sigma  # noqa: E402
from adaptkit.paths import PROCESSED as PROC, RESULTS  # noqa: E402
from adaptkit.simulator import SimUser, first_attempt, rng_for  # noqa: E402

OUT = RESULTS / "sim"
SEED = 42
MIN_TRIALS = 20

SURFACE, INK, INK2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
REAL, SIM = "#2a78d6", "#eb6834"


def fit_params(g, lapse):
    """Fit one session's trials. b below zero (noise in small samples) is set to 0."""
    a, b, _ = fit_mt_by_condition(g["amplitude"], g["target_w"], g["time_ms"])
    if not np.isfinite(b) or b < 0:
        a, b = float(g["time_ms"].median()), 0.0
    sigma, at_bound = fit_sigma(g["target_w"], g["hit"], lapse)
    ids = np.log2(g["amplitude"] / g["target_w"] + 1)
    pred = np.maximum(100.0, a + b * ids)
    log_sd = float(np.std(np.log(g["time_ms"] / pred)))
    return {"a_ms": round(a, 2), "b_ms_per_bit": round(b, 2), "sigma_px": round(sigma, 3), "lapse": lapse,
            "log_sd": round(log_sd, 4), "sigma_at_bound": int(at_bound)}


def lapses(clean, train_ids):
    """Slip rate per device: the miss rate on the largest common target (96 px), train split only."""
    t = clean[clean["participant"].isin(train_ids) & (clean["target_w"] == 96)]
    return {d: round(float(1 - g["hit"].mean()), 4) for d, g in t.groupby("device")}


def simulate_real_conditions(params, device, conds, rng):
    user = SimUser("", "", device, params["a_ms"], params["b_ms_per_bit"], params["sigma_px"], params["lapse"], params["log_sd"], 0, 0)
    return [first_attempt(user, a, w, rng) for a, w in conds]


def validate_same_person(test_clean, lapse, rng):
    rows = []
    for session, g in test_clean.groupby("session"):
        g = g.sort_values("trial")
        half = len(g) // 2
        first, second = g.iloc[:half], g.iloc[half:]
        if len(first) < MIN_TRIALS or first["target_w"].nunique() < 2:
            continue
        p = fit_params(first, lapse[g["device"].iloc[0]])
        conds = list(zip(second["amplitude"], second["target_w"]))
        sims = [simulate_real_conditions(p, g["device"].iloc[0], conds, rng) for _ in range(20)]
        rows.append({
            "device": g["device"].iloc[0],
            "real_hit": second["hit"].mean(),
            "sim_hit": float(np.mean([[h for h, _ in s] for s in sims])),
            "real_median_ms": second["time_ms"].median(),
            "sim_median_ms": float(np.median([[t for _, t in s] for s in sims])),
        })
    df = pd.DataFrame(rows)
    out = {}
    for device, g in df.groupby("device"):
        out[device] = {
            "sessions": int(len(g)),
            "hit_rate_mae": round(float((g["real_hit"] - g["sim_hit"]).abs().mean()), 4),
            "hit_rate_bias": round(float((g["sim_hit"] - g["real_hit"]).mean()), 4),
            "hit_rate_corr": round(float(pearsonr(g["real_hit"], g["sim_hit"])[0]), 3),
            "median_time_mae_ms": round(float((g["real_median_ms"] - g["sim_median_ms"]).abs().mean()), 1),
            "median_time_bias_ms": round(float((g["sim_median_ms"] - g["real_median_ms"]).mean()), 1),
            "median_time_corr": round(float(pearsonr(g["real_median_ms"], g["sim_median_ms"])[0]), 3),
        }
    return out


def validate_new_people(clean, users, test_ids, rng):
    """Train-split users versus real test-split participants, per device x impairment x width."""
    test = clean[clean["participant"].isin(test_ids)]
    rows, ks = [], {}
    for (device, imp), real_g in test.groupby(["device", "motor_impairment"]):
        pool = users[(users["device"] == device) & (users["motor_impairment"] == imp) & (users["split"] == "train")]
        sim_times = []
        for (amp, w), cond in real_g.groupby(["amplitude", "target_w"]):
            if len(cond) < 30:
                continue
            res = []
            for u in pool.itertuples(index=False):
                su = SimUser("", "", device, u.a_ms, u.b_ms_per_bit, u.sigma_px, u.lapse, u.log_sd, imp, 0)
                res.extend(first_attempt(su, amp, w, rng) for _ in range(20))
            sim_times.extend(t for _, t in res)
            rows.append({"device": device, "motor_impairment": int(imp), "amplitude": amp, "target_w": w, "n_real": int(len(cond)),
                         "real_hit": round(float(cond["hit"].mean()), 4), "sim_hit": round(float(np.mean([h for h, _ in res])), 4),
                         "real_median_ms": float(cond["time_ms"].median()), "sim_median_ms": round(float(np.median([t for _, t in res])), 1)})
        stat = ks_2samp(real_g["time_ms"], sim_times)
        ks[f"{device}_impairment_{int(imp)}"] = {"ks_d": round(float(stat.statistic), 4), "real_trials": int(len(real_g)), "train_users": int(len(pool))}
    return pd.DataFrame(rows), ks


def chart(table):
    agg = table.groupby(["device", "motor_impairment", "target_w"]).apply(
        lambda g: pd.Series({"real": np.average(g["real_hit"], weights=g["n_real"]), "sim": np.average(g["sim_hit"], weights=g["n_real"])}),
        include_groups=False).reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.9), sharey=True, facecolor=SURFACE)
    fig.suptitle("Simulator check: first-attempt hit rate, simulated vs real held-out people", color=INK, fontsize=12, x=0.01, ha="left")
    handles = [plt.Line2D([], [], color=REAL, linewidth=2, marker="o", label="Real (test people)"),
               plt.Line2D([], [], color=SIM, linewidth=2, marker="o", linestyle="--", label="Simulated (train users)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.935), ncol=2, frameon=False, fontsize=8.5, labelcolor=INK2)
    for ax, device in zip(axes, ["mouse", "touch"]):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK2, labelsize=9)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for imp in (0, 1):
            g = agg[(agg["device"] == device) & (agg["motor_impairment"] == imp)].sort_values("target_w")
            ax.plot(g["target_w"], g["real"] * 100, color=REAL, linewidth=2, marker="o", markersize=6, markeredgecolor=SURFACE)
            ax.plot(g["target_w"], g["sim"] * 100, color=SIM, linewidth=2, marker="o", markersize=6, markeredgecolor=SURFACE, linestyle="--")
            label = "impairment" if imp else "no impairment"
            ax.annotate(label, (g["target_w"].iloc[0], g["real"].iloc[0] * 100), xytext=(4, -13 if imp else 7), textcoords="offset points", fontsize=8, color=INK2)
        ax.set_title({"mouse": "Mouse (web)", "touch": "Touch (mobile)"}[device], color=INK, fontsize=10, loc="left")
        ax.set_xlabel("Target width (px)", color=INK2, fontsize=9)
        ax.set_xticks([32, 64, 96])
    axes[0].set_ylabel("Hit on first attempt (%)", color=INK2, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    fig.savefig(OUT / "sim_validation_hit_rate.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(PROC / "findlater_events.csv", low_memory=False)
    profiles = pd.read_csv(PROC / "findlater_profiles.csv")
    clean = events[events["outlier"] == 0].merge(profiles[["participant", "motor_impairment", "low_vision", "split"]], on="participant")
    train_ids = set(profiles.loc[profiles["split"] == "train", "participant"])
    test_ids = set(profiles.loc[profiles["split"] == "test", "participant"])
    lapse = lapses(clean, train_ids)

    rows = []
    for session, g in clean.groupby("session", sort=True):
        if len(g) < MIN_TRIALS:
            continue
        p = fit_params(g, lapse[g["device"].iloc[0]])
        rows.append({"session": session, "participant": g["participant"].iloc[0], "device": g["device"].iloc[0], **p,
                     "motor_impairment": int(g["motor_impairment"].iloc[0]), "low_vision": int(g["low_vision"].iloc[0]), "split": g["split"].iloc[0]})
    users = pd.DataFrame(rows)
    users.to_csv(PROC / "simulator_users.csv", index=False)

    rng = rng_for(SEED)
    same_person = validate_same_person(clean[clean["participant"].isin(test_ids)], lapse, rng)
    table, ks = validate_new_people(clean, users, test_ids, rng)
    table.to_csv(OUT / "sim_validation_conditions.csv", index=False)
    chart(table)
    result = {
        "lapse_per_device": lapse,
        "users": {s: int(n) for s, n in users["split"].value_counts().items()},
        "train_users_by_group": users[users["split"] == "train"].groupby(["device", "motor_impairment"]).size().rename("n").reset_index().to_dict("records"),
        "train_low_vision_users": int(users[(users["split"] == "train")]["low_vision"].sum()),
        "sigma_at_bound_sessions": int(users["sigma_at_bound"].sum()),
        "same_person_second_half": same_person,
        "new_people_ks_time": ks,
        "new_people_hit_mae": round(float((table["real_hit"] - table["sim_hit"]).abs().mean()), 4),
        "new_people_median_time_mae_ms": round(float((table["real_median_ms"] - table["sim_median_ms"]).abs().mean()), 1),
    }
    (OUT / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=1))
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
