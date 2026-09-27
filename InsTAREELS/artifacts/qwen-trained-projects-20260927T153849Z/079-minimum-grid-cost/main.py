import sys
import heapq

def min_path_sum(grid):
    if not grid:
        return 0
    
    m, n = len(grid), len(grid[0])
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    
    heap = []
    heapq.heappush(heap, (grid[0][0], 0, 0))
    
    visited = set()
    visited.add((0, 0))
    
    while heap:
        current_sum, x, y = heapq.heappop(heap)
        
        if (x, y) == (m-1, n-1):
            return current_sum
        
        for dx, dy in directions:
            nx, ny = x+dx, y+dy
            if 0 <= nx < m and 0 <= ny < n and (nx, ny) not in visited:
                visited.add((nx, ny))
                heapq.heappush(heap, (current_sum + grid[nx][ny], nx, ny))
    
    return None

if __name__ == "__main__":
    import sys
    result = min_path_sum(json.load(sys.stdin))
    print(json.dumps(result))
