# Invoice calculator transfer task

Create main.py as a complete standard-library Python JSON CLI invoice calculator. Read one JSON object from stdin with items (list of objects containing price and qty), discount_pct and tax_pct. All values are nonnegative, qty is an integer and percentages are 0..100. Output only one JSON object with numeric subtotal, discount, net, tax and total. Round subtotal=sum(price*qty) to two decimal places using decimal ROUND_HALF_UP. Round discount=subtotal*discount_pct/100 to two places HALF_UP; net=subtotal-discount. Round tax=net*tax_pct/100 HALF_UP; total=net+tax. Empty/zero-quantity items contribute zero. Retain every item including duplicates. Use Decimal from string representations for cents. No files, network, processes, eval, installation or extra stdout labels.

Run `python main.py`. Two examples were provided; eight follow-up cases were withheld.
