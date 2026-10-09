import json
import sys

def jaccard_similarity(list1, list2):
    set1 = set(list1)
    set2 = set(list2)
    if not set1 and not set2:
        return 1.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union)

def main():
    try:
        input_data = json.load(sys.stdin)
        if isinstance(input_data, list) and len(input_data) == 2:
            result = jaccard_similarity(input_data[0], input_data[1])
            print(json.dumps(result))
        else:
            print(json.dumps(None))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
    except Exception:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()