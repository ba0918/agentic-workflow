"""Detect secret-shaped content without returning the matched value."""
import re

# Shares the brainstorm state writer's detector contract, extended for private-key files.
CREDENTIAL_ASSIGNMENT = re.compile(
    rb"(?im)\b(?:api[_-]?(?:key|token)|access[_-]?token|client[_-]?secret|"
    rb"token|secret|credential|password)\b\s*[:=]\s*[\"']?"
    rb"(?!(?:os\.)?environ\b)[^\s\"'#]{8,}"
)
PRIVATE_KEY_HEADER = re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")

def contains_secret(content: bytes) -> bool:
    return CREDENTIAL_ASSIGNMENT.search(content) is not None or PRIVATE_KEY_HEADER.search(content) is not None
