import sys
import tkinter as tk
from tkinter import ttk


def calculate(operation, a, b):
    if operation == "add":
        return a + b
    if operation == "subtract":
        return a - b
    if operation == "multiply":
        return a * b
    if operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    raise ValueError("Unknown operation")


def main():
    root = tk.Tk()
    root.title("Calculator")
    
    # Input A
    entry_a = ttk.Entry(root)
    entry_a.pack(pady=5)
    
    # Operation Combobox
    combobox_op = ttk.Combobox(root, values=["add", "subtract", "multiply", "divide"])
    combobox_op.current(0)  # Default to first item
    combobox_op.pack(pady=5)
    
    # Input B
    entry_b = ttk.Entry(root)
    entry_b.pack(pady=5)
    
    # Calculate Button
    btn_calc = ttk.Button(root, text="Calculate", command=lambda: update_result())
    btn_calc.pack(pady=10)
    
    # Result Label
    label_result = ttk.Label(root, text="")
    label_result.pack(pady=5)
    
    def update_result():
        try:
            a = float(entry_a.get())
            b = float(entry_b.get())
            op = combobox_op.get()
            result = calculate(op, a, b)
            label_result.config(text=f"Result: {result}")
        except ValueError as e:
            label_result.config(text=f"Error: {e}")
    
    root.mainloop()


if __name__ == "__main__":
    main()
