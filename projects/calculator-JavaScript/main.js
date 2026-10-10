// Basic Calculator functions
function add(a, b) {
    return a + b;
}

function subtract(a, b) {
    return a - b;
}

function multiply(a, b) {
    return a * b;
}

function divide(a, b) {
    if (b === 0) {
        throw new Error("Cannot divide by zero");
    }
    return a / b;
}

// Demonstration of calculator usage with fixed sample data
if (require.main === module) {
    const x = 12;
    const y = 3;

    console.log("Calculator Demo:");
    console.log(`${x} + ${y} = ${add(x, y)}`);
    console.log(`${x} - ${y} = ${subtract(x, y)}`);
    console.log(`${x} * ${y} = ${multiply(x, y)}`);
    try {
        console.log(`${x} / ${y} = ${divide(x, y)}`);
    } catch (e) {
        console.log(e.message);
    }
    // Demo division by zero
    try {
        console.log(`Division by zero: ${x} / 0 = ${divide(x, 0)}`);
    } catch (e) {
        console.log(`Caught error: ${e.message}`);
    }
}

// Export functions for testing
module.exports = { add, subtract, multiply, divide };