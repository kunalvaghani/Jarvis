"""100 distinct JSON CLI projects, with independent executable reference cases.

Reference expressions below are developer-authored, never model-generated.
They are used only by the evaluator and are not supplied to the coding model.
"""
import base64
import bisect
from collections import Counter
import csv
from datetime import date, timedelta
import hashlib
import heapq
import io
import itertools
import json
import math
import re
import statistics

def fib(n):
    a,b=0,1
    for _ in range(n): a,b=b,a+b
    return a

def roman(n):
    result=''
    for value,symbol in [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]:
        while n>=value: result+=symbol;n-=value
    return result

def intervals(rows):
    result=[]
    for a,b in sorted(rows):
        if result and a<=result[-1][1]:result[-1][1]=max(b,result[-1][1])
        else:result.append([a,b])
    return result

def rle(s):
    return [[k,len(list(v))] for k,v in itertools.groupby(s)]

def brackets(s):
    stack=[];pairs={')':'(',']':'[','}':'{'}
    for ch in s:
        if ch in '([{':stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop()!=pairs[ch]:return False
    return not stack

def factor(n):
    result=[];d=2
    while d*d<=n:
        while n%d==0:result.append(d);n//=d
        d+=1
    if n>1:result.append(n)
    return result

def edit(a,b):
    row=list(range(len(b)+1))
    for i,ch in enumerate(a,1):
        nxt=[i]
        for j,c in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(ch!=c)))
        row=nxt
    return row[-1]

def lcs(a,b):
    row=[0]*(len(b)+1)
    for ch in a:
        nxt=[0]
        for j,c in enumerate(b):nxt.append(row[j]+1 if ch==c else max(row[j+1],nxt[-1]))
        row=nxt
    return row[-1]

def coins(x):
    values,target=x;dp=[0]+[target+1]*target
    for n in range(1,target+1):dp[n]=min([dp[n-c]+1 for c in values if c<=n]+[target+1])
    return dp[target] if dp[target]<=target else -1

def knapsack(x):
    items,capacity=x;dp=[0]*(capacity+1)
    for weight,value in items:
        for n in range(capacity,weight-1,-1):dp[n]=max(dp[n],dp[n-weight]+value)
    return dp[-1]

def lis(values):
    tail=[]
    for value in values:
        i=bisect.bisect_left(tail,value)
        if i==len(tail):tail.append(value)
        else:tail[i]=value
    return len(tail)

def maxsum(values):
    best=current=values[0]
    for value in values[1:]:current=max(value,current+value);best=max(best,current)
    return best

def reachable(x):
    graph,start=x;seen=set();todo=[start]
    while todo:
        node=todo.pop()
        if node in seen:continue
        seen.add(node);todo.extend(graph.get(node,[]))
    return sorted(seen)

def distance(x):
    graph,start,target=x;todo=[(start,0)];seen={start}
    for node,d in todo:
        if node==target:return d
        for neighbor in graph.get(node,[]):
            if neighbor not in seen:seen.add(neighbor);todo.append((neighbor,d+1))
    return -1

def dijkstra(x):
    graph,start=x;cost={start:0};queue=[(0,start)]
    while queue:
        d,node=heapq.heappop(queue)
        if d!=cost[node]:continue
        for neighbor,weight in graph.get(node,[]):
            candidate=d+weight
            if candidate<cost.get(neighbor,math.inf):cost[neighbor]=candidate;heapq.heappush(queue,(candidate,neighbor))
    return dict(sorted(cost.items()))

def topo(graph):
    nodes=set(graph)|{n for row in graph.values() for n in row};degree={n:0 for n in nodes}
    for row in graph.values():
        for n in row:degree[n]+=1
    queue=[n for n in nodes if degree[n]==0];heapq.heapify(queue);result=[]
    while queue:
        node=heapq.heappop(queue);result.append(node)
        for n in graph.get(node,[]):
            degree[n]-=1
            if degree[n]==0:heapq.heappush(queue,n)
    return result if len(result)==len(nodes) else []

def components(graph):
    todo=set(graph)|{n for row in graph.values() for n in row};result=[]
    while todo:
        group=reachable([graph,min(todo)]);result.append(group);todo-=set(group)
    return result

