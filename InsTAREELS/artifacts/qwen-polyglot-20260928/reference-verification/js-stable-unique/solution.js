function solve(values) { const seen = new Set(); return values.filter(value => { if (seen.has(value)) return false; seen.add(value); return true; }); }
module.exports = { solve };
