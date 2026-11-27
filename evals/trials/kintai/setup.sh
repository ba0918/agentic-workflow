#!/bin/sh
# setup.sh --skill DIR --records DIR --person-model MODEL [--root DIR] <skills-commit>
#
# Build one trial of this kit: a trial root holding a local bare origin and the trial
# repository, the workflow skills of <skills-commit> under the repository's .claude/skills/
# (kept out of its history), the developer instruction file beside the repository, and the
# person role installed into <records>/person with the skill's ask_person.py.
#
# --skill   the ba0918-workflow-trial skill directory (its scripts/ask_person.py is used)
# --records the run's record directory, .agents/trials/kintai/<run-id>/ in the host's
#           repository; its name is the run id. It must be ignored by git and empty.
# --root    default ${TMPDIR:-/tmp}/aw-trial-kintai-<run-id>
#
# Writes <records>/trial.env (the values the host passes to the launcher) and
# <records>/setup.txt (commits and tool versions), and prints the record directory.
set -eu

KIT=$(cd "$(dirname "$0")" && pwd)
SRC=$(git -C "$KIT" rev-parse --show-toplevel)
MAIN=$(dirname "$(git -C "$KIT" rev-parse --path-format=absolute --git-common-dir)")

skill='' records='' person_model='' root=''
while [ $# -gt 1 ]; do
  case $1 in
    --skill) skill=$2; shift 2 ;;
    --records) records=$2; shift 2 ;;
    --person-model) person_model=$2; shift 2 ;;
    --root) root=$2; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
if [ $# -ne 1 ] || [ -z "$skill" ] || [ -z "$records" ] || [ -z "$person_model" ]; then
  sed -n '2,15p' "$0" >&2; exit 2
fi
[ -f "$skill/scripts/ask_person.py" ] || { echo "no scripts/ask_person.py in $skill" >&2; exit 2; }
skill=$(cd "$skill" && pwd)
commit=$(git -C "$SRC" rev-parse --verify "$1^{commit}")
run_id=$(basename "$records")
root=${root:-${TMPDIR:-/tmp}/aw-trial-kintai-$run_id}

for d in "$root" "$records"; do
  if [ -e "$d" ] && [ -n "$(ls -A "$d")" ]; then echo "not empty: $d" >&2; exit 1; fi
done
mkdir -p "$root" "$records/person"
root=$(cd "$root" && pwd); records=$(cd "$records" && pwd)
# The records hold the person-role exchange and absolute paths of this machine.
if git -C "$records" rev-parse --is-inside-work-tree > /dev/null 2>&1 \
    && ! git -C "$records" check-ignore -q "$records"; then
  echo "not ignored by git: $records" >&2; exit 1
fi
repo=$root/repo

# Origin and repository with the sample input only.
git init -q --bare -b main "$root/origin.git"
git init -q -b main "$repo"
git -C "$repo" config user.name "trial person"
git -C "$repo" config user.email "person@example.invalid"
mkdir "$repo/sample"
cp "$KIT/sample/punches.csv" "$repo/sample/punches.csv"
git -C "$repo" add sample/punches.csv
git -C "$repo" commit -q -m "chore: 打刻機の出力の見本を置く"
git -C "$repo" remote add origin "$root/origin.git"
git -C "$repo" push -q -u origin main

# Workflow skills at the given commit. Untracked and excluded locally, so they are never part
# of a diff the workflow reviews and cannot be committed by accident.
tmp=$(mktemp -d)
git -C "$SRC" archive "$commit" skills | tar -x -C "$tmp"
mkdir -p "$repo/.claude/skills"
for s in "$tmp"/skills/ba0918-*; do cp -R "$s" "$repo/.claude/skills/"; done
rm -rf "$tmp"
mkdir -p "$repo/.git/info"
printf '/.claude/skills/\n' >> "$repo/.git/info/exclude"

# Developer instruction file: outside the repository, appended to the system prompt. The kit
# is hidden from the developer, so the file is copied where the developer can read it.
cp "$KIT/worker-instructions.md" "$root/worker-instructions.md"

# Person role. Its instructions sit in its workspace, the one part of the records the
# developer can reach, because the person role runs from the developer's shell.
cp "$KIT/person.md" "$records/person/person.md"
python3 -I "$skill/scripts/ask_person.py" install --home "$records/person" \
  --config "$KIT/person.json" --var model="$person_model" --var repo="$repo" \
  --var instructions="$records/person/person.md" --var trial_root="$root" > /dev/null

# What the isolation hides: the kit, the main checkout's copy of it, and the records (all
# past runs too, unless the trial root lies under the same parent).
kit_main=$MAIN/evals/trials/kintai
[ -d "$kit_main" ] || kit_main=$KIT
records_parent=$(dirname "$records")
case $root/ in
  "$records_parent"/*) hidden_records=$records ;;
  *) hidden_records=$records_parent ;;
esac

cat > "$records/trial.env" <<EOF
TRIAL_KIT='$KIT'
TRIAL_KIT_MAIN='$kit_main'
TRIAL_ROOT='$root'
TRIAL_REPO='$repo'
TRIAL_RECORDS='$records'
TRIAL_HIDDEN_RECORDS='$hidden_records'
TRIAL_INSTRUCTIONS='$root/worker-instructions.md'
TRIAL_SKILLS_COMMIT='$commit'
TRIAL_RUN_ID='$run_id'
EOF
{
  echo "setup: $(date +%Y-%m-%dT%H:%M:%S%z)"
  echo "skills commit: $commit"
  echo "kit commit: $(git -C "$SRC" rev-parse HEAD) (dirty: $(git -C "$SRC" status --porcelain -- "$KIT" | wc -l) files)"
  echo "skills: $(cd "$repo/.claude/skills" && printf "%s " ba0918-*)"
  echo "person model: $person_model"
  echo "claude: $(claude --version 2>/dev/null || echo unknown)"
  echo "kakoi: $(kakoi --version 2>/dev/null || echo unknown)"
} > "$records/setup.txt"
echo "$records"
