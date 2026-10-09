import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps([]), file=sys.stderr)
        return
    
    if not isinstance(input_data, dict):
        print(json.dumps([]), file=sys.stderr)
        return
    
    adj_list = {}
    for node in input_data:
        if not isinstance(node, str):
            print(json.dumps([]), file=sys.stderr)
            return
        if node not in adj_list:
            adj_list[node] = []
        edges = input_data.get(node, [])
        if not isinstance(edges, list):
            print(json.dumps([]), file=sys.stderr)
            return
        for edge in edges:
            if not isinstance(edge, str):
                print(json.dumps([]), file=sys.stderr)
                return
            adj_list[node].append(edge)
    
    all_nodes = set(adj_list.keys())
    for node in adj_list:
        for neighbor in adj_list[node]:
            all_nodes.add(neighbor)
    
    visited = set()
    result = []
    
    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        neighbors = sorted(adj_list.get(node, []))
        for neighbor in neighbors:
            dfs(neighbor)
        result.append(node)
    
    for node in sorted(all_nodes):
        dfs(node)
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()