import sys
import itertools
import operator
import functools

def polyval(coeffs,x):
    return sum(c*x**i for i,c in enumerate(coeffs))

def makepoly(x,coeffs):
    return functools.reduce(operator.add,[c*x**i for i,c in enumerate(coeffs)])

def expand(coeffs):
    return [makepoly(x,coeff) for x in range(-10,11)]

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError,ValueError):
        sys.exit(1)
    
    if not isinstance(data, list) or len(data)<2:
        sys.exit(1)
    
    coeffs,x=data[0],data[1]
    if not isinstance(coeffs,list) or not isinstance(x,(int,float)):
        sys.exit(1)
    
    result=expand(coeffs)
    print(polyval(result,x))

if __name__ == "__main__":
    main()