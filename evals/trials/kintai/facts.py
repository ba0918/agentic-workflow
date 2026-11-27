#!/usr/bin/env python3
"""Print the mechanical facts of each run from a record directory.

usage: facts.py <records-dir>

For every run<n>.json: wall time, worker cost and turns, stop reason, permission denials;
from run<n>.session.jsonl: the skills loaded in order, the number of agents launched and of
subagent logs, the ask-person calls, git push/merge commands, and reads that touch the
person sheet or the kit (leak check); from person/person.transcript.jsonl: the person role's
cost and the number of messages during the run. Judgments (question classes, routes, the
one-line declaration) are left to the host.
"""
import glob
import json
import os
import re
import sys

LEAK = re.compile(r"person\.md|ask-person\.sh|oracle\.py|evals/trials|PROTOCOL\.md|trial\.env")


def tool_uses(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            m = o.get("message")
            if isinstance(m, dict) and isinstance(m.get("content"), list):
                for c in m["content"]:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        yield c.get("name"), c.get("input") or {}


def person_records(records):
    path = os.path.join(records, "person", "person.transcript.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def stamp(t):
    import time
    return time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))


def main(records):
    persons = person_records(records)
    for run_json in sorted(glob.glob(os.path.join(records, "run*.json"))):
        n = re.search(r"run(\d+)\.json$", run_json).group(1)
        base = os.path.join(records, f"run{n}")
        print(f"== run {n}")
        try:
            start, end = (int(open(f"{base}.{k}").read()) for k in ("start", "end"))
            print(f"wall time: {end - start} s")
        except (OSError, ValueError):
            start = end = None
        try:
            o = json.load(open(run_json))
        except ValueError:
            print("run json unreadable; see", base + ".err")
            continue
        print(f"worker cost: {o.get('total_cost_usd')} USD, turns {o.get('num_turns')}, "
              f"stop {o.get('subtype')}/{o.get('terminal_reason')}, error {o.get('is_error')}")
        print("permission denials:", len(o.get("permission_denials") or []))
        print("subagent_stats:", json.dumps(o.get("subagent_stats"), ensure_ascii=False))
        log = base + ".session.jsonl"
        if os.path.exists(log):
            skills, agents, asks, git_out, leaks = [], 0, 0, [], []
            logs = [log] + glob.glob(os.path.join(base + ".session", "subagents", "*.jsonl"))
            for p in logs:
                for name, inp in tool_uses(p):
                    if name == "Skill":
                        skills.append(inp.get("skill"))
                    if name in ("Agent", "Task") and p == log:
                        agents += 1
                    text = json.dumps(inp, ensure_ascii=False)
                    if name == "Bash":
                        cmd = inp.get("command", "")
                        if "ask-person" in cmd and p == log:
                            asks += 1
                        if re.search(r"\bgit\b.*\b(push|merge)\b", cmd):
                            git_out.append(cmd[:120])
                    if LEAK.search(text) and not (name == "Bash" and "ask-person " in text
                                                  and "ask-person.sh" not in text):
                        leaks.append(f"{name} {text[:160]}")
            print("skills loaded (main and subagents, in order):", skills)
            print("agents launched by the main session:", agents,
                  "| subagent logs:", len(logs) - 1)
            print("ask-person calls from the main session:", asks)
            print("git push/merge commands:", git_out or "none")
            print("reads touching the person sheet or the kit:", leaks or "none")
        else:
            print("no session log copied")
        if start is not None:
            mine = [r for r in persons if start <= stamp(r["t"]) <= end + 60]
            cost = sum(r.get("cost") or 0 for r in mine)
            print(f"person role: {len(mine)} messages, {cost:.4f} USD")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
