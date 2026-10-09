function solve(text) { if (!/^[+-]?\d+$/.test(text)) return null; const value = Number(text); return Number.isSafeInteger(value) ? value : null; }
module.exports = { solve };
