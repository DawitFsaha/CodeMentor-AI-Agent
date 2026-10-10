def divide(a, b):
    """Return the quotient of a and b. Raises ValueError if dividing by zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b