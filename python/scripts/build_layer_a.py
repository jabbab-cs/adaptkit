"""Build Layer A: Findlater & Zhang (2020) converted into the AdaptKit format.

    python -I python/scripts/build_layer_a.py          (from the adaptkit folder)

Reads  workspace/raw/            (untouched downloads, see python/scripts/download_findlater.py)
Writes workspace/processed/      events, profiles, per-session fits, reference Fitts' model, summary, datasheet
       workspace/results/eda/    descriptive figures of the real data
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from adaptkit.data import findlater  # noqa: E402
from adaptkit.fitts import fit_mt_by_condition, fit_sigma, index_of_difficulty  # noqa: E402
from adaptkit.paths import PROCESSED, RAW, RESULTS  # noqa: E402

OUT = PROCESSED
EDA = RESULTS / "eda"
SEED = 42

# Chart style (dataviz reference palette, light mode; slots 1-2)
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
GROUP_COLOUR = {0: "#2a78d6", 1: "#eb6834"}
GROUP_LABEL = {0: "No motor impairment", 1: "Motor impairment"}
DEVICE_LABEL = {"mouse": "Mouse (web)", "touch": "Touch (mobile)"}


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def new_figure(title):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True, facecolor=SURFACE)
    fig.suptitle(title, color=INK, fontsize=12, x=0.01, ha="left")
    return fig, axes


def label_ends(ax, items, min_gap_px=13):
    """Direct labels at line ends; labels closer than min_gap_px are pushed apart vertically."""
    ax.figure.canvas.draw()
    to_px = ax.transData.transform
    placed = sorted(items, key=lambda it: to_px((it[0], it[1]))[1])
    offsets = [0.0] * len(placed)
    for i in range(1, len(placed)):
        y_prev = to_px((placed[i - 1][0], placed[i - 1][1]))[1] + offsets[i - 1]
        y_cur = to_px((placed[i][0], placed[i][1]))[1]
        if y_cur - y_prev < min_gap_px:
            offsets[i] = y_prev + min_gap_px - y_cur
    dpi_scale = 72 / ax.figure.dpi
    for (x, y, text, colour), off in zip(placed, offsets):
        ax.annotate(text, (x, y), xytext=(7, off * dpi_scale), textcoords="offset points", va="center", fontsize=8.5, color=INK2)


def add_legend(fig):
    handles = [plt.Line2D([], [], color=GROUP_COLOUR[g], linewidth=2, marker="o", markersize=6,
                          markeredgecolor=SURFACE, label=GROUP_LABEL[g]) for g in (0, 1)]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.935), ncol=2, frameon=False,
               fontsize=8.5, labelcolor=INK2)


def session_fits(events, profiles):
    clean = events[events["outlier"] == 0]
    rows = []
    for session, g in clean.groupby("session", sort=True):
        a, b, r2 = fit_mt_by_condition(g["amplitude"], g["target_w"], g["time_ms"])
        sigma, at_bound = fit_sigma(g["target_w"], g["hit"])
        rows.append({
            "session": session,
            "participant": g["participant"].iloc[0],
            "device": g["device"].iloc[0],
            "n_trials": len(g),
            "hit_rate": g["hit"].mean(),
            "median_time_ms": g["time_ms"].median(),
            "a_ms": a,
            "b_ms_per_bit": b,
            "r2": r2,
            "sigma_px": sigma,
            "sigma_at_bound": int(at_bound),
        })
    fits = pd.DataFrame(rows)
    keep = ["participant", "age", "age_group", "motor_impairment", "low_vision", "split"]
    return fits.merge(profiles[keep], on="participant", how="left")


def reference_fitts(events, profiles):
    train_ids = set(profiles.loc[profiles["split"] == "train", "participant"])
    clean = events[(events["outlier"] == 0) & events["participant"].isin(train_ids)]
    ref = {}
    for device, g in clean.groupby("device"):
        a, b, r2 = fit_mt_by_condition(g["amplitude"], g["target_w"], g["time_ms"])
        ref[device] = {"a_ms": round(a, 3), "b_ms_per_bit": round(b, 3), "r2": round(r2, 4), "n_trials": int(len(g))}
    return ref


def fig_hit_rate(events, profiles):
    df = events[events["outlier"] == 0].merge(profiles[["participant", "motor_impairment"]], on="participant")
    main_w = [w for w, n in df["target_w"].value_counts().items() if n >= 1000]
    df = df[df["target_w"].isin(main_w)]
    fig, axes = new_figure("First-attempt hit rate by target width (Findlater & Zhang 2020, Pointing task, real data)")
    table = []
    ends = {}
    for ax, device in zip(axes, ["mouse", "touch"]):
        style_axes(ax)
        ends[device] = []
        for grp in (0, 1):
            g = df[(df["device"] == device) & (df["motor_impairment"] == grp)]
            s = g.groupby("target_w")["hit"].agg(["mean", "size"]).sort_index()
            ax.plot(s.index, s["mean"] * 100, color=GROUP_COLOUR[grp], linewidth=2, marker="o", markersize=6,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
            ends[device].append((s.index[-1], s["mean"].iloc[-1] * 100, f"{s['mean'].iloc[-1] * 100:.1f}%", GROUP_COLOUR[grp]))
            for w, row in s.iterrows():
                table.append({"device": device, "motor_impairment": grp, "target_w": w, "hit_rate": row["mean"], "n": int(row["size"])})
        ax.set_title(DEVICE_LABEL[device], color=INK, fontsize=10, loc="left")
        ax.set_xlabel("Target width (px)", color=INK2, fontsize=9)
        ax.set_xticks(sorted(main_w))
        ax.set_xlim(min(main_w) - 8, max(main_w) + 30)
    axes[0].set_ylabel("Hit on first attempt (%)", color=INK2, fontsize=9)
    add_legend(fig)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    for ax, device in zip(axes, ["mouse", "touch"]):
        label_ends(ax, ends[device])
    fig.savefig(EDA / "eda_hit_rate_by_width.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return pd.DataFrame(table)


def fig_fitts(events, profiles, ref):
    df = events[events["outlier"] == 0].merge(profiles[["participant", "motor_impairment"]], on="participant")
    df = df.assign(id_bits=index_of_difficulty(df["amplitude"], df["target_w"]))
    counts = df.groupby(["amplitude", "target_w"]).size()
    main = counts[counts >= 1000].index
    df = df.set_index(["amplitude", "target_w"]).loc[main].reset_index()
    fig, axes = new_figure("Median movement time vs Index of Difficulty (real data); dashed = reference Fitts' model")
    ends = {}
    for ax, device in zip(axes, ["mouse", "touch"]):
        style_axes(ax)
        ends[device] = []
        for grp in (0, 1):
            g = df[(df["device"] == device) & (df["motor_impairment"] == grp)]
            s = g.groupby("id_bits")["time_ms"].median().sort_index()
            ax.plot(s.index, s.values, color=GROUP_COLOUR[grp], linewidth=2, marker="o", markersize=6,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
            ends[device].append((s.index[-1], s.values[-1], f"{s.values[-1]:.0f} ms", GROUP_COLOUR[grp]))
        xs = np.linspace(df["id_bits"].min(), df["id_bits"].max(), 20)
        r = ref[device]
        ax.plot(xs, r["a_ms"] + r["b_ms_per_bit"] * xs, color=MUTED, linewidth=1.2, linestyle="--")
        ax.set_title(DEVICE_LABEL[device], color=INK, fontsize=10, loc="left")
        ax.set_xlabel("Index of Difficulty (bits)", color=INK2, fontsize=9)
        ax.set_xlim(df["id_bits"].min() - 0.2, df["id_bits"].max() + 0.6)
    axes[0].set_ylabel("Median movement time (ms)", color=INK2, fontsize=9)
    add_legend(fig)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    for ax, device in zip(axes, ["mouse", "touch"]):
        label_ends(ax, ends[device])
    fig.savefig(EDA / "eda_fitts.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_sigma(fits):
    fig, axes = new_figure("Endpoint spread per session (lower = more accurate; real data, model estimate)")
    for ax, device in zip(axes, ["mouse", "touch"]):
        style_axes(ax)
        data = [fits[(fits["device"] == device) & (fits["motor_impairment"] == grp)]["sigma_px"].dropna() for grp in (0, 1)]
        bp = ax.boxplot(data, widths=0.45, patch_artist=True, showfliers=False,
                        medianprops={"color": INK, "linewidth": 1.5}, whiskerprops={"color": AXIS}, capprops={"color": AXIS})
        for patch, grp in zip(bp["boxes"], (0, 1)):
            patch.set_facecolor(GROUP_COLOUR[grp])
            patch.set_edgecolor(SURFACE)
            patch.set_alpha(0.85)
        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"{GROUP_LABEL[g]}\n(n={len(d)})" for g, d in zip((0, 1), data)], fontsize=8.5, color=INK2)
        ax.set_title(DEVICE_LABEL[device], color=INK, fontsize=10, loc="left")
    axes[0].set_ylabel("Endpoint spread sigma (px)", color=INK2, fontsize=9)
    fig.tight_layout()
    fig.savefig(EDA / "eda_sigma.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def group_table(fits):
    rows = []
    for (device, grp), g in fits.groupby(["device", "motor_impairment"]):
        rows.append({
            "device": device, "motor_impairment": int(grp), "sessions": len(g),
            "hit_rate_mean": round(g["hit_rate"].mean(), 4),
            "median_time_ms_median": round(g["median_time_ms"].median(), 1),
            "sigma_px_median": round(g["sigma_px"].median(), 2),
            "sigma_at_bound": int(g["sigma_at_bound"].sum()),
            "b_ms_per_bit_median": round(g["b_ms_per_bit"].median(), 1),
        })
    for (device, lv), g in fits.groupby(["device", "low_vision"]):
        rows.append({
            "device": device, "low_vision": int(lv), "sessions": len(g),
            "hit_rate_mean": round(g["hit_rate"].mean(), 4),
            "median_time_ms_median": round(g["median_time_ms"].median(), 1),
            "sigma_px_median": round(g["sigma_px"].median(), 2),
            "sigma_at_bound": int(g["sigma_at_bound"].sum()),
            "b_ms_per_bit_median": round(g["b_ms_per_bit"].median(), 1),
        })
    return rows


def write_datasheet(summary):
    s = summary
    text = f"""# Datasheet: Layer A (Findlater & Zhang 2020, converted)

