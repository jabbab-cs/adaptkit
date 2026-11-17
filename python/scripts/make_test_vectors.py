"""Write adaptkit/spec/test_vectors.json from hand-written test cases.

The cases are TEST FIXTURES (source = "test", is_synthetic = 1), not data.
Expected values come from the Python reference implementation; the JavaScript
runtime test (adaptkit/js/test/features.test.mjs) must reproduce them.

    python -I python/scripts/make_test_vectors.py          # write
    python -I python/scripts/make_test_vectors.py --check  # verify file still matches
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptkit import features as F  # noqa: E402
from adaptkit.paths import SPEC  # noqa: E402

OUT = SPEC / "test_vectors.json"

POLICY = {
    "adaptkit_policy_version": "0.1",
    "kind": "test",
    "is_placeholder": True,
    "notes": "Hand-written values for testing only. Not trained, not for the study.",
    "window_size": 6,
    "decision_every": 3,
    "speed_ratio_cap": 4.0,
    "reference_fitts": {"mouse": {"a_ms": 385.0, "b_ms_per_bit": 166.0}, "touch": {"a_ms": 289.0, "b_ms_per_bit": 122.0}},
    "bins": {"miss_rate": [0.1, 0.3], "speed_ratio": [0.9, 1.25], "variability": [0.3], "need": [0.35, 0.65]},
    "need_model": {"intercept": -1.5, "coef": {"miss_rate": 4.0, "log_speed_ratio": 2.0, "variability": 1.0, "device_touch": 0.5}},
    "levels": {"target_px": [32, 44, 64], "font_scale": [1, 1.5, 2], "contrast": ["normal", "high"], "layout": ["compact", "spacious"]},
    "actions": F.ACTIONS,
    "shield": {"min_events_before_first_change": 5, "block_undone_actions": True},
    "table": {},
    "default_action": "none",
}


def ev(device, w, a, hit, t, outlier=0):
    return {"source": "test", "is_synthetic": 1, "participant": "X1", "session": "X1-s", "device": device,
            "task": "test", "target_w": w, "amplitude": a, "hit": hit, "time_ms": t, "outlier": outlier}


def numbered(events):
    return [{**e, "trial": i} for i, e in enumerate(events)]


UI0 = {"target": 0, "text": 0, "contrast": 0, "layout": 0}

CASES = [
    ("mouse_fast_accurate", numbered([ev("mouse", 64, 250, 1, t) for t in (600, 640, 580, 700, 620, 610, 650)]), UI0),
    ("touch_slow_misses", numbered([ev("touch", 32, 250, h, t) for h, t in
                                    [(0, 1100), (1, 950), (0, 1400), (0, 1200), (1, 1000), (0, 1600), (1, 900), (0, 1300)]]), UI0),
    ("mixed_outlier_and_missing_amplitude", numbered([
        ev("touch", 44, None, 1, 800), ev("touch", 44, 300, 1, 700), ev("touch", 44, 300, 0, 50, outlier=1),
        ev("touch", 44, 120, 0, 900), ev("touch", 44, 500, 1, 750)]), {"target": 1, "text": 0, "contrast": 0, "layout": 0}),
    ("thinking_pauses_ignored", numbered([ev("mouse", 32, 500, h, t) for h, t in
                                          [(1, 9000), (1, 1000), (1, 20000), (1, 1100), (1, 1200), (1, 15000)]]), UI0),
    ("too_few_ratios", numbered([ev("mouse", 32, None, 1, 500), ev("mouse", 32, 250, 0, 900)]), UI0),
    ("empty", [], UI0),
    ("top_levels", numbered([ev("touch", 64, 250, 0, 1500) for _ in range(6)]),
     {"target": 2, "text": 2, "contrast": 1, "layout": 1}),
    ("top_levels_contrast_off", numbered([ev("touch", 64, 250, 0, 1500) for _ in range(6)]),
     {"target": 2, "text": 2, "contrast": 0, "layout": 1}),
]

# Decision cases: (name, case name, proposed action put in the table, ctx)
DECISIONS = [
    ("allowed_target_up", "touch_slow_misses", "target_up", {"events_seen": 8, "undone": []}),
    ("blocked_too_early", "touch_slow_misses", "target_up", {"events_seen": 4, "undone": []}),
    ("blocked_undone", "touch_slow_misses", "target_up", {"events_seen": 8, "undone": ["target_up"]}),
    ("blocked_out_of_range", "top_levels", "target_up", {"events_seen": 6, "undone": []}),
    ("toggle_at_top_allowed", "top_levels_contrast_off", "contrast_toggle", {"events_seen": 6, "undone": []}),
    ("table_miss_uses_default", "mouse_fast_accurate", None, {"events_seen": 7, "undone": []}),
]


def build():
    policy = json.loads(json.dumps(POLICY))
    cases_out = []
    by_name = {}
    for name, events, ui in CASES:
        feats = F.window_features(events, policy)
        device = events[-1]["device"] if events else "mouse"
        key = F.state_key(feats, ui, device, policy)
        by_name[name] = (events, ui, key)
        cases_out.append({"name": name, "events": events, "ui": ui, "expected": {"features": feats, "state": key}})

    decisions_out = []
    for name, case, proposed, ctx in DECISIONS:
        events, ui, key = by_name[case]
        if proposed is not None:
            assert policy["table"].get(key, proposed) == proposed, f"{name}: state {key} already maps elsewhere"
            policy["table"][key] = proposed
        decisions_out.append({"name": name, "case": case, "ctx": ctx})
    for d in decisions_out:
        events, ui, _ = by_name[d["case"]]
        res = F.decide(events, ui, {"events_seen": d["ctx"]["events_seen"], "undone": set(d["ctx"]["undone"])}, policy)
        d["expected"] = {"state": res["state"], "proposed": res["proposed"], "action": res["action"],
                         "ui_after": F.apply_action(ui, res["action"], policy)}

    bins = [{"value": v, "thresholds": t, "expected": F.bin_value(v, t)} for v, t in [
        (None, [0.1, 0.3]), (0.1, [0.1, 0.3]), (0.0999, [0.1, 0.3]), (0.3, [0.1, 0.3]), (5, [0.1, 0.3]),
        (None, [0.3]), (0.3, [0.3]), (0.29, [0.3])]]
    ids = [{"amplitude": a, "target_w": w, "expected": F.index_of_difficulty(a, w)} for a, w in
           [(250, 32), (500, 64), (0, 32), (None, 32), (250, 0)]]
    return {
        "note": "TEST FIXTURES for adaptkit/spec/features.md. Not data. Generated by adaptkit/python/scripts/make_test_vectors.py.",
        "tolerance": 1e-9,
        "policy": policy,
        "index_of_difficulty": ids,
        "bins": bins,
        "cases": cases_out,
        "decisions": decisions_out,
    }


def close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=tol)
    return a == b


def main():
    data = build()
    if "--check" in sys.argv:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
        ok = close(json.loads(json.dumps(data)), saved, data["tolerance"])
        print("test vectors match" if ok else "MISMATCH: regenerate or fix features.py")
        sys.exit(0 if ok else 1)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(data['cases'])} cases, {len(data['decisions'])} decisions)")
    for c in data["cases"]:
        print(f"  {c['name']:38} {c['expected']['state']}  {c['expected']['features']}")
    for d in data["decisions"]:
        print(f"  {d['name']:38} {d['expected']}")


if __name__ == "__main__":
    main()
