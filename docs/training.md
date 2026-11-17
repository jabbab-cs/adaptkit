# Train your own policy

The shipped `policies/default.json` was trained with this pipeline. Run it again to reproduce it, or change the settings to fit your own interface.

```
python -m pip install -r requirements.txt
python -I python/scripts/download_findlater.py      # 0. get the real pointing data (36 MB)
python -I python/scripts/build_layer_a.py           # 1. convert it to the AdaptKit format, fit Fitts' law per person
python -I python/scripts/check_layer_a.py           # 2. check it against the schemas
python -I python/scripts/train_need_model.py        # 3. train the need classifier (logistic regression)
python -I python/scripts/calibrate_simulator.py     # 4. one simulated user per real session + checks on held-out people
python -I python/scripts/train_policy.py --split val            # 5. train and compare on validation users
python -I python/scripts/train_policy.py --split test --final   # 6. once, at the end: evaluate on test users, write policies/
```

Everything is written to `workspace/` (never committed). Set `ADAPTKIT_WORKSPACE` to use another folder.

## What you can change

| Where | What | Default |
|---|---|---|
| `python/adaptkit/simulator.py` → `LEVELS` | target sizes, text scales, contrast and layout levels | 32/44/64 px · 1/1.5/2 · normal/high · compact/spacious |
| `python/adaptkit/simulator.py` → `ASSUMPTIONS` | effects not measured in the data (text and contrast for low vision, spacing) | `mid` |
| `python/adaptkit/env.py` → `DEFAULT_WEIGHTS` | how errors, time, changes and layout size are scored | error 1 · time 0.5/s · change 0.2 · layout 0.05 |
| `python/adaptkit/baselines.py` | how often the AI decides, safety rules, the rule-based baseline | every 3 presses |
| `python/adaptkit/qlearning.py` | learning settings (discount, exploration, warm start) | γ 0.9 |

## How it works

1. **Real data.** Findlater & Zhang (2020): 735 people pointing with a mouse or a touchscreen, 43,092 pointing trials.
2. **Simulated users.** Each real session becomes one simulated user with its own speed line (Fitts' law), endpoint spread and slip rate, so the benefit of a bigger target comes from that person's own data.
3. **Need classifier.** Logistic regression on the last 10 presses (miss rate, speed compared with typical, variability, device).
4. **Q-learning.** The state is the binned signals plus the current interface levels (3,888 states); the actions are the 7 possible changes. Training sessions are 39 presses; a decision is made every 3 presses.
5. **Safety shield.** The same rules run in training and in the browser: no change in the first 5 presses, stay inside the levels, never repeat an undone change.

## Check the two sides agree

```
python -I python/scripts/make_test_vectors.py --check
node --test js/test/
```

The JavaScript runtime and the Python trainer must compute identical features and decisions; the shared test cases in `spec/test_vectors.json` prove it.
