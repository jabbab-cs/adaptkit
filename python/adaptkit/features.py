"""Behaviour features, state key and safety shield.

Reference implementation of adaptkit/spec/features.md. The JavaScript runtime
(adaptkit/js/adaptkit.js) must give the same results; both are checked against
adaptkit/spec/test_vectors.json.
"""

import math

ACTIONS = ["none", "target_up", "target_down", "text_up", "text_down", "contrast_toggle", "layout_toggle"]

_LEVEL_OF = {"target_up": ("target", 1), "target_down": ("target", -1), "text_up": ("text", 1), "text_down": ("text", -1)}
_LEVEL_LIST = {"target": "target_px", "text": "font_scale", "contrast": "contrast", "layout": "layout"}


def index_of_difficulty(amplitude, target_w):
    if amplitude is None or target_w is None or not target_w > 0:
        return None
    return math.log2(amplitude / target_w + 1)


def speed_ratio(event, policy):
    i = index_of_difficulty(event.get("amplitude"), event.get("target_w"))
    if i is None:
        return None
    ref = policy["reference_fitts"].get(event["device"])
    if ref is None:
        return None
    pred = ref["a_ms"] + ref["b_ms_per_bit"] * i
    if not pred > 0:
        return None
    r = event["time_ms"] / pred
    cap = policy.get("speed_ratio_cap")
    if cap is not None and r > cap:
        return None  # a reading/deciding pause, not movement
    return r


def _median(values):
    s = sorted(values)
    n = len(s)
    return s[(n - 1) // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


def window_features(events, policy):
    clean = [e for e in events if e.get("outlier") != 1]
    win = clean[-policy["window_size"]:]
    out = {"miss_rate": None, "speed_ratio": None, "variability": None, "need": None}
    if not win:
        return out
    out["miss_rate"] = sum(1 - e["hit"] for e in win) / len(win)
    ratios = [r for r in (speed_ratio(e, policy) for e in win) if r is not None]
    if ratios:
        out["speed_ratio"] = _median(ratios)
    if len(ratios) >= 3:
        mean = sum(ratios) / len(ratios)
        variance = sum((r - mean) ** 2 for r in ratios) / len(ratios)
        out["variability"] = math.sqrt(variance) / mean if mean > 0 else None
    if out["miss_rate"] is not None and out["speed_ratio"] is not None and out["speed_ratio"] > 0:
        m = policy["need_model"]
        device_touch = 1 if win[-1]["device"] == "touch" else 0
        z = (m["intercept"]
             + m["coef"]["miss_rate"] * out["miss_rate"]
             + m["coef"]["log_speed_ratio"] * math.log(out["speed_ratio"])
             + m["coef"]["variability"] * (out["variability"] if out["variability"] is not None else 0)
             + m["coef"]["device_touch"] * device_touch)
        out["need"] = sigmoid(z)
    return out


def bin_value(value, thresholds):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return len(thresholds) // 2
    return sum(1 for t in thresholds if t <= value)


def state_key(features, ui, device, policy):
    b = policy["bins"]
    return "-".join([
        f"m{bin_value(features['miss_rate'], b['miss_rate'])}",
        f"s{bin_value(features['speed_ratio'], b['speed_ratio'])}",
        f"v{bin_value(features['variability'], b['variability'])}",
        f"n{bin_value(features['need'], b['need'])}",
        f"t{ui['target']}", f"x{ui['text']}", f"c{ui['contrast']}", f"l{ui['layout']}",
        f"d{1 if device == 'touch' else 0}",
    ])


def apply_action(ui, action, policy):
    nxt = dict(ui)
    if action in _LEVEL_OF:
        key, step = _LEVEL_OF[action]
        nxt[key] = ui[key] + step
    elif action == "contrast_toggle":
        nxt["contrast"] = 1 if ui["contrast"] == 0 else 0
    elif action == "layout_toggle":
        nxt["layout"] = 1 if ui["layout"] == 0 else 0
    return nxt


def _in_range(ui, policy):
    return all(0 <= ui[key] < len(policy["levels"][lst]) for key, lst in _LEVEL_LIST.items())


def shield_action(action, ctx, ui, policy):
    """ctx = {"events_seen": int, "undone": set of actions}."""
    if action == "none":
        return "none"
    if ctx["events_seen"] < policy["shield"]["min_events_before_first_change"]:
        return "none"
    if policy["shield"]["block_undone_actions"] and action in ctx["undone"]:
        return "none"
    if not _in_range(apply_action(ui, action, policy), policy):
        return "none"
    return action


def decide(events, ui, ctx, policy):
    features = window_features(events, policy)
    device = events[-1]["device"] if events else "mouse"
    state = state_key(features, ui, device, policy)
    proposed = policy["table"].get(state, policy["default_action"])
    action = shield_action(proposed, ctx, ui, policy)
    return {"features": features, "state": state, "proposed": proposed, "action": action}
