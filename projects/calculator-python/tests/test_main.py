import pytest
from add3 import add
from subtract import subtract
from multiply import multiply
from divide import divide

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(3, 5) == -2

def test_multiply():
    assert multiply(4, 2) == 8
    assert multiply(0, 5) == 0

def test_divide_normal():
    assert divide(10, 2) == 5
    assert divide(-6, 3) == -2

def test_divide_zero():
    with pytest.raises(ValueError):
        divide(5, 0)