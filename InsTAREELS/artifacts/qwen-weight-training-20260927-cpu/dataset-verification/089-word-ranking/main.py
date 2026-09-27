import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list):
        return
    
    words = []
    for item in input_data:
        if isinstance(item, str):
            tokens = item.lower().split()
            words.extend(tokens)
    
    word_counts = {}
    for w in words:
        word_counts[w] = word_counts.get(w, 0) + 1
    
    result = sorted(word_counts.items(), key=lambda x: (-x[1], x[0]))
    print(json.dumps(result))

if __name__ == "__main__":
    main()