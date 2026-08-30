def dedupe_lines(lines):
    seen = set()
    out = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out
