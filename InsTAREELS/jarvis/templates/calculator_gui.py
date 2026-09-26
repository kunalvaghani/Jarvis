"""A calculator with a desktop UI and a command-line mode.

Run without arguments to open the UI, or run:
    python calculator.py add 5 10
"""

import argparse
import sys


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


def launch_ui() -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Calculator")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky="nsew")

    first = tk.StringVar()
    second = tk.StringVar()
    operation = tk.StringVar(value="add")
    result = tk.StringVar(value="Enter two numbers and choose an operation.")

    ttk.Label(frame, text="First number").grid(row=0, column=0, sticky="w", pady=4)
    first_entry = ttk.Entry(frame, textvariable=first, width=24)
    first_entry.grid(row=0, column=1, pady=4)
    ttk.Label(frame, text="Operation").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Combobox(frame, textvariable=operation, values=("add", "subtract", "multiply", "divide"),
                 state="readonly", width=21).grid(row=1, column=1, pady=4)
    ttk.Label(frame, text="Second number").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=second, width=24).grid(row=2, column=1, pady=4)

    def show_result(*_args) -> None:
        try:
            value = calculate(operation.get(), float(first.get()), float(second.get()))
        except ValueError as error:
            result.set(str(error))
        else:
            result.set(f"Result: {value:g}")

    ttk.Button(frame, text="Calculate", command=show_result).grid(row=3, column=0, columnspan=2,
                                                                   sticky="ew", pady=(10, 6))
    ttk.Label(frame, textvariable=result, wraplength=300).grid(row=4, column=0, columnspan=2,
                                                                 sticky="w", pady=4)
    root.bind("<Return>", show_result)
    first_entry.focus_set()
    root.mainloop()


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
    if len(sys.argv) == 1:
        launch_ui()
    else:
        main()
