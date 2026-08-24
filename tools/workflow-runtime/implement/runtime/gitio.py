"""One place that shells out to git."""
from runtime.deps import execution_model
import subprocess

from runtime.types import RepositoryInfo, RuntimeResult, ok, failure
from pathlib import Path


def run_git(checkout: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )


def discover_repository(checkout: Path) -> RuntimeResult:
    candidate = checkout.resolve()
    bare = run_git(candidate, "rev-parse", "--is-bare-repository")
    if bare.returncode != 0:
        return failure("repository_unavailable", "path is not a Git repository", bare.stderr.strip())
    if bare.stdout.strip() == "true":
        return failure("bare_repository", "bare repositories cannot host implement worktrees")

    superproject = run_git(candidate, "rev-parse", "--show-superproject-working-tree")
    if superproject.returncode == 0 and superproject.stdout.strip():
        return failure("submodule_repository", "submodules are not accepted as implement repositories")
    top = run_git(candidate, "rev-parse", "--show-toplevel")
    common = run_git(candidate, "rev-parse", "--path-format=absolute", "--git-common-dir")
    head = run_git(candidate, "rev-parse", "HEAD")
    if any(result.returncode != 0 for result in (top, common, head)):
        return failure("repository_unavailable", "Git metadata is incomplete")

    checkout_root = Path(top.stdout.strip()).resolve()
    common_directory = Path(common.stdout.strip()).resolve()
    if common_directory.name != ".git" or not common_directory.is_dir():
        return failure("repository_identity_invalid", "Git common directory is not a main checkout .git")
    main_checkout = common_directory.parent.resolve()
    repository_identity = execution_model.content_identity(
        {"git_common_directory": str(common_directory)}
    )
    return ok(
        RepositoryInfo(
            main_checkout=main_checkout,
            common_directory=common_directory,
            checkout=checkout_root,
            base_head=head.stdout.strip(),
            repository_identity=repository_identity,
        )
    )
