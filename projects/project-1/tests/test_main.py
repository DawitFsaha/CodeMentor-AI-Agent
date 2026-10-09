import math

from main import add, subtract, multiply, divide, simple_calculator

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 5) == 4
    assert add(0, 0) == 0
    assert add(-2, -3) == -5
    assert add(1.5, 2.5) == 4.0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5
    assert subtract(-2, -3) == 1
    assert subtract(3.5, 2) == 1.5

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(-1, 5) == -5
    assert multiply(0, 10) == 0
    assert multiply(-2, -3) == 6
    assert multiply(2.5, 2) == 5.0

def test_divide():
    assert divide(6, 3) == 2
    assert divide(-6, 3) == -2
    assert divide(7, 2) == 3.5
    assert divide(0, 5) == 0
    assert divide(5, 0) == "Error: Division by zero."

def test_simple_calculator_add():
    assert simple_calculator(5, 7, "+") == 12
    assert simple_calculator(-2, 3, "+") == 1

def test_simple_calculator_subtract():
    assert simple_calculator(10, 4, "-") == 6
    assert simple_calculator(-5, -6, "-") == 1

def test_simple_calculator_multiply():
    assert simple_calculator(3, 7, "*") == 21
    assert simple_calculator(-2, 5, "*") == -10

def test_simple_calculator_divide():
    assert simple_calculator(8, 2, "/") == 4
    assert simple_calculator(7, 2, "/") == 3.5
    assert simple_calculator(5, 0, "/") == "Error: Division by zero."
    assert simple_calculator(0, 5, "/") == 0

def test_simple_calculator_invalid_op():
    assert simple_calculator(4, 2, "^") == "Error: Unsupported operation."
    assert simple_calculator(4, 2, "%") == "Error: Unsupported operation."
    assert simple_calculator(4, 2, "") == "Error: Unsupported operation."
    assert simple_calculator(4, 2, None) == "Error: Unsupported operation."

def test_floats_and_large_numbers():
    # Large numbers
    assert simple_calculator(1e10, 1e10, "+") == 2e10
    # Floats
    assert simple_calculator(2.5, 1.5, "+") == 4.0
    assert simple_calculator(2.5, 1.5, "-") == 1.0
    assert math.isclose(simple_calculator(2.5, 1.5, "*"), 3.75)
    assert math.isclose(simple_calculator(2.5, 2, "/"), 1.25)

if __name__ == "__main__":
    test_add()
    test_subtract()
    test_multiply()
    test_divide()
    test_simple_calculator_add()
    test_simple_calculator_subtract()
    test_simple_calculator_multiply()
    test_simple_calculator_divide()
    test_simple_calculator_invalid_op()
    test_floats_and_large_numbers()
    print("All tests passed.")