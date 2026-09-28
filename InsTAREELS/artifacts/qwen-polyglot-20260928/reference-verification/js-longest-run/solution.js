function solve(values) { let best = 0, run = 0; for (let i = 0; i < values.length; i++) { run = i && values[i] === values[i - 1] ? run + 1 : 1; best = Math.max(best, run); } return best; }
module.exports = { solve };
