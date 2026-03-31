import json
from react_engine import run_react

INPUT = "/app/data/input.json"
OUTPUT = "/app/data/output.json"


def main():
    with open(INPUT) as f:
        data = json.load(f)

    try:
        result = run_react(data)
    except Exception as e:
        result = {"error": str(e), "steps": [], "final_answer": ""}

    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
