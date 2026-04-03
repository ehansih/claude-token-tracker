#!/usr/bin/env python3
"""
Claude Code Session Token Status
Reads the most recent session JSONL and prints a compact token/cost summary.
Called as a UserPromptSubmit hook in Claude Code.

Status indicators:
  🟢  ctx < 500k      — safe
  🟡  ctx 500k–2M     — moderate
  🟠  ctx 2M–10M      — high usage
  🔴  ctx > 10M       — danger, limit risk
"""

import json
import os
import glob
from pathlib import Path

# Sonnet 4.6 pricing (per 1M tokens)
COSTS = {
    "input":        3.00,
    "output":      15.00,
    "cache_read":   0.30,
    "cache_write":  3.75,
}

THRESHOLDS = [
    (10_000_000, "🔴", "DANGER — limit risk, start a new session"),
    ( 2_000_000, "🟠", "HIGH — heavy usage"),
    (   500_000, "🟡", "MODERATE"),
    (         0, "🟢", "OK"),
]

def find_current_session():
    projects_dir = Path.home() / ".claude" / "projects"
    all_jsonl = glob.glob(str(projects_dir / "**" / "*.jsonl"), recursive=True)
    if not all_jsonl:
        return None
    return max(all_jsonl, key=os.path.getmtime)

def parse_session(path):
    ti = to = cr = cw = 0
    turns = 0
    with open(path, "r") as f:
        for line in f:
            try:
                d = json.loads(line)
                u = d.get("usage") or d.get("message", {}).get("usage", {})
                if u:
                    ti  += u.get("input_tokens", 0)
                    to  += u.get("output_tokens", 0)
                    cr  += u.get("cache_read_input_tokens", 0)
                    cw  += u.get("cache_creation_input_tokens", 0)
                    turns += 1
            except Exception:
                pass
    return ti, to, cr, cw, turns

def get_status(ctx_tokens):
    for threshold, emoji, label in THRESHOLDS:
        if ctx_tokens >= threshold:
            return emoji, label
    return "🟢", "OK"

def fmt(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}k"
    return str(n)

def main():
    path = find_current_session()
    if not path:
        return

    ti, to, cr, cw, turns = parse_session(path)
    if turns == 0:
        return

    cost = (
        ti / 1e6 * COSTS["input"] +
        to / 1e6 * COSTS["output"] +
        cr / 1e6 * COSTS["cache_read"] +
        cw / 1e6 * COSTS["cache_write"]
    )

    total_ctx = ti + cr + cw
    emoji, label = get_status(total_ctx)

    print(
        f"{emoji} [tokens] turns={turns} "
        f"in={fmt(ti)} out={fmt(to)} "
        f"cache_read={fmt(cr)} cache_write={fmt(cw)} "
        f"ctx={fmt(total_ctx)} "
        f"est_cost=${cost:.4f}  {label}"
    )

if __name__ == "__main__":
    main()
