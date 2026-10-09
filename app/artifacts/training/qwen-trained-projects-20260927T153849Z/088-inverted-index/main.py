import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list):
        return
    
    result = {}
    for doc in input_data:
        if not isinstance(doc, str):
            continue
        
        words = doc.lower().split()
        seen = set()
        for word in words:
            if word in seen:
                continue
            seen.add(word)
            result[word] = result.get(word, []) + [len(result)]
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()