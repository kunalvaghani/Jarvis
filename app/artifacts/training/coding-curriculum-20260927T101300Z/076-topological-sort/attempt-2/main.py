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
    all_nodes = set()
    
    for node in input_data:
        if not isinstance(node, str):
            print(json.dumps([]), file=sys.stderr)
            return
        all_nodes.add(node)
        edges = input_data[node]
        if not isinstance(edges, list):
            print(json.dumps([]), file=sys.stderr)
            return
        for edge in edges:
            if not isinstance(edge, str):
                print(json.dumps([]), file=sys.stderr)
                return
            all_nodes.add(edge)
            adj_list[node] = adj_list.get(node, []) + [edge]
    
    # Ensure all nodes are keys in adj_list
    for node in all_nodes:
        if node not in adj_list:
            adj_list[node] = []
    
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
    
    # Sort nodes lexicographically to ensure deterministic start order
    sorted_nodes = sorted(all_nodes)
    for node in sorted_nodes:
        dfs(node)
    
    # Check for cycles: if a node is visited but not added to result, it's part of a cycle
    # However, the standard DFS post-order traversal above handles topological sort.
    # To detect cycles properly for this specific requirement (lexicographically smallest topo order),
    # we need to ensure that if a cycle exists, we output [].
    # The current DFS approach produces a valid topological order only if acyclic.
    # If there's a back edge (cycle), the result will still be generated but not strictly topological.
    # We need to detect cycles explicitly.
    
    # Re-implement with cycle detection using in-degree or explicit cycle check
    in_degree = {node: 0 for node in all_nodes}
    for node in adj_list:
        for neighbor in adj_list[node]:
            in_degree[neighbor] += 1
    
    # Kahn's algorithm with lexicographical tie-breaking
    queue = []
    for node in sorted(all_nodes):
        if in_degree[node] == 0:
            queue.append(node)
    
    result = []
    processed_count = 0
    
    while queue:
        # Sort queue to ensure lexicographically smallest choice
        queue.sort()
        node = queue.pop(0)
        result.append(node)
        processed_count += 1
        
        for neighbor in adj_list[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # If we didn't process all nodes, there is a cycle
    if processed_count != len(all_nodes):
        print(json.dumps([]))
    else:
        print(json.dumps(result))

if __name__ == "__main__":
    main()