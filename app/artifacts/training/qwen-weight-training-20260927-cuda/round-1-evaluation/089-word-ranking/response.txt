import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps([]))
            return
        counts = {}
        for item in data:
            if isinstance(item, str):
                if item in counts:
                    counts[item] += 1
                else:
                    counts[item] = 1
            elif isinstance(item, list):
                for subitem in item:
                    if isinstance(subitem, str):
                        if subitem in counts:
                            counts[subitem] += 1
                        else:
                            counts[subitem] = 1
        sorted_counts = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        for word, count in sorted_counts:
            print(f"{word}: {count}")
    except json.JSONDecodeError:
        print(json.dumps([]))

if __name__ == "__main__":
    main()