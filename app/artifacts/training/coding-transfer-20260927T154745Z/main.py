import sys
from decimal import Decimal
import json

def calculate(items):
    subtotal = sum(item['price']*item['qty'] for item in items)
    discount = subtotal*Decimal(item['discount_pct'])/100
    net = subtotal-discount
    tax = net*Decimal(item['tax_pct'])/100
    total = net+tax
    return {'subtotal': subtotal, 'discount': discount, 'net': net, 'tax': tax, 'total': total}

try:
    input_data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(1)

if not isinstance(input_data, dict):
    sys.exit(1)

if 'items' not in input_data or not isinstance(input_data['items'], list):
    sys.exit(1)

result = calculate(input_data['items'])
print(json.dumps(result))
