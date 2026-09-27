import json
import sys
from decimal import Decimal, ROUND_HALF_UP

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(input_data, dict):
        print(json.dumps({"error": "Input must be a JSON object"}), file=sys.stderr)
        sys.exit(1)
    
    items = input_data.get("items", [])
    discount_pct = Decimal(str(input_data.get("discount_pct", 0)))
    tax_pct = Decimal(str(input_data.get("tax_pct", 0)))
    
    subtotal = Decimal('0')
    for item in items:
        if not isinstance(item, dict):
            continue
        price = Decimal(str(item.get("price", 0)))
        qty = Decimal(str(item.get("qty", 0)))
        if qty > 0:
            subtotal += price * qty
    
    subtotal_rounded = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    discount = (subtotal_rounded * discount_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net = subtotal_rounded - discount
    tax = (net * tax_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = net + tax
    
    result = {
        "subtotal": float(subtotal_rounded),
        "discount": float(discount),
        "net": float(net),
        "tax": float(tax),
        "total": float(total)
    }
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()