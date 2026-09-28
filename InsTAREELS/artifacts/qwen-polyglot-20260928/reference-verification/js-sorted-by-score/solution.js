function solve(rows) { return [...rows].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name)); }
module.exports = { solve };
