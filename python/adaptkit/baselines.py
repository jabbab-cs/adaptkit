"""Policy files: shared settings, the rule-based baseline, and table helpers."""

import itertools
import json
from datetime import date

from . import features as F
from .simulator import LEVELS

WINDOW_SIZE = 10
DECISION_EVERY = 3
SHIELD = {"min_events_before_first_change": 5, "block_undone_actions": True}


def base_policy(need_file, kind, is_placeholder, trained_on, notes, seed=None):
    """Everything except the table. need_file = results/ml/need_model.json."""
    need = json.loads(need_file.read_text(encoding="utf-8"))
    return {
        "adaptkit_policy_version": "0.1",
        "kind": kind,
        "is_placeholder": is_placeholder,
        "created": date.today().isoformat(),
        "trained_on": trained_on,
        "seed": seed,
        "notes": notes,
        "window_size": WINDOW_SIZE,
        "decision_every": DECISION_EVERY,
        "speed_ratio_cap": need["speed_ratio_cap"],
        "reference_fitts": need["reference_fitts"],
        "bins": need["bins"],
        "need_model": need["need_model"],
        "levels": LEVELS,
        "actions": F.ACTIONS,
        "shield": SHIELD,
        "table": {},
        "default_action": "none",
    }


def all_states():
    """Yields (key, miss, speed, target, text, contrast, layout) for the 3,888 states."""
    for m, s, v, n, t, x, c, lay, d in itertools.product(range(3), range(3), range(2), range(3), range(3), range(3), range(2), range(2), range(2)):
        yield f"m{m}-s{s}-v{v}-n{n}-t{t}-x{x}-c{c}-l{lay}-d{d}", m, s, t, x, c, lay


def rule_action(miss, speed, target, text, layout):
    """Hand-written rules. Bins: miss/speed 0 = low/fast, 1 = medium/normal, 2 = high/slow."""
    if miss == 2:  # many misses: bigger targets, then more spacing
        if target < 2:
            return "target_up"
        if layout == 0:
            return "layout_toggle"
        return "none"
    if miss == 1 and speed == 2:  # some misses and slow: bigger text, then bigger targets
        if text < 2:
            return "text_up"
        if target < 2:
            return "target_up"
    return "none"


def rule_table():
    table = {}
    for key, m, s, t, x, _, lay in all_states():
        action = rule_action(m, s, t, x, lay)
        if action != "none":
            table[key] = action
    return table
