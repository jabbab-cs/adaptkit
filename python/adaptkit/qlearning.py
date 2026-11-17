"""Tabular Q-learning (Watkins & Dayan, 1992) with a warm start from the rule-based policy."""

import random

from . import features as F
from .baselines import rule_action
from .env import AdaptEnv

GAMMA = 0.90
EPS_START, EPS_END = 0.30, 0.02
MIN_VISITS = 30       # a state seen fewer times than this falls back to "no change"
WARM_BONUS = 0.30     # head start for the rule's choice


def sample_user(pools, rng):
    """Half of training time on people with no reported difficulty, half on people with one.

    Without this, the few people who need help most would hardly influence what is learned.
    """
    device = pools[rng.choice(("mouse", "touch"))]
    r = rng.random()
    group = "none" if r < 0.5 else ("motor" if r < 0.8 else "low_vision")
    pool = device[group] or device["motor"] or device["none"]
    return rng.choice(pool)


def make_pools(users):
    pools = {d: {"none": [], "motor": [], "low_vision": []} for d in ("mouse", "touch")}
    for u in users:
        group = "low_vision" if u.low_vision else ("motor" if u.motor_impairment else "none")
        pools[u.device][group].append(u)
    return pools


def _parse(key):
    p = key.split("-")
    return int(p[0][1:]), int(p[1][1:]), int(p[4][1:]), int(p[5][1:]), int(p[7][1:])


def train(users, policy, assumptions, weights, episodes, seed, use_need=True, warm_start=True):
    """Returns (Q, visits). Q maps state key -> {action: value}."""
    rng = random.Random(seed)
    env = AdaptEnv(policy, assumptions, weights, use_need)
    pools = make_pools(users)

    # Starting value: what doing nothing earns over the full discounted horizon. It must not be
    # higher than real returns, or untried settings always look better and the agent drifts to the maximum.
    total, blocks = 0.0, 0
    for _ in range(300):
        env.reset(sample_user(pools, rng), rng)
        done = False
        while not done:
            _, r, done = env.step("none", rng)
            total += r
            blocks += 1
    q0 = (total / blocks) / (1 - GAMMA)

    Q, visits = {}, {}

    def row(key, ui):
        if key not in Q:
            Q[key] = {a: q0 for a in env.valid_actions(ui)}
            if warm_start:
                m, s, t, x, lay = _parse(key)
                action = rule_action(m, s, t, x, lay)
                if action in Q[key] and action != "none":
                    Q[key][action] += WARM_BONUS
            visits[key] = {a: 0 for a in Q[key]}
        return Q[key]

    for ep in range(episodes):
        eps = EPS_END + (EPS_START - EPS_END) * max(0.0, 1 - ep / (0.8 * episodes))
        state = env.reset(sample_user(pools, rng), rng)
        done = False
        while not done:
            allowed = env.allowed_now()
            q = row(state, env.ui)
            if len(allowed) > 1 and rng.random() < eps:
                action = rng.choice(allowed)
            else:
                action = max(allowed, key=q.__getitem__)
            next_state, reward, done = env.step(action, rng)
            n = visits[state][action] = visits[state][action] + 1
            alpha = max(0.01, 1.0 / n ** 0.7)
            # A session's end is a time limit, not a real ending, and the state does not show the time
            # left. So always look ahead. Otherwise settings reached late in a session look cheap
            # (little cost remains) and the agent drifts to the maximum (Pardo et al., 2018).
            nq = row(next_state, env.ui)
            target = reward + GAMMA * max(nq[a] for a in env.allowed_now())
            q[action] += alpha * (target - q[action])
            state = next_state
    return Q, visits


def greedy_table(Q, visits, use_need=True, margin=0.0):
    """State -> best action. Rarely seen states stay out of the table, so they mean 'no change'.

    margin: a change is kept only if its value beats 'no change' by at least this much, so
    the interface does not change on small, noisy differences.
    """
    table = {}
    for key, q in Q.items():
        if sum(visits[key].values()) < MIN_VISITS:
            continue
        action = max(q, key=q.__getitem__)
        if action == "none" or q[action] - q["none"] < margin:
            continue
        if use_need:
            table[key] = action
        else:
            p = key.split("-")
            for n in range(3):
                p[3] = f"n{n}"
                table["-".join(p)] = action
    return table


def run_policy(user, policy, assumptions, weights, seed, collect=False):
    """One session with a finished policy, through the same decide() + shield as the live app."""
    rng = random.Random(seed)
    env = AdaptEnv(policy, assumptions, weights)
    env.reset(user, rng)
    total = env.first_reward
    changes = 0
    log = []
    done = False
    while not done:
        ctx = {"events_seen": len(env.events), "undone": ()}
        decision = F.decide(env.events, env.ui, ctx, policy)
        action = decision["action"]
        changes += action != "none"
        if collect:
            log.append((len(env.events) - 1, action, dict(env.ui)))
        _, r, done = env.step(action, rng)
        total += r
    misses = sum(1 - e["hit"] for e in env.events)
    return {
        "miss_rate": misses / len(env.events),
        "time_ms": sum(e["time_ms"] for e in env.events) / len(env.events),
        "reward": total,
        "changes": changes,
        **{f"end_{k}": v for k, v in env.ui.items()},
    }, (env.events, log)
