from pathlib import Path


def resolve_project_root(option: Path | None, script: Path) -> Path:
    return option.resolve() if option is not None else script.resolve().parents[2]
