from pathlib import Path
import subprocess


def initialize_repository(root: Path) -> None:
    if (root / ".git").exists():
        return
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    baseline = root / "baseline.txt"
    baseline.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "baseline.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)


def initialize_python_repository(root: Path) -> Path:
    initialize_repository(root)
    source = root / "tools" / "quality" / "probe.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 'baseline'\n", encoding="utf-8")
    subprocess.run(["git", "add", "tools/quality/probe.py"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "add probe"], cwd=root, check=True)
    return source
