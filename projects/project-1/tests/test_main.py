# test_main.py

from main import add_two_numbers

def test_add_positive_integers():
    assert add_two_numbers(2, 3) == 5

def test_add_negative_integers():
    assert add_two_numbers(-5, -7) == -12

def test_add_mixed_sign_integers():
    assert add_two_numbers(10, -3) == 7
    assert add_two_numbers(-10, 3) == -7

def test_add_zeros():
    assert add_two_numbers(0, 0) == 0
    assert add_two_numbers(0, 5) == 5
    assert add_two_numbers(8, 0) == 8

def test_add_floats():
    assert add_two_numbers(2.5, 3.1) == 5.6
    assert add_two_numbers(-1.2, 1.2) == 0.0

def test_add_int_and_float():
    assert add_two_numbers(5, 2.5) == 7.5
    assert add_two_numbers(-3, 4.5) == 1.5

def test_add_large_numbers():
    assert add_two_numbers(10**18, 10**18) == 2 * 10**18

def test_add_with_non_numeric_types():
    try:
        add_two_numbers("a", 5)
        assert False, "Should raise TypeError"
    except TypeError:
        pass
    try:
        add_two_numbers([1, 2], 3)
        assert False, "Should raise TypeError"
    except TypeError:
        pass

if __name__ == "__main__":
    test_add_positive_integers()
    test_add_negative_integers()
    test_add_mixed_sign_integers()
    test_add_zeros()
    test_add_floats()
    test_add_int_and_float()
    test_add_large_numbers()
    test_add_with_non_numeric_types()
    print("All tests passed.")