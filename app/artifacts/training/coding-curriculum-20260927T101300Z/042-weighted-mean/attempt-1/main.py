import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps({"error": "Input must be a list"}), file=sys.stderr)
            return
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for pair in input_data:
            if not isinstance(pair, list) or len(pair) != 2:
                print(json.dumps({"error": "Each element must be a list of two values"}), file=sys.stderr)
                return
            
            value, weight = pair[0], pair[1]
            
            if not isinstance(value, (int, float)) or not isinstance(weight, (int, float)):
                print(json.dumps({"error": "Value and weight must be numeric"}), file=sys.stderr)
                return
            
            if weight <= 0:
                print(json.dumps({"error": "Weight must be positive"}), file=sys.stderr)
                return
            
            weighted_sum += value * weight
            total_weight += weight
        
        if total_weight == 0:
            print(json.dumps({"error": "Total weight is zero"}), file=sys.stderr)
            return
        
        result = weighted_sum / total_weight
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()