import sys
import json

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

x = json.load(sys.stdin)
result = (celsius_to_fahrenheit(x))
print(json.dumps(result))
