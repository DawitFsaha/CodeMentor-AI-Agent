def largest_of_three(a, b, c):
    """Return the largest of three numbers."""
    if a >= b and a >= c:
        return a
    elif b >= a and b >= c:
        return b
    else:
        return c

if __name__ == "__main__":
    # Sample data for demonstration
    x, y, z = 10, 25, 15
    result = largest_of_three(x, y, z)
    print(f"The largest of {x}, {y}, and {z} is: {result}")

    # Another example
    a, b, c = 7, 3, 7
    result = largest_of_three(a, b, c)
    print(f"The largest of {a}, {b}, and {c} is: {result}")