"""Freeze the exact tests that established RED."""
import hashlib

def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()

def freeze_test(files: dict[str, bytes], *, command: str) -> dict:
    return {
        "files": {path: _digest(content) for path, content in sorted(files.items())},
        "command": _digest(command.encode("utf-8")),
    }

def frozen_test_matches(snapshot: dict, files: dict[str, bytes], *, command: str) -> bool:
    return snapshot == freeze_test(files, command=command)
