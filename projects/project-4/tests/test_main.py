from main import largest_of_three

def test_distinct():
    assert largest_of_three(1, 2, 3) == 3
    assert largest_of_three(9, 4, 7) == 9
    assert largest_of_three(-1, -5, -2) == -1

def test_two_equal_largest():
    assert largest_of_three(5, 5, 3) == 5
    assert largest_of_three(2, 8, 8) == 8

def test_all_equal():
    assert largest_of_three(6, 6, 6) == 6