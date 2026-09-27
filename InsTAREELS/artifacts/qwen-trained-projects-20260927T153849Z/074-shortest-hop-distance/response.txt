import sys
import heapq
import itertools

def dijkstra(graph, start, target):
    n = len(graph)
    dist = [float('inf')] * n
    dist[start] = 0
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v in graph[u]:
            if dist[v] > d + 1:
                dist[v] = d + 1
                heapq.heappush(pq, (dist[v], v))
    return dist[target] if dist[target] != float('inf') else -1

def main():
    try:
        input_data = sys.stdin.read().strip()
    except Exception:
        sys.exit(1)
    if not input_data:
        sys.exit(0)
    
    data = json.loads(input_data)
    if len(data) != 3:
        sys.exit(1)
    
    graph = data[0]
    start = data[1]
    target = data[2]
    
    result = dijkstra(graph, start, target)
    print(json.dumps(result))

if __name__ == "__main__":
    main()