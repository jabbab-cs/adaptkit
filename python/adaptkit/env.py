"""Training environment: simulated users working through a session.

Follows the usual reset() / step(action) pattern. It uses the same feature, state and
safety-rule code as the live app (adaptkit.features), so the AI trains on what it will see.
"""

from . import features as F
from .simulator import selection

UI0 = {"target": 0, "text": 0, "contrast": 0, "layout": 0}
EPISODE_SELECTIONS = 39  # about three clinic bookings

DEFAULT_WEIGHTS = {
    "error": 1.0,     # per selection that needed a retry
    "time": 0.5,      # per second
    "change": 0.2,    # per change of the interface
    "layout": 0.05,   # per selection, per level of target / text / layout above the default
    "contrast": 0.01, # per selection at high contrast
}


class AdaptEnv:
    def __init__(self, policy, assumptions, weights=None, use_need=True, episode_selections=EPISODE_SELECTIONS):
        self.policy = policy
        self.assumptions = assumptions
        self.weights = weights or DEFAULT_WEIGHTS
        self.use_need = use_need
        self.n = episode_selections
        self.every = policy["decision_every"]
        self.min_events = policy["shield"]["min_events_before_first_change"]
        self._valid_cache = {}

    def valid_actions(self, ui):
        key = (ui["target"], ui["text"], ui["contrast"], ui["layout"])
        if key not in self._valid_cache:
            ctx = {"events_seen": 10 ** 9, "undone": ()}
            self._valid_cache[key] = [a for a in F.ACTIONS if F.shield_action(a, ctx, ui, self.policy) == a]
        return self._valid_cache[key]

    def state(self):
        f = F.window_features(self.events, self.policy)
        if not self.use_need:
            f["need"] = None  # always the middle bin: the agent cannot see the need score
        return F.state_key(f, self.ui, self.user.device, self.policy)

    def _select_block(self, rng):
        w = self.weights
        reward = 0.0
        for _ in range(self.every):
            e = selection(self.user, self.ui, rng, self.assumptions)
            self.events.append(e)
            levels = self.ui["target"] + self.ui["text"] + self.ui["layout"]
            reward -= (w["error"] * (1 - e["hit"]) + w["time"] * e["time_ms"] / 1000.0
                       + w["layout"] * levels + w["contrast"] * self.ui["contrast"])
        return reward

    def reset(self, user, rng):
        self.user = user
        self.ui = dict(UI0)
        self.events = []
        self.first_reward = self._select_block(rng)
        return self.state()

    def allowed_now(self):
        """Actions the agent may pick right now (the shield forces 'none' at the start)."""
        if len(self.events) < self.min_events:
            return ["none"]
        return self.valid_actions(self.ui)

    def step(self, action, rng):
        changed = action != "none"
        if changed:
            self.ui = F.apply_action(self.ui, action, self.policy)
        reward = self._select_block(rng) - (self.weights["change"] if changed else 0.0)
        done = len(self.events) >= self.n
        return self.state(), reward, done
