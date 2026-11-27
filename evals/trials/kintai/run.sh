#!/bin/sh
# run.sh <n> <request-file> [records-dir]
#
# Run one request as a fresh headless worker session inside the sandbox, with the trial
# repository as its working directory. records-dir defaults to $TRIAL_RECORDS (printed by
# setup.sh). Writes run<n>.prompt.txt, .start, .end, .json, .err, .base, and copies the worker's
# session log to run<n>.session.jsonl (subagent logs, when present, to run<n>.session/).
#
# WORKER_MODEL overrides the worker model (default claude-opus-5-5); PERSON_MODEL is passed on
# to ask-person. Use the overrides only for probing the kit, never for a scored run.
set -eu
[ $# -ge 2 ] || { sed -n '2,10p' "$0" >&2; exit 2; }
n=$1
req=$(cat "$2")
R=${3:-${TRIAL_RECORDS:?give the record directory}}
# shellcheck source=/dev/null
. "$R/trial.env"
for f in json start end err; do
  [ ! -e "$TRIAL_RECORDS/run$n.$f" ] || { echo "run $n already recorded" >&2; exit 1; }
done

ask="$TRIAL_RECORDS/person/ask-person"
prompt="$(sed "s|{{ASK_PERSON}}|$ask|g" "$TRIAL_KIT/preface.txt")
$req"
printf '%s\n' "$prompt" > "$TRIAL_RECORDS/run$n.prompt.txt"
git -C "$TRIAL_REPO" rev-parse main > "$TRIAL_RECORDS/run$n.base"

# Hide the kit (oracle, protocol, past results) and the record directories, past runs included;
# the worker can write only the trial root and the person role's directory.
records_parent=$(dirname "$TRIAL_RECORDS")
case $TRIAL_ROOT/ in
  "$records_parent"/*) hide_records=$TRIAL_RECORDS ;;
  *) hide_records=$records_parent ;;
esac
set -- --workspace "$TRIAL_ROOT" --hide "$TRIAL_KIT" --hide "$hide_records" \
  --rw "$TRIAL_RECORDS/person"
main_kit=$TRIAL_MAIN_CHECKOUT/evals/trials/kintai
if [ -d "$main_kit" ] && [ "$main_kit" != "$TRIAL_KIT" ]; then set -- "$@" --hide "$main_kit"; fi

cd "$TRIAL_REPO"
date +%s > "$TRIAL_RECORDS/run$n.start"
PERSON_MODEL=${PERSON_MODEL:-claude-sonnet-5-5} kakoi "$@" -- \
  claude -p --model "${WORKER_MODEL:-claude-opus-5-5}" --setting-sources project \
  --append-system-prompt-file "$TRIAL_ROOT/worker-instructions.md" \
  --dangerously-skip-permissions --output-format json "$prompt" \
  < /dev/null > "$TRIAL_RECORDS/run$n.json" 2> "$TRIAL_RECORDS/run$n.err" \
  || echo "exit=$?" >> "$TRIAL_RECORDS/run$n.err"
date +%s > "$TRIAL_RECORDS/run$n.end"

sid=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("session_id",""))' \
  "$TRIAL_RECORDS/run$n.json" 2>/dev/null || true)
if [ -n "$sid" ]; then
  log=$(find "$HOME/.claude/projects" -maxdepth 2 -name "$sid.jsonl" 2>/dev/null | head -n 1)
  if [ -n "$log" ]; then
    cp "$log" "$TRIAL_RECORDS/run$n.session.jsonl"
    if [ -d "${log%.jsonl}" ]; then cp -R "${log%.jsonl}" "$TRIAL_RECORDS/run$n.session"; fi
  else
    echo "session log for $sid not found" >> "$TRIAL_RECORDS/run$n.err"
  fi
fi
echo "run $n: $(( $(cat "$TRIAL_RECORDS/run$n.end") - $(cat "$TRIAL_RECORDS/run$n.start") ))s, records in $TRIAL_RECORDS"
