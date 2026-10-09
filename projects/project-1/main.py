# main.py

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        return "Error: Division by zero."
    return a / b

def simple_calculator(a, b, operation):
    if operation == "+":
        return add(a, b)
    elif operation == "-":
        return subtract(a, b)
    elif operation == "*":
        return multiply(a, b)
    elif operation == "/":
        return divide(a, b)
    else:
        return "Error: Unsupported operation."

if __name__ == "__main__":
    # Demonstration using fixed values
    print("5 + 3 =", simple_calculator(5, 3, "+"))
    print("5 - 3 =", simple_calculator(5, 3, "-"))
    print("5 * 3 =", simple_calculator(5, 3, "*"))
    print("5 / 3 =", simple_calculator(5, 3, "/"))
    print("5 / 0 =", simple_calculator(5, 0, "/"))
    print("5 ^ 3 =", simple_calculator(5, 3, "^"))