"""Freeze the exact tests that established RED."""
import hashlib

def freeze_test(files: dict[str, bytes]) -> dict[str, str]:
    return {
        path: "sha256:" + hashlib.sha256(content).hexdigest()
        for path, content in sorted(files.items())
    }

def frozen_test_matches(snapshot: dict[str, str], files: dict[str, bytes]) -> bool:
    return snapshot == freeze_test(files)
