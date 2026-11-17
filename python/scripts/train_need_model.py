"""Train the need classifier on real windows of Layer A (participant-level splits).

    python -I python/scripts/train_need_model.py          (from the adaptkit folder)

Writes workspace/results/ml/need_model.json (numbers the live app uses) and need_model_metrics.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from adaptkit import need_model as N  # noqa: E402
from adaptkit.paths import PROCESSED as PROC, RESULTS  # noqa: E402

OUT = RESULTS / "ml"
WINDOW, STRIDE, CAP = 10, 5, 4.0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(PROC / "findlater_events.csv", low_memory=False)
    profiles = pd.read_csv(PROC / "findlater_profiles.csv")
    ref_raw = json.loads((PROC / "reference_fitts.json").read_text(encoding="utf-8"))
    ref = {d: {"a_ms": ref_raw[d]["a_ms"], "b_ms_per_bit": ref_raw[d]["b_ms_per_bit"]} for d in ("mouse", "touch")}

    df = N.window_table(events, profiles, ref, WINDOW, STRIDE, CAP)
    train, val, test = (df[df["split"] == s] for s in ("train", "val", "test"))
    metrics = {"windows": {s: int((df["split"] == s).sum()) for s in ("train", "val", "test")},
               "window_size": WINDOW, "stride": STRIDE, "speed_ratio_cap": CAP, "label": "self-reported motor impairment",
               "majority_baseline_accuracy_session_test": None, "models": {}}

    for name, proto in N.new_models().items():
        cv_auc = {"mouse": [], "touch": []}
        for tr_idx, va_idx in GroupKFold(n_splits=5).split(train, groups=train["participant"]):
            tr, va = train.iloc[tr_idx], train.iloc[va_idx]
            m = clone(proto).fit(tr[N.FEATURES], tr["motor_impairment"], sample_weight=N.balance_weights(tr))
            for device, g in va.groupby("device"):
                cv_auc[device].append(roc_auc_score(g["motor_impairment"], m.predict_proba(g[N.FEATURES])[:, 1]))
        model = clone(proto).fit(train[N.FEATURES], train["motor_impairment"], sample_weight=N.balance_weights(train))
        metrics["models"][name] = {
            "cv_window_auc_within_device": {d: {"mean": round(float(np.mean(v)), 4), "sd": round(float(np.std(v)), 4)} for d, v in cv_auc.items()},
            "val": N.evaluate(model, val),
            "test": N.evaluate(model, test),
        }
        if name == "logistic_regression":
            portable = N.portable(model)
            metrics["models"][name]["coefficients"] = portable
        else:
            metrics["models"][name]["feature_importance"] = {f: round(float(i), 4) for f, i in zip(N.FEATURES, model.feature_importances_)}

    s = test.groupby("session")["motor_impairment"].first()
    metrics["majority_baseline_accuracy_session_test"] = round(float(max(s.mean(), 1 - s.mean())), 4)

    bins = N.fit_bins(train, portable)
    (OUT / "need_model.json").write_text(json.dumps({
        "fitted_on": "Findlater & Zhang (2020) Pointing, clean trials, train split, windows of 10 (real data)",
        "need_model": portable, "bins": bins, "speed_ratio_cap": CAP, "window_size": WINDOW,
        "reference_fitts": ref,
    }, indent=2), encoding="utf-8")
    (OUT / "need_model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=1))
    print("bins:", bins)


if __name__ == "__main__":
    main()
