import sys
import itertools


def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps([]))
            return
        
        result = []
        for perm in itertools.permutations(data):
            result.append(list(perm))
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)


if __name__ == "__main__":
    main()