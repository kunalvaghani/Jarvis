import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        decoded = ""
        for run in input_data:
            if len(run) == 2 and isinstance(run[0], str) and isinstance(run[1], int):
                char, count = run
                decoded += char * count
        print(decoded)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"JSON decode error: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()