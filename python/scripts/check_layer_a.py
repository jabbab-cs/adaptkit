"""Check Layer A files against the AdaptKit schemas and basic sanity rules.

    python -I python/scripts/check_layer_a.py          (from the adaptkit folder)
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptkit.paths import PROCESSED as PROC, SPEC  # noqa: E402

problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


for table, schema_file in [("findlater_events.csv", "events.schema.json"), ("findlater_profiles.csv", "profiles.schema.json")]:
    schema = json.loads((SPEC / schema_file).read_text(encoding="utf-8"))
    df = pd.read_csv(PROC / table, low_memory=False)
    cols = list(df.columns)
    check(sorted(cols) == sorted(schema["properties"]), f"{table}: columns differ from {schema_file}")
    for col in schema["required"]:
        check(df[col].notna().all(), f"{table}: required column '{col}' has empty values")
    for col, prop in schema["properties"].items():
        if "enum" in prop and col in df:
            allowed = {v for v in prop["enum"] if v is not None}
            bad = set(df[col].dropna().unique()) - allowed
            check(not bad, f"{table}: '{col}' has values outside the schema: {sorted(bad)[:5]}")
    print(f"{table}: {len(df):,} rows x {len(cols)} columns")

ev = pd.read_csv(PROC / "findlater_events.csv", low_memory=False)
pr = pd.read_csv(PROC / "findlater_profiles.csv")
check((ev["is_synthetic"] == 0).all(), "events: Layer A must be real (is_synthetic = 0)")
check(set(ev["participant"]) <= set(pr["participant"]), "events: participant missing from profiles")
check(pr["participant"].is_unique, "profiles: duplicate participant")
check(pr["split"].isin(["train", "val", "test"]).all(), "profiles: every participant needs a split")
check((ev.groupby("session")["trial"].apply(lambda s: list(s) == list(range(len(s))))).all(), "events: trial order is not 0..n-1 per session")
check(ev.groupby("session")["participant"].nunique().max() == 1, "events: a session has more than one participant")

if problems:
    print("PROBLEMS:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("Layer A matches the AdaptKit schemas; all checks passed.")
