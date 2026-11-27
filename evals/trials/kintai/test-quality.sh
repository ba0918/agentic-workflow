#!/bin/sh
# test-quality.sh <records-dir> clean -- <test command...>
# test-quality.sh <records-dir> <rule> <patch-file> -- <test command...>
#
# Works on a throwaway clone of the trial repository's main, never on the repository itself,
# and appends one JSON line per call to <records-dir>/test-quality.jsonl.
#
# clean: run the product's documented test command on the fresh clone and record its exit code.
# <rule>: (one of P1 P2 P3 P4 P6 Z1 X1) confirm the rule passes on the clone, apply the patch
#   (a change to the product that breaks only that rule), confirm with the oracle that the rule
#   now fails, run the test command, and record whether it failed ("killed"). Other rules that
#   fail with the patch are recorded too. The clone is deleted afterwards, which reverts the patch.
# ORACLE_TEMPLATE (a JSON argv with {month} and {csv}) overrides the launch found by the oracle.
set -eu
[ $# -ge 4 ] || { sed -n '2,13p' "$0" >&2; exit 2; }
R=$1; rule=$2
# shellcheck source=/dev/null
. "$R/trial.env"
if [ "$rule" = clean ]; then patch=; shift 2; else patch=$(cd "$(dirname "$3")" && pwd)/$(basename "$3"); shift 3; fi
[ "$1" = -- ] || { echo "expected -- before the test command" >&2; exit 2; }
shift
oracle=$TRIAL_KIT/oracle.py
out=$TRIAL_RECORDS/test-quality.jsonl
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git clone -q --branch main "$TRIAL_REPO" "$work/repo"
head=$(git -C "$work/repo" rev-parse HEAD)
cd "$work/repo"

score() {  # score <json-out>
  if [ -n "${ORACLE_TEMPLATE:-}" ]; then
    eval "set -- $(python3 -c 'import json,shlex,sys; print(" ".join(map(shlex.quote, json.loads(sys.argv[1]))))' "$ORACLE_TEMPLATE")"
    python3 -I "$oracle" score --repo "$work/repo" --json "$1.tmp" -- "$@" > /dev/null
  else
    python3 -I "$oracle" score --repo "$work/repo" --json "$1.tmp" > /dev/null
  fi
  mv "$1.tmp" "$1"
}
failing() {  # failing <json> -> space-separated rules with a failed case
  python3 -c 'import json,sys; b=json.load(open(sys.argv[1]))["by_rule"]; print(" ".join(sorted(k for k,(a,t) in b.items() if a<t)))' "$1"
}
record() {
  python3 - "$out" "$@" <<'PY'
import json, sys, time
path, *kv = sys.argv[1:]
rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S")}
for item in kv:
    k, v = item.split("=", 1)
    rec[k] = v
with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(json.dumps(rec, ensure_ascii=False))
PY
}

cmd="$*"
if [ -z "$patch" ]; then
  set +e; "$@" > "$work/test.log" 2>&1; rc=$?; set -e
  tail -n 20 "$work/test.log"
  record kind=clean head="$head" command="$cmd" exit_code="$rc"
  exit 0
fi

score "$work/before.json"
before=$(failing "$work/before.json")
case " $before " in
  *" $rule "*) record kind=mutation rule="$rule" head="$head" patch="$patch" \
      result=skipped reason="rule already fails before the patch" failing_before="$before"
    exit 0 ;;
esac
git apply "$patch"
score "$work/after.json"
after=$(failing "$work/after.json")
case " $after " in
  *" $rule "*) ;;
  *) record kind=mutation rule="$rule" head="$head" patch="$patch" \
      result=invalid reason="patch does not break the rule" failing_after="$after"
    exit 0 ;;
esac
set +e; "$@" > "$work/test.log" 2>&1; rc=$?; set -e
tail -n 20 "$work/test.log"
if [ "$rc" -ne 0 ]; then result=killed; else result=survived; fi
record kind=mutation rule="$rule" head="$head" patch="$patch" command="$cmd" \
  result="$result" test_exit_code="$rc" failing_before="$before" failing_after="$after"
