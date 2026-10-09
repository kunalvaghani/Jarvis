import csv
from decimal import Decimal, InvalidOperation
from typing import Dict


def read_totals(path: str) -> Dict[str, any]:
    """
    Read CSV expense file and return totals.
    
    Args:
        path: Path to CSV file with columns 'category' and 'amount'.
    
    Returns:
        Dictionary with 'total' (string, two decimals) and 'by_category' (dict of strings).
    
    Raises:
        ValueError: If amount is invalid or missing required columns.
    """
    total = Decimal('0')
    by_category: Dict[str, Decimal] = {}
    
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        if reader.fieldnames is None or 'category' not in reader.fieldnames or 'amount' not in reader.fieldnames:
            raise ValueError("Missing required columns 'category' and 'amount'.")
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 assuming header is row 1
            try:
                amount_str = row['amount'].strip()
                if not amount_str:
                    raise ValueError(f"Invalid amount on row {row_num}: empty value.")
                
                amount = Decimal(amount_str)
                
                if not amount.is_finite():
                    raise ValueError(f"Invalid amount on row {row_num}: non-finite value ({amount}).")
                
                category = row['category'].strip()
                if not category:
                    category = 'uncategorized'
                
                total += amount
                by_category[category] = by_category.get(category, Decimal('0')) + amount
                
            except InvalidOperation as e:
                raise ValueError(f"Invalid amount on row {row_num}: {e}")
    
    return {
        "total": f"{total:.2f}",
        "by_category": {k: f"{v:.2f}" for k, v in by_category.items()}
    }