from add3 import add
from subtract import subtract
from multiply import multiply
from divide import divide

def demo_calculator():
    a = 10
    b = 5

    print(f"Add: {a} + {b} = {add(a, b)}")
    print(f"Subtract: {a} - {b} = {subtract(a, b)}")
    print(f"Multiply: {a} * {b} = {multiply(a, b)}")
    try:
        print(f"Divide: {a} / {b} = {divide(a, b)}")
    except ValueError as e:
        print(f"Divide: Error: {e}")

    # Demonstrate divide by zero
    try:
        divide(a, 0)
    except ValueError as e:
        print(f"Divide by zero test: {e}")

if __name__ == "__main__":
    demo_calculator()