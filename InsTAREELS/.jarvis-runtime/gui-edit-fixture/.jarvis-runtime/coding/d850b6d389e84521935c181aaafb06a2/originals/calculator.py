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
    print(calculate("multiply", 6, 7))

if __name__ == "__main__":
    main()
