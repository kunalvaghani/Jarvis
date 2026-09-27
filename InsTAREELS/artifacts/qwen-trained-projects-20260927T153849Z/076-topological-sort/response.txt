import sys
import heapq
import collections

def topological_sort(graph):
    indegree = collections.defaultdict(int)
    for u in graph:
        for v in graph[u]:
            indegree[v] += 1
    queue = [u for u in graph if indegree[u] == 0]
    result = []
    while queue:
        node = heapq.heappop(queue)
        result.append(node)
        for neighbor in graph[node]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)
    return result if len(result) == len(graph) else []

def main():
    try:
        input_data = sys.stdin.read().strip()
    except Exception:
        sys.exit(1)
    if not input_data:
        sys.exit(0)
    try:
        graph = json.loads(input_data)
    except (json.JSONDecodeError, ValueError):
        sys.exit(1)
    if not isinstance(graph, dict):
        sys.exit(1)
    try:
        result = topological_sort(graph)
    except Exception as e:
        sys.exit(1)
    print(json.dumps(result))

if __name__ == "__main__":
    main()