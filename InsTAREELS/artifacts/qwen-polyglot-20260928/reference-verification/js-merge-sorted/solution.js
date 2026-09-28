function solve({ left, right }) { const out = []; let i = 0, j = 0; while (i < left.length && j < right.length) out.push(left[i] <= right[j] ? left[i++] : right[j++]); return out.concat(left.slice(i), right.slice(j)); }
module.exports = { solve };
