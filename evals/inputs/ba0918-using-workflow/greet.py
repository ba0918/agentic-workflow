import sys

GREETING = "Hello"


def greet(name):
    if not name:
        raise ValueError("bad name")
    return f"{GREETING}, {name}!"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("greet: bad args", file=sys.stderr)
        sys.exit(2)
    print(greet(sys.argv[1]))
