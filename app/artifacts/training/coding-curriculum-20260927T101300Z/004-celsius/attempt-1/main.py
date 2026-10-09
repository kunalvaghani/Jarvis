import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        celsius = float(input_data)
        fahrenheit = (celsius * 9 / 5) + 32
        print(fahrenheit)
    except ValueError:
        pass

if __name__ == "__main__":
    main()