def flatten(obj,prefix=''):
    result={}
    for key,value in obj.items():
        path=(prefix+'.' if prefix else '')+key
        if isinstance(value,dict):result.update(flatten(value,path))
        else:result[path]=value
    return result

def merge(a,b):
    result=dict(a)
    for key,value in b.items():
        result[key]=merge(result[key],value) if key in result and isinstance(result[key],dict) and isinstance(value,dict) else value
    return result

def business(x):
    start,end=map(date.fromisoformat,x);count=0
    while start<end:
        count+=start.weekday()<5;start+=timedelta(days=1)
    return count

def cache(x):
    capacity,keys=x;order=[];hits=0
    for key in keys:
        if key in order:hits+=1;order.remove(key)
        order.append(key)
        if len(order)>capacity:order.pop(0)
    return {'hits':hits,'keys':order}

def gridcost(grid):
    row=[math.inf]*len(grid[0])
    for i,values in enumerate(grid):
        for j,value in enumerate(values):row[j]=value+(0 if i==j==0 else min(row[j],row[j-1] if j else math.inf))
    return row[-1]

def rpn(tokens):
    stack=[]
    for token in tokens:
        if token in ['+','-','*','/']:
            b,a=stack.pop(),stack.pop();stack.append({'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[token]())
        else:stack.append(float(token))
    return stack[0]

def catalogue():
    rows=[]
    def add(name,contract,expr,samples):
        namespace=globals().copy()
        cases=[]
        for value in samples:
            namespace['x']=value
            expected=eval(expr,namespace)
            expected=json.loads(json.dumps(expected))
            cases.append({'input':value,'expected':expected})
        rows.append({'id':f'{len(rows)+1:03d}-{name}','name':name,'level':1+len(rows)//25,
                     'contract':contract,'cases':cases})
    add('sum','Sum a JSON list of numbers. Empty list returns 0.','sum(x)',[[],[1,2,3],[-2,4]])
    add('pair-add','Add the two numbers in the input pair.','x[0]+x[1]',[[0,0],[4,8],[-5,2]])
    add('product','Multiply list values; empty product is 1.','math.prod(x)',[[],[2,3,4],[0,5]])
    add('celsius','Convert Celsius number to Fahrenheit.','x*9/5+32',[0,100,-40])
    add('rectangle','Pair width,height to rectangle area.','math.prod(x)',[[3,4],[0,7],[2.5,4]])
    add('triangle','Pair base,height to triangle area.','x[0]*x[1]/2',[[3,4],[0,2],[5,5]])
    add('circle','Radius to area using math.pi.','math.pi*x*x',[0,1,3])
    add('discount','Pair price,percentage to discounted price.','x[0]*(1-x[1]/100)',[[100,20],[20,0],[80,100]])
    add('tip','Pair bill,tip percentage to total including tip.','x[0]*(1+x[1]/100)',[[100,20],[50,0],[0,20]])
    add('bmi','Pair kilograms,meters to BMI.','x[0]/x[1]**2',[[80,2],[50,1.5],[60,1.8]])
    add('simple-interest','Triple principal,annual percent,years to interest alone.','x[0]*x[1]*x[2]/100',[[100,5,2],[200,0,10],[1000,3,1]])
    add('compound-interest','Triple principal,annual percent,integer years to final balance.','x[0]*(1+x[1]/100)**x[2]',[[100,10,2],[20,0,5],[100,5,0]])
    add('seconds','Nonnegative seconds to [hours,minutes,seconds], hours unbounded.','[x//3600,x//60%60,x%60]',[0,3661,90000])
    add('evens','Preserve order of even integers only.','[n for n in x if n%2==0]',[[],[1,2,3,4],[-2,-1,0]])
    add('positive-count','Count values strictly greater than zero.','sum(n>0 for n in x)',[[],[-1,0,2],[1,2,3]])
    add('numeric-span','Nonempty list to maximum minus minimum.','max(x)-min(x)',[[3],[1,5,2],[-5,-2]])
    add('mean','Mean of nonempty numeric list.','statistics.mean(x)',[[1],[1,2,3],[-4,4]])
    add('median','Median of nonempty numeric list.','statistics.median(x)',[[1],[3,1,2],[1,4,2,3]])
    add('reverse-text','Reverse the input string.','x[::-1]',['','abc','hello world'])
    add('word-count','Count whitespace-separated words.','len(x.split())',['','one two','  a\n b\t c '])
    add('vowel-count','Count ASCII vowels case-insensitively.','sum(c.lower() in "aeiou" for c in x)',['','HELLO','rhythm'])
    add('slug','Lowercase; replace each run of non ASCII alphanumeric with hyphen; strip edge hyphens.','re.sub(r"[^a-z0-9]+","-",x.lower()).strip("-")',['Hello World!','  A___B ','---'])
    add('palindrome','Ignore nonalphanumeric characters and case to test palindrome.','(lambda s:s==s[::-1])("".join(c.lower() for c in x if c.isalnum()))',['','A man, a plan, a canal: Panama','hello'])
    add('title-case','Apply Python str.title to input text.','x.title()',['hello world','mIXed CASE',''])
    add('ordered-unique','Remove duplicate integers preserving first occurrence order.','list(dict.fromkeys(x))',[[],[2,1,2,3],[0,0,0]])
    add('frequencies','Count string items into JSON object.','dict(Counter(x))',[[],['a','b','a'],['x','x']])
    add('numeric-sort','Sort integers ascending retaining duplicates.','sorted(x)',[[],[3,1,2],[2,2,-1]])
    add('second-largest','Second largest DISTINCT integer; fewer than two distinct values returns null.','sorted(set(x))[-2] if len(set(x))>1 else None',[[1],[3,2,3,1],[-2,-5]])
    add('chunks','Pair list,positive chunk size to consecutive chunks, retaining final partial chunk.','[x[0][i:i+x[1]] for i in range(0,len(x[0]),x[1])]',[[[],2],[[1,2,3,4,5],2],[[1],4]])
    add('rotate','Pair list,k to right rotation by k, wrapping; empty list remains empty.','(lambda a,k:a[-k:]+a[:-k] if k else a)(x[0],x[1]%len(x[0])) if x[0] else []',[[[],3],[[1,2,3],1],[[1,2,3],4]])
    add('flatten-list','Flatten exactly one level of nested lists.','list(itertools.chain.from_iterable(x))',[[],[[1,2],[],[3]],[[0]]])
    add('transpose','Transpose rectangular matrix; empty matrix returns [].','list(map(list,zip(*x)))',[[],[[1,2],[3,4]],[[1,2,3]]])
    add('matrix-product','Pair compatible nonempty matrices to matrix multiplication.','[[sum(a*b for a,b in zip(row,col)) for col in zip(*x[1])] for row in x[0]]',[[[[1]],[[2]]],[[[1,2]],[[3],[4]]],[[[1,0],[0,1]],[[2,3],[4,5]]]])
    add('running-totals','Cumulative sums of numeric list.','list(itertools.accumulate(x))',[[],[1,2,3],[-2,2,5]])
    add('moving-average','Pair list,positive window size to means of complete sliding windows.','[statistics.mean(x[0][i:i+x[1]]) for i in range(len(x[0])-x[1]+1)]',[[[1,2,3],2],[[1],2],[[2,4],1]])
    add('merge-sorted','Pair sorted integer lists to merged sorted list.','sorted(x[0]+x[1])',[[[],[]],[[1,3],[2,4]],[[1,1],[1]]])
    add('missing-integers','Pair observed integers,n to missing numbers in inclusive range 1..n.','[n for n in range(1,x[1]+1) if n not in x[0]]',[[[],3],[[1,3],4],[[1,2],2]])
    add('pair-sum','Pair list,target to sorted unique value pairs a<=b from distinct indices summing to target.','sorted({tuple(sorted((a,b))) for i,a in enumerate(x[0]) for b in x[0][i+1:] if a+b==x[1]})',[[[1,2,3,4],5],[[2,2,2],4],[[],0]])
    add('three-sum','List to sorted unique ascending value triples from distinct indices summing to zero.','sorted({tuple(sorted(t)) for t in itertools.combinations(x,3) if sum(t)==0})',[[0,0,0],[-1,0,1,2,-1,-4],[]])
    add('merge-intervals','Merge overlapping OR touching closed [start,end] intervals; sort output.','intervals(x)',[[],[[1,3],[2,5],[8,9]],[[1,2],[2,3]]])
    add('jaccard','Pair lists to set Jaccard similarity; both empty returns 1.','len(set(x[0])&set(x[1]))/len(set(x[0])|set(x[1])) if x[0] or x[1] else 1',[[[],[]],[[1,2],[2,3]],[[1],[1]]])
    add('weighted-mean','List of [value,positive weight] pairs to weighted average.','sum(v*w for v,w in x)/sum(w for v,w in x)',[[[1,1]],[[1,1],[3,3]],[[0,2],[10,2]]])
    add('minmax-normalize','Nonempty numeric list to (value-min)/(max-min); constant list returns all zeros.','[(v-min(x))/(max(x)-min(x)) if max(x)!=min(x) else 0 for v in x]',[[5],[1,2,3],[-5,5]])
    add('run-length-encode','String to [character,count] runs.','rle(x)',['','aaabbc','ababa'])
    add('run-length-decode','List of [character,count] runs to decoded string.','"".join(c*n for c,n in x)',[[],[['a',3],['b',2]],[['x',0]]])
    add('caesar','Pair string,integer shift; shift ASCII lowercase only and leave other characters unchanged.','"".join(chr((ord(c)-97+x[1])%26+97) if "a"<=c<="z" else c for c in x[0])',[['abc',1],['xyz',3],['Hi!',-2]])
    add('anagram-groups','Group case-sensitive strings by sorted characters; sort members and sort groups lexicographically.','sorted([sorted(v) for v in (lambda d:d.values())(__import__("functools").reduce(lambda d,s:(d.setdefault("".join(sorted(s)),[]).append(s) or d),x,{}))])',[[],['eat','tea','tan','ate','nat'],['a','a','b']])
    add('binary-to-int','Binary digit string to integer.','int(x,2)',['0','101','1111'])
    add('balanced-brackets','Validate (), [], {} nesting; ignore other characters.','brackets(x)',['','([{}])','([)]'])
    add('roman-numerals','Convert integer 1..3999 to uppercase Roman numerals.','roman(x)',[1,49,1994])
    add('rpn-calculator','Evaluate valid reverse Polish tokens +,-,*,/ with normal operand order.','rpn(x)',[['2','3','+'],['5','2','-'],['4','2','/','3','*']])
    add('polynomial-value','Pair ascending-power coefficients,value to polynomial evaluation.','sum(c*x[1]**i for i,c in enumerate(x[0]))',[[[1,2,3],2],[[5],10],[[],3]])
    add('polynomial-derivative','Ascending-power coefficients to derivative coefficients; constants return [].','[i*c for i,c in enumerate(x) if i]',[[5],[1,2,3],[]])
    add('gcd','Pair nonnegative integers to greatest common divisor.','math.gcd(*x)',[[0,0],[12,18],[7,3]])
    add('lcm','Pair nonnegative integers to least common multiple.','math.lcm(*x)',[[0,4],[4,6],[7,3]])
    add('prime-list','Integer n to all primes <=n ascending.','[p for p in range(2,x+1) if all(p%d for d in range(2,math.isqrt(p)+1))]',[1,10,30])
    add('prime-factors','Integer >=1 to ascending prime factors with multiplicity.','factor(x)',[1,12,97])
    add('fibonacci','Nth Fibonacci F0=0,F1=1; n>=0.','fib(x)',[0,10,25])
    add('factorial','Integer n>=0 to n factorial.','math.factorial(x)',[0,5,10])
    add('divisors','Positive integer to ascending positive divisors.','[n for n in range(1,x+1) if x%n==0]',[1,12,17])
    add('edit-distance','Pair strings to Levenshtein distance with unit insertion/deletion/substitution costs.','edit(*x)',[['','abc'],['kitten','sitting'],['same','same']])
    add('lcs-length','Pair strings to longest common subsequence length.','lcs(*x)',[['','abc'],['abcde','ace'],['abc','def']])
    add('coin-change','Pair positive denominations,target>=0 to minimum coins with unlimited supply; impossible -1.','coins(x)',[[[1,3,4],6],[[2],3],[[2],0]])
    add('knapsack','Pair [weight,value] items,capacity to maximum value in 0/1 knapsack.','knapsack(x)',[[[[2,3],[3,4],[4,5]],5],[[],5],[[[1,10]],0]])
    add('lis-length','List integers to strictly increasing subsequence length.','lis(x)',[[],[10,9,2,5,3,7,101,18],[2,2,2]])
    add('grid-path-count','Pair positive rows,columns to count right/down paths in unobstructed grid.','math.comb(x[0]+x[1]-2,x[0]-1)',[[1,1],[3,3],[2,5]])
    add('max-subarray','Nonempty list to maximum NONEMPTY contiguous subarray sum.','maxsum(x)',[[1],[-5,-2,-8],[-2,1,-3,4,-1,2,1,-5,4]])
    add('subsets','Distinct integers to all subsets, each sorted; sort output lexicographically.','sorted([sorted(c) for n in range(len(x)+1) for c in itertools.combinations(x,n)])',[[],[1,2],[3,1]])
    add('unique-permutations','Integer list to sorted unique permutations as lists.','sorted(set(itertools.permutations(x)))',[[],[1,2],[1,1,2]])
    add('combinations','Pair distinct integers,k to sorted unique sorted k-element combinations.','sorted({tuple(sorted(c)) for c in itertools.combinations(x[0],x[1])})',[[[1,2,3],2],[[1],0],[[1],2]])
    add('binary-insertion','Pair sorted list,target to leftmost insertion index.','bisect.bisect_left(*x)',[[[],3],[[1,2,2,4],2],[[1,3],5]])
    add('hamming-distance','Equal-length strings to differing character count.','sum(a!=b for a,b in zip(*x))',[['',''],['abc','axc'],['111','000']])
    add('reachability','Pair directed adjacency object,start to sorted reachable nodes including start.','reachable(x)',[[{},'a'],[{'a':['b'],'b':['c']},'a'],[{'a':['a']},'a']])
    add('shortest-hop-distance','Triple directed adjacency,start,target to shortest edge count, -1 if unreachable.','distance(x)',[[{},'a','a'],[{'a':['b'],'b':['c']},'a','c'],[{},'a','z']])
    add('weighted-shortest-path','Pair directed adjacency with [neighbor,nonnegative weight] entries,start to distances for reachable nodes only.','dijkstra(x)',[[{},'a'],[{'a':[['b',5],['c',1]],'c':[['b',1]]},'a'],[{'a':[['b',0]]},'a']])
    add('topological-sort','Directed adjacency object to lexicographically smallest topological order, [] if cyclic.','topo(x)',[{}, {'a':['c'],'b':['c']},{'a':['b'],'b':['a']}])
    add('connected-components','UNDIRECTED adjacency object to sorted components, each sorted.','components(x)',[{}, {'a':['b'],'b':['a'],'c':[]},{'a':[]}])
    add('lru-simulation','Pair positive capacity,sequence of string keys to {hits,keys}; keys ordered oldest to newest.','cache(x)',[[2,['a','b','a','c']],[1,['a','a','b']],[2,[]]])
    add('minimum-grid-cost','Nonempty rectangular numeric grid to minimum top-left/bottom-right path sum, right/down only, include both endpoints.','gridcost(x)',[[[5]],[[1,3],[2,4]],[[1,9,1],[1,1,1]]])
    add('csv-records','CSV text with header to list of string-valued record objects using csv.DictReader.','list(csv.DictReader(io.StringIO(x)))',['a,b\n1,2\n','a,b\n"x,y",z\n','a,b\n'])
    add('flatten-object','Nested JSON objects to dotted-key object; retain lists as leaves; empty objects contribute nothing.','flatten(x)',[{}, {'a':{'b':2},'c':[1,2]}, {'a':{}}])
    add('deep-merge','Pair JSON objects; recursively merge objects, otherwise right value replaces left including lists.','merge(*x)',[[{},{}],[{'a':{'b':1}},{'a':{'c':2}}],[{'a':[1]},{'a':[2]}]])
    add('business-days','Pair ISO dates start,end to weekdays in half-open [start,end); start<=end. No holiday rules.','business(x)',[['2026-09-21','2026-09-28'],['2026-09-26','2026-09-28'],['2026-09-21','2026-09-21']])
    add('date-difference','Pair ISO dates to signed end-start days.','(date.fromisoformat(x[1])-date.fromisoformat(x[0])).days',[['2024-02-28','2024-03-01'],['2026-01-02','2026-01-01'],['2026-01-01','2026-01-01']])
    add('base64-encode','UTF-8 string to standard Base64 ASCII text.','base64.b64encode(x.encode()).decode()',['','hello','café'])
    add('base64-decode','Valid Base64 of UTF-8 text to decoded string.','base64.b64decode(x).decode()',['','aGVsbG8=','Y2Fmw6k='])
    add('sha256-text','UTF-8 string to lowercase SHA256 hex digest.','hashlib.sha256(x.encode()).hexdigest()',['','hello','abc'])
    add('inverted-index','List document strings to word->ascending document indices; lowercase whitespace tokens, deduplicate within document.','{w:[i for i,d in enumerate(x) if w in d.lower().split()] for w in sorted(set(" ".join(x).lower().split()))}',[[],['A b a','b c'],['X','x']])
    add('word-ranking','List strings to [word,count] pairs sorted descending count, then alphabetical; lowercase whitespace tokens.','sorted(Counter(" ".join(x).lower().split()).items(),key=lambda p:(-p[1],p[0]))',[[],['a b a','b c'],['z a']])
    add('interval-conflicts','List closed intervals to pairs of original indices i<j whose intervals overlap or touch, sorted.','[[i,j] for i,a in enumerate(x) for j,b in enumerate(x) if i<j and max(a[0],b[0])<=min(a[1],b[1])]',[[],[[1,3],[3,5],[7,8]],[[0,10],[2,3],[4,5]]])
    add('longest-common-prefix','List strings to longest common prefix; empty list returns empty string.','__import__("os").path.commonprefix(x)',[[],['flower','flow','flight'],['a','b']])
    add('multiset-intersection','Pair integer lists to sorted intersection retaining minimum multiplicities.','sorted((Counter(x[0])&Counter(x[1])).elements())',[[[],[]],[[1,1,2],[1,2,2]],[[3],[4]]])
    add('window-maxima','Pair integer list,positive window size to maxima of complete sliding windows.','[max(x[0][i:i+x[1]]) for i in range(len(x[0])-x[1]+1)]',[[[1,3,-1,-3,5,3,6,7],3],[[1],2],[[2,1],1]])
    add('histogram-area','Nonnegative heights to largest rectangle area under histogram, unit widths.','max([min(x[i:j])*(j-i) for i in range(len(x)) for j in range(i+1,len(x)+1)]+[0])',[[],[2,1,5,6,2,3],[2,2]])
    add('trapped-water','Nonnegative heights to total trapped water, unit widths.','sum(max(0,min(max(x[:i+1]),max(x[i:]))-h) for i,h in enumerate(x))',[[],[0,1,0,2,1,0,1,3,2,1,2,1],[2,0,2]])
    add('minimum-jumps','Nonnegative jump capacities; minimum jumps from index0 to final index, -1 unreachable, empty/single returns0.','(lambda a: distance([{str(i):[str(j) for j in range(i+1,min(len(a),i+a[i]+1))] for i in range(len(a))},"0",str(len(a)-1)]) if len(a)>1 else 0)(x)',[[2,3,1,1,4],[0,1],[]])
    add('partition-equal-sum','Nonnegative integer list to whether it can split into equal-sum subsets, empty true.','any(sum(c)*2==sum(x) for n in range(len(x)+1) for c in itertools.combinations(x,n))',[[],[1,5,11,5],[1,2,3,5]])
    add('longest-palindrome','String to longest palindromic SUBSTRING; ties choose earliest start, empty string stays empty.','max([x[i:j] for i in range(len(x)) for j in range(i+1,len(x)+1) if x[i:j]==x[i:j][::-1]]+[""],key=len)',['','babad','cbbd'])
    add('balanced-parentheses-generation','n>=0 to all balanced n-pair parentheses strings, lexicographic order.','sorted(s for s in map("".join,itertools.product("()",repeat=2*x)) if brackets(s))',[0,1,3])
    add('longest-unique-substring','String to length of longest substring without duplicate characters.','max([j-i for i in range(len(x)) for j in range(i+1,len(x)+1) if len(set(x[i:j]))==j-i]+[0])',['','abcabcbb','bbbbb'])
    assert len(rows)==100, len(rows)
    return rows
