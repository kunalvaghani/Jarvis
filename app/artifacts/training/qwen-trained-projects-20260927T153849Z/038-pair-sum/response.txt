import sys
import itertools
import bisect


def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps([]))
            return
        
        lst, target = data
        
        if not (isinstance(lst, list) and isinstance(target, int)):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0], list) and isinstance(lst[1], int)):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int)):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[1], list) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int)):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0][-1], int) and isinstance(lst[1][0], int) and isinstance(lst[1][-1], int))):
            print(json.dumps([]))
            return
        
        if not (isinstance(lst[0][0], int) and isinstance(lst[0