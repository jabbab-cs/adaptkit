# AdaptKit behaviour signals, state and safety rules (v0.1)

This file is the single definition. `adaptkit/python/adaptkit/features.py` and `adaptkit/js/adaptkit.js` must both follow it, and both are checked against `test_vectors.json`.

## 1. Inputs
A list of events (see `events.schema.json`) for **one participant, one session, one device**, in `trial` order. Events with `outlier = 1` are ignored.

### Recording rules (live runtime)
- A **press** = `pointerdown` followed by `pointerup` with less than 10 px of movement and no `pointercancel` (so scrolling and swiping are not presses).
- A press whose starting element is inside `[data-adapt-target]` is a **selection** and creates one event.
- A press on anything else is a **miss**. Only misses within **1500 ms before** the next selection count for that selection (`misses`, `hit = 0`); older misses are dropped.
- `miss_dist_px` = distance from the first counted miss to the nearest edge of the selected target.
- `time_ms` = time from the previous selection (or the start of the session) to this selection. `amplitude` = distance from the previous selection point to this target's centre (null for the first selection).
- `hesitation_ms` = time from the previous selection until the first pointer activity (move or down).
- Presses inside `[data-adapt-ignore]` (e.g. the adaptation notice, the researcher panel) are not recorded at all.
- **Known limits (v0.1):** keyboard selections (Tab + Enter) are not recorded, only pointer presses. For a mouse, any small movement counts as activity, so `hesitation_ms` is close to 0 and is mainly meaningful for touch.
- **Saved logs are never deleted silently:** each session is saved in the browser under `adaptkit:<participant>:<session>`; starting a session with the same name first keeps a `:backup-<time>` copy. `downloadAllSaved()` exports every saved log.

## 2. Per-event values
- **Index of Difficulty (bits):** `id = log2(amplitude / target_w + 1)` (Shannon form). Missing if `amplitude` is null.
- **Predicted time:** `pred_ms = a_ms + b_ms_per_bit * id`, using `policy.reference_fitts[device]`.
- **Speed ratio:** `r = time_ms / pred_ms` (missing if `id` is missing or `pred_ms <= 0`). Above 1 = slower than a typical person on this device.
- **Thinking pauses:** if `policy.speed_ratio_cap` is set and `r > speed_ratio_cap`, `r` is treated as missing. In real interfaces the time before a press also includes reading and deciding, which is not movement. The value 4.0 comes from Findlater & Zhang (2020): at most 0.75% of clean pointing trials exceed it, even for people with motor impairment.

## 3. Window features
The window is the last `policy.window_size` events (or all of them, if fewer).

| Feature | Definition | Missing when |
|---|---|---|
| `miss_rate` | mean of `(1 - hit)` | window is empty |
| `speed_ratio` | **median** of `r` over events where `r` exists | no `r` in window |
| `variability` | population std of `r` divided by mean of `r` (coefficient of variation, ddof = 0) | fewer than 3 `r` values |
| `need` | `sigmoid(intercept + c1*miss_rate + c2*ln(speed_ratio) + c3*variability + c4*device_touch)` with `device_touch` = 1 for touch, 0 for mouse (device of the newest event); a missing `variability` counts as 0 here | `miss_rate` or `speed_ratio` missing, or `speed_ratio <= 0` |

Median of an even count = mean of the two middle values.

## 4. Binning
For thresholds `t` (ascending): `bin = number of thresholds that are <= value`. So with `t = [a, b]`: value < a → 0, a ≤ value < b → 1, value ≥ b → 2.
**A missing value maps to the middle bin** (`floor(len(t) / 2)`, i.e. 1 for two thresholds, 0 for one threshold). Meaning: "no evidence" is treated as "normal".

## 5. State key
```
m{miss}-s{speed}-v{var}-n{need}-t{target}-x{text}-c{contrast}-l{layout}-d{device}
```
- `miss, speed, var, need` = bins from section 4.
- `target, text, contrast, layout` = current UI level indexes (`ui_*`), starting at 0.
- `device` = 0 for mouse, 1 for touch.

Example: `m2-s2-v1-n2-t0-x0-c0-l0-d1`.

## 6. When decisions happen
After every `policy.decision_every`-th event of the session (counting all non-outlier events: 1-based count `k`, decide when `k % decision_every == 0`).

## 7. Action and safety shield
1. Look up the state key in `policy.table`; if absent, use `policy.default_action`.
2. **Shield** (applied in this order; the first rule that fires turns the action into `none`):
   1. Fewer than `shield.min_events_before_first_change` events seen so far → `none`.
   2. `shield.block_undone_actions` is true and the user has undone this action earlier in the session → `none`.
   3. The action would move a level outside its range (e.g. `target_up` at the top level) → `none`.
3. At most one action is applied per decision (by construction).
4. `contrast_toggle` / `layout_toggle` flip between level 0 and 1.

## 8. Undo
Undo restores the UI levels from before the last applied action, records `undo = 1` on the event that triggered it, and (if `block_undone_actions`) blocks that action for the rest of the session.

## 9. Rounding in test vectors
Feature values in `test_vectors.json` are compared with an absolute tolerance of `1e-9`.
