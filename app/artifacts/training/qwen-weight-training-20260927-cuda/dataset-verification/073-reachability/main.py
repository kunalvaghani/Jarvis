import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps({"error": "Input must be a list of two elements: [adjacency_object, start_node]"}), file=sys.stderr)
            sys.exit(1)
        
        adjacency = input_data[0]
        if not isinstance(adjacency, dict):
            print(json.dumps({"error": "First element must be an object (adjacency list)"}), file=sys.stderr)
            sys.exit(1)
        
        start_node = input_data[1]
        if not isinstance(start_node, str):
            print(json.dumps({"error": "Second element must be a string (start node)"}), file=sys.stderr)
            sys.exit(1)
        
        visited = set()
        queue = [start_node]
        visited.add(start_node)
        result = [start_node]
        
        while queue:
            current = queue.pop(0)
            neighbors = adjacency.get(current, [])
            if not isinstance(neighbors, list):
                continue
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    result.append(neighbor)
                    queue.append(neighbor)
        
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()