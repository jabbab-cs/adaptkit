"""Need score: how much does a person seem to struggle, judged from recent behaviour?

Trained on short windows of real trials (Layer A). The class label is self-reported
motor impairment. Logistic regression is what the live app runs, because it is a few
numbers any software can compute; random forest is an offline comparison.
"""

import math

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from . import features as F

FEATURES = ["miss_rate", "log_speed_ratio", "variability", "device_touch"]
SEED = 42


def _stub_policy(reference_fitts, window_size, cap):
    return {
        "reference_fitts": reference_fitts,
        "window_size": window_size,
        "speed_ratio_cap": cap,
        "need_model": {"intercept": 0.0, "coef": {"miss_rate": 0.0, "log_speed_ratio": 0.0, "variability": 0.0, "device_touch": 0.0}},
    }


def window_table(events, profiles, reference_fitts, window_size=10, stride=5, cap=4.0):
    """One row per window of clean trials, using the same feature code as the live app."""
    policy = _stub_policy(reference_fitts, window_size, cap)
    clean = events[events["outlier"] == 0]
    info = profiles.set_index("participant")[["motor_impairment", "split"]]
    rows = []
    for session, g in clean.groupby("session", sort=True):
        participant = g["participant"].iloc[0]
        recs = g[["device", "target_w", "amplitude", "hit", "time_ms"]].to_dict("records")
        for end in range(window_size, len(recs) + 1, stride):
            f = F.window_features(recs[end - window_size:end], policy)
            if f["speed_ratio"] is None or f["speed_ratio"] <= 0:
                continue
            rows.append({
                "session": session,
                "participant": participant,
                "device": recs[0]["device"],
                "miss_rate": f["miss_rate"],
                "speed_ratio": f["speed_ratio"],
                "log_speed_ratio": math.log(f["speed_ratio"]),
                "variability": f["variability"] if f["variability"] is not None else 0.0,
                "device_touch": 1 if recs[0]["device"] == "touch" else 0,
                "motor_impairment": int(info.loc[participant, "motor_impairment"]),
                "split": info.loc[participant, "split"],
            })
    return pd.DataFrame(rows)


def new_models():
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, random_state=SEED),
        "random_forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=20, random_state=SEED, n_jobs=1),
    }


def balance_weights(df):
    """Balance the classes separately within each device.

    The dataset recruited far fewer motor-impaired people on touch (30 of 367 sessions)
    than on mouse (197 of 414). Without this, a model learns "on a phone you probably
    do not need help", which reflects recruitment, not people.
    """
    counts = df.groupby(["device", "motor_impairment"])["session"].transform("size")
    return (1.0 / counts).to_numpy() * len(df) / 4


def _scores(y, prob):
    pred = (prob >= 0.5).astype(int)
    return {
        "n": int(len(y)),
        "positive_share": round(float(np.mean(y)), 4),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y, prob)), 4) if len(set(y)) > 1 else None,
    }


def evaluate(model, df):
    """Scores per window and per session (mean probability of the session's windows)."""
    prob = model.predict_proba(df[FEATURES])[:, 1]
    out = {"window": _scores(df["motor_impairment"].to_numpy(), prob)}
    s = df.assign(prob=prob).groupby("session").agg(prob=("prob", "mean"), y=("motor_impairment", "first"), device=("device", "first"))
    out["session"] = _scores(s["y"].to_numpy(), s["prob"].to_numpy())
    for device, g in s.groupby("device"):
        out[f"session_{device}"] = _scores(g["y"].to_numpy(), g["prob"].to_numpy())
    return out


def portable(lr):
    return {
        "intercept": round(float(lr.intercept_[0]), 6),
        "coef": {name: round(float(c), 6) for name, c in zip(FEATURES, lr.coef_[0])},
    }


def need_values(need_model, df):
    z = need_model["intercept"] + sum(need_model["coef"][f] * df[f] for f in FEATURES)
    return 1 / (1 + np.exp(-z))


def fit_bins(train_df, need_model):
    """Thresholds for the state. Miss-rate bins are fixed by meaning (none / 1-2 of 10 / 3 or more of 10)."""
    return {
        "miss_rate": [0.1, 0.3],
        "speed_ratio": [round(float(q), 4) for q in np.quantile(train_df["speed_ratio"], [1 / 3, 2 / 3])],
        "variability": [round(float(np.median(train_df["variability"])), 4)],
        "need": [round(float(q), 4) for q in np.quantile(need_values(need_model, train_df), [1 / 3, 2 / 3])],
    }
