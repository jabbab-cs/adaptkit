"""User simulator: each simulated user is one REAL session's measured behaviour.

Grounded in real data (fitted per session on Findlater & Zhang 2020):
  - movement time:  MT = a + b * ID, with the session's own noise
  - accuracy:       P(hit) = (1 - lapse) * erf(W / (2 * sqrt(2) * sigma))
So the effect of a larger target comes from each person's own measurements.

ASSUMED, not measured (the dataset never changed these; tested in a sensitivity analysis):
  - how much larger text and higher contrast speed up people with low vision
  - how much a spacious layout reduces slips
  - how much larger elements increase travel distance
"""

import math
import random
from dataclasses import dataclass

AMPLITUDES = (250.0, 500.0)  # the dataset's two main amplitudes
MAX_RETRIES = 5
LEVELS = {"target_px": [32, 44, 64], "font_scale": [1, 1.5, 2], "contrast": ["normal", "high"], "layout": ["compact", "spacious"]}

# Every number here is a design assumption. Results must be read together with the sensitivity analysis.
ASSUMPTIONS = {
    "mid": {
        "text_slowdown_per_level": 0.15,    # low-vision users: extra time per text level below the largest
        "contrast_slowdown": 0.10,          # low-vision users: extra time at normal contrast
        "spacious_slip_factor": 0.5,        # spacious layout multiplies the slip (lapse) rate by this
        "spacious_travel_factor": 1.15,     # spacious layout multiplies travel distance by this
        "target_travel_per_level": 0.10,    # each target level adds this share of travel distance
        "text_travel_per_level": 0.05,      # each text level adds this share of travel distance
    },
    "low": {
        "text_slowdown_per_level": 0.05, "contrast_slowdown": 0.03, "spacious_slip_factor": 0.8,
        "spacious_travel_factor": 1.25, "target_travel_per_level": 0.15, "text_travel_per_level": 0.10,
    },
    "high": {
        "text_slowdown_per_level": 0.30, "contrast_slowdown": 0.20, "spacious_slip_factor": 0.3,
        "spacious_travel_factor": 1.05, "target_travel_per_level": 0.05, "text_travel_per_level": 0.02,
    },
}


@dataclass
class SimUser:
    session: str
    participant: str
    device: str
    a_ms: float
    b_ms_per_bit: float
    sigma_px: float
    lapse: float
    log_sd: float
    motor_impairment: int
    low_vision: int


def users_from_table(df):
    return [SimUser(r.session, r.participant, r.device, r.a_ms, r.b_ms_per_bit, r.sigma_px, r.lapse, r.log_sd,
                    int(r.motor_impairment), int(r.low_vision)) for r in df.itertuples(index=False)]


def first_attempt(user, amplitude, width, rng, slow=1.0, lapse=None):
    """One aimed movement. Returns (hit, time_ms)."""
    pred = max(100.0, user.a_ms + user.b_ms_per_bit * math.log2(amplitude / width + 1))
    t = pred * math.exp(rng.gauss(0.0, user.log_sd)) * slow
    keep = 1.0 - (user.lapse if lapse is None else lapse)
    p = keep * math.erf(width / (2.0 * math.sqrt(2.0) * user.sigma_px))
    return rng.random() < p, t


def selection(user, ui, rng, assumptions):
    """One selection at the given UI levels, retrying after a miss until it succeeds.

    A retry is a short corrective movement: its distance is where the miss landed,
    and its time comes from the person's own Fitts' law fit.
    """
    width = float(LEVELS["target_px"][ui["target"]])
    a = assumptions
    amp = rng.choice(AMPLITUDES) * (1 + a["target_travel_per_level"] * ui["target"] + a["text_travel_per_level"] * ui["text"])
    lapse = user.lapse
    if ui["layout"] == 1:
        amp *= a["spacious_travel_factor"]
        lapse *= a["spacious_slip_factor"]
    slow = 1.0
    if user.low_vision:
        slow = (1 + a["text_slowdown_per_level"] * (2 - ui["text"])) * (1 + a["contrast_slowdown"] * (1 - ui["contrast"]))

    hit, total = first_attempt(user, amp, width, rng, slow, lapse)
    misses = 0
    while not hit and misses < MAX_RETRIES:
        misses += 1
        dist = max(width, width / 2 + abs(rng.gauss(0.0, user.sigma_px)))
        hit, extra = first_attempt(user, dist, width, rng, slow, lapse)
        total += extra
    return {
        "device": user.device, "target_w": width, "amplitude": round(amp, 1), "hit": 1 if misses == 0 else 0,
        "time_ms": round(total, 1), "misses": misses, "outlier": 0,
    }


def rng_for(seed):
    return random.Random(seed)
