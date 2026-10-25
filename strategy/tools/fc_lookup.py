#!/usr/bin/env python3
"""List forecasts whose market id starts with any given prefix.

Usage: python3 strategy/tools/fc_lookup.py <prefix> [<prefix> ...]

Why this exists (2026-10-25 14:2xZ FULL): this session's sandbox refuses
inline `python3 -c` and awk pipelines, so checking whether an escalated
Kalshi rung already has a live forecast cost a hand-read of very long
forecasts.jsonl lines. One row per forecast: ts, id, market, outcome,
est_prob, mid at record, skip reason, and whether a later row superseded it.
"""
import json
import os
import sys

FORECASTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "journal", "forecasts.jsonl")


def main(prefixes):
    rows = []
    superseded = set()
    with open(FORECASTS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("supersedes"):
                superseded.add(r["supersedes"])
            if str(r.get("market_id", "")).startswith(tuple(prefixes)):
                rows.append(r)
    for r in rows:
        mid = r.get("mid_at_record", r.get("mid"))
        print(r.get("ts", "")[:16], r.get("id"), r.get("market_id"),
              r.get("outcome"), r.get("est_prob"), "mid=%s" % mid,
              r.get("skip_reason"), r.get("status", ""),
              "SUPERSEDED" if r.get("id") in superseded else "")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
