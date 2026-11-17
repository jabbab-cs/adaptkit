"""Convert Findlater & Zhang (2020) into AdaptKit events and profiles.

Only the Pointing task is converted: it is the one that matches selecting a
target in a user interface. Values are reshaped, never changed.
"""

from pathlib import Path

import numpy as np
import pandas as pd

TRIALS_FILE = "SummaryDataPerTrial N=735.csv"
PROFILES_FILE = "ParticipantQuestionnaireData N=735.csv"

EVENT_COLUMNS = [
    "source", "is_synthetic", "participant", "session", "device", "platform", "condition", "task", "trial",
    "target_w", "amplitude", "hit", "time_ms", "misses", "miss_dist_px", "hesitation_ms", "zoom",
    "target_x", "target_y", "tap_x", "tap_y", "ui_target_level", "ui_text_level", "ui_contrast", "ui_layout",
    "policy_action", "undo", "outlier", "timestamp",
]

PROFILE_COLUMNS = [
    "source", "is_synthetic", "participant", "age", "age_group", "motor_impairment", "low_vision",
    "colour_vision", "other_vision", "concentration", "motor_detail",
    "device_difficulty_mouse", "device_difficulty_touch", "split",
]

MOTOR_DETAIL = {
    "MotorDifficultyRapidFatigue": "rapid_fatigue",
    "MotorDifficultyLackOfCoordination": "lack_of_coordination",
    "MotorDifficultyLowStrength": "low_strength",
    "MotorDifficultySlowMovements": "slow_movements",
    "MotorRangeOfMotion": "range_of_motion",
    "MotorDifficultyGripping": "gripping",
    "MotorDifficultyHolding": "holding",
    "MotorDifficultyTremor": "tremor",
    "MotorDifficultySpasm": "spasm",
    "MotorDifficultyMovementDirection": "movement_direction",
    "MotorDifficultyMovementDistance": "movement_distance",
    "MotorDifficultyLackOfSensation": "lack_of_sensation",
    "MotorDifficultyOther": "other",
}

MIN_PLAUSIBLE_MS = 100  # faster than any aimed movement; treated as an outlier

DEVICE = {"DESKTOP": "mouse", "TOUCH": "touch"}
PLATFORM = {"DESKTOP": "web", "TOUCH": "mobile"}


def age_group(age):
    if pd.isna(age):
        return None
    for upper, label in [(24, "18-24"), (34, "25-34"), (49, "35-49"), (64, "50-64")]:
        if age <= upper:
            return label
    return "65+"


def load_events(raw_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Pointing trials as AdaptKit events. Returns (events, cleaning counts)."""
    t = pd.read_csv(raw_dir / TRIALS_FILE, low_memory=False)
    p = t[t["TaskName"] == "Pointing"].copy()
    p = p.sort_values(["ExperimentId", "BlockIndex", "TrialIndex"], kind="stable")

    spatial = p["IsSpatialOutlier"].astype(bool)
    temporal = p["IsTemporalOutlier"].eq(True)  # NaN (rows already flagged spatial) -> False
    too_fast = p["Trial_MTe"] < MIN_PLAUSIBLE_MS
    outlier = spatial | temporal | too_fast

    ev = pd.DataFrame({
        "source": "findlater2020",
        "is_synthetic": 0,
        "participant": "F" + p["ParticipantId"].astype(str),
        "session": "F" + p["ExperimentId"].astype(str),
        "device": p["DeviceType"].map(DEVICE),
        "platform": p["DeviceType"].map(PLATFORM),
        "condition": None,
        "task": "pointing",
        "trial": p.groupby("ExperimentId").cumcount(),
        "target_w": p["Trial_W_Nominal"].astype(float),
        "amplitude": p["Trial_A_Nominal"].astype(float),
        "hit": p["Trial_Success"].astype(int),
        "time_ms": p["Trial_MTe"].astype(float),
        "outlier": outlier.astype(int),
    })
    for col in EVENT_COLUMNS:
        if col not in ev.columns:
            ev[col] = None
    counts = {
        "pointing_trials": int(len(p)),
        "outlier_spatial": int(spatial.sum()),
        "outlier_temporal": int(temporal.sum()),
        "outlier_too_fast_lt_100ms": int(too_fast.sum()),
        "outlier_total": int(outlier.sum()),
        "clean_trials": int((~outlier).sum()),
    }
    return ev[EVENT_COLUMNS].reset_index(drop=True), counts


def load_profiles(raw_dir: Path) -> pd.DataFrame:
    q = pd.read_csv(raw_dir / PROFILES_FILE)
    rows = []
    for pid, g in q.groupby("ParticipantId", sort=True):
        first = g.iloc[0]
        detail = [name for col, name in MOTOR_DETAIL.items() if g[col].notna().any()]
        mouse = g[g["DeviceType"] == "DESKTOP"]["SelfReportInputDeviceDifficulty"].dropna()
        touch = g[g["DeviceType"] == "TOUCH"]["SelfReportTouchscreenDifficulty"].dropna()
        rows.append({
            "source": "findlater2020",
            "is_synthetic": 0,
            "participant": f"F{pid}",
            "age": int(first["Age"]),
            "age_group": age_group(first["Age"]),
            "motor_impairment": int(g["SelfReportMotorImpairment"].max()),
            "low_vision": int(g["VisionDifficultyLowVision"].max()),
            "colour_vision": int(g["VisionDifficultyColor"].max()),
            "other_vision": int(g["VisionDifficultyOther"].max()),
            "concentration": None,
            "motor_detail": ";".join(detail) if detail else None,
            "device_difficulty_mouse": int(mouse.iloc[0]) if len(mouse) else None,
            "device_difficulty_touch": int(touch.iloc[0]) if len(touch) else None,
            "split": None,
        })
    return pd.DataFrame(rows, columns=PROFILE_COLUMNS)


def assign_splits(profiles: pd.DataFrame, seed: int = 42, train=0.7, val=0.1) -> pd.DataFrame:
    """Participant-level split, stratified by motor impairment and low vision."""
    rng = np.random.default_rng(seed)
    out = profiles.copy()
    strata = out["motor_impairment"].astype(str) + "_" + out["low_vision"].astype(str)
    for _, idx in out.groupby(strata).groups.items():
        idx = np.array(sorted(idx))
        rng.shuffle(idx)
        n = len(idx)
        n_train = int(round(n * train))
        n_val = int(round(n * val))
        out.loc[idx[:n_train], "split"] = "train"
        out.loc[idx[n_train:n_train + n_val], "split"] = "val"
        out.loc[idx[n_train + n_val:], "split"] = "test"
    return out
