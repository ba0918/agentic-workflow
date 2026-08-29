def dedupe_lines(lines):
    # keep the last occurrence of each line
    last = {}
    for index, line in enumerate(lines):
        last[line] = index
    return [line for index, line in enumerate(lines) if last[line] == index]