Built by `adaptkit/python/scripts/build_layer_a.py` on {s['built']}. **REAL data** (`is_synthetic = 0`), reshaped into the AdaptKit format; no values were changed.

## Source
Findlater, L. and Zhang, L. (2020) *Input accessibility: a large dataset and summary analysis of age, motor ability and input performance*, ASSETS 2020. Licence CC BY 4.0. Downloaded 3 Nov 2026 from https://github.com/leahkf/mouseandtouchinput (files in `workspace/raw/`, untouched).

## Files
| File | Rows | What it is |
|---|---|---|
| `findlater_events.csv` | {s['events_rows']:,} | Pointing trials in the AdaptKit event format (`adaptkit/spec/events.schema.json`) |
| `findlater_profiles.csv` | {s['profiles_rows']:,} | One row per participant (`profiles.schema.json`), with the data split |
| `findlater_sessions.csv` | {s['sessions_rows']:,} | One row per participant x device: hit rate, Fitts' fit (a, b, r2), endpoint spread sigma |
| `reference_fitts.json` | - | Population Fitts' model per device, fitted on the **train split only** |
| `layer_a_summary.json` | - | All counts below, machine-readable |

## What was converted
- Only the **Pointing** task ({s['cleaning']['pointing_trials']:,} trials): it is the one that matches selecting a target in an interface. Dragging, crossing and steering were not converted.
- `participant` = "F" + ParticipantId; `session` = "F" + ExperimentId (one person x one device); `device` mouse/touch; `trial` = order within the session (block, then trial index).
- `target_w` = nominal width, `amplitude` = nominal amplitude (px), `hit` = Trial_Success (first-attempt success), `time_ms` = Trial_MTe.
- Not available in the summary file (left empty): tap coordinates, miss distance, hesitation, number of misses.

