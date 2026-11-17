"""Where AdaptKit reads and writes files.

The kit's own files (spec, policies, examples) sit next to the code. Data and training
outputs go into a workspace folder that is never committed. By default it is
adaptkit/workspace/; set the environment variable ADAPTKIT_WORKSPACE to use another folder.
"""

import os
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
SPEC = KIT / "spec"
POLICIES = KIT / "policies"
EXAMPLES = KIT / "examples"

WORKSPACE = Path(os.environ.get("ADAPTKIT_WORKSPACE", KIT / "workspace"))
RAW = WORKSPACE / "raw"              # downloaded datasets, never edited
PROCESSED = WORKSPACE / "processed"  # real data converted to the AdaptKit format
SYNTHETIC = WORKSPACE / "synthetic"  # simulated sessions (is_synthetic = 1)
RESULTS = WORKSPACE / "results"      # charts, model files, evaluation tables
