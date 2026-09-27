import sys
from ledger import read_totals
import json


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <csv_path>", file=sys.stderr)
        sys.exit(1)
    
    csv_path = sys.argv[1]
    try:
        result = read_totals(csv_path)
        print(json.dumps(result))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()