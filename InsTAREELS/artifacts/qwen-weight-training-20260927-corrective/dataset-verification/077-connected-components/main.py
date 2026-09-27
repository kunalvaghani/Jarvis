import sys
import json

def reachable(x):
    graph,start=x;seen=set();todo=[start]
    while todo:
        node=todo.pop()
        if node in seen:continue
        seen.add(node);todo.extend(graph.get(node,[]))
    return sorted(seen)
def components(graph):
    todo=set(graph)|{n for row in graph.values() for n in row};result=[]
    while todo:
        group=reachable([graph,min(todo)]);result.append(group);todo-=set(group)
    return result

x = json.load(sys.stdin)
result = (components(x))
print(json.dumps(result))