## Cleaning
Rows are kept and flagged with `outlier = 1` (excluded from fits and features):
- spatial outlier (source flag): {s['cleaning']['outlier_spatial']:,}
- temporal outlier (source flag): {s['cleaning']['outlier_temporal']:,}
- movement time under 100 ms (too fast for an aimed movement): {s['cleaning']['outlier_too_fast_lt_100ms']:,}
- **total flagged: {s['cleaning']['outlier_total']:,}; clean trials: {s['cleaning']['clean_trials']:,}**

## Split (by participant, seed {SEED}, stratified by motor impairment x low vision)
{s['split_counts']}

## Derived measures (per session)
- Fitts' law `MT = a + b * ID`, `ID = log2(A/W + 1)`, fitted on the median time of each A x W condition.
- Endpoint spread sigma: maximum likelihood from first-attempt hits and misses across widths, `P(hit) = erf(W / (2*sqrt(2)*sigma))` (1-D Gaussian approximation). Sessions with no misses have no upper information: sigma sits at the 1 px bound (`sigma_at_bound = 1`, {s['sigma_at_bound']} sessions).

## Known limits
- Impairments are self-reported. Low vision: 42 people, 30 of whom also report motor impairment.
- Collected 2015-16, online and in person, on participants' own devices (screen sizes vary).
- Nominal widths/amplitudes are in the experiment's px units; real physical size depends on the device.
- No data on text size or contrast changes.
"""
    (OUT / "datasheet.md").write_text(text, encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    EDA.mkdir(parents=True, exist_ok=True)

    events, cleaning = findlater.load_events(RAW)
    profiles = findlater.assign_splits(findlater.load_profiles(RAW), seed=SEED)
    fits = session_fits(events, profiles)
    ref = reference_fitts(events, profiles)

    events.to_csv(OUT / "findlater_events.csv", index=False)
    profiles.to_csv(OUT / "findlater_profiles.csv", index=False)
    fits.to_csv(OUT / "findlater_sessions.csv", index=False)
    (OUT / "reference_fitts.json").write_text(json.dumps({
        "fitted_on": "Findlater & Zhang (2020) Pointing, clean trials, train split only; OLS on median MT per A x W condition",
        **ref,
    }, indent=2), encoding="utf-8")

    hit_table = fig_hit_rate(events, profiles)
    fig_fitts(events, profiles, ref)
    fig_sigma(fits)
    hit_table.to_csv(EDA / "eda_hit_rate_by_width.csv", index=False)

    split_counts = profiles.groupby(["split", "motor_impairment"]).size().unstack(fill_value=0)
    split_md = "| split | no motor impairment | motor impairment | total |\n|---|---|---|---|\n" + "\n".join(
        f"| {sp} | {row.get(0, 0)} | {row.get(1, 0)} | {row.sum()} |" for sp, row in split_counts.iterrows())
    summary = {
        "built": date.today().isoformat(),
        "events_rows": int(len(events)),
        "profiles_rows": int(len(profiles)),
        "sessions_rows": int(len(fits)),
        "cleaning": cleaning,
        "split": {sp: int(n) for sp, n in profiles["split"].value_counts().items()},
        "split_counts": split_md,
        "sigma_at_bound": int(fits["sigma_at_bound"].sum()),
        "reference_fitts": ref,
        "session_fit_r2_median": round(float(fits["r2"].median()), 4),
        "groups": group_table(fits),
    }
    (OUT / "layer_a_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_datasheet(summary)

    print(json.dumps({k: v for k, v in summary.items() if k != "split_counts"}, indent=2))
    print("\nhit rate table:\n", hit_table.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
