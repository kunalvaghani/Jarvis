import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}), file=sys.stderr)
        return
    
    if not isinstance(input_data, list):
        print(json.dumps({}), file=sys.stderr)
        return
    
    word_to_docs = {}
    
    for doc_idx, doc_str in enumerate(input_data):
        if not isinstance(doc_str, str):
            continue
        
        tokens = doc_str.lower().split()
        unique_tokens = list(dict.fromkeys(tokens))
        
        for token in unique_tokens:
            if token not in word_to_docs:
                word_to_docs[token] = []
            word_to_docs[token].append(doc_idx)
    
    result = {k: sorted(v) for k, v in word_to_docs.items()}
    print(json.dumps(result))

if __name__ == "__main__":
    main()