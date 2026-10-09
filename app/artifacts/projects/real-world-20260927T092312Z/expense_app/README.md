# Expense Report App

A simple command-line tool for reading CSV expense files and generating a JSON report of totals by category.

## Overview

This application reads a CSV file containing `category` and `amount` columns, calculates the total expenses, and groups amounts by category. It uses only Python's standard library and requires no external dependencies or installation.

## Usage

Run the application with the path to your CSV file as an argument:

```bash
python main.py expenses.csv
```

### Expected CSV Format

The CSV file must have a header row with the following columns:
- `category`: The expense category (e.g., "Food", "Transport")
- `amount`: The numeric amount (positive or negative for refunds)

Example `expenses.csv`:
```
category,amount
Food,25.50
Transport,-10.00
Food,15.75
```

### Output Format

On success, the application prints a JSON object to standard output:
```json
{
  "total": "31.25",
  "by_category": {
    "Food": "41.25",
    "Transport": "-10.00"
  }
}
```

## Behavior

### Valid Input
- Blank category fields are treated as `uncategorized`.
- Negative amounts are accepted (e.g., refunds).
- Empty data results in `{"total":"0.00","by_category":{}}`.

### Error Handling
- Missing required columns (`category`, `amount`) raise a `ValueError`.
- Invalid or empty amount values raise a `ValueError` indicating the row number.
- Non-finite amounts (NaN, Infinity) raise a `ValueError`.
- All errors are printed to standard error and cause the program to exit with a non-zero status code.

## Dependencies

None. Uses only Python 3's standard library (`csv`, `decimal`, `sys`).

## Files

- `main.py`: Entry point script.
- `ledger.py`: Core logic for reading and processing CSV data.
