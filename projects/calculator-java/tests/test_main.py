import pytest
from main import add, subtract, multiply, divide

def test_add():
    assert add(3, 7) == 10
    assert add(-2, 2) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(-1, -1) == 0

def test_multiply():
    assert multiply(4, 6) == 24
    assert multiply(-3, 2) == -6

def test_divide_normal():
    assert divide(10, 2) == 5
    assert divide(-9, 3) == -3

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)