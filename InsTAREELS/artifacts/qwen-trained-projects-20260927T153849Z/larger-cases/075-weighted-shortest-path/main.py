import sys
import json


def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        graph = data[0]
        start = data[1]
        
        if not isinstance(graph, dict) or not isinstance(start, str):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if start not in graph:
            print(json.dumps(None), file=sys.stderr)
            return
        
        neighbors = graph[start]
        if not isinstance(neighbors, list):
            print(json.dumps(None), file=sys.stderr)
            return
        
        distances = {}
        for neighbor, weight in neighbors:
            if neighbor not in distances:
                distances[neighbor] = float('inf')
            distances[neighbor] = min(distances[neighbor], weight)
        
        result = json.dumps(distances)
        print(result)
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)


if __name__ == "__main__":
    main()