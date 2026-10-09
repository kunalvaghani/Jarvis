import json
import sys

def longest_unique_substring_length(s: str) -> int:
    """
    Calculate the length of the longest substring without duplicate characters.
    Uses a sliding window approach with O(n) time complexity.
    """
    if not s:
        return 0
    
    char_index_map = {}
    max_length = 0
    start = 0
    
    for end, char in enumerate(s):
        if char in char_index_map and char_index_map[char] >= start:
            start = char_index_map[char] + 1
        
        char_index_map[char] = end
        current_length = end - start + 1
        max_length = max(max_length, current_length)
    
    return max_length

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            result = 0
        else:
            parsed_input = json.loads(input_data)
            # The input is expected to be a string (or JSON-encoded string)
            # Based on examples: "abcabcbb" -> 3, "" -> 0
            if isinstance(parsed_input, str):
                s = parsed_input
            elif isinstance(parsed_input, list) and len(parsed_input) == 1:
                s = parsed_input[0]
            else:
                # If input is not a string or single-element list containing a string,
                # treat it as invalid per contract examples which show direct strings.
                # However, to be robust for JSON CLI, we try to extract the string value.
                if isinstance(parsed_input, dict):
                    s = str(parsed_input.get('input', ''))
                else:
                    s = str(parsed_input)
            
            result = longest_unique_substring_length(s)
    except json.JSONDecodeError:
        # If JSON parsing fails, treat as empty input per silent output lesson
        result = 0
    except Exception:
        result = 0
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()