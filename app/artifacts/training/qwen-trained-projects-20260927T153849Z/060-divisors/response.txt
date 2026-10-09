import sys
import math

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        x = int(input_data)
        
        if x < 0:
            print(json.dumps([]))
            return
        
        divisors = []
        for i in range(1, int(math.sqrt(x)) + 1):
            if x % i == 0:
                divisors.append(i)
                if i != x // i:
                    divisors.append(x // i)
        
        result = sorted(divisors)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()