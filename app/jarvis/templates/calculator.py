"""A small command-line calculator.

Examples:
    python calculator.py add 5 10
    python calculator.py divide 12 4
"""

import argparse


def calculate(operation: str, first: float, second: float) -> float:
    if operation == "add":
        return first + second
    if operation == "subtract":
        return first - second
    if operation == "multiply":
        return first * second
    if operation == "divide":
        if second == 0:
            raise ValueError("Cannot divide by zero.")
        return first / second
    raise ValueError(f"Unknown operation: {operation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add, subtract, multiply, or divide two numbers.")
    parser.add_argument("operation", choices=("add", "subtract", "multiply", "divide"))
    parser.add_argument("first", type=float)
    parser.add_argument("second", type=float)
    args = parser.parse_args()
    try:
        result = calculate(args.operation, args.first, args.second)
    except ValueError as error:
        parser.error(str(error))
    print(f"{result:g}")


if __name__ == "__main__":
    main()
