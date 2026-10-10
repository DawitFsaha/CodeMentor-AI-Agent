const test = require('node:test');
const assert = require('node:assert/strict');
const { add, subtract, multiply, divide } = require('../main.js');

test('add returns the sum of two numbers', () => {
    assert.strictEqual(add(2, 3), 5);
    assert.strictEqual(add(-1, 1), 0);
});

test('subtract returns the difference of two numbers', () => {
    assert.strictEqual(subtract(5, 2), 3);
});

test('multiply returns the product of two numbers', () => {
    assert.strictEqual(multiply(3, 4), 12);
    assert.strictEqual(multiply(3, 0), 0);
});

test('divide returns the quotient for nonzero divisor', () => {
    assert.strictEqual(divide(10, 2), 5);
});

test('divide throws on division by zero', () => {
    assert.throws(() => divide(7, 0), Error);
});