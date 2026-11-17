"""Step 0 of the training pipeline: download the Findlater & Zhang (2020) summary files.

    python -I python/scripts/download_findlater.py          (from the adaptkit folder)

Saves them untouched in workspace/raw/. About 36 MB. Licence: CC BY 4.0, so cite:
Findlater, L. and Zhang, L. (2020) Input accessibility: a large dataset and summary analysis
of age, motor ability and input performance. ASSETS 2020. https://github.com/leahkf/mouseandtouchinput
The 660 MB folder of raw movement traces (alldata/) is not needed and is not downloaded.
"""

import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptkit.paths import RAW  # noqa: E402

BASE = "https://raw.githubusercontent.com/leahkf/mouseandtouchinput/master/"
FILES = ["README.md", "Data description.xlsx", "ParticipantQuestionnaireData N=735.csv", "SummaryDataPerTrial N=735.csv"]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = RAW / name
        if target.exists():
            print(f"already there: {name}")
            continue
        url = BASE + urllib.parse.quote(name)
        print(f"downloading {name} ...", flush=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "adaptkit"})) as r, target.open("wb") as f:
            f.write(r.read())
        print(f"  {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
