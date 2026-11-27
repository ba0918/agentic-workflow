#!/bin/sh
# setup.sh [--root DIR] [--records DIR] [--run-id ID] <skills-commit>
#
# Build one trial: a trial root holding a local bare origin and the trial repository, the
# workflow skills of <skills-commit> under the repository's .claude/skills/ (kept out of its
# history), the worker's instructions, and a record directory with the person role's files.
#
# Defaults: run id = current time; root = ${TMPDIR:-/tmp}/aw-trial-kintai-<run-id>;
# records = <main checkout of this repository>/.agents/trials/kintai/<run-id>.
# Prints the record directory; run.sh and test-quality.sh read <records>/trial.env.
set -eu

KIT=$(cd "$(dirname "$0")" && pwd)
SRC=$(git -C "$KIT" rev-parse --show-toplevel)
MAIN=$(dirname "$(git -C "$KIT" rev-parse --path-format=absolute --git-common-dir)")

root='' records='' run_id=''
while [ $# -gt 1 ]; do
  case $1 in
    --root) root=$2; shift 2 ;;
    --records) records=$2; shift 2 ;;
    --run-id) run_id=$2; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[ $# -eq 1 ] || { sed -n '2,11p' "$0" >&2; exit 2; }
commit=$(git -C "$SRC" rev-parse --verify "$1^{commit}")
run_id=${run_id:-$(date +%Y%m%d-%H%M%S)}
root=${root:-${TMPDIR:-/tmp}/aw-trial-kintai-$run_id}
records=${records:-$MAIN/.agents/trials/kintai/$run_id}

for d in "$root" "$records"; do
  if [ -e "$d" ] && [ -n "$(ls -A "$d")" ]; then echo "not empty: $d" >&2; exit 1; fi
done
mkdir -p "$root" "$records/person"
root=$(cd "$root" && pwd); records=$(cd "$records" && pwd)
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

# Worker instructions: outside the repository, appended to the worker's system prompt.
cp "$KIT/worker-instructions.md" "$root/worker-instructions.md"

# Person role. Everything the worker may touch in the record directory lives in person/.
cp "$KIT/person.md" "$records/person/person.md"
cp "$KIT/ask-person" "$records/person/ask-person.sh"
cat > "$records/person/ask-person" <<EOF
#!/bin/sh
ASK_PERSON_HOME='$records/person' ASK_PERSON_REPO='$repo' ASK_PERSON_ADD_DIR='$root' \\
  exec sh '$records/person/ask-person.sh' "\$@"
EOF
chmod +x "$records/person/ask-person" "$records/person/ask-person.sh"

cat > "$records/trial.env" <<EOF
TRIAL_KIT='$KIT'
TRIAL_MAIN_CHECKOUT='$MAIN'
TRIAL_ROOT='$root'
TRIAL_REPO='$repo'
TRIAL_RECORDS='$records'
TRIAL_SKILLS_COMMIT='$commit'
TRIAL_RUN_ID='$run_id'
EOF
{
  echo "setup: $(date +%Y-%m-%dT%H:%M:%S%z)"
  echo "skills commit: $commit"
  echo "kit commit: $(git -C "$SRC" rev-parse HEAD) (dirty: $(git -C "$SRC" status --porcelain -- "$KIT" | wc -l) files)"
  echo "skills: $(cd "$repo/.claude/skills" && printf "%s " ba0918-*)"
  echo "claude: $(claude --version 2>/dev/null || echo unknown)"
  echo "kakoi: $(kakoi --version 2>/dev/null || echo unknown)"
} > "$records/setup.txt"
echo "$records"
