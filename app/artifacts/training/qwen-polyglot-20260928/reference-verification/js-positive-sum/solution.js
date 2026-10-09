function solve(numbers) { return numbers.reduce((sum, value) => sum + (Number.isFinite(value) && value > 0 ? value : 0), 0); }
module.exports = { solve };
