"""Parse Git's NUL-delimited porcelain status without losing path boundaries."""
from __future__ import annotations


def parse_porcelain_v1_z(output: str, *, excluded_prefixes: tuple[str, ...] = ()) -> list[str]:
    records = output.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise ValueError("porcelain status record is incomplete")
        candidates = [record[3:]]
        if "R" in record[:2] or "C" in record[:2]:
            if index >= len(records) or not records[index]:
                raise ValueError("porcelain rename or copy source is missing")
            candidates.append(records[index])
            index += 1
        paths.update(
            path for path in candidates
            if path and not any(path.startswith(prefix) for prefix in excluded_prefixes)
        )
    return sorted(paths)
