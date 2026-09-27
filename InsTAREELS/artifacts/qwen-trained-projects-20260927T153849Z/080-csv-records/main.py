import csv
import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        reader = csv.DictReader(input_data.splitlines())
        result = [row for row in reader]
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()