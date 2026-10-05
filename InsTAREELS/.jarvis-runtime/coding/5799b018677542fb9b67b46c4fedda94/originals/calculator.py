# Jarvis draft: calculator.py. Waiting for generated code.
import sys

def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        print("Error: Division by zero is not allowed.")
        return None
    return x / y

def main():
    print("Simple Calculator")
    print("-----------------")
    
    try:
        num1 = float(input("Enter first number: "))
        num2 = float(input("Enter second number: "))
        operation = input("Choose operation (+, -, *, /): ").strip()
        
        if operation == '+':
            result = add(num1, num2)
            print(f"Result: {num1} + {num2} = {result}")
        elif operation == '-':
            result = subtract(num1, num2)
            print(f"Result: {num1} - {num2} = {result}")
        elif operation == '*':
            result = multiply(num1, num2)
            print(f"Result: {num1} * {num2} = {result}")
        elif operation == '/':
            result = divide(num1, num2)
            if result is not None:
                print(f"Result: {num1} / {num2} = {result}")
        else:
            print("Invalid operation. Please choose +, -, *, or /")
    except ValueError:
        print("Error: Invalid")
