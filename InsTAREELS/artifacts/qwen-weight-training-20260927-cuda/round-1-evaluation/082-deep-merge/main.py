import json

def main():
    try:
        data = json.load(sys.stdin)
        if isinstance(data, list):
            return json.dumps(merge_dicts(*data))
        else:
            return json.dumps(data)
    except json.JSONDecodeError:
        print("Invalid JSON input")
        sys.exit(1)

def merge_dicts(dict1, dict2):
    if isinstance(dict1, dict) and isinstance(dict2, dict):
        merged_dict = {}
        for key in dict1.keys() | dict2.keys():
            if key in dict1 and key in dict2:
                merged_dict[key] = merge_dicts(dict1[key], dict2[key])
            elif key in dict1:
                merged_dict[key] = dict1[key]
            elif key in dict2:
                merged_dict[key] = dict2[key]
        return merged_dict
    else:
        return dict1 or dict2

if __name__ == "__main__":
    main()