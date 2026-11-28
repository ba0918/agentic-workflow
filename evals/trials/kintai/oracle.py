#!/usr/bin/env python3
"""Hidden oracle for the kintai trial. Never shown to the worker or to the person role.

usage:
  oracle.py selftest
      The reference implementation, run as a real CLI through the same discovery and scoring
      path as a product, passes every case; each rule-removed variant fails its target rule,
      and the rules that fail alongside it are exactly the known couplings.
  oracle.py find <repo>
      Locate the product's launch command in <repo> and print it as a template.
  oracle.py score [--json FILE] (--repo <repo> | -- <template...>)
      Score the product. A template is an argv with {month} and {csv} placeholders, e.g.
        oracle.py score -- python3 -m kintai summary --month {month} {csv}
      With --repo the template comes from `find`.
  oracle.py rules (--repo <repo> | [--repo <repo>] -- <template...>)
      Score the same way and print only {"rules": {"<id>": true|false, ...}} on stdout, true
      when every case of that rule passes; everything else goes to stderr. This is the grader
      output measure_test_quality.py reads, given as
        ["python3", "-I", "<kit>/oracle.py", "rules", "--repo", "{{repo}}"]
      When no launch is found, every rule is false.

Rules (truths):
  P1 night shift and month boundary: a shift belongs to the day (and month) of its `in`
  P2 no break punches: deduct 45 min over 6 h, 60 min over 8 h (exactly 6 h: none; exactly 8 h: 45)
  P3 the day's minutes after breaks are floored to 15-minute units
  P4 a shift without `out` is left out, the rest is counted, employee and date go to stderr
  P6 the same kind punched again within 5 minutes by the same employee is ignored
  Z1 an employee in the CSV with no counted shift in the month gets a 0,0 row
  X1 exit code 1 when a shift without `out` was left out of the month; X0 exit code 0 otherwise
  base ordinary day
Environment: PYTHON overrides the interpreter used to launch a discovered product.
"""
import contextlib
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

MONTH = "2026-10"
H = "employee_id,timestamp,kind\n"

# name -> (rule it targets, csv text)
FIX = {
    "plain": ("base", H +
        "E001,2026-10-01T09:00:00,in\nE001,2026-10-01T12:00:00,break_start\n"
        "E001,2026-10-01T13:00:00,break_end\nE001,2026-10-01T18:00:00,out\n"),
    "month_boundary": ("P1", H +
        "E002,2026-09-30T22:00:00,in\nE002,2026-10-01T06:00:00,out\n"
        "E002,2026-10-10T08:30:00,in\nE002,2026-10-10T12:00:00,break_start\n"
        "E002,2026-10-10T12:45:00,break_end\nE002,2026-10-10T17:45:00,out\n"
        "E002,2026-10-31T22:00:00,in\nE002,2026-11-01T02:00:00,break_start\n"
        "E002,2026-11-01T03:00:00,break_end\nE002,2026-11-01T06:00:00,out\n"
        "E002,2026-11-02T09:00:00,in\nE002,2026-11-02T12:00:00,out\n"),
    "auto_break": ("P2", H +
        "E001,2026-10-02T09:00:00,in\nE001,2026-10-02T18:30:00,out\n"      # 570 >480 -> -60 = 510
        "E001,2026-10-03T09:00:00,in\nE001,2026-10-03T15:00:00,out\n"      # 360 not >360 -> 360
        "E001,2026-10-04T09:00:00,in\nE001,2026-10-04T16:30:00,out\n"      # 450 >360 -> -45 = 405
        "E001,2026-10-05T09:00:00,in\nE001,2026-10-05T17:00:00,out\n"),    # 480 not >480 -> -45 = 435
    "rounding": ("P3", H +
        "E003,2026-10-20T10:00:00,in\nE003,2026-10-20T14:07:00,out\n"      # 247 -> 240
        "E003,2026-10-21T09:00:00,in\nE003,2026-10-21T12:00:00,break_start\n"
        "E003,2026-10-21T13:00:00,break_end\nE003,2026-10-21T18:29:00,out\n"),  # 509 -> 495
    "missing_out": ("P4", H +
        "E002,2026-10-11T09:00:00,in\n"
        "E002,2026-10-12T09:00:00,in\nE002,2026-10-12T15:00:00,out\n"),
    "double_punch": ("P6", H +
        "E001,2026-10-05T09:00:00,in\nE001,2026-10-05T12:00:00,break_start\n"
        "E001,2026-10-05T13:00:00,break_end\nE001,2026-10-05T18:14:00,out\n"
        "E001,2026-10-05T18:16:00,out\n"                                   # first out wins: 494 -> 480
        "E001,2026-10-06T09:00:00,in\nE001,2026-10-06T09:03:00,in\n"
        "E001,2026-10-06T15:00:00,out\n"),                                 # first in wins: 360
    "zero_row": ("Z1", H +
        "E001,2026-10-01T09:00:00,in\nE001,2026-10-01T12:00:00,break_start\n"
        "E001,2026-10-01T13:00:00,break_end\nE001,2026-10-01T18:00:00,out\n"
        "E005,2026-11-02T09:00:00,in\nE005,2026-11-02T12:00:00,break_start\n"
        "E005,2026-11-02T13:00:00,break_end\nE005,2026-11-02T18:00:00,out\n"),
}

