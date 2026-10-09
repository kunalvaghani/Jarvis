import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
            return
        if not isinstance(data[0], list) or len(data[0]) != 3:
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
            return
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
            return
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[0][0], int) or not isinstance(data[0][1], int) or not isinstance(data[0][2], int):
            print(json.dumps({"error": "Invalid input"}), file=sys.stderr)
        if not isinstance(data[1], int