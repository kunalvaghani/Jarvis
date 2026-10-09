function solve(text) { const stack = []; const pairs = { ')': '(', ']': '[', '}': '{' }; for (const ch of text) { if ('([{'.includes(ch)) stack.push(ch); else if (Object.hasOwn(pairs, ch) && stack.pop() !== pairs[ch]) return false; } return stack.length === 0; }
module.exports = { solve };
