import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list) or len(input_data) != 2:
        return
    
    capacity, keys = input_data[0], input_data[1]
    
    if not isinstance(capacity, int) or capacity <= 0:
        return
    
    if not isinstance(keys, list):
        return
    
    hits = 0
    cache = {}
    
    for key in keys:
        if not isinstance(key, str):
            continue
        
        if key in cache:
            hits += 1
        else:
            if len(cache) >= capacity:
                oldest_key = min(cache.keys())
                del cache[oldest_key]
            cache[key] = True
    
    result_keys = sorted([k for k in cache.keys()])
    
    print(json.dumps({"hits": hits, "keys": result_keys}))

if __name__ == "__main__":
    main()