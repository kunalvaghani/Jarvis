function solve(words) { const counts = Object.create(null); for (const word of words) counts[word] = (counts[word] ?? 0) + 1; return counts; }
module.exports = { solve };