# Each variant removes one rule from the reference.
VARIANTS = {
    "P1": {"by_out": True}, "P2": {"auto_break": False}, "P3": {"rounding": False},
    "P4": {"abort_on_missing": True}, "P6": {"dedupe": False},
    "Z1": {"zero_rows": False}, "X1": {"exit_on_missing": False},
}
# Rules that fail alongside the target, by construction of the fixtures:
# without the 15-minute floor the double-punch day is 494, not 480;
# without dedupe the second `in` looks like a missing `out`, so the exit code becomes 1.
COUPLED = {"P3": {"P6"}, "P6": {"X0"}}

# The person's wanted form, tried first.
SHAPES = [
    ["summary", "--month", "{month}", "{csv}"],
    ["summary", "{csv}", "--month", "{month}"],
    ["--month", "{month}", "{csv}"],
    ["{csv}", "--month", "{month}"],
]


def reference(text, month, by_out=False, auto_break=True, rounding=True, dedupe=True,
              abort_on_missing=False, zero_rows=True, exit_on_missing=True):
    """-> (rows {emp: (days, minutes)}, warnings [(emp, date)], exit code)"""
    rows_in = sorted(csv.DictReader(io.StringIO(text)),
                     key=lambda r: (r["employee_id"], r["timestamp"]))
    out, warn, last, cur = {}, [], {}, {}

    def close(emp, t_out):
        s = cur.pop(emp)
        gross = int((t_out - s["in"]).total_seconds() // 60)
        brk = sum(int((b - a).total_seconds() // 60) for a, b in s["breaks"])
        if not s["breaks"] and auto_break:
            brk = 60 if gross > 480 else 45 if gross > 360 else 0
        m = gross - brk
        if rounding:
            m -= m % 15
        if (t_out if by_out else s["in"]).strftime("%Y-%m") == month:
            d = out.setdefault(emp, [0, 0])
            d[0] += 1
            d[1] += m

    for r in rows_in:
        emp, t, k = r["employee_id"], datetime.fromisoformat(r["timestamp"]), r["kind"]
        if dedupe and last.get((emp, k)) and t - last[(emp, k)] <= timedelta(minutes=5):
            continue
        last[(emp, k)] = t
        if k == "in":
            if emp in cur:
                if abort_on_missing:
                    return {}, [], 1
                s = cur.pop(emp)
                if s["in"].strftime("%Y-%m") == month:
                    warn.append((emp, s["in"].strftime("%Y-%m-%d")))
            cur[emp] = {"in": t, "breaks": [], "bs": None}
        elif emp in cur:
            s = cur[emp]
            if k == "break_start":
                s["bs"] = t
            elif k == "break_end" and s["bs"]:
                s["breaks"].append((s["bs"], t))
                s["bs"] = None
            elif k == "out":
                close(emp, t)
    for emp, s in cur.items():
        if s["in"].strftime("%Y-%m") == month:
            if abort_on_missing:
                return {}, [], 1
            warn.append((emp, s["in"].strftime("%Y-%m-%d")))
    rows = {e: (v[0], v[1]) for e, v in out.items()}
    if zero_rows:
        for r in csv.DictReader(io.StringIO(text)):
            rows.setdefault(r["employee_id"], (0, 0))
    return rows, warn, (1 if warn and exit_on_missing else 0)


def reference_main(argv):
    """The reference as a CLI: `summary --month M <csv>`; with KINTAI_REF_FORM=alt only
    `<csv> --month M`. KINTAI_REF_VARIANT names a rule to remove."""
    if os.environ.get("KINTAI_REF_FORM") == "alt":
        if len(argv) != 3 or argv[1] != "--month":
            print("usage: kintai <csv> --month M", file=sys.stderr)
            return 2
        args = argv
    elif argv[:2] == ["summary", "--month"] and len(argv) == 4:
        args = argv[1:]
    else:
        print("usage: kintai summary --month M <csv>", file=sys.stderr)
        return 2
    i = args.index("--month")
    month = args[i + 1]
    path = [a for j, a in enumerate(args) if j not in (i, i + 1)][0]
    variant = VARIANTS.get(os.environ.get("KINTAI_REF_VARIANT", ""), {})
    with open(path, encoding="utf-8") as f:
        rows, warn, code = reference(f.read(), month, **variant)
    if code and not rows and not warn:
        print("missing out; aborting", file=sys.stderr)
        return code
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["employee_id", "days_worked", "total_minutes"])
    for emp in sorted(rows):
        w.writerow([emp, *rows[emp]])
    for emp, day in warn:
        print(f"missing out: {emp} {day}", file=sys.stderr)
    return code


def cases():
    """-> [(fixture, rule, employee, field, wanted)]"""
    cs = []
    for name, (rule, text) in FIX.items():
        rows, warn, code = reference(text, MONTH)
        for emp, (days, total) in sorted(rows.items()):
            r = "Z1" if (days, total) == (0, 0) else rule
            cs.append((name, r, emp, "days_worked", days))
            cs.append((name, r, emp, "total_minutes", total))
        for emp, day in warn:
            cs.append((name, rule, emp, "stderr_mentions", day))
        cs.append((name, "X1" if code else "X0", "-", "exit_code", code))
    return cs


def run_cli(template, text, cwd=None, env=None):
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(text)
        path = f.name
    argv = [a.replace("{month}", MONTH).replace("{csv}", path) for a in template]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60, cwd=cwd, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, str(e), None, False
    finally:
        os.unlink(path)
    rows, header_ok = {}, False
    try:
        reader = csv.DictReader(io.StringIO(p.stdout))
        header_ok = reader.fieldnames == ["employee_id", "days_worked", "total_minutes"]
        for r in reader:
            rows[(r.get("employee_id") or "").strip()] = r
    except Exception:
        pass
    return rows, p.stderr, p.returncode, header_ok


def score(template, cwd=None, env=None):
    cache, res = {}, []
    for name, rule, emp, field, want in cases():
        if name not in cache:
            cache[name] = run_cli(template, FIX[name][1], cwd, env)
        rows, err, code, _ = cache[name]
        if field == "stderr_mentions":
            ok, got = (emp in err and want in err), "(stderr)"
        elif field == "exit_code":
            ok, got = (code == want), code
        else:
            got = rows.get(emp, {}).get(field)
            ok = got is not None and str(got).strip() == str(want)
        res.append({"ok": ok, "fixture": name, "rule": rule, "employee": emp, "field": field,
                    "want": want, "got": got})
    header = cache["plain"][3]
    return res, header


def report(res, header=None):
    by = {}
    for r in res:
        p = by.setdefault(r["rule"], [0, 0])
        p[1] += 1
        p[0] += r["ok"]
    for r in res:
        if not r["ok"]:
            print(f"FAIL {r['rule']} {r['fixture']} {r['employee']} {r['field']}: "
                  f"want {r['want']} got {r['got']}")
    print(" ".join(f"{t}={a}/{b}" for t, (a, b) in sorted(by.items())),
          f"total={sum(r['ok'] for r in res)}/{len(res)}")
    if header is not None:
        print("header employee_id,days_worked,total_minutes exactly:", "yes" if header else "no")
    return by


def rules_of(res):
    """-> {rule: True when every case of the rule passed}"""
    out = {}
    for r in res:
        out[r["rule"]] = out.get(r["rule"], True) and r["ok"]
    return out


# --- locating the product -------------------------------------------------------------

def _python():
    return os.environ.get("PYTHON") or sys.executable


def _product_env(repo):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # leave no __pycache__ in the scored repository
    paths = [os.path.join(repo, "src"), repo]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def launchers(repo):
    """-> [(description, argv prefix)] in order of preference."""
    found = []
    pyproject = os.path.join(repo, "pyproject.toml")
    if os.path.exists(pyproject):
        import tomllib
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        scripts = data.get("project", {}).get("scripts", {})
        scripts.update(data.get("tool", {}).get("poetry", {}).get("scripts", {}) or {})
        for name, target in sorted(scripts.items(), key=lambda kv: kv[0] != "kintai"):
            if not isinstance(target, str) or ":" not in target:
                continue
            mod, func = target.split(":", 1)
            code = (f"import sys; sys.argv[0] = {name!r}; from {mod} import {func.strip()} as f; "
                    "r = f(); sys.exit(r if isinstance(r, int) else 0)")
            found.append((f"pyproject script {name} = {target}", [_python(), "-c", code]))
    for base in (repo, os.path.join(repo, "src")):
        for pkg in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if os.path.exists(os.path.join(base, pkg, "__main__.py")):
                found.append((f"python -m {pkg}", [_python(), "-m", pkg]))
    for rel in ("kintai", "bin/kintai"):
        p = os.path.join(repo, rel)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            found.append((f"executable {rel}", [p]))
    return found


def find(repo):
    """-> (template, description, person_form, tried) or (None, None, False, tried)."""
    repo = os.path.abspath(repo)
    env = _product_env(repo)
    tried = []
    for desc, prefix in launchers(repo):
        for si, shape in enumerate(SHAPES):
            template = prefix + shape
            rows, _, code, _ = run_cli(template, FIX["plain"][1], repo, env)
            ok = "E001" in rows and code in (0, 1)
            tried.append((desc, " ".join(shape), ok))
            if ok:
                return template, f"{desc} + {' '.join(shape)}", si == 0, tried
    return None, None, False, tried


def print_find(repo):
    template, desc, person_form, tried = find(repo)
    for d, s, ok in tried:
        print(f"tried {d} + {s}: {'works' if ok else 'no'}")
    if not template:
        print("no launch found; pass a template after --")
        return None
    print("launch:", desc)
    print("template:", json.dumps(template, ensure_ascii=False))
    print("person's argument form (`summary --month M <csv>`):",
          "yes" if person_form else "no")
    return template


# --- self-check -----------------------------------------------------------------------

def _write_reference_product(root, person_form=True):
    pkg = os.path.join(root, "src", "kintai")
    os.makedirs(pkg)
    with open(os.path.join(pkg, "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(pkg, "cli.py"), "w") as f:
        f.write("import importlib.util, os, sys\n"
                "spec = importlib.util.spec_from_file_location('oracle', os.environ['KINTAI_ORACLE'])\n"
                "o = importlib.util.module_from_spec(spec); spec.loader.exec_module(o)\n"
                "def main():\n    return o.reference_main(sys.argv[1:])\n")
    if person_form:
        with open(os.path.join(root, "pyproject.toml"), "w") as f:
            f.write('[project]\nname = "kintai"\nversion = "0"\n'
                    '[project.scripts]\nkintai = "kintai.cli:main"\n')
    else:  # a product reachable only as `python -m kintai <csv> --month M`
        with open(os.path.join(pkg, "__main__.py"), "w") as f:
            f.write("import sys\nfrom kintai.cli import main\nsys.exit(main())\n")


def selftest():
    os.environ["KINTAI_ORACLE"] = os.path.abspath(__file__)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # the reference loads the oracle from the kit
    with tempfile.TemporaryDirectory() as root:
        _write_reference_product(root)
        template = print_find(root)
        assert template, "discovery must find the reference"
        assert find(root)[2], "the reference is in the person's form"
        env = _product_env(root)
        res, header = score(template, root, env)
        base = report(res, header)
        assert header and all(a == b for a, b in base.values()), "reference must pass"
        assert all(rules_of(res).values()), "rules output must hold for the reference"
        for rule, _ in VARIANTS.items():
            print("--- reference without", rule)
            env["KINTAI_REF_VARIANT"] = rule
            res = score(template, root, env)[0]
            by = report(res)
            failing = {t for t, (a, b) in by.items() if a < b}
            assert rule in failing, f"{rule} not detected"
            assert {t for t, ok in rules_of(res).items() if not ok} == failing, \
                f"{rule}: rules output disagrees with the report"
            assert failing - {rule} == COUPLED.get(rule, set()), \
                f"{rule}: unexpected also-failing {failing - {rule}}"
            print("    also failing (known coupling):", sorted(failing - {rule}))
    with tempfile.TemporaryDirectory() as root:
        print("--- discovery of a product in another form")
        _write_reference_product(root, person_form=False)
        os.environ["KINTAI_REF_FORM"] = "alt"
        template = print_find(root)
        assert template and not find(root)[2], "other form must be found and flagged"
        by = report(score(template, root, _product_env(root))[0])
        assert all(a == b for a, b in by.values()), "other form must still score"
        del os.environ["KINTAI_REF_FORM"]
    print("selftest ok")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "selftest":
        selftest()
        return 0
    if argv[0] == "find":
        return 0 if print_find(argv[1]) else 1
    if argv[0] == "rules":
        rest, repo, template = argv[1:], None, None
        if "--" in rest:
            template = rest[rest.index("--") + 1:]
            rest = rest[:rest.index("--")]
        if "--repo" in rest:
            repo = os.path.abspath(rest[rest.index("--repo") + 1])
        if not template and not repo:
            print("rules needs --repo <repo> or -- <template>", file=sys.stderr)
            return 2
        with contextlib.redirect_stdout(sys.stderr):
            if not template:
                template = print_find(repo)
            if template:
                res = score(template, repo, _product_env(repo) if repo else None)[0]
                report(res)
                rules = rules_of(res)
            else:
                rules = {rule: False for _, rule, _, _, _ in cases()}
        print(json.dumps({"rules": rules}, sort_keys=True))
        return 0
    if argv[0] == "score":
        rest, out_json, repo, template = argv[1:], None, None, None
        if "--" in rest:
            template = rest[rest.index("--") + 1:]
            rest = rest[:rest.index("--")]
        if "--json" in rest:
            out_json = rest[rest.index("--json") + 1]
        if "--repo" in rest:
            repo = os.path.abspath(rest[rest.index("--repo") + 1])
        if not template:
            if not repo:
                print("score needs --repo <repo> or -- <template>", file=sys.stderr)
                return 2
            template = print_find(repo)
            if not template:
                return 1
        res, header = score(template, repo, _product_env(repo) if repo else None)
        by = report(res, header)
        if out_json:
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump({"template": template, "header_exact": header,
                           "by_rule": by, "cases": res}, f, ensure_ascii=False, indent=1)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
