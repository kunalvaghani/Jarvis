import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps([]))
            return
        if len(data) != 2:
            print(json.dumps([]))
            return
        a, b = data
        if not isinstance(a, list) or not isinstance(b, list):
            print(json.dumps([]))
            return
        if len(a) == 0 or len(b) == 0:
            print(json.dumps([]))
            return
        if len(a) != len(b):
            print(json.dumps([]))
            return
        result = []
        for i in range(len(a)):
            for j in range(len(b)):
                if a[i] == b[j]:
                    result.append(a[i])
                    break
        result.sort()
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps([]))