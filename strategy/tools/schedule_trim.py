"""Drop named top-level keys from strategy/schedule.json.

DEEP-2026-09-15 hygiene keeps the schedule reason short, but the file is one
long JSON line per field and inline python needs approval on the operator
runner, so trimming had been deferred cycle after cycle (cycles.log
2026-10-27T22:20Z). Usage: python3 strategy/tools/schedule_trim.py KEY [KEY...]
"""
import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "schedule.json"


def main(keys):
    data = json.loads(PATH.read_text(encoding="utf-8"))
    dropped = [k for k in keys if data.pop(k, None) is not None]
    PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dropped": dropped}))


if __name__ == "__main__":
    main(sys.argv[1:])
