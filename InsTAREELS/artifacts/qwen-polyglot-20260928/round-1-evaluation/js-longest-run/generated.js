const { strict as assert } = require('assert');
const { maxBy } = require('lodash');

function solve(input) {
    if (Array.isArray(input) && input.length === 0) return 0;
    let maxLength = 1;
    let currentLength = 1;
    for (let i = 1; i < input.length; i++) {
        if (input[i] === input[i - 1]) {
            currentLength++;
        } else {
            maxLength = Math.max(maxLength, currentLength);
            currentLength = 1;
        }
    }
    maxLength = Math.max(maxLength, currentLength);
    return maxLength;
}

module.exports = solve;
```

```javascript
const { strict as assert } = require('assert');
const { maxBy } = require('lodash');

function solve(input) {
    if (Array.isArray(input) && input.length === 0) return 0;
    let maxLength = 1;
    let currentLength = 1;
    for (let i = 1; i < input.length; i++) {
        if (input[i] === input[i - 1]) {
            currentLength++;
        } else {
            maxLength = Math.max(maxLength, currentLength);